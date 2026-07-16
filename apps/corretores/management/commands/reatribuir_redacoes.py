from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.avaliacoes.banca_selector import selecionar_banca
from apps.avaliacoes.notifications import notificar_corretor_humano
from apps.avaliacoes.tasks import disparar_avaliacao_llm
from apps.corretores.models import PoolCorretor
from apps.redacoes.models import Redacao

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Reatribui redações pendentes sem banca para bancas ativas "
        "com capacidade disponível"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limite",
            type=int,
            default=50,
            help="Máximo de redações a processar (default: 50)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas lista as redações que seriam reatribuídas",
        )

    def handle(self, **options):
        limite = options["limite"]
        dry_run = options["dry_run"]

        redacoes = Redacao.objects.filter(
            pool__isnull=True,
            status=Redacao.Status.PENDENTE,
        ).order_by("criada_em")[:limite]

        if not redacoes:
            self.stdout.write("Nenhuma redação pendente sem banca.")
            return

        self.stdout.write(
            f"Encontradas {len(redacoes)} redação(ões) pendente(s) sem banca."
        )
        reatribuidas = 0
        sem_vaga = 0

        for redacao in redacoes:
            banca = selecionar_banca()
            if banca is None:
                sem_vaga += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  [DRY-RUN] Redação {redacao.id} → banca {banca.nome}"
                )
                reatribuidas += 1
                continue

            redacao.pool = banca
            redacao.status = Redacao.Status.EM_AVALIACAO
            redacao.save(update_fields=["pool", "status"])

            has_llm = PoolCorretor.objects.filter(pool=banca, tipo="llm").exists()
            has_humano = PoolCorretor.objects.filter(pool=banca, tipo="humano").exists()

            if has_llm:
                disparar_avaliacao_llm(
                    str(redacao.id), str(banca.id), banca.modo,
                )

            if has_humano:
                for pc in PoolCorretor.objects.filter(
                    pool=banca, tipo="humano"
                ).select_related("usuario"):
                    notificar_corretor_humano(
                        pc.usuario,
                        get_user_model().objects.none(),
                        redacao,
                    )

            if not has_llm:
                redacao.status = Redacao.Status.PENDENTE
                redacao.save(update_fields=["status"])

            self.stdout.write(
                f"  Redação {redacao.id} reatribuída → banca {banca.nome}"
            )
            reatribuidas += 1

        resumo = f"Reatribuídas: {reatribuidas}"
        if sem_vaga:
            resumo += f" | Sem vaga: {sem_vaga}"
        self.stdout.write(self.style.SUCCESS(resumo))
