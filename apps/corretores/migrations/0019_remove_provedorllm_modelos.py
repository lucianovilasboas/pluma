from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("corretores", "0018_add_provedor_tipo"),
    ]

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE "provedores_llm" DROP COLUMN IF EXISTS "modelos";',
            reverse_sql=(
                'ALTER TABLE "provedores_llm"'
                " ADD COLUMN IF NOT EXISTS \"modelos\""
                " jsonb NOT NULL DEFAULT '[]'::jsonb;"
            ),
        ),
    ]
