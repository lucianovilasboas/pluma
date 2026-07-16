from django.db import migrations, models


def marcar_avaliacoes_como_publicadas(apps, schema_editor):
    Avaliacao = apps.get_model("avaliacoes", "Avaliacao")
    Avaliacao.objects.filter(rascunho=True).update(rascunho=False)


class Migration(migrations.Migration):

    dependencies = [
        ("avaliacoes", "0003_avaliacao_rascunho"),
    ]

    operations = [
        migrations.AlterField(
            model_name="avaliacao",
            name="rascunho",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(marcar_avaliacoes_como_publicadas, migrations.RunPython.noop),
    ]
