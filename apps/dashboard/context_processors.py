from __future__ import annotations

from django.db.models import Q

from apps.accounts.models import CustomUser, Turma, UserType
from apps.avaliacoes.models import Avaliacao, Notificacao
from apps.corretores.models import PoolCorretor
from apps.redacoes.models import Redacao


def nav_counts(request):
    usuario = getattr(request, "user", None)
    if not usuario or not usuario.is_authenticated:
        return {}

    counts = {}
    ut = usuario.user_type

    notificacoes_nao_lidas = Notificacao.objects.filter(
        usuario=usuario, lida=False
    ).count()
    if notificacoes_nao_lidas:
        counts["notificacoes_nao_lidas"] = notificacoes_nao_lidas

    if ut in (UserType.CORRETOR, UserType.PROFESSOR, UserType.ADMIN):
        pools_ids = PoolCorretor.objects.filter(
            usuario=usuario, pool__ativo=True
        ).values_list("pool_id", flat=True)

        if not pools_ids:
            counts["sem_pool"] = True
        else:
            pendentes = (
                Redacao.objects.filter(
                    Q(avaliacoes__pool_id__in=pools_ids)
                    | Q(pool_id__in=pools_ids, status=Redacao.Status.PENDENTE)
                )
                .exclude(
                    avaliacoes__avaliador_usuario=usuario,
                )
                .exclude(usuario=usuario)
                .exclude(status__in=[Redacao.Status.CORRIGIDA, Redacao.Status.ERRO])
                .exclude(excluida_em__isnull=False)
                .distinct()
                .count()
            )
            counts["pendentes_count"] = pendentes

            rascunhos = Avaliacao.objects.filter(
                avaliador_usuario=usuario,
                rascunho=True,
                pool_id__in=pools_ids,
                redacao__status__in=[Redacao.Status.PENDENTE, Redacao.Status.EM_AVALIACAO],
            ).count()
            if rascunhos:
                counts["rascunhos_count"] = rascunhos

    if ut == UserType.ALUNO:
        corrigidas = (
            Avaliacao.objects.filter(
                redacao__usuario=usuario,
                redacao__excluida_em__isnull=True,
                rascunho=False,
            )
            .values("redacao")
            .distinct()
            .count()
        )
        counts["corrigidas_count"] = corrigidas

        em_avaliacao = (
            Redacao.objects.filter(
                usuario=usuario,
                excluida_em__isnull=True,
                status=Redacao.Status.EM_AVALIACAO,
            )
            .exclude(avaliacoes__isnull=False)
            .count()
        )
        counts["em_avaliacao_count"] = em_avaliacao

    if ut in (UserType.ADMIN, UserType.PROFESSOR):
        if ut == UserType.PROFESSOR:
            turmas_ids = list(Turma.objects.filter(professores=usuario).values_list("id", flat=True))
            pre_correcoes = Avaliacao.objects.filter(
                rascunho=True,
                liberada_em__isnull=True,
                redacao__atividade__turmas__id__in=turmas_ids,
            ).count() if turmas_ids else 0
        else:
            pre_correcoes = Avaliacao.objects.filter(
                rascunho=True,
                liberada_em__isnull=True,
                redacao__atividade__isnull=False,
            ).count()
        if pre_correcoes:
            counts["pre_correcoes_count"] = pre_correcoes

    if ut == UserType.ADMIN:
        usuarios_sem_banca = (
            CustomUser.objects.filter(
                user_type__in=[
                    UserType.CORRETOR,
                    UserType.PROFESSOR,
                    UserType.ADMIN,
                ],
            )
            .exclude(
                vinculos_pool__pool__ativo=True,
            )
            .count()
        )
        counts["usuarios_sem_banca"] = usuarios_sem_banca

    return counts
