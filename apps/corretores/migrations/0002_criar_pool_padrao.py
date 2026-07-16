from __future__ import annotations

import os

from django.db import migrations


def criar_pool_padrao(apps, schema_editor):
    CorretorLLM = apps.get_model("corretores", "CorretorLLM")
    PoolCorrecao = apps.get_model("corretores", "PoolCorrecao")
    PoolCorretor = apps.get_model("corretores", "PoolCorretor")

    if CorretorLLM.objects.exists():
        return

    modelo = os.getenv("LLM_MODEL", "gpt-4o")
    llm = CorretorLLM.objects.create(
        nome="GPT-4o Padrão",
        provedor="openai",
        modelo=modelo,
    )

    pool = PoolCorrecao.objects.create(
        nome="Padrão",
        metodo="mediana",
        ativo=True,
    )

    PoolCorretor.objects.create(
        pool=pool,
        tipo="llm",
        corretor_llm=llm,
        peso=1.0,
        ordem=0,
    )


def remover_pool_padrao(apps, schema_editor):
    PoolCorrecao = apps.get_model("corretores", "PoolCorrecao")
    PoolCorrecao.objects.filter(nome="Padrão").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("corretores", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(criar_pool_padrao, remover_pool_padrao),
    ]
