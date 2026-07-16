from __future__ import annotations

import logging
import os
from typing import Any

from asgiref.sync import async_to_sync
from django.utils import timezone

from apps.avaliacoes.models import Notificacao
from apps.avaliacoes.notifications import criar_notificacao, notificar_aluno_correcao_concluida
from apps.corretores.models import PoolCorrecao, PoolCorretor
from apps.corretores.providers import obter_api_key
from apps.redacoes.models import Redacao
from essay_essay.domain.enums import CompetenciaNome, NotaCompetencia
from essay_essay.domain.models import Avaliacao as AvaliacaoDomain
from essay_essay.domain.models import Redacao as RedacaoDomain
from essay_essay.evaluators.factory import criar_llm_client
from essay_essay.evaluators.ferramentas import (
    executar_ferramentas,
    formatar_resultados_ferramentas,
)
from essay_essay.evaluators.llm import LLMClient
from essay_essay.evaluators.openai_client import OpenAILLMClient
from essay_essay.evaluators.orchestrator import (
    PromptTemplateProvider,
    avaliar_com_pool,
    avaliar_com_revisor,
    avaliar_com_um,
    consolidar_notas,
)
from essay_essay.evaluators.orchestrator_especialistas import avaliar_com_especialistas
from essay_essay.evaluators.orchestrator_subagentes import avaliar_com_subagentes
from essay_essay.evaluators.span_matcher import encontrar_trecho

from .models import Anotacao, Avaliacao, Consolidacao

logger = logging.getLogger(__name__)


def _tema_exibicao(redacao: Redacao) -> str:
    return redacao.tema or (redacao.tema_ref.titulo if redacao.tema_ref else "redação sem título")


_COMP_PARA_SLUG: dict[str, str] = {
    "c1": "c1", "c2": "c2", "c3": "c3", "c4": "c4", "c5": "c5",
}


def _carregar_rubricas_do_banco() -> dict[CompetenciaNome, str]:
    from apps.corretores.models import Rubrica

    rubricas: dict[CompetenciaNome, str] = {}
    slug_para_enum = {
        "c1": CompetenciaNome.C1,
        "c2": CompetenciaNome.C2,
        "c3": CompetenciaNome.C3,
        "c4": CompetenciaNome.C4,
        "c5": CompetenciaNome.C5,
    }
    rubric_objs = Rubrica.objects.filter(ativa=True).order_by("competencia", "-versao")
    seen: set[str] = set()
    for r in rubric_objs:
        if r.competencia in seen:
            continue
        seen.add(r.competencia)
        texto = (r.arvore or {}).get("texto", "")
        if texto and r.competencia in slug_para_enum:
            rubricas[slug_para_enum[r.competencia]] = texto
    return rubricas


def _avaliar_modo_especialistas(
    llm: LLMClient,
    redacao: Redacao,
    redacao_domain: RedacaoDomain,
    modelo: str | None = None,
    pool: PoolCorrecao | None = None,
) -> None:
    from essay_essay.config import config as app_config
    from essay_essay.evaluators.extrator import extrair_estrutura

    default_model = modelo or app_config.llm_model or "gpt-4o"

    textos_motivadores = None
    if redacao.tema_ref and redacao.tema_ref.texto:
        textos_motivadores = redacao.tema_ref.texto
    tema_para_ferramenta = redacao_domain.tema or ""

    resultados_ferramentas = executar_ferramentas(
        texto=redacao_domain.texto,
        tema=tema_para_ferramenta,
        textos_motivadores=textos_motivadores,
        llm=llm,
        modelo=default_model,
    )
    logger.info(
        "Ferramentas: palavras=%d(%s), tema=%.3f(fuga=%s,tang=%s), paragrafos=%d",
        resultados_ferramentas["palavras"]["total"],
        "ok" if resultados_ferramentas["palavras"]["valido"] else "fora",
        resultados_ferramentas["tema"]["score"],
        resultados_ferramentas["tema"]["fuga_total"],
        resultados_ferramentas["tema"]["tangencia"],
        resultados_ferramentas["estrutura"]["paragrafos"],
    )

    if resultados_ferramentas["bloqueante"]:
        logger.info(
            "Redação %s: ferramentas detectaram bloqueio (%s) — "
            "prosseguindo com avaliação completa para feedback pedagógico",
            redacao.id,
            resultados_ferramentas["blocking_msg"][:80],
        )

    logger.info("Modo especialistas (via pool) — extraindo estrutura...")
    contexto = async_to_sync(extrair_estrutura)(
        llm, redacao_domain, modelo=default_model,
    )
    rubricas_db = _carregar_rubricas_do_banco()
    logger.info("Rubricas carregadas do banco: %d/%d", len(rubricas_db), 5)
    bloco_ferramentas = formatar_resultados_ferramentas(resultados_ferramentas)
    av, anotacoes = async_to_sync(avaliar_com_especialistas)(
        llm, redacao_domain,
        modelo=default_model,
        contexto_extracao=contexto,
        rubricas=rubricas_db if rubricas_db else None,
        resultados_ferramentas=bloco_ferramentas,
    )
    _validar_notas_pos_llm(av, resultados_ferramentas)
    debug_info = {"ferramentas": resultados_ferramentas}
    av_db = _criar_avaliacao_de_domain(redacao, av, pool=pool, debug_info=debug_info)
    _criar_anotacoes_de_domain(av_db, anotacoes, redacao.texto)
    logger.info("Especialistas concluídos — nota %d/1000", av.nota_total)


