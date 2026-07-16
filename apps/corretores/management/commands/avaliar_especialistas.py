from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.avaliacoes.tasks import disparar_avaliacao_llm
from apps.redacoes.models import Redacao


class Command(BaseCommand):
    help = "Dispara avaliação com modo especialistas (C1-C5) ou via pool configurado"

    def add_arguments(self, parser):
        parser.add_argument("redacao_id", type=str, help="UUID da redação")
        parser.add_argument(
            "--pool", "-p", type=str, default=None,
            help="ID da banca (PoolCorrecao) a ser usada",
        )
        parser.add_argument(
            "--modo", "-m", type=str, default="especialistas",
            choices=["especialistas", "um", "pool"],
            help="Modo de avaliação (default: especialistas)",
        )

    def handle(self, **options):
        redacao_id = options["redacao_id"]
        pool_id = options["pool"]
        modo = options["modo"]

        try:
            redacao = Redacao.objects.get(pk=redacao_id)
        except Redacao.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Redação {redacao_id} não encontrada."))
            return

        self.stdout.write(f"Redação: {redacao.tema or '(sem título)'} - {len(redacao.texto)} chars")
        self.stdout.write(f"Modo: {modo} | Pool: {pool_id or 'nenhuma'}")

        if pool_id:
            from apps.corretores.models import PoolCorrecao

            try:
                pool = PoolCorrecao.objects.get(pk=pool_id)
                self.stdout.write(f"  Banca: {pool.nome} | modo={pool.modo} | método={pool.metodo}")
                self.stdout.write(
                    f"  Membros LLM: {pool.corretores.filter(tipo='llm').count()}"
                )
            except PoolCorrecao.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Pool {pool_id} não encontrada."))
                return

        self.stdout.write(f"\nDisparando avaliação {redacao_id}...")
        disparar_avaliacao_llm(redacao_id, pool_id=pool_id, modo=modo)

        self.stdout.write(self.style.SUCCESS(
            "Job enfileirado. Aguarde alguns segundos e verifique "
            "a avaliação no admin ou dashboard."
        ))
