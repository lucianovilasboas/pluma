from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.corretores.models import CorretorLLM
from apps.corretores.services import recalcular_rating_corretor


class Command(BaseCommand):
    help = "Recalcula rating de todos os corretores com base nos feedbacks"

    def handle(self, *args, **options):
        total = CorretorLLM.objects.count()
        for cl in CorretorLLM.objects.iterator():
            recalcular_rating_corretor(cl.id)
        self.stdout.write(f"Rating recalculado para {total} corretor(es).")
