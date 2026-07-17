from __future__ import annotations

import logging

from django.conf import settings
from django_q.tasks import async_task

from apps.accounts.models import CustomUser
from apps.redacoes.models import Redacao

from .models import Notificacao

logger = logging.getLogger(__name__)


def criar_notificacao(
    usuario: CustomUser,
    tipo: str,
    mensagem: str,
    redacao: Redacao | None = None,
) -> Notificacao:
    return Notificacao.objects.create(
        usuario=usuario,
        tipo=tipo,
        mensagem=mensagem,
        redacao=redacao,
    )


def enviar_email_notificacao(
    usuario: CustomUser,
    assunto: str,
    mensagem: str,
) -> None:
    if not usuario.email:
        return
    async_task(
        "django.core.mail.send_mail",
        subject=f"[Pluma] {assunto}",
        message=mensagem,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[usuario.email],
        fail_silently=True,
    )
    logger.debug("Email enfileirado para %s: %s", usuario.email, assunto)


def _tema_exibicao(redacao: Redacao) -> str:
    return redacao.tema or (redacao.tema_ref.titulo if redacao.tema_ref else "redação sem título")


def notificar_corretor_humano(
    usuario: CustomUser,
    aluno: CustomUser,
    redacao: Redacao,
) -> None:
    mensagem = (
        f"O aluno {aluno.nome_exibicao} solicitou que você corrija "
        f"a redação sobre '{_tema_exibicao(redacao)}'."
    )
    criar_notificacao(
        usuario=usuario,
        tipo=str(Notificacao.Tipo.CORRECAO_SOLICITADA),
        mensagem=mensagem,
        redacao=redacao,
    )
    enviar_email_notificacao(
        usuario=usuario,
        assunto="Nova redação solicitada para correção",
        mensagem=mensagem + "\n\nAcesse o sistema para aceitar ou recusar.",
    )


def notificar_corretor_humano_direto(
    usuario: CustomUser,
    aluno: CustomUser,
    redacao: Redacao,
) -> None:
    mensagem = (
        f"O aluno {aluno.nome_exibicao} solicitou que você corrija "
        f"a redação sobre '{_tema_exibicao(redacao)}'."
    )
    enviar_email_notificacao(
        usuario=usuario,
        assunto="Nova redação para correção",
        mensagem=mensagem + "\n\nAcesse o sistema para corrigir.",
    )


def notificar_aluno_correcao_concluida(
    redacao: Redacao,
    nota: int,
) -> None:
    if not redacao.usuario:
        return
    criar_notificacao(
        usuario=redacao.usuario,
        tipo=str(Notificacao.Tipo.CORRECAO_CONCLUIDA),
        mensagem=(
            f"Correção concluída — sua redação "
            f"recebeu nota {nota}/1000."
        ),
        redacao=redacao,
    )
    enviar_email_notificacao(
        usuario=redacao.usuario,
        assunto="Redação corrigida!",
        mensagem=(
            f"Sua redação foi corrigida "
            f"e recebeu nota {nota}/1000.\n\n"
            f"Acesse o sistema para ver os detalhes."
        ),
    )