def _notas_por_competencia(avaliacao_domain: AvaliacaoDomain) -> dict[str, NotaCompetencia]:
    return {f"c{nota.competencia.value}": nota for nota in avaliacao_domain.notas}


def _criar_avaliacao_de_domain(
    redacao: Redacao,
    avaliacao_domain: AvaliacaoDomain,
    pool: PoolCorrecao | None = None,
    debug_info: dict | None = None,
) -> Avaliacao:
    notas = _notas_por_competencia(avaliacao_domain)
    corretor_llm_id = avaliacao_domain.corretor_llm_id or None

    di = debug_info or {}
    log_prompts = os.getenv("PLUMA_LOG_PROMPTS", "").lower() in ("true", "1", "yes", "on")
    di.setdefault("pluma_log_prompts", log_prompts)
    di.setdefault("tamanho_sistema", len(avaliacao_domain.sistema) if avaliacao_domain.sistema else 0)
    di.setdefault("tamanho_usuario", len(avaliacao_domain.usuario) if avaliacao_domain.usuario else 0)
    di.setdefault("tempo_llm_ms", avaliacao_domain.tempo_llm_ms)
    di.setdefault("tokens_entrada", avaliacao_domain.tokens_entrada)
    di.setdefault("tokens_saida", avaliacao_domain.tokens_saida)

    # TODO: substituir por consulta dinâmica quando disponível via API
    from essay_essay.evaluators.openai_client import CONTEXTOS_CONHECIDOS
    modelo = avaliacao_domain.modelo_llm
    max_ctx = 0
    for prefix, ctx in CONTEXTOS_CONHECIDOS.items():
        if modelo.startswith(prefix):
            max_ctx = ctx
            break
    if max_ctx and di.get("tokens_entrada"):
        di["modelo_max_contexto"] = max_ctx
        di["contexto_utilizado_pct"] = round(di["tokens_entrada"] / max_ctx * 100, 1)

    if log_prompts:
        di.setdefault("prompt_sistema", avaliacao_domain.sistema)
        di.setdefault("prompt_usuario", avaliacao_domain.usuario)

    av = Avaliacao.objects.create(
        redacao=redacao,
        pool=pool,
        corretor_llm_id=corretor_llm_id,
        c1_nota=notas["c1"].nota,
        c1_justificativa=notas["c1"].justificativa,
        c1_sugestoes=notas["c1"].sugestoes,
        c2_nota=notas["c2"].nota,
        c2_justificativa=notas["c2"].justificativa,
        c2_sugestoes=notas["c2"].sugestoes,
        c3_nota=notas["c3"].nota,
        c3_justificativa=notas["c3"].justificativa,
        c3_sugestoes=notas["c3"].sugestoes,
        c4_nota=notas["c4"].nota,
        c4_justificativa=notas["c4"].justificativa,
        c4_sugestoes=notas["c4"].sugestoes,
        c5_nota=notas["c5"].nota,
        c5_justificativa=notas["c5"].justificativa,
        c5_sugestoes=notas["c5"].sugestoes,
        nota_total=sum(n.nota for n in avaliacao_domain.notas),
        avaliador=avaliacao_domain.avaliador,
        modelo_llm=avaliacao_domain.modelo_llm,
        rascunho=False,
        debug_info=di,
    )
    logger.debug(
        "Avaliacao %s criada — nota_total=%d, avaliador=%s, pool=%s",
        av.pk, av.nota_total, av.avaliador, pool.nome if pool else "nenhuma",
    )
    return av


