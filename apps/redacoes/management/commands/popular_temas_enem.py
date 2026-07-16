from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.redacoes.models import TemaRedacao


class Command(BaseCommand):
    help = "Popula o banco com os temas de redação do ENEM (1998-2025)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--arquivo",
            default="planos/enem_temas.json",
            help="Caminho do arquivo JSON com os temas (padrão: planos/enem_temas.json)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas exibe o que seria inserido, sem alterar o banco",
        )

    def handle(self, **_kwargs):
        arquivo = _kwargs.get("arquivo", "planos/enem_temas.json")
        dry_run = _kwargs.get("dry_run", False)

        caminho = Path(arquivo)
        if not caminho.exists():
            self.stdout.write(
                self.style.ERROR(f"Arquivo não encontrado: {caminho.resolve()}")
            )
            return

        dados = json.loads(caminho.read_text(encoding="utf-8"))

        criados = 0
        existentes = 0
        atualizados = 0

        for item in dados:
            titulo = item["titulo"].strip()
            texto = item.get("texto", titulo)

            if dry_run:
                ja_existe = TemaRedacao.objects.filter(titulo=titulo).exists()
                if ja_existe:
                    tema_existente = TemaRedacao.objects.get(titulo=titulo)
                    if tema_existente.texto != texto:
                        atualizados += 1
                        self.stdout.write(
                            self.style.WARNING(f"  ~ {item['ano']} [{item['edicao']}]: {titulo} (texto atualizaria)")
                        )
                    else:
                        existentes += 1
                        self.stdout.write(f"  = {item['ano']} [{item['edicao']}]: {titulo} (já existe)")
                else:
                    criados += 1
                    self.stdout.write(
                        self.style.WARNING(f"  ? {item['ano']} [{item['edicao']}]: {titulo}")
                    )
            else:
                tema, created = TemaRedacao.objects.get_or_create(
                    titulo=titulo,
                    defaults={"texto": texto, "ativo": True},
                )
                if created:
                    criados += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"  + {item['ano']} [{item['edicao']}]: {titulo}")
                    )
                elif tema.texto != texto:
                    tema.texto = texto
                    tema.save(update_fields=["texto"])
                    atualizados += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"  = {item['ano']} [{item['edicao']}]: {titulo} (texto atualizado)")
                    )
                else:
                    existentes += 1
                    self.stdout.write(f"  = {item['ano']} [{item['edicao']}]: {titulo} (já existe)")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDRY RUN — seriam criados {criados}, "
                    f"atualizados {atualizados}, já existentes {existentes}. "
                    "Nada foi alterado."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nConcluído: {criados} criados, {atualizados} atualizados, "
                    f"{existentes} já existentes."
                )
            )
