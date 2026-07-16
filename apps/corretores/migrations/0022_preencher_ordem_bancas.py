from django.db import migrations


ORDENS = {
    "Banca - Testes 1": 1,
    "Banca ENEM Oficial": 2,
    "Banca de Especialistas": 3,
    "Banca Multiagente": 4,
    "Banca ENEM (Mista)": 5,
    "Banca - Somente humanos": 6,
}


def preencher_ordem(apps, schema_editor):
    PoolCorrecao = apps.get_model("corretores", "PoolCorrecao")
    for banca in PoolCorrecao.objects.all():
        if banca.nome in ORDENS:
            banca.ordem = ORDENS[banca.nome]
            banca.save(update_fields=["ordem"])


def reverse_func(apps, schema_editor):
    PoolCorrecao = apps.get_model("corretores", "PoolCorrecao")
    PoolCorrecao.objects.all().update(ordem=0)


class Migration(migrations.Migration):

    dependencies = [
        ("corretores", "0021_alter_poolcorrecao_options_and_more"),
    ]

    operations = [
        migrations.RunPython(preencher_ordem, reverse_func),
    ]
