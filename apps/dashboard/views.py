from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Avg, Count, Q, StdDev
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.utils import timezone
from django.utils.html import escape, mark_safe

from apps.accounts.models import CustomUser, Escola, Turma, UserType
from apps.avaliacoes.models import Anotacao, Avaliacao, Consolidacao, Notificacao
from apps.avaliacoes.tasks import agendar_consolidacao, disparar_avaliacao_llm
from apps.corretores.models import PoolCorrecao, PoolCorretor
from apps.redacoes.models import Redacao, TemaRedacao

from .charts import (
    COMPETENCIAS,
    ERRO_CORES,
    ERRO_LABELS,
    bar_chart,
    barh_chart,
    fake_wordcloud_chart,
    heatmap_chart,
    histogram_chart,
    pie_chart,
    radar_chart,
    scatter_chart,
    stacked_bar_chart,
    timeline_chart,
    timeline_comp_chart,
    timeline_mean_std_chart,
)
from .context_processors import nav_counts
from .forms import AvaliacaoHumanaForm, LoginForm, RedacaoForm, RegisterForm

logger = logging.getLogger(__name__)


def _is_staff_user(user: CustomUser) -> bool:
    return user.user_type in {UserType.ADMIN, UserType.PROFESSOR, UserType.CORRETOR} or user.is_staff


def _build_annotation_style(tipos):
    shadow_parts = []
    bg_parts = []
    for i, t in enumerate(tipos):
        cor = ERRO_CORES.get(t, "#94a3b8")
        offset = 3 + i * 3
        shadow_parts.append(f"inset {offset}px 0 0 0 {cor}")
        bg_parts.append(f"rgba({int(cor[1:3],16)},{int(cor[3:5],16)},{int(cor[5:7],16)},0.10)")
    bg = f"linear-gradient(90deg, {', '.join(bg_parts)})" if bg_parts else "transparent"
    return f"box-shadow:{','.join(shadow_parts)};background:{bg};padding-left:{len(tipos) * 3}px;border-radius:3px;cursor:help;display:inline"


def renderizar_texto_com_anotacoes(texto, anotacoes):
    if not anotacoes:
        return mark_safe(escape(texto))
    boundaries = {0, len(texto)}
    for a in anotacoes:
        boundaries.add(a.trecho_inicio)
        boundaries.add(a.trecho_fim)
    boundaries = sorted(boundaries)
    sorted_anns = sorted(anotacoes, key=lambda a: a.trecho_inicio)
    partes = []
    rotulos = dict(Anotacao.TipoErro.choices)
    for i in range(len(boundaries) - 1):
        inicio = boundaries[i]
        fim = boundaries[i + 1]
        if inicio >= fim:
            continue
        segmento = texto[inicio:fim]
        covering = [a for a in sorted_anns if a.trecho_inicio <= inicio and a.trecho_fim >= fim]
        if not covering:
            partes.append(f'<span class="ann-plain">{escape(segmento)}</span>')
            continue
        tipos_ordenados = []
        seen = set()
        for a in covering:
            if a.tipo_erro not in seen:
                tipos_ordenados.append(a.tipo_erro)
                seen.add(a.tipo_erro)
        cls = " ".join(f"anotacao-{t}" for t in tipos_ordenados)
        modelo = covering[0].avaliacao.modelo_llm or ""
        is_ia = modelo and modelo != "humano"
        if is_ia:
            cls += " anotacao-ia"
        anns_data = [
            {
                "tipo": a.tipo_erro,
                "label": rotulos.get(a.tipo_erro, a.tipo_erro),
                "comentario": a.comentario or "",
                "is_ia": bool(a.avaliacao.modelo_llm and a.avaliacao.modelo_llm != "humano"),
                "autor": a.avaliacao.avaliador or "",
            }
            for a in covering
        ]
        style = _build_annotation_style(tipos_ordenados)
        data_ia = ' data-ia="true"' if is_ia else ""
        data_anns = escape(json.dumps(anns_data, ensure_ascii=False))
        partes.append(
            f'<span class="{cls}" style="{style}" data-anotacoes=\'{data_anns}\'{data_ia}>'
            f'{escape(segmento)}</span>'
        )
    return mark_safe("".join(partes))


@login_required
def api_nav_counts(request):
    return JsonResponse(nav_counts(request))


