from __future__ import annotations

import logging
import os
import threading

from django.db import close_old_connections
from django_q.tasks import async_task

from apps.avaliacoes.notifications import notificar_aluno_correcao_concluida
from apps.redacoes.models import Redacao

from .services import executar_avaliacao_llm


logger = logging.getLogger(__name__)


def _executar_avaliacao_job(redacao_id: str, pool_id: str | None = None, modo: str = "um", corretor_ids: list[str] | None = None) -> None:
    logger.info(
        "Job iniciado — redacao=%s, pool=%s, modo=%s",
        redacao_id, pool_id, modo,
    )
    close_old_connections()
    try:
        executar_avaliacao_llm(redacao_id, pool_id, modo, corretor_ids)
        if pool_id:
            agendar_consolidacao(redacao_id, pool_id)
    except Exception:
        logger.exception("Falha na avaliação da redação %s", redacao_id)
        Redacao.objects.filter(id=redacao_id).update(status=Redacao.Status.ERRO)
        raise
    finally:
        close_old_connections()


def agendar_avaliacao_llm(redacao_id: str, pool_id: str | None = None, modo: str = "um", corretor_ids: list[str] | None = None) -> None:
    async_task("apps.avaliacoes.tasks._executar_avaliacao_job", redacao_id, pool_id, modo, corretor_ids)


def executar_avaliacao_imediata(redacao_id: str, pool_id: str | None = None, modo: str = "um", corretor_ids: list[str] | None = None) -> None:
    if os.getenv("PYTEST_CURRENT_TEST"):
        _executar_avaliacao_job(redacao_id, pool_id, modo, corretor_ids)
        return
    t = threading.Thread(
        target=_executar_avaliacao_job,
        args=(redacao_id, pool_id, modo, corretor_ids),
        daemon=True,
    )
    t.start()


def disparar_avaliacao_llm(redacao_id: str, pool_id: str | None = None, modo: str = "um", corretor_ids: list[str] | None = None) -> None:
    logger.info(
        "Dispatcher: redacao=%s, pool=%s, modo=%s",
        redacao_id, pool_id, modo,
    )
    if os.getenv("PYTEST_CURRENT_TEST"):
        logger.debug("Dispatcher: modo teste detectado, ignorando")
        return
    usar_q2 = os.getenv("AVALIACAO_USE_Q2", "false").lower() in {"1", "true", "yes"}
    if usar_q2:
        logger.info("Dispatcher: rota Q2 (AVALIACAO_USE_Q2=true)")
        agendar_avaliacao_llm(redacao_id, pool_id, modo, corretor_ids)
        return
    logger.info("Dispatcher: rota thread (AVALIACAO_USE_Q2=false)")
    executar_avaliacao_imediata(redacao_id, pool_id, modo, corretor_ids)


def consolidar_avaliacao_job(redacao_id: str, pool_id: str) -> None:
    logger.info("Consolidacao iniciada — redacao=%s, pool=%s", redacao_id, pool_id)
    try:
        redacao = Redacao.objects.select_related("tema_ref").get(pk=redacao_id)
        from apps.corretores.models import PoolCorrecao

        pool = PoolCorrecao.objects.get(pk=pool_id)

        from .services import _preparar_revisor_se_configurado, atualizar_consolidacao

        revisor_llm, revisor_modelo, revisor_prompt = _preparar_revisor_se_configurado(pool)

        redacao_domain = None
        if revisor_llm:
            texto = redacao.texto
            if redacao.tema:
                texto = f"Título: {redacao.tema}\n\n{texto}"
            tema_texto = f"Tema: {redacao.tema_ref.titulo}" if redacao.tema_ref else ""
            if redacao.tema_ref and redacao.tema_ref.texto:
                tema_texto += f"\n\nDescrição do tema:\n{redacao.tema_ref.texto}"
            from essay_essay.domain.models import Redacao as RedacaoDomain

            redacao_domain = RedacaoDomain(id=str(redacao.id), texto=texto, tema=tema_texto)

        cons = atualizar_consolidacao(
            redacao, pool, revisor_llm, redacao_domain, revisor_modelo, revisor_prompt,
        )

        if cons and cons.status == "final":
            Redacao.objects.filter(id=redacao_id).update(status=Redacao.Status.CORRIGIDA)
            notificar_aluno_correcao_concluida(redacao, cons.nota_total)
            logger.info(
                "Consolidacao final — redacao=%s, nota=%d%s",
                redacao_id, cons.nota_total,
                " (revisor)" if cons.usou_revisor_llm else "",
            )
        elif cons:
            logger.info(
                "Consolidacao parcial — redacao=%s, corretores=%d/%d",
                redacao_id, cons.quantidade_corretores, cons.quantidade_esperada,
            )
    except Exception:
        logger.exception("Falha na consolidacao — redacao=%s", redacao_id)


def _executar_pre_correcao_copiloto_job(redacao_id: str, corretor_llm_id: str) -> None:
    close_old_connections()
    try:
        from apps.corretores.models import CorretorLLM

        redacao = Redacao.objects.get(pk=redacao_id)
        corretor_llm = CorretorLLM.objects.get(pk=corretor_llm_id)
        from apps.dashboard.views import _executar_pre_correcao_copiloto

        _executar_pre_correcao_copiloto(redacao, corretor_llm)
        logger.info(
            "Pré-correção copiloto concluída — redacao=%s, corretor=%s",
            redacao_id, corretor_llm.nome,
        )
    except Exception:
        logger.exception("Falha na pré-correção copiloto — redacao=%s", redacao_id)
        Redacao.objects.filter(id=redacao_id).update(status=Redacao.Status.ERRO)
    finally:
        close_old_connections()


def disparar_pre_correcao_copiloto(redacao_id: str, corretor_llm_id: str) -> None:
    if os.getenv("PYTEST_CURRENT_TEST"):
        logger.debug("Dispatcher copiloto: modo teste, ignorando")
        return
    usar_q2 = os.getenv("AVALIACAO_USE_Q2", "false").lower() in {"1", "true", "yes"}
    if usar_q2:
        logger.info("Dispatcher copiloto: rota Q2")
        async_task("apps.avaliacoes.tasks._executar_pre_correcao_copiloto_job", redacao_id, corretor_llm_id)
        return
    logger.info("Dispatcher copiloto: rota thread")
    t = threading.Thread(
        target=_executar_pre_correcao_copiloto_job,
        args=(redacao_id, corretor_llm_id),
        daemon=True,
    )
    t.start()


def agendar_consolidacao(redacao_id: str, pool_id: str) -> None:
    usar_q2 = os.getenv("AVALIACAO_USE_Q2", "false").lower() in {"1", "true", "yes"}
    if usar_q2:
        async_task("apps.avaliacoes.tasks.consolidar_avaliacao_job", redacao_id, pool_id)
    else:
        consolidar_avaliacao_job(redacao_id, pool_id)