def _criar_avaliacao_zero(
    redacao: Redacao, pool: PoolCorrecao | None, resultados_ferramentas: dict
) -> None:
    motivo = resultados_ferramentas.get("blocking_msg", "Critérios programáticos não atendidos.")
    notas = [
        NotaCompetencia(c, 0, motivo, "")
        for c in CompetenciaNome
    ]
    av_domain = AvaliacaoDomain(
        redacao_id=str(redacao.id),
        notas=notas,
        avaliador="filtro-programatico",
        modelo_llm="",
    )
    _criar_avaliacao_de_domain(redacao, av_domain, pool=pool)
    if pool:
        atualizar_consolidacao(redacao, pool)
    logger.info("Redação %s bloqueada por filtros programáticos: %s", redacao.id, motivo)


def _validar_notas_pos_llm(
    av_domain: AvaliacaoDomain,
    resultados_ferramentas: dict,
) -> None:
    from essay_essay.evaluators.conhecimento_loader import carregar_kb_diretorio

    kb = carregar_kb_diretorio("base_de_conhecimento")

    tema = resultados_ferramentas.get("tema", {})
    notas_ajustadas: list[NotaCompetencia] = []
    for nota in av_domain.notas:
        if tema.get("fuga_total") and nota.competencia == CompetenciaNome.C2 and nota.nota > 0:
            notas_ajustadas.append(NotaCompetencia(
                competencia=nota.competencia,
                nota=0,
                justificativa=(
                    "Redação não aborda o tema proposto — nota zerada "
                    "automaticamente. "
                ) + nota.justificativa,
                sugestoes=nota.sugestoes,
            ))
            logger.warning(
                "Fuga total detectada mas LLM deu nota > 0 em C2 — corrigido para 0"
            )
        elif tema.get("tangencia") and nota.competencia == CompetenciaNome.C2 and nota.nota > 80:
            notas_ajustadas.append(NotaCompetencia(
                competencia=nota.competencia,
                nota=80,
                justificativa=(
                    "[CORRIGIDO] Nota limitada a 80 por tangenciamento de tema. "
                ) + nota.justificativa,
                sugestoes=nota.sugestoes,
            ))
            logger.warning(
                "Tangenciamento detectado mas LLM deu nota %d em C2 — limitado a 80",
                nota.nota,
            )
        else:
            notas_ajustadas.append(nota)
    av_domain.notas = notas_ajustadas

    if kb is not None:
        _validar_niveis_kb(av_domain, kb)

    for nota in av_domain.notas:
        if len(nota.justificativa.strip()) < 50:
            logger.warning(
                "Justificativa curta (%d chars) na C%d: '%s'",
                len(nota.justificativa.strip()),
                nota.competencia.value,
                nota.justificativa[:80],
            )


def _validar_niveis_kb(av_domain: AvaliacaoDomain, kb) -> None:
    """Valida se as notas estão dentro dos níveis definidos pela base de conhecimento."""
    for nota in av_domain.notas:
        nome_comp = f"C{nota.competencia.value}"
        niveis = kb.obter_niveis_validos(nome_comp)
        if not niveis:
            continue
        if nota.nota not in niveis:
            mais_proximo = min(niveis, key=lambda n: abs(n - nota.nota))
            logger.warning(
                "Nota %d na %s fora dos níveis da KB %s — sugerido %d",
                nota.nota, nome_comp, niveis, mais_proximo,
            )


def avaliacoes_para_domain(avaliacoes: list[Avaliacao]) -> list[AvaliacaoDomain]:
    resultado: list[AvaliacaoDomain] = []
    for av in avaliacoes:
        notas = [
            NotaCompetencia(CompetenciaNome.C1, av.c1_nota, av.c1_justificativa, av.c1_sugestoes),
            NotaCompetencia(CompetenciaNome.C2, av.c2_nota, av.c2_justificativa, av.c2_sugestoes),
            NotaCompetencia(CompetenciaNome.C3, av.c3_nota, av.c3_justificativa, av.c3_sugestoes),
            NotaCompetencia(CompetenciaNome.C4, av.c4_nota, av.c4_justificativa, av.c4_sugestoes),
            NotaCompetencia(CompetenciaNome.C5, av.c5_nota, av.c5_justificativa, av.c5_sugestoes),
        ]
        resultado.append(
            AvaliacaoDomain(
                id=str(av.id),
                redacao_id=str(av.redacao_id),
                notas=notas,
                avaliador=av.avaliador,
                modelo_llm=av.modelo_llm,
                criada_em=av.criada_em,
            )
        )
    return resultado