@login_required
def api_ultima_corrigida(request):
    redacao = (
        Redacao.objects.filter(
            usuario=request.user,
            status=Redacao.Status.CORRIGIDA,
            consolidacoes__status="final",
            excluida_em__isnull=True,
        )
        .select_related("tema_ref")
        .prefetch_related("consolidacoes")
        .order_by("-consolidacoes__atualizada_em")
        .first()
    )
    if not redacao:
        return JsonResponse({"tem_ultima": False})

    cons = redacao.consolidacoes.first()
    return JsonResponse({
        "tem_ultima": True,
        "id": str(redacao.id),
        "tema": redacao.tema or (redacao.tema_ref.titulo if redacao.tema_ref else "redação"),
        "nota": cons.nota_total if cons else 0,
    })


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request=request,
            username=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
        )
        if user is None:
            messages.error(request, "Credenciais inválidas.")
        else:
            login(request, user)
            return redirect("home")

    return render(request, "dashboard/login.html", {"form": form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    tipo = request.GET.get("tipo", "aluno")
    if tipo not in ("aluno", "professor", "corretor"):
        tipo = "aluno"

    form = RegisterForm(request.POST or None, tipo=tipo)
    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data["email"].lower().strip()
            escola = None
            turma = None

            escola_nome = form.cleaned_data.get("escola_nome", "").strip()
            if escola_nome:
                escola_municipio = form.cleaned_data.get("escola_municipio", "").strip()
                escola_uf = form.cleaned_data.get("escola_uf", "").strip()
                try:
                    escola = Escola.objects.get(nome__iexact=escola_nome)
                    update_fields = []
                    if escola_municipio and not escola.municipio:
                        escola.municipio = escola_municipio
                        update_fields.append("municipio")
                    if escola_uf and not escola.uf:
                        escola.uf = escola_uf
                        update_fields.append("uf")
                    if update_fields:
                        escola.save(update_fields=update_fields)
                except Escola.DoesNotExist:
                    escola = Escola.objects.create(
                        nome=escola_nome,
                        municipio=escola_municipio,
                        uf=escola_uf,
                    )

            if escola and tipo == "aluno":
                turma_ano = form.cleaned_data.get("turma_ano", "").strip()
                if turma_ano:
                    turma = Turma.objects.get_or_create(
                        escola=escola,
                        ano=turma_ano,
                        identificador=form.cleaned_data.get("turma_identificador", "").strip(),
                        curso=form.cleaned_data.get("turma_curso", "").strip(),
                    )[0]

            tipo_para_user_type = {
                "aluno": UserType.ALUNO,
                "professor": UserType.PROFESSOR,
                "corretor": UserType.CORRETOR,
            }

            user = CustomUser.objects.create_user(
                email=email,
                nome=form.cleaned_data["nome"],
                password=form.cleaned_data["senha"],
                user_type=tipo_para_user_type[tipo],
                escola=escola,
                turma=turma,
            )
            login(request, user)
            messages.success(request, "Conta criada com sucesso.")
            return redirect("home")

        for field_name, errs in form.errors.items():
            for err in errs:
                if field_name == "email" and "já existe" in err.lower():
                    messages.error(request, "Já existe um usuário com este e-mail.")
                else:
                    label = form[field_name].label if field_name in form.fields else field_name
                    messages.error(request, f"{label}: {err}")
                break
            break

    return render(request, "dashboard/register.html", {"form": form, "tipo": tipo})


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


def home(request):
    if request.user.is_authenticated:
        user = request.user
        is_staff = _is_staff_user(user)

        if is_staff:
            minhas_avaliacoes = Avaliacao.objects.filter(avaliador_usuario=user)
            total_correcoes = minhas_avaliacoes.count()
            media_nota = minhas_avaliacoes.aggregate(Avg("nota_total"))["nota_total__avg"]
            alunos_corrigidos = minhas_avaliacoes.values("redacao__usuario").distinct().count()

            ultimas = minhas_avaliacoes.select_related("redacao", "redacao__usuario").order_by("-criada_em")[:5]

            medias_comp = {
                "C1 - Norma": round(minhas_avaliacoes.aggregate(Avg("c1_nota"))["c1_nota__avg"] or 0, 2),
                "C2 - Tema": round(minhas_avaliacoes.aggregate(Avg("c2_nota"))["c2_nota__avg"] or 0, 2),
                "C3 - Argumentação": round(minhas_avaliacoes.aggregate(Avg("c3_nota"))["c3_nota__avg"] or 0, 2),
                "C4 - Coesão": round(minhas_avaliacoes.aggregate(Avg("c4_nota"))["c4_nota__avg"] or 0, 2),
                "C5 - Intervenção": round(minhas_avaliacoes.aggregate(Avg("c5_nota"))["c5_nota__avg"] or 0, 2),
            }
            todas_notas = list(minhas_avaliacoes.filter(nota_total__gt=0).values_list("nota_total", flat=True))

            return render(request, "dashboard/home.html", {
                "is_staff_user": True,
                "total_correcoes": total_correcoes,
                "media_nota": round(media_nota or 0, 2),
                "alunos_corrigidos": alunos_corrigidos,
                "ultimas_correcoes": ultimas,
                "radar_json": radar_chart(medias_comp, title="Média por Competência"),
                "histograma_json": histogram_chart(todas_notas) if todas_notas else None,
            })

        return redirect("dashboard-minhas-redacoes")

    stats = {
        "total_redacoes": Redacao.objects.count(),
        "total_avaliacoes": Avaliacao.objects.count(),
        "total_alunos": CustomUser.objects.filter(user_type=UserType.ALUNO).count(),
    }
    return render(request, "dashboard/landing.html", stats)


@login_required
def submeter(request):
    form = RedacaoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        titulo = form.cleaned_data.get("titulo", "").strip()
        tema_ref_id = form.cleaned_data.get("tema_ref_id")
        tema_ref = None
        if tema_ref_id:
            tema_ref = TemaRedacao.objects.filter(id=tema_ref_id, ativo=True).first()
            if tema_ref and not titulo:
                titulo = tema_ref.titulo

        pool = PoolCorrecao.objects.filter(ativo=True).first()

        redacao = Redacao.objects.create(
            usuario=request.user,
            tema=titulo,
            tema_ref=tema_ref,
            pool=pool,
            texto=form.cleaned_data["texto"],
            status=Redacao.Status.EM_AVALIACAO,
        )

        if pool:
            from apps.avaliacoes.notifications import notificar_corretor_humano
            from apps.corretores.models import PoolCorretor

            if PoolCorretor.objects.filter(pool=pool, tipo="llm").exists():
                disparar_avaliacao_llm(str(redacao.id), str(pool.id), "um")
                messages.info(request, "Redação enviada! Ela está sendo avaliada — volte em instantes para ver o resultado.")
            else:
                redacao.status = Redacao.Status.PENDENTE
                redacao.save(update_fields=["status"])
                for pc in PoolCorretor.objects.filter(pool=pool, tipo="humano").select_related("usuario"):
                    notificar_corretor_humano(pc.usuario, request.user, redacao)
                messages.info(request, "Redação enviada! Ela será corrigida por um corretor humano em breve.")
        else:
            redacao.status = Redacao.Status.PENDENTE
            redacao.save(update_fields=["status"])
            messages.warning(request, "Redação recebida, mas não há banca de correção ativa no momento.")

        return redirect("dashboard-minhas-redacoes")

    temas = TemaRedacao.objects.filter(ativo=True).order_by("titulo")
    return render(request, "dashboard/submeter.html", {"form": form, "temas": temas})


@login_required
def resubmeter(request, redacao_id: str):
    from apps.avaliacoes.notifications import notificar_corretor_humano

    redacao = Redacao.objects.filter(id=redacao_id, usuario=request.user).first()
    if redacao is None:
        messages.error(request, "Redação não encontrada.")
        return redirect("dashboard-minhas-redacoes")

    if redacao.status == Redacao.Status.CORRIGIDA:
        messages.warning(request, "Esta redação já foi corrigida.")
        return redirect("dashboard-minhas-redacoes")

    redacao.status = Redacao.Status.EM_AVALIACAO
    redacao.save(update_fields=["status"])

    redirect_to = redirect("dashboard-minhas-redacoes").url
    referer = request.META.get("HTTP_REFERER", "")
    if "notificacoes" in referer:
        redirect_to = redirect("notificacoes").url

    Notificacao.objects.filter(
        usuario=request.user,
        redacao=redacao,
        tipo=Notificacao.Tipo.CORRECAO_RECUSADA,
    ).delete()

    corretores_recusaram = (
        Notificacao.objects.filter(
            redacao=redacao,
            tipo=Notificacao.Tipo.CORRECAO_RECUSADA,
        )
        .exclude(usuario=request.user)
        .select_related("usuario")
    )

    for n in corretores_recusaram:
        if n.usuario:
            notificar_corretor_humano(
                usuario=n.usuario,
                aluno=request.user,
                redacao=redacao,
            )
        n.delete()

    messages.info(request, "Redação reenviada com sucesso!")
    return redirect(redirect_to)


@login_required
def detalhe_redacao(request, redacao_id: str):
    is_staff = _is_staff_user(request.user)
    qs = Redacao.objects.select_related("tema_ref").all() if is_staff else Redacao.objects.select_related("tema_ref").filter(usuario=request.user)
    redacao = qs.filter(id=redacao_id).first()
    if redacao is None:
        messages.error(request, "Redação não encontrada.")
        url = "dashboard-minhas-correcoes" if is_staff else "dashboard-minhas-redacoes"
        return redirect(url)

    if is_staff and redacao.usuario_id != request.user.id:
        if request.user.user_type in {UserType.ADMIN, UserType.PROFESSOR}:
            avaliacoes = Avaliacao.objects.filter(redacao=redacao, rascunho=False).order_by("-criada_em")
        else:
            avaliacoes = Avaliacao.objects.filter(redacao=redacao, avaliador_usuario=request.user, rascunho=False).order_by("-criada_em")
    else:
        avaliacoes = Avaliacao.objects.filter(redacao=redacao, rascunho=False).order_by("-criada_em")
    consolidacao = redacao.consolidacoes.filter(status="final").select_related("pool__revisor_corretor").order_by("-atualizada_em").first()

    COMP_KEYS = ["c1_nota", "c2_nota", "c3_nota", "c4_nota", "c5_nota"]
    COMP_LABELS = ["C1 - Norma", "C2 - Tema", "C3 - Argumentação", "C4 - Coesão", "C5 - Intervenção"]

    notas_consolidado: dict[str, float] | None = None
    radar_json = None
    if consolidacao:
        notas_consolidado = {
            COMP_LABELS[i]: float(getattr(consolidacao, COMP_KEYS[i]))
            for i in range(5)
        }
        radar_json = radar_chart(notas_consolidado, title="Nota Consolidada")
        if consolidacao.pool and consolidacao.pool.modo == "especialistas":
            consolidacao.modo_display = "5 especialistas (C1–C5)"
        else:
            consolidacao.modo_display = f"{consolidacao.quantidade_corretores} corretor(es)"

    anotacoes = Anotacao.objects.filter(
        avaliacao__redacao=redacao,
        avaliacao__rascunho=False,
    ).select_related("avaliacao__avaliador_usuario").order_by("trecho_inicio")
    texto_html = renderizar_texto_com_anotacoes(redacao.texto, anotacoes)

    anotacoes_por_avaliacao: dict[str, list] = {}
    for a in anotacoes:
        anotacoes_por_avaliacao.setdefault(str(a.avaliacao_id), []).append(a)

    avaliacoes_com_anotacoes = []
    for av in avaliacoes:
        anots = anotacoes_por_avaliacao.get(str(av.id), [])
        avaliacoes_com_anotacoes.append({
            "avaliacao": av,
            "anotacoes": anots,
            "tem_anotacoes": len(anots) > 0,
        })

    return render(request, "dashboard/detalhe_redacao.html", {
        "redacao": redacao,
        "avaliacoes_com_anotacoes": avaliacoes_com_anotacoes,
        "anotacoes": anotacoes,
        "texto_html": texto_html,
        "consolidacao": consolidacao,
        "radar_json": radar_json,
        "COMP_LABELS": COMP_LABELS,
        "COMP_KEYS": COMP_KEYS,
    })


@login_required
def minhas_redacoes(request):
    redacoes = (
        Redacao.objects.filter(usuario=request.user, excluida_em__isnull=True)
        .prefetch_related("avaliacoes", "consolidacoes")
        .order_by("-criada_em")
    )

    corrigidas = [r for r in redacoes if r.status == Redacao.Status.CORRIGIDA]
    consolidacoes = [
        c for r in corrigidas for c in r.consolidacoes.all() if c.status == "final"
    ]
    consolidacoes.sort(key=lambda c: c.criada_em)

    redacoes_com_parciais = set(
        Avaliacao.objects.filter(
            redacao__usuario=request.user,
            rascunho=False,
            redacao__status=Redacao.Status.EM_AVALIACAO,
        )        .values_list("redacao_id", flat=True)
    )

    agregacao = request.GET.get("agregacao", "dia")

    if consolidacoes:
        if agregacao == "hora":
            by_hour: dict = defaultdict(list)
            for c in consolidacoes:
                key = c.criada_em.replace(minute=0, second=0, microsecond=0)
                by_hour[key].append(c.nota_total)
            sorted_keys = sorted(by_hour.keys())
            datas = [k.strftime("%d/%m/%Y %H:00") for k in sorted_keys]
            notas = [round(sum(by_hour[k]) / len(by_hour[k]), 1) for k in sorted_keys]
        else:
            by_day: dict = defaultdict(list)
            for c in consolidacoes:
                key = c.criada_em.date()
                by_day[key].append(c.nota_total)
            sorted_keys = sorted(by_day.keys())
            datas = [k.strftime("%d/%m/%Y") for k in sorted_keys]
            notas = [round(sum(by_day[k]) / len(by_day[k]), 1) for k in sorted_keys]

        timeline_json = timeline_chart(
            datas=datas,
            notas=notas,
            title=f"Evolução das notas — por {agregacao}",
        )
        ultima = consolidacoes[-1]
        radar_json = radar_chart(
            {
                "C1 - Norma": ultima.c1_nota,
                "C2 - Tema": ultima.c2_nota,
                "C3 - Argumentação": ultima.c3_nota,
                "C4 - Coesão": ultima.c4_nota,
                "C5 - Intervenção": ultima.c5_nota,
            },
            title="Última Consolidação",
        )
    else:
        timeline_json = None
        radar_json = None

    from django.db.models.functions import TruncMonth

    anotacoes_aluno = Anotacao.objects.filter(avaliacao__redacao__usuario=request.user, avaliacao__rascunho=False)
    pizza_erros_json = None
    stacked_bar_json = None

    tipos = anotacoes_aluno.values("tipo_erro").annotate(total=Count("id")).order_by("-total")
    if tipos:
        pizza_erros_json = pie_chart(
            labels=[ERRO_LABELS.get(t["tipo_erro"], t["tipo_erro"]) for t in tipos],
            values=[t["total"] for t in tipos],
            title="Seus erros mais frequentes",
        )

        evolucao = anotacoes_aluno.annotate(
            mes=TruncMonth("criada_em")
        ).values("mes", "tipo_erro").annotate(total=Count("id")).order_by("mes")
        datas_unicas = sorted(set(e["mes"].strftime("%Y-%m") for e in evolucao if e["mes"]))
        tipos_unicos = sorted(set(e["tipo_erro"] for e in evolucao))
        if datas_unicas:
            valores_por_tipo: dict[str, list[int]] = {t: [0] * len(datas_unicas) for t in tipos_unicos}
            for e in evolucao:
                if e["mes"]:
                    idx = datas_unicas.index(e["mes"].strftime("%Y-%m"))
                    valores_por_tipo[e["tipo_erro"]][idx] = e["total"]
            stacked_bar_json = stacked_bar_chart(
                datas=datas_unicas,
                tipos=tipos_unicos,
                valores_por_tipo=valores_por_tipo,
                title="Evolução dos seus erros",
            )

    return render(
        request,
        "dashboard/minhas_redacoes.html",
        {
            "redacoes": redacoes,
            "redacoes_com_parciais": redacoes_com_parciais,
            "total_redacoes": len(redacoes),
            "timeline_json": timeline_json,
            "radar_json": radar_json,
            "agregacao": agregacao,
            "pizza_erros_json": pizza_erros_json,
            "stacked_bar_json": stacked_bar_json,
        },
    )


@login_required
def corrigir(request):
    if request.user.user_type == UserType.ALUNO:
        messages.warning(request, "Apenas corretores, professores ou admin podem corrigir redações.")
        return redirect("home")

    if request.method == "POST":
        form = AvaliacaoHumanaForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            redacao = Redacao.objects.filter(id=data["redacao_id"]).first()
            if redacao is None:
                logger.warning("Correção submetida para redação inexistente — id=%s", data["redacao_id"])
                messages.error(request, "Redação não encontrada.")
            elif redacao.status == Redacao.Status.CORRIGIDA:
                logger.warning(
                    "Tentativa de re-correção rejeitada — redacao=%s, usuario=%s",
                    redacao.id, request.user.email,
                )
                messages.warning(
                    request,
                    "Esta redação já foi corrigida. Não é possível enviar uma nova correção.",
                )
            else:
                pool_ativo = PoolCorrecao.objects.filter(ativo=True).first()
                campos = {
                    "c1_nota": data["c1_nota"],
                    "c1_justificativa": data["c1_justificativa"],
                    "c1_sugestoes": data["c1_sugestoes"],
                    "c2_nota": data["c2_nota"],
                    "c2_justificativa": data["c2_justificativa"],
                    "c2_sugestoes": data["c2_sugestoes"],
                    "c3_nota": data["c3_nota"],
                    "c3_justificativa": data["c3_justificativa"],
                    "c3_sugestoes": data["c3_sugestoes"],
                    "c4_nota": data["c4_nota"],
                    "c4_justificativa": data["c4_justificativa"],
                    "c4_sugestoes": data["c4_sugestoes"],
                    "c5_nota": data["c5_nota"],
                    "c5_justificativa": data["c5_justificativa"],
                    "c5_sugestoes": data["c5_sugestoes"],
                    "nota_total": sum(data[f"c{i}_nota"] for i in range(1, 6)),
                    "avaliador": data["nome_avaliador"],
                    "modelo_llm": "humano",
                    "rascunho": False,
                    "redacao": redacao,
                    "pool": pool_ativo,
                    "avaliador_usuario": request.user,
                }
                avaliacao, _created = Avaliacao.objects.update_or_create(
                    redacao=redacao,
                    avaliador_usuario=request.user,
                    defaults={**campos, "rascunho": False},
                )
                logger.info(
                    "Correção submetida — redacao=%s, usuario=%s, avaliacao_id=%s",
                    redacao.id, request.user.email, str(avaliacao.id),
                )

                Notificacao.objects.filter(
                    redacao=redacao,
                    tipo=Notificacao.Tipo.CORRECAO_RECUSADA,
                ).delete()

                logger.info(
                    "Correção submetida — redacao=%s, usuario=%s, avaliacao_id=%s",
                    redacao.id, request.user.email, data.get("avaliacao_id") or "(nova)",
                )

                if pool_ativo is not None:
                    agendar_consolidacao(str(redacao.id), str(pool_ativo.id))
                messages.success(request, "Avaliação salva com sucesso.")
                return redirect("dashboard-corrigir")
    else:
        form = AvaliacaoHumanaForm(initial={"nome_avaliador": request.user.nome_exibicao})

    pools_ids = PoolCorretor.objects.filter(
        usuario=request.user, pool__ativo=True
    ).values_list("pool_id", flat=True)

    if not pools_ids:
        tem_vinculo = PoolCorretor.objects.filter(usuario=request.user).exists()
        if tem_vinculo:
            tem_ativa = PoolCorrecao.objects.filter(
                id__in=PoolCorretor.objects.filter(
                    usuario=request.user,
                ).values_list("pool_id", flat=True),
                ativo=True,
            ).exists()
            if tem_ativa:
                msg = "Configuração de banca inconsistente. Solicite ao administrador."
            else:
                msg = (
                    "Você está vinculado a bancas, mas nenhuma delas está ativa. "
                    "Solicite ao administrador que ative alguma banca."
                )
        else:
            msg = "Você não está alocado em nenhuma banca de correção. Solicite ao administrador."
        messages.info(request, msg)
        return render(
            request,
            "dashboard/corrigir.html",
            {"pendentes": [], "form": form},
        )

    pendentes = []
    redacoes = (
        Redacao.objects.filter(
            models.Q(avaliacoes__pool_id__in=pools_ids)
            | models.Q(pool_id__in=pools_ids, status=Redacao.Status.PENDENTE)
        )
        .exclude(usuario=request.user)
        .exclude(status__in=[Redacao.Status.CORRIGIDA, Redacao.Status.ERRO])
        .exclude(excluida_em__isnull=False)
        .select_related("usuario")
        .distinct()
        .order_by("-criada_em")[:30]
    )

    redacoes_recusadas = set(
        Notificacao.objects.filter(
            usuario=request.user,
            tipo=Notificacao.Tipo.CORRECAO_RECUSADA,
            redacao__isnull=False,
        ).values_list("redacao_id", flat=True)
    )

    for redacao in redacoes:
        if redacao.id in redacoes_recusadas:
            continue
        corrigiu = Avaliacao.objects.filter(
            redacao=redacao,
            avaliador_usuario=request.user,
            rascunho=False,
        ).exists()
        if not corrigiu:
            tem_rascunho = Avaliacao.objects.filter(
                redacao=redacao,
                avaliador_usuario=request.user,
                rascunho=True,
            ).exists()
            pendentes.append((redacao, tem_rascunho))

    return render(
        request,
        "dashboard/corrigir.html",
        {"pendentes": pendentes, "form": form},
    )


@login_required
def minhas_correcoes(request):
    if request.user.user_type == UserType.ALUNO:
        messages.warning(request, "Apenas corretores, professores ou admin podem acessar esta área.")
        return redirect("home")

    correcoes = (
        Avaliacao.objects.filter(avaliador_usuario=request.user, rascunho=False)
        .select_related("redacao", "redacao__usuario")
        .order_by("-criada_em")
    )
    return render(request, "dashboard/minhas_correcoes.html", {"correcoes": correcoes})


@login_required
def editar_correcao(request, avaliacao_id: str):
    if request.user.user_type == UserType.ALUNO:
        messages.warning(request, "Apenas corretores, professores ou admin podem editar correções.")
        return redirect("home")

    avaliacao = Avaliacao.objects.filter(id=avaliacao_id, avaliador_usuario=request.user).first()
    if avaliacao is None:
        messages.error(request, "Avaliação não encontrada.")
        return redirect("dashboard-minhas-correcoes")

    redacao = Redacao.objects.select_related("tema_ref").get(id=avaliacao.redacao_id)

    if request.method == "POST":
        form = AvaliacaoHumanaForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            for i in range(1, 6):
                setattr(avaliacao, f"c{i}_nota", data[f"c{i}_nota"])
                setattr(avaliacao, f"c{i}_justificativa", data[f"c{i}_justificativa"])
                setattr(avaliacao, f"c{i}_sugestoes", data[f"c{i}_sugestoes"])
            avaliacao.nota_total = sum(data[f"c{i}_nota"] for i in range(1, 6))
            avaliacao.avaliador = data["nome_avaliador"]
            avaliacao.save()
            Notificacao.objects.filter(
                redacao=avaliacao.redacao,
                tipo=Notificacao.Tipo.CORRECAO_RECUSADA,
            ).delete()
            pool_ativo = PoolCorrecao.objects.filter(ativo=True).first()
            if pool_ativo:
                agendar_consolidacao(str(avaliacao.redacao_id), str(pool_ativo.id))
            messages.success(request, "Correção atualizada com sucesso.")
            return redirect("dashboard-minhas-correcoes")
    else:
        initial = {
            "redacao_id": str(redacao.id),
            "avaliacao_id": str(avaliacao.id),
            "nome_avaliador": avaliacao.avaliador,
            **{f"c{i}_nota": getattr(avaliacao, f"c{i}_nota") for i in range(1, 6)},
            **{f"c{i}_justificativa": getattr(avaliacao, f"c{i}_justificativa") for i in range(1, 6)},
            **{f"c{i}_sugestoes": getattr(avaliacao, f"c{i}_sugestoes") for i in range(1, 6)},
        }
        form = AvaliacaoHumanaForm(initial=initial)

    anotacoes = Anotacao.objects.filter(avaliacao=avaliacao).order_by("trecho_inicio")
    texto_html = renderizar_texto_com_anotacoes(redacao.texto, anotacoes)
    anotacoes_json = json.dumps([
        {
            "id": str(a.id),
            "avaliacao": str(a.avaliacao_id),
            "trecho_inicio": a.trecho_inicio,
            "trecho_fim": a.trecho_fim,
            "trecho_texto": a.trecho_texto,
            "tipo_erro": a.tipo_erro,
            "comentario": a.comentario,
        }
        for a in anotacoes
    ])

    return render(request, "dashboard/editar_correcao.html", {
        "form": form,
        "avaliacao": avaliacao,
        "redacao": redacao,
        "anotacoes": anotacoes,
        "anotacoes_json": anotacoes_json,
        "redacao_texto": redacao.texto,
        "texto_html": texto_html,
    })


@login_required
def turma(request):
    if request.user.user_type not in {UserType.ADMIN, UserType.PROFESSOR}:
        messages.warning(request, "Apenas professores e admin acessam esta área.")
        return redirect("home")

    alunos = (
        CustomUser.objects.filter(user_type=UserType.ALUNO)
        .annotate(total_redacoes=Count("redacoes"), media_nota=Avg("redacoes__avaliacoes__nota_total"))
        .order_by("nome", "email")
    )

    nomes = [a.nome_exibicao for a in alunos if a.media_nota]
    medias = [float(a.media_nota) for a in alunos if a.media_nota]
    barras_json = bar_chart(nomes, medias, title="Média dos Alunos") if nomes else None

    return render(
        request,
        "dashboard/turma.html",
        {"alunos": alunos, "barras_json": barras_json},
    )


@login_required
def estatisticas(request):
    if request.user.user_type not in {UserType.ADMIN, UserType.PROFESSOR, UserType.CORRETOR}:
        messages.warning(request, "Apenas professores, corretores e admin acessam estatísticas.")
        return redirect("home")

    from django.db.models.functions import TruncMonth

    if request.user.user_type == UserType.CORRETOR:
        anotacoes = Anotacao.objects.filter(avaliacao__avaliador_usuario=request.user)
        total_correcoes = Avaliacao.objects.filter(avaliador_usuario=request.user).count()
        total_anotacoes = anotacoes.count()

        tipos = anotacoes.values("tipo_erro").annotate(total=Count("id")).order_by("-total")
        pizza_json = None
        if tipos:
            pizza_json = pie_chart(
                labels=[ERRO_LABELS.get(t["tipo_erro"], t["tipo_erro"]) for t in tipos],
                values=[t["total"] for t in tipos],
                title="Distribuição dos seus erros marcados",
            )

        ultimas = anotacoes.select_related(
            "avaliacao__redacao", "avaliacao__redacao__usuario"
        ).order_by("-criada_em")[:10]

        return render(request, "dashboard/dashboard_estatisticas.html", {
            "modo": "corretor",
            "total_correcoes": total_correcoes,
            "total_anotacoes": total_anotacoes,
            "pizza_erros_json": pizza_json,
            "ultimas_anotacoes": ultimas,
        })

    total_redacoes = Redacao.objects.count()
    total_avaliacoes = Avaliacao.objects.count()
    agregados = Avaliacao.objects.aggregate(
        media_total=Avg("nota_total"),
        c1=Avg("c1_nota"),
        c2=Avg("c2_nota"),
        c3=Avg("c3_nota"),
        c4=Avg("c4_nota"),
        c5=Avg("c5_nota"),
    )
    medias_comp = {
        "C1 - Norma": round(agregados["c1"] or 0, 2),
        "C2 - Tema": round(agregados["c2"] or 0, 2),
        "C3 - Argumentação": round(agregados["c3"] or 0, 2),
        "C4 - Coesão": round(agregados["c4"] or 0, 2),
        "C5 - Intervenção": round(agregados["c5"] or 0, 2),
    }

    todas_notas = list(
        Avaliacao.objects.filter(nota_total__gt=0).values_list("nota_total", flat=True)
    )
    temas = (
        Redacao.objects.values("tema")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    context = {
        "modo": "admin_prof",
        "total_redacoes": total_redacoes,
        "total_avaliacoes": total_avaliacoes,
        "media_total": round(agregados["media_total"] or 0, 2),
        "medias_comp": medias_comp,
        "radar_json": radar_chart(medias_comp, title="Média por Competência"),
        "histograma_json": histogram_chart(todas_notas) if todas_notas else None,
        "pizza_json": pie_chart(
            labels=[t["tema"] for t in temas],
            values=[t["total"] for t in temas],
        ) if temas else None,
    }

    anotacoes_turma = Anotacao.objects.filter(
        avaliacao__redacao__usuario__user_type=UserType.ALUNO,
        avaliacao__rascunho=False,
    )

    tipos_turma = anotacoes_turma.values("tipo_erro").annotate(total=Count("id")).order_by("-total")
    if tipos_turma:
        context["pizza_erros_turma_json"] = pie_chart(
            labels=[ERRO_LABELS.get(t["tipo_erro"], t["tipo_erro"]) for t in tipos_turma],
            values=[t["total"] for t in tipos_turma],
            title="Distribuição de erros da turma",
        )

    evolucao = anotacoes_turma.annotate(
        mes=TruncMonth("criada_em")
    ).values("mes", "tipo_erro").annotate(total=Count("id")).order_by("mes")

    datas_unicas = sorted(set(e["mes"].strftime("%Y-%m") for e in evolucao if e["mes"]))
    tipos_unicos = sorted(set(e["tipo_erro"] for e in evolucao))
    valores_por_tipo: dict[str, list[int]] = {t: [0] * len(datas_unicas) for t in tipos_unicos}
    for e in evolucao:
        if e["mes"]:
            idx = datas_unicas.index(e["mes"].strftime("%Y-%m"))
            valores_por_tipo[e["tipo_erro"]][idx] = e["total"]

    if datas_unicas:
        context["stacked_bar_json"] = stacked_bar_chart(
            datas=datas_unicas,
            tipos=tipos_unicos,
            valores_por_tipo=valores_por_tipo,
            title="Evolução mensal dos erros",
        )

    alunos_erros = (
        CustomUser.objects.filter(user_type=UserType.ALUNO)
        .annotate(
            total_erros=Count("redacoes__avaliacoes__anotacoes"),
            media_nota=Avg("redacoes__avaliacoes__nota_total"),
        )
        .filter(total_erros__gt=0)
    )
    if alunos_erros:
        context["scatter_json"] = scatter_chart(
            x_vals=[a.total_erros for a in alunos_erros],
            y_vals=[float(a.media_nota) for a in alunos_erros],
            labels=[a.nome_exibicao for a in alunos_erros],
            title="Relação erros × nota média",
        )

    pivot: list[dict] = []
    for aluno in CustomUser.objects.filter(user_type=UserType.ALUNO).order_by("nome"):
        erros = (
            Anotacao.objects.filter(avaliacao__redacao__usuario=aluno, avaliacao__rascunho=False)
            .values("tipo_erro")
            .annotate(total=Count("id"))
        )
        if erros:
            row: dict = {"aluno": aluno.nome_exibicao, "total": sum(e["total"] for e in erros)}
            for e in erros:
                row[ERRO_LABELS.get(e["tipo_erro"], e["tipo_erro"])] = e["total"]
            pivot.append(row)
    context["pivot_erros"] = pivot

    return render(request, "dashboard/dashboard_estatisticas.html", context)


@login_required
def fila(request):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores acessam esta área.")
        return redirect("home")

    from django_q.models import OrmQ, Task

    hoje = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cinco_min_atras = timezone.now() - timedelta(minutes=5)

    fila_count = OrmQ.objects.count()
    em_execucao = Task.objects.filter(started__isnull=False, stopped__isnull=True).count()
    falhas_hoje = Task.objects.filter(success=False, started__gte=hoje).count()
    sucesso_hoje = Task.objects.filter(success=True, started__gte=hoje).count()
    worker_ativo = Task.objects.filter(stopped__gte=cinco_min_atras).exists()

    from django.core.mail import send_mail as django_send_mail

    from apps.corretores.models import PoolCorrecao
    from apps.redacoes.models import Redacao

    def _tema_exibicao(r):
        return r.tema or (r.tema_ref.titulo if r.tema_ref else "redação sem título")

    def _detectar_tipo_task(func):
        if "consolidar" in func:
            return "consolidacao"
        if "_executar_avaliacao" in func:
            return "avaliacao"
        if "send_mail" in func or "mail" in func:
            return "email"
        return "outro"

    def _extrair_args_task(func, args):
        dados = {"tipo": _detectar_tipo_task(func), "redacao_id": None, "pool_id": None}
        if not args:
            return dados
        if dados["tipo"] in ("avaliacao", "consolidacao"):
            dados["redacao_id"] = args[0] if len(args) >= 1 else None
            dados["pool_id"] = args[1] if len(args) >= 2 else None
        elif dados["tipo"] == "email":
            if len(args) >= 1:
                dados["email_assunto"] = str(args[0])[:80]
            if len(args) >= 4:
                dados["email_destino"] = args[3]
        return dados

    raw_queue = OrmQ.objects.order_by("key")[:20]
    queue_items = []
    for item in raw_queue:
        dados = {"id": item.id, "key": item.key, "func": item.func()}
        dados.update(_extrair_args_task(item.func(), item.args()))
        queue_items.append(dados)

    raw_tasks = Task.objects.all().order_by("-started")[:30]
    tasks_recentes = []
    for t in raw_tasks:
        dados = {
            "started": t.started,
            "stopped": t.stopped,
            "time_taken": t.time_taken(),
            "func": t.func,
            "success": t.success,
        }
        dados.update(_extrair_args_task(t.func, t.args))
        tasks_recentes.append(dados)

    redacao_ids = set()
    pool_ids = set()
    for item in queue_items + tasks_recentes:
        if item["redacao_id"]:
            redacao_ids.add(item["redacao_id"])
        if item["pool_id"]:
            pool_ids.add(item["pool_id"])

    redacoes_map = {}
    if redacao_ids:
        for r in Redacao.objects.select_related("tema_ref").filter(id__in=redacao_ids):
            redacoes_map[str(r.id)] = _tema_exibicao(r)
    pools_map = {str(p.id): p.nome for p in PoolCorrecao.objects.filter(id__in=pool_ids)}

    for item in queue_items + tasks_recentes:
        item["redacao_nome"] = redacoes_map.get(item["redacao_id"])
        item["pool_nome"] = pools_map.get(item["pool_id"])

    redacoes_erro = Redacao.objects.filter(
        status=Redacao.Status.ERRO,
    ).select_related("pool", "tema_ref").order_by("-criada_em")[:20]

    erro_items = []
    for r in redacoes_erro:
        pool = r.pool
        pool_corretores: list[dict] = []
        total = com_avaliacao = 0

        if pool:
            pcs = PoolCorretor.objects.filter(pool=pool, tipo="llm").select_related("corretor_llm")
            existing = set(
                Avaliacao.objects.filter(redacao=r, pool=pool)
                .exclude(corretor_llm=None)
                .values_list("corretor_llm_id", flat=True)
            )
            existing_str = {str(cid) for cid in existing if cid}

            for pc in pcs:
                tem_avaliacao = pc.corretor_llm_id and str(pc.corretor_llm_id) in existing_str
                if tem_avaliacao:
                    com_avaliacao += 1
                total += 1
                pool_corretores.append({
                    "id": str(pc.id),
                    "nome": pc.corretor_llm.nome if pc.corretor_llm else "?",
                    "tem_avaliacao": tem_avaliacao,
                })

        erro_items.append({
            "id": str(r.id),
            "tema": r.tema or (r.tema_ref.titulo if r.tema_ref else "sem título"),
            "pool_nome": pool.nome if pool else "Sem banca",
            "corretores": pool_corretores,
            "total": total,
            "com_avaliacao": com_avaliacao,
            "pode_forcar": com_avaliacao > 0,
        })

    context = {
        "fila_count": fila_count,
        "em_execucao": em_execucao,
        "falhas_hoje": falhas_hoje,
        "sucesso_hoje": sucesso_hoje,
        "worker_ativo": worker_ativo,
        "queue_items": queue_items,
        "tasks_recentes": tasks_recentes,
        "erro_items": erro_items,
        "agora": timezone.now(),
    }
    return render(request, "dashboard/fila.html", context)


@login_required
def fila_redisparar(request, redacao_id):
    if request.method != "POST":
        return redirect("dashboard-fila")
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores podem re-disparar avaliações.")
        return redirect("dashboard-fila")

    try:
        redacao = Redacao.objects.get(id=redacao_id)
    except Redacao.DoesNotExist:
        messages.error(request, "Redação não encontrada.")
        return redirect("dashboard-fila")

    if redacao.status != Redacao.Status.ERRO:
        messages.warning(request, "Redação não está em estado de ERRO.")
        return redirect("dashboard-fila")

    pool = redacao.pool
    if pool:
        pool_corretores = PoolCorretor.objects.filter(
            pool=pool, tipo="llm"
        ).select_related("corretor_llm")

        existing_corretor_ids = set(
            Avaliacao.objects.filter(redacao=redacao, pool=pool)
            .exclude(corretor_llm=None)
            .values_list("corretor_llm_id", flat=True)
        )
        existing_str = {str(cid) for cid in existing_corretor_ids if cid}

        missing_ids: list[str] = []
        for pc in pool_corretores:
            if pc.corretor_llm_id and str(pc.corretor_llm_id) not in existing_str:
                missing_ids.append(str(pc.id))

        if not missing_ids:
            messages.info(request, "Todos os corretores já avaliaram. Re-forçando consolidação.")
            agendar_consolidacao(str(redacao.id), str(pool.id))
        else:
            qtd_existing = len(existing_str)
            qtd_missing = len(missing_ids)
            disparar_avaliacao_llm(
                str(redacao.id),
                pool_id=str(pool.id),
                corretor_ids=missing_ids,
            )
            messages.success(
                request,
                f"⚠️ Re-disparando {qtd_missing} corretor(es) pendente(s). "
                f"{qtd_existing} avaliação(ões) preservada(s).",
            )
    else:
        from apps.avaliacoes.banca_selector import selecionar_banca

        banca = selecionar_banca()
        if banca:
            redacao.pool = banca
            redacao.save(update_fields=["pool"])
            from django.db.models import Q

            qs_ia = Avaliacao.objects.filter(redacao=redacao).exclude(
                Q(modelo_llm="") | Q(modelo_llm="humano")
            )
            qs_ia.delete()
            disparar_avaliacao_llm(str(redacao.id), pool_id=str(banca.id))
            messages.success(
                request,
                f"Banca «{banca.nome}» atribuída. "
                f"Redação re-disparada para «{redacao.tema[:60]}».",
            )
        else:
            messages.warning(
                request,
                "Nenhuma banca ativa disponível para atribuir a esta redação.",
            )
    return redirect("dashboard-fila")


@login_required
def fila_remover_queue(request, queue_id):
    if request.method != "POST":
        return redirect("dashboard-fila")
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores podem remover tarefas da fila.")
        return redirect("dashboard-fila")

    from django_q.models import OrmQ

    OrmQ.objects.filter(id=queue_id).delete()
    messages.success(request, "Tarefa removida da fila.")
    return redirect("dashboard-fila")


@login_required
def fila_retentar_corretor(request, redacao_id, pool_corretor_id):
    if request.method != "POST":
        return redirect("dashboard-fila")
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores podem re-tentar corretores.")
        return redirect("dashboard-fila")

    try:
        redacao = Redacao.objects.get(id=redacao_id)
    except Redacao.DoesNotExist:
        messages.error(request, "Redação não encontrada.")
        return redirect("dashboard-fila")

    try:
        pc = PoolCorretor.objects.select_related("corretor_llm").get(id=pool_corretor_id)
    except PoolCorretor.DoesNotExist:
        messages.error(request, "Corretor da banca não encontrado.")
        return redirect("dashboard-fila")

    if not pc.corretor_llm:
        messages.warning(request, "Este membro da banca não é um corretor LLM.")
        return redirect("dashboard-fila")

    ja_avaliou = Avaliacao.objects.filter(
        redacao=redacao, corretor_llm=pc.corretor_llm,
    ).exists()
    if ja_avaliou:
        messages.warning(request, "Este corretor já possui uma avaliação para esta redação.")
        return redirect("dashboard-fila")

    pool_id = str(pc.pool_id) if pc.pool_id else None
    disparar_avaliacao_llm(
        str(redacao.id),
        pool_id=pool_id,
        corretor_ids=[str(pc.id)],
    )
    messages.success(request, f"Re-tentando corretor «{pc.corretor_llm.nome}».")
    return redirect("dashboard-fila")


@login_required
def fila_forcar_consolidacao(request, redacao_id):
    if request.method != "POST":
        return redirect("dashboard-fila")
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores podem forçar consolidação.")
        return redirect("dashboard-fila")

    try:
        redacao = Redacao.objects.get(id=redacao_id)
    except Redacao.DoesNotExist:
        messages.error(request, "Redação não encontrada.")
        return redirect("dashboard-fila")

    pool = redacao.pool
    if not pool:
        messages.warning(request, "Redação não possui banca vinculada.")
        return redirect("dashboard-fila")

    from apps.avaliacoes.services import atualizar_consolidacao

    qtd_avaliacoes = Avaliacao.objects.filter(redacao=redacao).count()
    if qtd_avaliacoes == 0:
        messages.warning(request, "Nenhuma avaliação encontrada para consolidar.")
        return redirect("dashboard-fila")

    cons = atualizar_consolidacao(redacao, pool)
    if not cons:
        messages.error(request, "Não foi possível criar/atualizar a consolidação.")
        return redirect("dashboard-fila")

    if cons.status != "final":
        cons.status = "final"
        cons.save(update_fields=["status"])
        redacao.status = Redacao.Status.CORRIGIDA
        redacao.save(update_fields=["status"])
        from apps.avaliacoes.notifications import notificar_aluno_correcao_concluida
        notificar_aluno_correcao_concluida(redacao, cons.nota_total)
        messages.success(
            request,
            f"Consolidação forçada com {qtd_avaliacoes} avaliação(ões). "
            f"Nota: {cons.nota_total}.",
        )
    else:
        messages.info(request, "Consolidação já estava finalizada.")
    return redirect("dashboard-fila")


@login_required
def debug_lista(request):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores acessam esta área.")
        return redirect("home")

    from apps.avaliacoes.models import Consolidacao

    redacoes = Redacao.objects.select_related("usuario", "pool").order_by("-criada_em")[:100]

    items = []
    for r in redacoes:
        qtd_avaliacoes = Avaliacao.objects.filter(redacao=r).count()
        cons = Consolidacao.objects.filter(redacao=r).order_by("-atualizada_em").first()
        items.append({
            "id": str(r.id),
            "tema": r.tema or (r.tema_ref.titulo if r.tema_ref else "sem título"),
            "aluno": r.usuario.nome_exibicao if r.usuario else "?",
            "pool_nome": r.pool.nome if r.pool else "—",
            "status": r.status,
            "qtd_avaliacoes": qtd_avaliacoes,
            "consolidacao_status": cons.status if cons else None,
            "consolidacao_nota": cons.nota_total if cons else None,
            "criada_em": r.criada_em,
        })

    context = {
        "items": items,
        "total": len(items),
    }
    return render(request, "dashboard/debug_lista.html", context)


@login_required
def debug_detalhe(request, redacao_id):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores acessam esta área.")
        return redirect("home")

    from apps.avaliacoes.models import Consolidacao

    redacao = get_object_or_404(
        Redacao.objects.select_related("usuario", "pool", "tema_ref"),
        id=redacao_id,
    )

    avaliacoes = Avaliacao.objects.filter(
        redacao=redacao,
    ).select_related(
        "corretor_llm", "avaliador_usuario", "pool",
    ).prefetch_related("anotacoes").order_by("criada_em")

    consolidacao = Consolidacao.objects.filter(redacao=redacao).order_by("-atualizada_em").first()

    corretor_ids = set()
    for av in avaliacoes:
        if av.corretor_llm_id:
            corretor_ids.add(av.corretor_llm_id)
    corretores_config = {}
    if corretor_ids:
        from apps.corretores.models import CorretorLLM
        for cl in CorretorLLM.objects.filter(id__in=corretor_ids).select_related("provedor"):
            corretores_config[str(cl.id)] = {
                "nome": cl.nome,
                "modelo": cl.modelo,
                "provedor": cl.provedor.nome if cl.provedor else "—",
                "temperature": cl.temperature,
                "seed": cl.seed,
                "top_p": cl.top_p,
                "output_json": cl.output_json,
                "skills": list(cl.skills.all().values("nome", "descricao")),
                "ferramentas": list(cl.ferramentas_ativas.all().values("nome", "slug")),
                "prompt_personalizado": cl.prompt_personalizado,
            }

    context = {
        "redacao": redacao,
        "avaliacoes": avaliacoes,
        "consolidacao": consolidacao,
        "corretores_config": corretores_config,
    }
    return render(request, "dashboard/debug_detalhe.html", context)


@never_cache
@login_required
def debug_feedback(request, redacao_id, avaliacao_id):
    if request.user.user_type != UserType.ADMIN:
        return JsonResponse({"erro": "não autorizado"}, status=403)

    try:
        body = json.loads(request.body) if request.body else {}
        valor = body.get("valor", "")
    except json.JSONDecodeError:
        return JsonResponse({"erro": "JSON inválido"}, status=400)

    if valor not in ("bom", "ruim", ""):
        return JsonResponse({"erro": "valor deve ser 'bom', 'ruim' ou ''"}, status=400)

    from apps.avaliacoes.models import Avaliacao
    from apps.corretores.services import recalcular_rating_corretor

    Avaliacao.objects.filter(id=avaliacao_id, redacao_id=redacao_id).update(
        admin_feedback=valor,
    )

    rating_novo = None
    corretor_nome = None
    av = Avaliacao.objects.get(id=avaliacao_id)
    if av.corretor_llm_id:
        recalcular_rating_corretor(av.corretor_llm_id)
        from apps.corretores.models import CorretorLLM

        cl = CorretorLLM.objects.get(id=av.corretor_llm_id)
        rating_novo = cl.rating
        corretor_nome = cl.nome

    return JsonResponse({
        "status": "ok",
        "admin_feedback": valor,
        "rating": rating_novo,
        "corretor_nome": corretor_nome,
    })


def configuracoes(request):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas admin acessa esta área.")
        return redirect("home")
    return render(request, "dashboard/configuracoes.html")


@login_required
def rubricas(request):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas admin acessa esta área.")
        return redirect("home")

    from apps.corretores.models import Rubrica

    rubricas_qs = Rubrica.objects.order_by("competencia", "-versao")
    return render(request, "dashboard/rubricas.html", {"rubricas": rubricas_qs})


@login_required
def rubrica_form(request, rubrica_id=None):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas admin acessa esta área.")
        return redirect("home")

    from apps.corretores.models import Rubrica

    rubrica = None
    if rubrica_id:
        rubrica = Rubrica.objects.filter(id=rubrica_id).first()
        if rubrica is None:
            messages.error(request, "Rubrica não encontrada.")
            return redirect("rubricas")

    competencias = Rubrica.COMPETENCIA_CHOICES

    arvore_texto_previa = ""
    if rubrica and rubrica.arvore:
        arvore_texto_previa = rubrica.arvore.get("texto", "")

    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        competencia = request.POST.get("competencia", "").strip()
        versao_str = request.POST.get("versao", "").strip()
        ativa = request.POST.get("ativa", "") == "1"
        descricao = request.POST.get("descricao", "").strip()
        arvore_texto = request.POST.get("arvore_texto", "").strip()

        if nome and competencia and arvore_texto:
            arvore_data = {"texto": arvore_texto}
            versao = int(versao_str) if versao_str else 1

            if rubrica:
                rubrica.nome = nome
                rubrica.competencia = competencia
                rubrica.versao = versao
                rubrica.ativa = ativa
                rubrica.descricao = descricao
                rubrica.arvore = arvore_data
                rubrica.save()
                messages.success(request, "Rubrica atualizada com sucesso.")
            else:
                Rubrica.objects.create(
                    nome=nome,
                    competencia=competencia,
                    versao=versao,
                    ativa=ativa,
                    descricao=descricao,
                    arvore=arvore_data,
                )
                messages.success(request, "Rubrica criada com sucesso.")
            return redirect("rubricas")
        else:
            messages.error(request, "Preencha nome, competência e árvore de decisão.")

    return render(request, "dashboard/rubrica_form.html", {
        "rubrica": rubrica,
        "competencias": competencias,
        "arvore_texto_previa": arvore_texto_previa,
    })


@login_required
def notificacoes(request):
    notificacoes_qs = Notificacao.objects.filter(
        usuario=request.user
    ).select_related("redacao").order_by("-criada_em")[:50]

    return render(request, "dashboard/notificacoes.html", {
        "notificacoes": notificacoes_qs,
    })


@login_required
def limpar_notificacoes(request):
    if request.method == "POST":
        Notificacao.objects.filter(usuario=request.user).delete()
        messages.success(request, "Todas as notificações foram removidas.")
    return redirect("notificacoes")


@login_required
def rota_correcao(request):
    messages.warning(request, "Seleção de corretores estará disponível em breve.")
    return redirect("dashboard-minhas-redacoes")


@login_required
def admin_provedores(request):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas admin acessa esta área.")
        return redirect("home")
    from apps.corretores.models import ProvedorLLM
    from apps.corretores.providers import mascarar_api_key
    provedores = ProvedorLLM.objects.annotate(
        total_corretores=models.Count("corretores")
    ).order_by("nome")
    for p in provedores:
        p.api_key_mascarada = mascarar_api_key(p.api_key)
    return render(request, "dashboard/admin_provedores.html", {
        "provedores": provedores,
    })


@login_required
def admin_provedor_form(request, provedor_id=None):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas admin acessa esta área.")
        return redirect("home")
    import asyncio

    from apps.corretores.models import ProvedorLLM
    from apps.corretores.providers import listar_modelos

    instance = None
    if provedor_id:
        instance = ProvedorLLM.objects.filter(id=provedor_id).first()
        if instance is None:
            messages.error(request, "Provedor não encontrado.")
            return redirect("admin-provedores")

    if request.GET.get("testar") and instance:
        try:
            modelos = asyncio.run(listar_modelos(instance))
            messages.success(
                request,
                f"Conexão OK — {len(modelos)} modelo(s) disponível(is): "
                f"{', '.join(modelos[:5])}{'...' if len(modelos) > 5 else ''}",
            )
        except Exception as e:
            messages.error(request, f"Falha na conexão: {e}")

    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        base_url = request.POST.get("base_url", "").strip()
        ativo = request.POST.get("ativo") == "on"
        api_key = request.POST.get("api_key", "").strip()
        tipo = request.POST.get("tipo", "openai").strip()

        if not nome:
            messages.error(request, "Nome é obrigatório.")
        else:
            if instance:
                instance.nome = nome
                instance.base_url = base_url
                instance.ativo = ativo
                if api_key:
                    instance.api_key = api_key
                instance.save()
                messages.success(request, "Provedor atualizado.")
            else:
                if not api_key:
                    messages.error(request, "API Key é obrigatória.")
                else:
                    instance = ProvedorLLM.objects.create(
                        nome=nome, base_url=base_url, ativo=ativo,
                        api_key=api_key, tipo=tipo,
                    )
                    messages.success(request, "Provedor criado.")

            if request.POST.get("testar"):
                return redirect(f"/dashboard/configuracoes/provedores/{instance.id}/editar?testar=1")
            return redirect("admin-provedores")

    editando = instance is not None
    form = {}
    template_selecionado = ""
    if instance:
        form["nome"] = instance.nome
        form["base_url"] = instance.base_url
        form["ativo"] = instance.ativo
        form["tipo"] = instance.tipo
        form["provedor_id"] = str(instance.id)

    from apps.corretores.providers import PROVIDER_TEMPLATES

    if editando and instance.tipo == "gemini":
        template_selecionado = "gemini"
    elif editando and instance.tipo != "gemini":
        template_selecionado = "personalizado"

    return render(request, "dashboard/admin_provedor_form.html", {
        "titulo": "Editar provedor" if editando else "Novo provedor",
        "form": form,
        "editando": editando,
        "templates": PROVIDER_TEMPLATES,
        "template_selecionado": template_selecionado,
    })


@login_required
def bancas(request):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores acessam esta área.")
        return redirect("home")
    from apps.corretores.models import CorretorLLM, ProvedorLLM

    from django.db.models import Count
    from apps.redacoes.models import Redacao

    bancas = PoolCorrecao.objects.select_related("revisor_corretor").order_by("ordem", "nome")
    corretores_llm = CorretorLLM.objects.select_related("provedor").order_by("nome")
    provedores = ProvedorLLM.objects.filter(ativo=True).order_by("nome")

    cargas = dict(
        Redacao.objects.filter(
            status__in=[Redacao.Status.PENDENTE, Redacao.Status.EM_AVALIACAO],
            pool__isnull=False,
        ).values_list("pool").annotate(total=Count("id"))
    )

    return render(request, "dashboard/bancas.html", {
        "bancas": bancas,
        "corretores_llm": corretores_llm,
        "provedores": provedores,
        "cargas": cargas,
    })


@login_required
def banca_detalhe(request, banca_id):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores acessam esta área.")
        return redirect("home")

    banca = PoolCorrecao.objects.select_related("revisor_corretor").prefetch_related(
        "corretores__corretor_llm__provedor",
        "corretores__usuario",
    ).filter(id=banca_id).first()

    if banca is None:
        messages.error(request, "Banca não encontrada.")
        return redirect("bancas")

    from apps.avaliacoes.models import Consolidacao
    from apps.corretores.models import CorretorLLM, ProvedorLLM

    corretores_llm = CorretorLLM.objects.select_related("provedor").order_by("nome")
    provedores = ProvedorLLM.objects.filter(ativo=True).order_by("nome")
    usuarios = CustomUser.objects.filter(
        user_type__in=[UserType.CORRETOR, UserType.PROFESSOR, UserType.ADMIN]
    ).order_by("nome")

    revisor_usos = 0
    if banca.revisor_corretor:
        revisor_usos = Consolidacao.objects.filter(
            pool=banca, usou_revisor_llm=True,
        ).count()

    return render(request, "dashboard/banca_detalhe.html", {
        "banca": banca,
        "corretores_llm": corretores_llm,
        "provedores": provedores,
        "usuarios": usuarios,
        "revisor_usos": revisor_usos,
    })


@login_required
def membro_detalhe(request, banca_id, membro_id):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores acessam esta área.")
        return redirect("home")

    banca = PoolCorrecao.objects.filter(id=banca_id).first()
    if banca is None:
        messages.error(request, "Banca não encontrada.")
        return redirect("bancas")

    membro = PoolCorretor.objects.filter(
        id=membro_id, pool=banca,
    ).select_related(
        "corretor_llm__provedor", "usuario",
    ).first()

    if membro is None:
        messages.error(request, "Membro não encontrado.")
        return redirect("banca-detalhe", banca_id=banca_id)

    if request.method == "POST":
        descricao = request.POST.get("descricao", "").strip()
        membro.descricao = descricao
        peso_str = request.POST.get("peso", "").strip()
        update = ["descricao"]
        if peso_str:
            try:
                peso_val = float(peso_str)
                membro.peso = max(0.1, peso_val)
                update.append("peso")
            except ValueError:
                pass
        membro.save(update_fields=update)
        messages.success(request, "Configurações atualizadas com sucesso.")
        return redirect("membro-detalhe", banca_id=banca_id, membro_id=membro_id)

    return render(request, "dashboard/membro_detalhe.html", {
        "banca": banca,
        "membro": membro,
    })


@login_required
def agentes(request):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores acessam esta área.")
        return redirect("home")
    from apps.corretores.models import CorretorLLM, PoolCorrecao

    corretores = CorretorLLM.objects.select_related("provedor").prefetch_related(
        "vinculos_pool__pool",
    ).order_by("-rating", "nome")
    pools = PoolCorrecao.objects.filter(ativo=True).order_by("nome")
    return render(request, "dashboard/agentes.html", {
        "agentes": corretores,
        "pools": pools,
    })


@login_required
def agentes_prompts(request):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores acessam esta área.")
        return redirect("home")
    from apps.corretores.models import PromptTemplate

    templates = PromptTemplate.objects.order_by("-tipo", "nome")
    return render(request, "dashboard/agentes_prompts.html", {"templates": templates})


@login_required
def agente_prompt_form(request, prompt_id=None):
    import json

    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores acessam esta área.")
        return redirect("home")
    from apps.corretores.models import PromptTemplate

    instance = None
    if prompt_id:
        instance = PromptTemplate.objects.filter(id=prompt_id).first()
        if instance is None:
            messages.error(request, "Template não encontrado.")
            return redirect("agentes-prompts")

    duplicar_id = request.GET.get("duplicar")
    if duplicar_id and not instance and request.method == "GET":
        source = PromptTemplate.objects.filter(id=duplicar_id).first()
        if source:
            form = {
                "nome": source.nome + " (cópia)",
                "tipo": "custom",
                "descricao": source.descricao,
                "sistema_prompt": source.sistema_prompt,
                "formato_saida": source.formato_saida,
                "competencias_padrao": json.dumps(
                    source.competencias_padrao, ensure_ascii=False, indent=2,
                ) if source.competencias_padrao else "[]",
            }
            return render(request, "dashboard/agente_prompt_form.html", {
                "form": form,
                "editando": False,
            })
        messages.error(request, "Template original não encontrado para duplicação.")
        return redirect("agentes-prompts")

    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        tipo = request.POST.get("tipo", "custom")
        descricao = request.POST.get("descricao", "").strip()
        sistema_prompt = request.POST.get("sistema_prompt", "").strip()
        formato_saida = request.POST.get("formato_saida", "").strip()
        comp_raw = request.POST.get("competencias_padrao", "[]").strip()

        if not nome:
            messages.error(request, "Nome é obrigatório.")
        else:
            try:
                competencias = json.loads(comp_raw) if comp_raw else []
                if not isinstance(competencias, list):
                    competencias = []
            except json.JSONDecodeError:
                competencias = []

            if instance:
                if instance.tipo != "base":
                    instance.nome = nome
                    instance.tipo = tipo
                    instance.sistema_prompt = sistema_prompt
                instance.descricao = descricao
                instance.formato_saida = formato_saida
                instance.competencias_padrao = competencias
                instance.save()
                messages.success(request, "Template atualizado.")
            else:
                PromptTemplate.objects.create(
                    nome=nome, tipo=tipo, descricao=descricao,
                    sistema_prompt=sistema_prompt, formato_saida=formato_saida,
                    competencias_padrao=competencias,
                )
                messages.success(request, "Template criado.")
            return redirect("agentes-prompts")

    editando = instance is not None
    form = {
        "nome": instance.nome if instance else "",
        "tipo": instance.tipo if instance else "custom",
        "descricao": instance.descricao if instance else "",
        "sistema_prompt": instance.sistema_prompt if instance else "",
        "formato_saida": instance.formato_saida if instance else "",
        "competencias_padrao": json.dumps(
            instance.competencias_padrao, ensure_ascii=False, indent=2
        ) if instance and instance.competencias_padrao else "[]",
    }

    return render(request, "dashboard/agente_prompt_form.html", {
        "form": form,
        "editando": editando,
    })


@login_required
def agente_detalhe(request, agente_id):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores acessam esta área.")
        return redirect("home")

    from apps.corretores.models import CorretorLLM, Ferramenta, PromptTemplate, ProvedorLLM, Skill

    agente = CorretorLLM.objects.select_related("provedor").prefetch_related(
        "skills", "ferramentas_ativas", "subagentes",
    ).filter(id=agente_id).first()

    if agente is None:
        messages.error(request, "Agente não encontrado.")
        return redirect("agentes")

    provedores = ProvedorLLM.objects.filter(ativo=True).order_by("nome")
    templates = PromptTemplate.objects.order_by("-tipo", "nome")
    todas_skills = Skill.objects.order_by("nome")
    todas_ferramentas = Ferramenta.objects.order_by("nome")

    if request.method == "POST":
        if request.POST.get("acao") == "aplicar_sugestao":
            tipo = request.POST.get("tipo_sugestao")
            if tipo == "temperature":
                valor = request.POST.get("valor_sugerido")
                if valor:
                    agente.temperature = float(valor)
                    agente.save(update_fields=["temperature"])
                    messages.success(request, f"Temperature alterada para {valor}.")
            elif tipo == "prompt":
                messages.info(request, "Role até a seção 'Prompt de Avaliação' para editar.")
            elif tipo == "skills":
                messages.info(request, "Role até a seção 'Skills' para revisar.")
            return redirect("agente-detalhe", agente_id=agente_id)

        nome = request.POST.get("nome", "").strip()
        descricao = request.POST.get("descricao", "").strip()
        provedor_id = request.POST.get("provedor", "").strip()
        modelo = request.POST.get("modelo", "").strip()
        prompt_template = request.POST.get("prompt_template", "").strip()
        prompt_personalizado = request.POST.get("prompt_personalizado", "").strip()
        prompt_ref_id = request.POST.get("prompt_template_ref", "").strip()
        skills_ids = request.POST.getlist("skills")
        ferramentas_ids = request.POST.getlist("ferramentas_ativas")
        subagentes_ids = request.POST.getlist("subagentes")
        temperature_str = request.POST.get("temperature", "").strip()
        seed_str = request.POST.get("seed", "").strip()
        top_p_str = request.POST.get("top_p", "").strip()
        output_json = request.POST.get("output_json", "") == "1"

        if nome:
            agente.nome = nome
            agente.descricao = descricao
            if provedor_id:
                agente.provedor_id = provedor_id
            if modelo:
                agente.modelo = modelo
            if prompt_template:
                agente.prompt_template = prompt_template
            agente.prompt_personalizado = prompt_personalizado
            if prompt_ref_id:
                agente.prompt_template_ref_id = prompt_ref_id
            agente.skills.set(skills_ids)
            agente.ferramentas_ativas.set(ferramentas_ids)
            agente.subagentes.set(subagentes_ids)
            if temperature_str:
                try:
                    agente.temperature = float(temperature_str)
                except ValueError:
                    pass
            if seed_str:
                try:
                    agente.seed = int(seed_str)
                except ValueError:
                    pass
            else:
                agente.seed = None
            if top_p_str:
                try:
                    agente.top_p = float(top_p_str)
                except ValueError:
                    pass
            agente.output_json = output_json
            agente.incluir_protocolo_enem = request.POST.get("incluir_protocolo_enem") == "on"
            agente.incluir_base_conhecimento = (
                request.POST.get("incluir_base_conhecimento") == "on"
            )
            agente.save()
            messages.success(request, "Agente atualizado com sucesso.")
        return redirect("agente-detalhe", agente_id=agente_id)

    skills_vinculadas = set(agente.skills.values_list("id", flat=True))
    ferramentas_vinculadas = set(agente.ferramentas_ativas.values_list("id", flat=True))
    subagentes_vinculados = set(agente.subagentes.values_list("id", flat=True))

    subagentes_disponiveis = CorretorLLM.objects.exclude(id=agente_id).order_by("nome")

    from apps.avaliacoes.models import Avaliacao
    from apps.corretores.services import sugestoes_para_rating

    qtd_feedbacks = Avaliacao.objects.filter(
        corretor_llm=agente,
    ).exclude(admin_feedback="").count()
    sugestoes = sugestoes_para_rating(agente)

    return render(request, "dashboard/agente_detalhe.html", {
        "agente": agente,
        "provedores": provedores,
        "templates": templates,
        "todas_skills": todas_skills,
        "todas_ferramentas": todas_ferramentas,
        "skills_vinculadas": skills_vinculadas,
        "ferramentas_vinculadas": ferramentas_vinculadas,
        "subagentes_disponiveis": subagentes_disponiveis,
        "subagentes_vinculados": subagentes_vinculados,
        "sugestoes": sugestoes,
        "qtd_feedbacks": qtd_feedbacks,
    })


def admin_corretores(request):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas admin acessa esta área.")
        return redirect("home")
    return redirect("agentes")


@login_required
def admin_corretor_form(request, corretor_id=None):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas admin acessa esta área.")
        return redirect("home")
    from apps.corretores.models import CorretorLLM, ProvedorLLM

    instance = None
    if corretor_id:
        instance = CorretorLLM.objects.filter(id=corretor_id).first()
        if instance is None:
            messages.error(request, "Corretor não encontrado.")
            return redirect("agentes")
        return redirect("agente-detalhe", agente_id=corretor_id)

    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        provedor_id = request.POST.get("provedor", "").strip()
        modelo = request.POST.get("modelo", "").strip()
        descricao = request.POST.get("descricao", "").strip()

        if not nome or not modelo:
            messages.error(request, "Nome e modelo são obrigatórios.")
        else:
            provedor = ProvedorLLM.objects.filter(id=provedor_id).first() if provedor_id else None
            novo = CorretorLLM.objects.create(
                nome=nome, provedor=provedor, modelo=modelo,
                descricao=descricao,
            )
            messages.success(request, "Corretor criado.")
            return redirect("agente-detalhe", agente_id=novo.id)

    provedores = ProvedorLLM.objects.filter(ativo=True).order_by("nome")
    form = {}

    return render(request, "dashboard/admin_corretor_form.html", {
        "titulo": "Novo corretor",
        "form": form,
        "provedores": provedores,
    })


@login_required
def admin_skills(request):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores acessam esta área.")
        return redirect("home")
    from apps.corretores.models import Skill

    skills = Skill.objects.order_by("nome")
    return render(request, "dashboard/admin_skills.html", {"skills": skills})


@login_required
def admin_skill_form(request, skill_id=None):
    import json

    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores acessam esta área.")
        return redirect("home")
    from apps.corretores.models import Skill

    instance = None
    if skill_id:
        instance = Skill.objects.filter(id=skill_id).first()
        if instance is None:
            messages.error(request, "Skill não encontrada.")
            return redirect("admin-skills")

    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        icone = request.POST.get("icone", "").strip()
        descricao = request.POST.get("descricao", "").strip()
        comp_raw = request.POST.get("competencias", "[]").strip()

        if not nome:
            messages.error(request, "Nome é obrigatório.")
        else:
            try:
                competencias = json.loads(comp_raw) if comp_raw else []
                if not isinstance(competencias, list):
                    competencias = []
            except json.JSONDecodeError:
                competencias = []

            if instance:
                instance.nome = nome
                instance.icone = icone
                instance.descricao = descricao
                instance.competencias = competencias
                instance.save()
                messages.success(request, "Skill atualizada.")
            else:
                Skill.objects.create(
                    nome=nome, icone=icone, descricao=descricao,
                    competencias=competencias,
                )
                messages.success(request, "Skill criada.")
            return redirect("admin-skills")

    form = {}
    if instance:
        form["nome"] = instance.nome
        form["icone"] = instance.icone or ""
        form["descricao"] = instance.descricao or ""
        form["competencias"] = json.dumps(
            instance.competencias, ensure_ascii=False, indent=2
        ) if instance.competencias else "[]"

    return render(request, "dashboard/admin_skill_form.html", {
        "titulo": "Editar skill" if instance else "Nova skill",
        "form": form,
        "editando": instance is not None,
    })


@login_required
def admin_ferramentas(request):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores acessam esta área.")
        return redirect("home")
    from apps.corretores.models import Ferramenta

    ferramentas = Ferramenta.objects.order_by("nome")
    return render(request, "dashboard/admin_ferramentas.html", {"ferramentas": ferramentas})


@login_required
def admin_ferramenta_form(request, ferramenta_id=None):
    if request.user.user_type != UserType.ADMIN:
        messages.warning(request, "Apenas administradores acessam esta área.")
        return redirect("home")
    from apps.corretores.models import Ferramenta

    instance = None
    if ferramenta_id:
        instance = Ferramenta.objects.filter(id=ferramenta_id).first()
        if instance is None:
            messages.error(request, "Ferramenta não encontrada.")
            return redirect("admin-ferramentas")

    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        slug = request.POST.get("slug", "").strip()
        descricao = request.POST.get("descricao", "").strip()
        ativa_por_padrao = request.POST.get("ativa_por_padrao", "") == "on"

        if not nome:
            messages.error(request, "Nome é obrigatório.")
        elif instance and not slug:
            messages.error(request, "Slug é obrigatório.")
        else:
            if instance:
                instance.nome = nome
                instance.slug = slug
                instance.descricao = descricao
                instance.ativa_por_padrao = ativa_por_padrao
                instance.save()
                messages.success(request, "Ferramenta atualizada.")
            else:
                auto_slug = slug or nome.lower().replace(" ", "-")
                Ferramenta.objects.create(
                    nome=nome, slug=auto_slug, descricao=descricao,
                    ativa_por_padrao=ativa_por_padrao,
                )
                messages.success(request, "Ferramenta criada.")
            return redirect("admin-ferramentas")

    form = {}
    if instance:
        form["nome"] = instance.nome
        form["slug"] = instance.slug
        form["descricao"] = instance.descricao or ""
        form["ativa_por_padrao"] = instance.ativa_por_padrao

    return render(request, "dashboard/admin_ferramenta_form.html", {
        "titulo": "Editar ferramenta" if instance else "Nova ferramenta",
        "form": form,
        "editando": instance is not None,
    })


@login_required
def admin_temas(request):
    if request.user.user_type not in (UserType.ADMIN, UserType.PROFESSOR):
        messages.warning(request, "Apenas admin e professores acessam esta área.")
        return redirect("home")
    temas = TemaRedacao.objects.select_related("criado_por").order_by("-criado_em")
    temas_ctx = [
        {"obj": t, "inconsistente": _tema_inconsistente(t)}
        for t in temas
    ]
    return render(request, "dashboard/admin_temas.html", {"temas": temas_ctx})


# --- INÍCIO: detecção de temas inconsistentes (feature removível) ---
def _tema_inconsistente(tema) -> bool:
    """Heurística temporária: texto vazio, igual ao título, ou apenas repetição dele.

    Bloco autocontido — pode ser removido junto com o botão
    "Selecionar inconsistentes" no template sem afetar o restante.
    """
    texto = (tema.texto or "").strip()
    titulo = (tema.titulo or "").strip()
    if not texto:
        return True
    if texto == titulo:
        return True
    if texto.lower().startswith(titulo.lower()) and len(texto) - len(titulo) < 20:
        return True
    return False
# --- FIM: detecção de temas inconsistentes (feature removível) ---


@login_required
def admin_tema_form(request, tema_id=None):
    if request.user.user_type not in (UserType.ADMIN, UserType.PROFESSOR):
        messages.warning(request, "Apenas admin e professores acessam esta área.")
        return redirect("home")

    instance = None
    if tema_id:
        instance = TemaRedacao.objects.filter(id=tema_id).first()
        if instance is None:
            messages.error(request, "Tema não encontrado.")
            return redirect("admin-temas")

    if request.method == "POST":
        titulo = request.POST.get("titulo", "").strip()
        texto = request.POST.get("texto", "").strip()
        ativo = request.POST.get("ativo") == "on"

        if not titulo:
            messages.error(request, "Título é obrigatório.")
        elif not texto:
            messages.error(request, "Texto do tema é obrigatório.")
        else:
            if instance:
                instance.titulo = titulo
                instance.texto = texto
                instance.ativo = ativo
                if "imagem" in request.FILES:
                    instance.imagem = request.FILES["imagem"]
                instance.save()
                messages.success(request, "Tema atualizado.")
            else:
                TemaRedacao.objects.create(
                    titulo=titulo,
                    texto=texto,
                    ativo=ativo,
                    imagem=request.FILES.get("imagem"),
                    criado_por=request.user,
                )
                messages.success(request, "Tema criado.")
            return redirect("admin-temas")

    editando = instance is not None
    form = {}
    if instance:
        form["titulo"] = instance.titulo
        form["texto"] = instance.texto
        form["ativo"] = instance.ativo
        form["imagem"] = instance.imagem

    return render(request, "dashboard/admin_tema_form.html", {
        "titulo": "Editar tema" if editando else "Novo tema",
        "form": form,
        "editando": editando,
    })


_STOPWORDS = {
    "de", "a", "o", "e", "que", "do", "da", "em", "um", "para", "com",
    "não", "uma", "os", "no", "se", "na", "por", "mais", "as", "dos",
    "como", "mas", "ao", "ele", "das", "à", "seu", "sua", "ou", "quando",
    "muito", "nos", "já", "eu", "também", "só", "pelo", "pela", "até",
    "isso", "ela", "entre", "depois", "sem", "mesmo", "aos", "seus",
    "quem", "nas", "me", "esse", "eles", "está", "você", "tinha", "foram",
    "essa", "num", "nem", "suas", "meu", "às", "minha", "numa", "pelos",
    "elas", "qual", "nós", "lhe", "deles", "essas", "esses",
}


@login_required
def relatorios(request):
    if request.user.user_type == UserType.ALUNO:
        messages.warning(request, "Esta área é exclusiva para staff.")
        return redirect("home")

    is_admin_prof = request.user.user_type in {UserType.ADMIN, UserType.PROFESSOR}
    context: dict = {"is_admin_prof": is_admin_prof}

    # ---- Seção 1: Progresso por Competência ----
    alunos_qs = CustomUser.objects.filter(user_type=UserType.ALUNO).order_by("nome")
    selected_aluno_id = request.GET.get("aluno_id")
    if selected_aluno_id:
        aluno = get_object_or_404(alunos_qs, id=selected_aluno_id)
    else:
        aluno = alunos_qs.first()

    context["alunos_list"] = alunos_qs
    context["selected_aluno"] = aluno

    if aluno:
        consolidacoes = Consolidacao.objects.filter(
            redacao__usuario=aluno, status="final"
        ).order_by("criada_em")
        if consolidacoes.count() >= 2:
            datas = [f"#{i+1}" for i in range(consolidacoes.count())]
            comp_data = {
                "C1": [c.c1_nota for c in consolidacoes],
                "C2": [c.c2_nota for c in consolidacoes],
                "C3": [c.c3_nota for c in consolidacoes],
                "C4": [c.c4_nota for c in consolidacoes],
                "C5": [c.c5_nota for c in consolidacoes],
            }
            context["timeline_comp_json"] = timeline_comp_chart(datas, comp_data)
            context["timeline_json"] = timeline_chart(
                datas, [c.nota_total for c in consolidacoes]
            )

    # ---- Seção 2: Word cloud + Erros ----
    justificativas_textos: list[str] = []
    redacoes_aluno = Redacao.objects.filter(usuario=aluno) if aluno else Redacao.objects.none()
    for r in redacoes_aluno:
        for av in r.avaliacoes.filter(rascunho=False):
            for campo in [
                f"c{i}_{s}" for i in range(1, 6) for s in ("justificativa", "sugestoes")
            ]:
                txt = getattr(av, campo, "")
                if txt:
                    justificativas_textos.append(txt)

    if justificativas_textos:
        palavras: list[str] = []
        for texto in justificativas_textos:
            words = re.findall(r"\b[a-záàâãéèêíïóôõöúçñ]+\b", texto.lower())
            palavras.extend(w for w in words if w not in _STOPWORDS and len(w) > 2)
        word_counts = Counter(palavras).most_common(30)
        if word_counts:
            wc_words = [w[0] for w in word_counts]
            wc_freqs = [w[1] for w in word_counts]
            context["wordcloud_json"] = fake_wordcloud_chart(wc_words, wc_freqs)

    # Erros por tipo ao longo do tempo
    anotacoes_qs = Anotacao.objects.filter(
        avaliacao__redacao__usuario=aluno, avaliacao__rascunho=False
    ) if aluno else Anotacao.objects.none()
    if anotacoes_qs.exists():
        tipos_erro = list(ERRO_LABELS.keys())
        erros_por_mes = (
            anotacoes_qs.annotate(mes=models.functions.TruncMonth("criada_em"))
            .values("mes", "tipo_erro")
            .annotate(total=Count("id"))
            .order_by("mes")
        )
        meses_set: dict[str, dict[str, int]] = {}
        for e in erros_por_mes:
            m = e["mes"].strftime("%m/%Y") if e["mes"] else "?"
            meses_set.setdefault(m, {}).setdefault(e["tipo_erro"], 0)
            meses_set[m][e["tipo_erro"]] += e["total"]
        meses_ord = sorted(meses_set.keys())
        valores_por_tipo = {t: [meses_set.get(m, {}).get(t, 0) for m in meses_ord] for t in tipos_erro}
        if meses_ord and any(sum(v) > 0 for v in valores_por_tipo.values()):
            context["erros_stacked_json"] = stacked_bar_chart(
                meses_ord, tipos_erro, valores_por_tipo, title="Evolução de erros por tipo"
            )

    # ---- Seção 3: IA vs Humano + Scorecard + Temas + Riscos (admin/professor) ----
    if is_admin_prof:
        redacoes_com_ambos = Redacao.objects.annotate(
            human=Count("avaliacoes", filter=Q(avaliacoes__modelo_llm="humano", avaliacoes__rascunho=False)),
            ia=Count("avaliacoes", filter=~Q(avaliacoes__modelo_llm="humano") & ~Q(avaliacoes__modelo_llm="") & Q(avaliacoes__rascunho=False)),
        ).filter(human__gt=0, ia__gt=0)

        diffs_c = {f"c{i}": [] for i in range(1, 6)}
        for r in redacoes_com_ambos:
            h = r.avaliacoes.filter(modelo_llm="humano", rascunho=False).first()
            ia = r.avaliacoes.exclude(modelo_llm="humano").exclude(modelo_llm="").first()
            if h and ia:
                for i in range(1, 6):
                    diffs_c[f"c{i}"].append(getattr(h, f"c{i}_nota") - getattr(ia, f"c{i}_nota"))

        if any(diffs_c[f"c{i}"] for i in range(1, 6)):
            medias_diffs = [
                sum(diffs_c[f"c{i}"]) / len(diffs_c[f"c{i}"])
                for i in range(1, 6)
            ]
            context["ia_humano_json"] = bar_chart(
                COMPETENCIAS,
                medias_diffs,
                title="Diferença média Humano − IA por competência (positivo = humano maior)",
            )

        corretores = (
            Avaliacao.objects.filter(modelo_llm="humano", rascunho=False)
            .values("avaliador")
            .annotate(
                total=Count("id"),
                media=Avg("nota_total"),
                media_c5=Avg("c5_nota"),
            )
            .order_by("-total")[:10]
        )
        if corretores:
            labels_c = [c["avaliador"][:15] for c in corretores]
            context["scorecard_json"] = bar_chart(
                labels_c,
                [round(c["media"] or 0) for c in corretores],
                title="Nota média por corretor",
            )

        temas_qs = (
            Redacao.objects.filter(tema_ref__isnull=False)
            .values("tema_ref__titulo")
            .annotate(media=Avg("consolidacoes__nota_total"), total=Count("id"))
            .order_by("-media")
        )
        if temas_qs:
            context["temas_json"] = bar_chart(
                [t["tema_ref__titulo"][:25] for t in temas_qs],
                [round(t["media"] or 0) for t in temas_qs],
                title="Nota média por tema",
            )

        alunos_em_risco = []
        for a in alunos_qs:
            ultimas = Consolidacao.objects.filter(
                redacao__usuario=a, status="final"
            ).order_by("-atualizada_em")[:3]
            if ultimas:
                media = sum(c.nota_total for c in ultimas) / len(ultimas)
                c5_media = sum(c.c5_nota for c in ultimas) / len(ultimas)
                if media < 400 or c5_media < 100:
                    alunos_em_risco.append({
                        "nome": a.nome_exibicao,
                        "media": round(media),
                        "c5": round(c5_media),
                        "total": len(ultimas),
                    })
        context["alunos_risco"] = alunos_em_risco

    return render(request, "dashboard/relatorios.html", context)


@login_required
def relatorios_corretores(request):
    if request.user.user_type == UserType.ALUNO:
        messages.warning(request, "Esta área é exclusiva para staff.")
        return redirect("home")

    context: dict = {}

    # ---- Corretor IA selecionado ----
    ia_qs = (
        Avaliacao.objects.filter(rascunho=False, corretor_llm__isnull=False)
        .exclude(modelo_llm="humano")
        .exclude(modelo_llm="")
        .values("corretor_llm_id", "corretor_llm__nome")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    context["ia_list"] = [
        {"id": str(ia["corretor_llm_id"]), "nome": ia["corretor_llm__nome"], "total": ia["total"]}
        for ia in ia_qs
    ]

    selected_ia = request.GET.get("corretor")
    if selected_ia:
        ia_avs = Avaliacao.objects.filter(
            rascunho=False, corretor_llm_id=selected_ia
        ).exclude(modelo_llm="humano").exclude(modelo_llm="")
    else:
        ia_avs = Avaliacao.objects.filter(
            rascunho=False, corretor_llm__isnull=False
        ).exclude(modelo_llm="humano").exclude(modelo_llm="")
    context["selected_ia"] = selected_ia

    # ---- 1. Ranking de consistência (barh) ----
    stats_qs = (
        ia_avs.values("avaliador")
        .annotate(
            total=Count("id"),
            media=Avg("nota_total"),
            std=StdDev("nota_total"),
            qtd_anotacoes=Count("anotacoes"),
            media_c1=Avg("c1_nota"),
            media_c2=Avg("c2_nota"),
            media_c3=Avg("c3_nota"),
            media_c4=Avg("c4_nota"),
            media_c5=Avg("c5_nota"),
        )
        .order_by("std")
    )
    labels_ranking = [s["avaliador"] for s in stats_qs if s["std"] is not None]
    stds_ranking = [s["std"] or 0 for s in stats_qs if s["std"] is not None]
    if labels_ranking:
        context["ranking_json"] = barh_chart(
            labels_ranking, stds_ranking,
            title="Consistência dos corretores IA (menor desvio = mais estável)",
            color="#22c55e",
        )

    # ---- 2. Calibração por competência (heatmap) ----
    competencias = ["C1", "C2", "C3", "C4", "C5"]
    medias_gerais = Avaliacao.objects.filter(rascunho=False).aggregate(
        avg_c1=Avg("c1_nota"), avg_c2=Avg("c2_nota"), avg_c3=Avg("c3_nota"),
        avg_c4=Avg("c4_nota"), avg_c5=Avg("c5_nota"),
    )
    if stats_qs.count() >= 2:
        heatmap_z: list[list[float]] = []
        heatmap_labels: list[str] = []
        for s in stats_qs:
            heatmap_labels.append(s["avaliador"])
            heatmap_z.append([
                round((s["media_c1"] or 0) - (medias_gerais["avg_c1"] or 0), 1),
                round((s["media_c2"] or 0) - (medias_gerais["avg_c2"] or 0), 1),
                round((s["media_c3"] or 0) - (medias_gerais["avg_c3"] or 0), 1),
                round((s["media_c4"] or 0) - (medias_gerais["avg_c4"] or 0), 1),
                round((s["media_c5"] or 0) - (medias_gerais["avg_c5"] or 0), 1),
            ])
        context["calibracao_json"] = heatmap_chart(
            heatmap_z, competencias, heatmap_labels,
            title="Desvio da média por competência (vermelho = abaixo, azul = acima)",
        )

    # ---- 3. Perfil de anotações (stacked bar) ----
    anots_qs = Anotacao.objects.filter(
        avaliacao__rascunho=False, avaliacao__corretor_llm__isnull=False
    ).exclude(avaliacao__modelo_llm="humano").exclude(avaliacao__modelo_llm="")
    if selected_ia:
        anots_qs = anots_qs.filter(avaliacao__corretor_llm_id=selected_ia)

    perfil = (
        anots_qs.values("avaliacao__corretor_llm_id", "avaliacao__corretor_llm__nome", "tipo_erro")
        .annotate(total=Count("id"))
        .order_by("avaliacao__corretor_llm__nome")
    )
    tipos_erro = list(ERRO_LABELS.keys())
    corretor_para_erros: dict[str, dict[str, int]] = {}
    todos_corretores: list[str] = []
    for e in perfil:
        nome = e["avaliacao__corretor_llm__nome"] or e["avaliacao__corretor_llm_id"]
        if nome not in corretor_para_erros:
            corretor_para_erros[nome] = {t: 0 for t in tipos_erro}
            todos_corretores.append(nome)
        corretor_para_erros[nome][e["tipo_erro"]] += e["total"]

    if todos_corretores and len(todos_corretores) <= 15:
        valores_por_tipo = {
            t: [corretor_para_erros.get(c, {}).get(t, 0) for c in todos_corretores]
            for t in tipos_erro
        }
        context["anotacoes_profile_json"] = stacked_bar_chart(
            todos_corretores, tipos_erro, valores_por_tipo,
            title="Perfil de anotações por corretor IA",
        )

    # ---- 4. IA vs Humano detalhado ----
    redacoes_com_ambos = Redacao.objects.annotate(
        human=Count("avaliacoes", filter=Q(avaliacoes__modelo_llm="humano", avaliacoes__rascunho=False)),
        ia=Count("avaliacoes", filter=~Q(avaliacoes__modelo_llm="humano") & ~Q(avaliacoes__modelo_llm="") & Q(avaliacoes__rascunho=False)),
    ).filter(human__gt=0, ia__gt=0)

    diffs_por_avaliador: dict[str, list[float]] = {}
    diffs_por_competencia: dict[str, list[float]] = {f"c{i}": [] for i in range(1, 6)}
    for r in redacoes_com_ambos:
        h = r.avaliacoes.filter(modelo_llm="humano", rascunho=False).first()
        ias = r.avaliacoes.exclude(modelo_llm="humano").exclude(modelo_llm="").filter(rascunho=False)
        for ia in ias:
            nome = ia.avaliador
            diff = ia.nota_total - h.nota_total if h else 0
            if nome not in diffs_por_avaliador:
                diffs_por_avaliador[nome] = []
            diffs_por_avaliador[nome].append(diff)
            if h:
                for i in range(1, 6):
                    diffs_por_competencia[f"c{i}"].append(
                        getattr(ia, f"c{i}_nota") - getattr(h, f"c{i}_nota")
                    )

    if diffs_por_avaliador:
        labels_diff = []
        medias_diff = []
        for nome in sorted(diffs_por_avaliador, key=lambda n: sum(diffs_por_avaliador[n]) / len(diffs_por_avaliador[n])):
            vals = diffs_por_avaliador[nome]
            labels_diff.append(nome)
            medias_diff.append(sum(vals) / len(vals))
        context["ia_humano_detailed_json"] = barh_chart(
            labels_diff, medias_diff,
            title="Diferença média IA − Humano (nota total, positivo = IA superestima)",
            color="#f97316",
        )

    if any(diffs_por_competencia[c] for c in diffs_por_competencia):
        medias_comp_diff = []
        for i in range(1, 6):
            vals = diffs_por_competencia[f"c{i}"]
            medias_comp_diff.append(sum(vals) / len(vals) if vals else 0)
        context["ia_humano_comp_json"] = bar_chart(
            ["C1", "C2", "C3", "C4", "C5"], medias_comp_diff,
            title="Diferença média IA − Humano por competência",
        )

    # ---- 5. Comparação entre modelos ----
    modelos_qs = (
        Avaliacao.objects.filter(rascunho=False)
        .exclude(modelo_llm="humano")
        .exclude(modelo_llm="")
        .values("modelo_llm")
        .annotate(
            total=Count("id"),
            media=Avg("nota_total"),
            std=StdDev("nota_total"),
            media_c1=Avg("c1_nota"),
            media_c2=Avg("c2_nota"),
            media_c3=Avg("c3_nota"),
            media_c4=Avg("c4_nota"),
            media_c5=Avg("c5_nota"),
        )
        .order_by("modelo_llm")
    )
    modelos_list = list(modelos_qs)
    if modelos_list:
        labels_modelos = [m["modelo_llm"] for m in modelos_list]
        context["modelos_media_json"] = barh_chart(
            labels_modelos, [m["media"] or 0 for m in modelos_list],
            title="Nota média por modelo LLM", color="#3b82f6",
        )
        context["modelos_std_json"] = barh_chart(
            labels_modelos, [m["std"] or 0 for m in modelos_list],
            title="Desvio padrão por modelo LLM (menor = mais consistente)",
            color="#a855f7",
        )

    # ---- Resumo numérico ----
    total_ias = ia_avs.count()
    total_humanas = Avaliacao.objects.filter(rascunho=False, modelo_llm="humano").count()
    context["total_ias"] = total_ias
    context["total_humanas"] = total_humanas
    if total_ias:
        media_ia = ia_avs.aggregate(Avg("nota_total"))["nota_total__avg"]
        context["media_ia"] = round(media_ia or 0)
        std_ia = ia_avs.aggregate(StdDev("nota_total"))["nota_total__stddev"]
        context["std_ia"] = round(std_ia or 0)

    # ---- 6. Tendência temporal: média móvel + desvio padrão ----
    try:
        window = max(1, min(30, int(request.GET.get("window", "5"))))
    except (ValueError, TypeError):
        window = 5
    group_by = request.GET.get("group_by", "modelo")
    agregacao = request.GET.get("agregacao", "nenhuma")
    context["tendencia_window"] = window
    context["tendencia_group_by"] = group_by
    context["tendencia_agregacao"] = agregacao

    avs_timeline = Avaliacao.objects.filter(
        rascunho=False,
    ).order_by("criada_em").select_related("corretor_llm")

    if selected_ia:
        avs_timeline = avs_timeline.filter(corretor_llm_id=selected_ia)

    def _nome_grupo(av: Avaliacao) -> str:
        if group_by == "corretor":
            return av.avaliador or (
                av.corretor_llm.nome if av.corretor_llm else "Desconhecido"
            )
        return av.modelo_llm or "Desconhecido"

    groups_timeline: dict[str, list[tuple]] = {}

    if agregacao == "nenhuma":
        for av in avs_timeline:
            groups_timeline.setdefault(_nome_grupo(av), []).append((
                av.criada_em.strftime("%d/%m/%Y"),
                av.nota_total,
                av.c1_nota,
                av.c2_nota,
                av.c3_nota,
                av.c4_nota,
                av.c5_nota,
            ))
    else:
        temp: dict[tuple[str, str], list[list[int]]] = defaultdict(list)
        for av in avs_timeline:
            nome = _nome_grupo(av)
            if agregacao == "dia":
                periodo = av.criada_em.strftime("%d/%m/%Y")
            else:
                periodo = av.criada_em.strftime("%d/%m/%Y %H:00")
            temp[(nome, periodo)].append([
                av.nota_total,
                av.c1_nota, av.c2_nota, av.c3_nota, av.c4_nota, av.c5_nota,
            ])
        for (nome, periodo), valores_list in sorted(
            temp.items(), key=lambda x: x[0][1]
        ):
            n = len(valores_list)
            means = [round(sum(v[i] for v in valores_list) / n, 1) for i in range(6)]
            groups_timeline.setdefault(nome, []).append(
                tuple([periodo, means[0], means[1], means[2], means[3], means[4], means[5]])
            )

    if groups_timeline:
        dates_by_group = {
            g: [d[0] for d in data] for g, data in groups_timeline.items()
        }

        valores_total = {
            g: [d[1] for d in data] for g, data in groups_timeline.items()
        }
        agg_label = (
            "" if agregacao == "nenhuma"
            else f" — agregado por {agregacao}"
        )
        group_label = "por modelo LLM" if group_by == "modelo" else "por corretor"
        context["tendencia_total_json"] = timeline_mean_std_chart(
            dates_by_group,
            valores_total,
            window=window,
            title=(
                f"Média móvel da nota total "
                f"— {group_label}{agg_label} "
                f"(janela={window})"
            ),
            yaxis_title="Nota total",
            yaxis_range=[0, 1000],
        )

        competencias_nomes = [
            "C1 - Norma Padrão",
            "C2 - Tema",
            "C3 - Argumentação",
            "C4 - Coesão",
            "C5 - Intervenção",
        ]
        for idx_comp, nome_comp in enumerate(competencias_nomes):
            valores_comp = {
                g: [d[idx_comp + 2] for d in data]
                for g, data in groups_timeline.items()
            }
            context[f"tendencia_comp{idx_comp + 1}_json"] = timeline_mean_std_chart(
                dates_by_group,
                valores_comp,
                window=window,
                title=f"Média móvel — {nome_comp} (janela={window}{agg_label})",
                yaxis_title="Nota",
                yaxis_range=[0, 200],
            )

    return render(request, "dashboard/relatorios_corretores.html", context)
