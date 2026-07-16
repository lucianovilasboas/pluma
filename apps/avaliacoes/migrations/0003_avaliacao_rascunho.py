from django.db import migrations, models


def migrar_rascunho(apps, schema_editor):
    Avaliacao = apps.get_model("avaliacoes", "Avaliacao")
    Avaliacao.objects.filter(nota_total__gt=0).update(rascunho=False)


class Migration(migrations.Migration):

    dependencies = [
        ("avaliacoes", "0002_anotacao"),
    ]

    operations = [
        migrations.AddField(
            model_name="avaliacao",
            name="rascunho",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(migrar_rascunho, migrations.RunPython.noop),
    ]