def atualizar_consolidacao(
    redacao: Redacao,
    pool: PoolCorrecao | None,
    llm: LLMClient | None = None,
    redacao_domain: RedacaoDomain | None = None,
    modelo_revisor: str | None = None,
    sistema_prompt: str | None = None,
) -> Consolidacao | None:
    if pool is None:
        logger.debug("atualizar_consolidacao: pool=None, pulando")
        return None
    avaliacoes = list(Avaliacao.objects.filter(redacao=redacao, pool=pool).all())
    if not avaliacoes:
        logger.debug("atualizar_consolidacao: nenhuma avaliacao para redacao=%s", redacao.id)
        return None
    avaliacoes_domain = avaliacoes_para_domain(avaliacoes)

    deve_chamar_revisor = (
        llm is not None
        and redacao_domain is not None
        and verificar_regra_revisor(pool, avaliacoes_domain)
    )
    usou_revisor = False
    parecer_revisor = ""

    if deve_chamar_revisor:
        consolidada = async_to_sync(avaliar_com_revisor)(
            llm,
            redacao_domain,
            avaliacoes_domain,
            modelo=modelo_revisor or "gpt-4o",
            limiar=pool.limiar_desvio,
            sistema_prompt=sistema_prompt,
        )
        notas = consolidada.notas
        usou_revisor = True
        regra_nome = dict(PoolCorrecao.REGRA_REVISOR_CHOICES).get(pool.regra_revisor, pool.regra_revisor)
        parecer_revisor = (
            f"Revisor acionado — regra '{regra_nome}' ativada. "
            f"As avaliações dos {len(avaliacoes_domain)} corretores "
            f"foram analisadas criticamente."
        )
    else:
        pesos = {av.avaliador: 1.0 for av in avaliacoes_domain}
        notas = consolidar_notas(avaliacoes_domain, pesos=pesos, metodo=pool.metodo)

    consolidacao, _ = Consolidacao.objects.get_or_create(
        redacao=redacao,
        pool=pool,
        defaults={"metodo": pool.metodo},
    )
    notas_by = {nota.competencia: nota for nota in notas}

    consolidacao.c1_nota = notas_by[CompetenciaNome.C1].nota
    consolidacao.c1_justificativa = notas_by[CompetenciaNome.C1].justificativa
    consolidacao.c2_nota = notas_by[CompetenciaNome.C2].nota
    consolidacao.c2_justificativa = notas_by[CompetenciaNome.C2].justificativa
    consolidacao.c3_nota = notas_by[CompetenciaNome.C3].nota
    consolidacao.c3_justificativa = notas_by[CompetenciaNome.C3].justificativa
    consolidacao.c4_nota = notas_by[CompetenciaNome.C4].nota
    consolidacao.c4_justificativa = notas_by[CompetenciaNome.C4].justificativa
    consolidacao.c5_nota = notas_by[CompetenciaNome.C5].nota
    consolidacao.c5_justificativa = notas_by[CompetenciaNome.C5].justificativa
    consolidacao.nota_total = sum(n.nota for n in notas)

    if pool.modo == "especialistas":
        expected = 5
        status = "final"
    else:
        expected = PoolCorretor.objects.filter(pool=pool).count()
        status = "final" if expected and len(avaliacoes) >= expected else "parcial"
    consolidacao.quantidade_esperada = expected
    consolidacao.quantidade_corretores = len(avaliacoes)
    consolidacao.metodo = pool.metodo
    consolidacao.status = status
    consolidacao.usou_revisor_llm = usou_revisor
    consolidacao.parecer_revisor = parecer_revisor
    if usou_revisor:
        consolidacao.revisado_em = timezone.now()
    consolidacao.save()
    logger.info(
        "Consolidacao %s — status=%s, esperado=%d, obtido=%d, nota=%d%s",
        consolidacao.id,
        consolidacao.status,
        consolidacao.quantidade_esperada,
        consolidacao.quantidade_corretores,
        consolidacao.nota_total,
        " (revisor)" if usou_revisor else "",
    )
    return consolidacao


def _montar_prompt_config(corretor) -> dict[str, str]:
    cfg: dict[str, str] = {}
    if corretor.prompt_template_ref:
        tpl = corretor.prompt_template_ref
        cfg["sistema_prompt"] = tpl.sistema_prompt
        cfg["formato_saida"] = tpl.formato_saida
    else:
        from apps.corretores.models import PromptTemplate
        tpl = PromptTemplate.objects.filter(tipo="base").order_by("criado_em").first()
        if tpl:
            cfg["formato_saida"] = tpl.formato_saida
    if corretor.prompt_personalizado:
        cfg["personalizado"] = corretor.prompt_personalizado

    skills = corretor.skills.all()
    if skills:
        blocos = [f"- {s.icone or ''} {s.nome}: {s.descricao}" for s in skills]
        cfg["skills_bloco"] = (
            "\n\nSKILLS ESPECIALIZADAS DESTE AVALIADOR:\n" + "\n".join(blocos)
        )

    ferramentas = corretor.ferramentas_ativas.all()
    if ferramentas:
        blocos = [f"- {f.nome} ({f.slug}): {f.descricao}" for f in ferramentas]
        cfg["ferramentas_bloco"] = (
            "\n\nFERRAMENTAS DISPONIVEIS:\n" + "\n".join(blocos)
        )

    return cfg


