from __future__ import annotations

from django.db import migrations


def seed_data(apps, schema_editor):
    Ferramenta = apps.get_model("corretores", "Ferramenta")

    Ferramenta.objects.get_or_create(
        slug="busca-repertorio",
        defaults={
            "nome": "Busca de Repertório",
            "descricao": "Habilita busca de repertórios socioculturais válidos (citações, autores, dados históricos) para enriquecer a argumentação.",
            "ativa_por_padrao": True,
        },
    )
    Ferramenta.objects.get_or_create(
        slug="verificador-gramatical",
        defaults={
            "nome": "Verificador Gramatical",
            "descricao": "Análise de desvios gramaticais, ortográficos e de concordância no texto do aluno.",
            "ativa_por_padrao": False,
        },
    )
    Ferramenta.objects.get_or_create(
        slug="calculadora-notas",
        defaults={
            "nome": "Calculadora de Notas",
            "descricao": "Cálculo automático da nota final com ponderação das competências da matriz ENEM.",
            "ativa_por_padrao": True,
        },
    )


def reverse_seed(apps, schema_editor):
    Ferramenta = apps.get_model("corretores", "Ferramenta")
    Ferramenta.objects.filter(
        slug__in=["busca-repertorio", "verificador-gramatical", "calculadora-notas"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("corretores", "0008_seed_templates_ferramentas"),
    ]

    operations = [
        migrations.RunPython(seed_data, reverse_seed),
    ]
