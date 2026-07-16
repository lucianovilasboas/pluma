from __future__ import annotations

import logging

from apps.corretores.models import PoolCorrecao
from apps.redacoes.models import Redacao

logger = logging.getLogger(__name__)


def selecionar_banca() -> PoolCorrecao | None:
    bancas = PoolCorrecao.objects.filter(ativo=True).order_by("ordem", "criado_em")
    for banca in bancas:
        em_curso = Redacao.objects.filter(
            pool=banca,
            status__in=[Redacao.Status.PENDENTE, Redacao.Status.EM_AVALIACAO],
        ).count()
        if em_curso < banca.limite_concorrencia:
            logger.info(
                "Banca %s selecionada (%d/%d em curso)",
                banca.nome, em_curso, banca.limite_concorrencia,
            )
            return banca
        logger.info(
            "Banca %s no limite (%d/%d) — pulando",
            banca.nome, em_curso, banca.limite_concorrencia,
        )
    logger.warning("Nenhuma banca ativa com capacidade disponivel")
    return None