def _carregar_provider_padrao() -> PromptTemplateProvider | None:
    from apps.corretores.models import PromptTemplate

    tpl = PromptTemplate.objects.filter(tipo="base").order_by("criado_em").first()
    if not tpl:
        return None
    return PromptTemplateProvider(
        nome=tpl.nome,
        sistema_prompt=tpl.sistema_prompt,
        formato_saida=tpl.formato_saida,
    )


def _criar_cliente_para_corretor(corretor):
    if corretor.provedor:
        api_key = obter_api_key(corretor.provedor)
        base_url = corretor.provedor.base_url or None
        return criar_llm_client(
            corretor.provedor.nome,
            api_key=api_key,
            base_url=base_url,
            tipo=corretor.provedor.tipo,
        )
    return OpenAILLMClient()


def _criar_anotacoes_de_domain(
    avaliacao_db: Avaliacao, anotacoes: list[dict[str, str]], texto_completo: str
) -> None:
    for item in anotacoes:
        span = encontrar_trecho(texto_completo, item["trecho"])
        if span is None:
            continue
        inicio, fim, texto_exato = span
        Anotacao.objects.create(
            avaliacao=avaliacao_db,
            trecho_inicio=inicio,
            trecho_fim=fim,
            trecho_texto=texto_exato[:500],
            tipo_erro=item["tipo_erro"],
            comentario=item.get("comentario", ""),
        )


def _executar_subagentes_se_existirem(
    llm: LLMClient,
    redacao_domain: RedacaoDomain,
    config: dict[str, Any],
    conhecimento_dir: str,
) -> tuple[AvaliacaoDomain, list[dict[str, str]]] | None:
    subagentes_configs = config.pop("subagentes_configs", None)
    if not subagentes_configs:
        return None
    return async_to_sync(avaliar_com_subagentes)(
        llm,
        redacao_domain,
        config,
        subagentes_configs,
        conhecimento_dir=conhecimento_dir,
    )


def _montar_config_corretor(c: Any) -> dict[str, Any] | None:
    cl = c.corretor_llm
    if not cl:
        return None
    cliente = _criar_cliente_para_corretor(cl)
    prompt_config = _montar_prompt_config(cl)
    config: dict[str, Any] = {
        "avaliador": cl.nome,
        "modelo": cl.modelo,
        "llm": cliente,
        "prompt_config": prompt_config,
        "corretor_llm_id": str(cl.id),
        "temperature": float(cl.temperature),
        "seed": cl.seed,
        "top_p": float(cl.top_p),
        "output_json": bool(cl.output_json),
        "incluir_protocolo_enem": bool(cl.incluir_protocolo_enem),
        "incluir_base_conhecimento": bool(cl.incluir_base_conhecimento),
    }
    subagentes = cl.subagentes.all()
    n_sub = subagentes.count()
    logger.info(
        "Montando config para %s (%s)%s",
        cl.nome, cl.modelo,
        f" — {n_sub} subagente(s)" if n_sub else "",
    )
    if subagentes:
        sub_configs: list[dict[str, Any]] = []
        for sub in cl.subagentes.all():
            sub_cliente = _criar_cliente_para_corretor(sub)
            sub_prompt = _montar_prompt_config(sub)
            sub_configs.append({
                "avaliador": sub.nome,
                "modelo": sub.modelo,
                "llm": sub_cliente,
                "prompt_config": sub_prompt,
            })
        config["subagentes_configs"] = sub_configs
    return config


def _processar_avaliacao_pool(
    llm: LLMClient,
    redacao_domain: RedacaoDomain,
    redacao: Redacao,
    configs: list[dict[str, Any]],
    pool: PoolCorrecao | None,
    conhecimento_dir: str,
) -> None:
    simples: list[dict[str, Any]] = []
    for c in configs:
        if c.get("subagentes_configs"):
            nome = c.get("avaliador", "?")
            logger.info(
                "Bifurcando para fluxo multiagente — orquestrador: %s",
                nome,
            )
            av, anotacoes = async_to_sync(avaliar_com_subagentes)(
                llm, redacao_domain, c, c["subagentes_configs"],
                conhecimento_dir=conhecimento_dir,
            )
            av_db = _criar_avaliacao_de_domain(redacao, av, pool=pool)
            _criar_anotacoes_de_domain(av_db, anotacoes, redacao.texto)
        else:
            simples.append(c)

    if simples:
        avaliacao_pool, todas_anotacoes = async_to_sync(avaliar_com_pool)(
            llm, redacao_domain, simples, conhecimento_dir=conhecimento_dir,
        )
        for av, anotacoes in zip(avaliacao_pool, todas_anotacoes):
            av_db = _criar_avaliacao_de_domain(redacao, av, pool=pool)
            _criar_anotacoes_de_domain(av_db, anotacoes, redacao.texto)

    for c in configs:
        async_to_sync(c["llm"].aclose)()
        for sub in c.get("subagentes_configs", []):
            async_to_sync(sub["llm"].aclose)()


