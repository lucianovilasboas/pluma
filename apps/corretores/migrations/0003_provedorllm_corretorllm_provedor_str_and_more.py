import django.db.models.deletion
import uuid
from django.db import migrations, models


def migrar_provedor_antigo(apps, schema_editor):
    CorretorLLM = apps.get_model("corretores", "CorretorLLM")
    db_alias = schema_editor.connection.alias
    for c in CorretorLLM.objects.using(db_alias).exclude(provedor=""):
        c.provedor_str = c.provedor
        c.save(update_fields=["provedor_str"])


class Migration(migrations.Migration):

    dependencies = [
        ("corretores", "0002_criar_pool_padrao"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProvedorLLM",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("nome", models.CharField(max_length=100, unique=True)),
                ("api_key", models.TextField()),
                ("base_url", models.URLField(blank=True, max_length=500)),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "provedores_llm",
                "ordering": ["nome"],
            },
        ),
        migrations.AddField(
            model_name="corretorllm",
            name="provedor_str",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.RunPython(migrar_provedor_antigo, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="corretorllm",
            name="provedor",
        ),
        migrations.AddField(
            model_name="corretorllm",
            name="provedor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="corretores",
                to="corretores.provedorllm",
            ),
        ),
    ]