def _preparar_revisor_se_configurado(
    pool: PoolCorrecao | None,
) -> tuple[LLMClient | None, str | None, str | None]:
    if pool is None or pool.revisor_corretor is None:
        return None, None, None
    r = pool.revisor_corretor
    if not r.modelo or not r.provedor:
        return None, None, None
    return _criar_cliente_para_corretor(r), r.modelo, r.prompt_personalizado or None


def _mediana_por_competencia(
    avaliacoes: list[AvaliacaoDomain],
) -> tuple[list[NotaCompetencia], dict[CompetenciaNome, float]]:
    import statistics
    competencias = list(CompetenciaNome)
    notas_consolidadas = []
    desvios: dict[CompetenciaNome, float] = {}
    for comp in competencias:
        vals_nota = sorted([av.notas_dict[comp].nota for av in avaliacoes])
        med = statistics.median(vals_nota)
        nota_ref = avaliacoes[0].notas_dict[comp]
        notas_consolidadas.append(NotaCompetencia(
            competencia=comp,
            nota=int(med),
            justificativa=nota_ref.justificativa,
            sugestoes=nota_ref.sugestoes,
        ))
        if len(vals_nota) >= 2:
            desvios[comp] = statistics.stdev(vals_nota)
    return notas_consolidadas, desvios


def verificar_regra_revisor(
    pool: PoolCorrecao,
    avaliacoes_domain: list[AvaliacaoDomain],
) -> bool:
    if len(avaliacoes_domain) < 2:
        return False
    regra = pool.regra_revisor
    params = pool.parametros_revisor or {}
    if regra == "desvio_padrao":
        _, desvios = _mediana_por_competencia(avaliacoes_domain)
        max_desvio = max(desvios.values()) if desvios else 0.0
        return max_desvio > float(pool.limiar_desvio)
    elif regra == "diferenca_enem":
        return _verificar_regra_diferenca_enem(
            avaliacoes_domain,
            limiar_total=float(params.get("limiar_total", 100)),
            limiar_competencia=float(params.get("limiar_competencia", 80)),
        )
    elif regra == "personalizada":
        return _verificar_regra_personalizada(avaliacoes_domain, params)
    return False


def _verificar_regra_diferenca_enem(
    avaliacoes: list[AvaliacaoDomain],
    limiar_total: float = 100,
    limiar_competencia: float = 80,
) -> bool:
    if len(avaliacoes) < 2:
        return False
    av1, av2 = avaliacoes[0], avaliacoes[1]
    competencias = list(CompetenciaNome)
    notas1 = av1.notas_dict
    notas2 = av2.notas_dict
    diff_total = abs(
        sum(notas1[c].nota for c in competencias)
        - sum(notas2[c].nota for c in competencias)
    )
    if diff_total > limiar_total:
        return True
    for c in competencias:
        if abs(notas1[c].nota - notas2[c].nota) > limiar_competencia:
            return True
    return False


def _verificar_regra_personalizada(
    avaliacoes: list[AvaliacaoDomain],
    params: dict,
) -> bool:
    return False


def executar_avaliacao_llm(redacao_id: str, pool_id: str | None = None, modo: str = "um", corretor_ids: list[str] | None = None) -> None:
    redacao = Redacao.objects.get(pk=redacao_id)
    logger.info(
        "Iniciando avaliação — redacao %s, modo: %s%s",
        redacao_id, modo,
        f", pool: {pool_id}" if pool_id else "",
    )
    llm = OpenAILLMClient()
    if redacao.tema_ref_id and redacao.tema_ref:
        tema_texto = f"Tema: {redacao.tema_ref.titulo}"
        if redacao.tema_ref.texto:
            tema_texto += f"\n\nDescrição do tema:\n{redacao.tema_ref.texto}"
    else:
        tema_texto = ""
    texto = redacao.texto
    if redacao.tema:
        texto = f"Título: {redacao.tema}\n\n{texto}"
    logger.debug("Redacao %s: %d caracteres", redacao_id, len(redacao.texto))
    redacao_domain = RedacaoDomain(id=str(redacao.id), texto=texto, tema=tema_texto)

    if corretor_ids:
        logger.info("Redacao %s: caminho corretor_ids — %d corretores", redacao_id, len(corretor_ids))
        pool = None
        corretores = PoolCorretor.objects.filter(
            id__in=corretor_ids, tipo="llm"
        ).select_related(
            "corretor_llm", "corretor_llm__provedor",
            "corretor_llm__prompt_template_ref",
        ).prefetch_related(
            "corretor_llm__skills", "corretor_llm__ferramentas_ativas",
            "corretor_llm__subagentes",
        )
        configs: list[dict[str, Any]] = []
        pool_ids: set[str] = set()
        for c in corretores:
            config = _montar_config_corretor(c)
            if config is None:
                continue
            if c.pool_id:
                pool_ids.add(c.pool_id)
            configs.append(config)
        if not configs:
            msg = "Nenhum corretor IA selecionado esta disponivel"
            logger.error(msg)
            raise RuntimeError(msg)

        if pool_ids:
            pool = PoolCorrecao.objects.filter(id=next(iter(pool_ids))).first()

        if pool and pool.modo == "especialistas":
            if pool.provedor:
                llm = criar_llm_client(
                    pool.provedor.nome,
                    api_key=obter_api_key(pool.provedor),
                    base_url=pool.provedor.base_url or None,
                    tipo=pool.provedor.tipo,
                )
            modelo = pool.modelo_llm or None
            logger.info(
                "Redacao %s: modo especialistas (via corretor_ids), modelo=%s",
                redacao_id, modelo or "default",
            )
            result = _avaliar_modo_especialistas(
                llm, redacao, redacao_domain, modelo=modelo, pool=pool,
            )
            async_to_sync(llm.aclose)()
            return result

        logger.info(
            "Redacao %s: modo pool — %d corretores", redacao_id, len(configs),
        )
        _processar_avaliacao_pool(
            llm, redacao_domain, redacao, configs, pool,
            conhecimento_dir="base_de_conhecimento",
        )
        if pool:
            logger.info("Redacao %s: pool concluído", redacao_id)
        async_to_sync(llm.aclose)()
        return

    if pool_id:
        pool = PoolCorrecao.objects.get(pk=pool_id)

        if pool.modo == "especialistas":
            if pool.provedor:
                llm = criar_llm_client(
                    pool.provedor.nome,
                    api_key=obter_api_key(pool.provedor),
                    base_url=pool.provedor.base_url or None,
                    tipo=pool.provedor.tipo,
                )
            modelo = pool.modelo_llm or None
            logger.info(
                "Redacao %s: modo especialistas (via pool_id), modelo=%s",
                redacao_id, modelo or "default",
            )
            result = _avaliar_modo_especialistas(
                llm, redacao, redacao_domain, modelo=modelo, pool=pool,
            )
            async_to_sync(llm.aclose)()
            return result

        corretores = PoolCorretor.objects.filter(pool=pool, tipo="llm").select_related(
            "corretor_llm", "corretor_llm__provedor",
            "corretor_llm__prompt_template_ref",
        ).prefetch_related(
            "corretor_llm__skills", "corretor_llm__ferramentas_ativas",
            "corretor_llm__subagentes",
        )
        configs = []
        for c in corretores:
            config = _montar_config_corretor(c)
            if config is None:
                continue
            configs.append(config)
        if not configs:
            msg = f"Banca {pool.nome} nao possui corretores ativos"
            logger.error(msg)
            raise RuntimeError(msg)

        logger.info(
            "Redacao %s: modo pool (via pool_id=%s) — %d corretores",
            redacao_id, pool.nome, len(configs),
        )
        _processar_avaliacao_pool(
            llm, redacao_domain, redacao, configs, pool,
            conhecimento_dir="base_de_conhecimento",
        )
        async_to_sync(llm.aclose)()
        return

    if modo == "especialistas":
        from essay_essay.config import config as app_config
        from essay_essay.evaluators.extrator import extrair_estrutura

        logger.info(
            "Redacao %s: modo especialistas (inline, sem pool)",
            redacao_id,
        )
        default_model = app_config.llm_model or "gpt-4o"

        textos_motivadores = None
        if redacao.tema_ref and redacao.tema_ref.texto:
            textos_motivadores = redacao.tema_ref.texto
        tema_para_ferramenta = redacao_domain.tema or ""
        resultados_ferramentas = executar_ferramentas(
            texto=redacao_domain.texto,
            tema=tema_para_ferramenta,
            textos_motivadores=textos_motivadores,
            llm=llm,
            modelo=default_model,
        )
        logger.info(
            "Ferramentas (inline): palavras=%d(%s), tema=%.3f(fuga=%s,tang=%s), paragrafos=%d",
            resultados_ferramentas["palavras"]["total"],
            "ok" if resultados_ferramentas["palavras"]["valido"] else "fora",
            resultados_ferramentas["tema"]["score"],
            resultados_ferramentas["tema"]["fuga_total"],
            resultados_ferramentas["tema"]["tangencia"],
            resultados_ferramentas["estrutura"]["paragrafos"],
        )
        if resultados_ferramentas["bloqueante"]:
            logger.info(
                "Redação %s: ferramentas detectaram bloqueio (inline: %s) — "
                "prosseguindo com avaliação completa para feedback pedagógico",
                redacao_id,
                resultados_ferramentas["blocking_msg"][:80],
            )

        logger.info("Modo especialistas — extraindo estrutura da redação...")
        contexto = async_to_sync(extrair_estrutura)(
            llm, redacao_domain, modelo=default_model,
        )
        logger.info(
            "Estrutura extraída: %d parágrafos, tese: %s",
            contexto.get("qtd_paragrafos", 0),
            str(contexto.get("introducao", {}).get("tese", "?"))[:60],
        )
        rubricas_db = _carregar_rubricas_do_banco()
        logger.info("Rubricas carregadas do banco: %d/%d", len(rubricas_db), 5)
        bloco_ferramentas = formatar_resultados_ferramentas(resultados_ferramentas)
        av, anotacoes = async_to_sync(avaliar_com_especialistas)(
            llm, redacao_domain,
            modelo=default_model,
            contexto_extracao=contexto,
            rubricas=rubricas_db if rubricas_db else None,
            resultados_ferramentas=bloco_ferramentas,
        )
        _validar_notas_pos_llm(av, resultados_ferramentas)
        debug_info = {"ferramentas": resultados_ferramentas}
        av_db = _criar_avaliacao_de_domain(redacao, av, debug_info=debug_info)
        _criar_anotacoes_de_domain(av_db, anotacoes, redacao.texto)
        logger.info("Especialistas concluídos — nota %d/1000", av.nota_total)
        notificar_aluno_correcao_concluida(redacao, av.nota_total)
        async_to_sync(llm.aclose)()
        return

    logger.info("Redacao %s: modo um (avaliacao única)", redacao_id)
    from essay_essay.config import config as app_config

    default_model_um = app_config.llm_model or "gpt-4o"

    textos_motivadores = None
    if redacao.tema_ref and redacao.tema_ref.texto:
        textos_motivadores = redacao.tema_ref.texto

    resultados_ferramentas = executar_ferramentas(
        texto=redacao_domain.texto,
        tema=redacao_domain.tema or "",
        textos_motivadores=textos_motivadores,
        llm=llm,
        modelo=default_model_um,
    )
    logger.info(
        "Ferramentas (modo um): palavras=%d(%s), tema=%.3f(fuga=%s,tang=%s)",
        resultados_ferramentas["palavras"]["total"],
        "ok" if resultados_ferramentas["palavras"]["valido"] else "fora",
        resultados_ferramentas["tema"]["score"],
        resultados_ferramentas["tema"]["fuga_total"],
        resultados_ferramentas["tema"]["tangencia"],
    )
    if resultados_ferramentas["bloqueante"]:
        logger.info(
            "Redação %s: ferramentas detectaram bloqueio (%s) — "
            "prosseguindo com avaliação completa para feedback pedagógico",
            redacao_id,
            resultados_ferramentas["blocking_msg"][:80],
        )
    bloco_ferramentas = formatar_resultados_ferramentas(resultados_ferramentas)

    provider = _carregar_provider_padrao()
    av, anotacoes, _sistema, _usuario = async_to_sync(avaliar_com_um)(
        llm,
        redacao_domain,
        conhecimento_dir="base_de_conhecimento",
        provider=provider,
        resultados_ferramentas=bloco_ferramentas,
    )
    _validar_notas_pos_llm(av, resultados_ferramentas)
    debug_info = {"ferramentas": resultados_ferramentas}
    av_db = _criar_avaliacao_de_domain(redacao, av, debug_info=debug_info)
    _criar_anotacoes_de_domain(av_db, anotacoes, redacao.texto)
    logger.info("Modo um concluído — nota %d/1000", av.nota_total)
    notificar_aluno_correcao_concluida(redacao, av.nota_total)
    async_to_sync(llm.aclose)()
