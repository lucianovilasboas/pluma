#!/bin/bash
set -e

if [ "$SKIP_MIGRATE" != "true" ]; then
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput || true

    python manage.py shell <<EOF
import os
from apps.accounts.models import CustomUser
email = os.getenv("DJANGO_ADMIN_EMAIL", "").strip()
password = os.getenv("DJANGO_ADMIN_PASSWORD", "").strip()
if not email or not password:
    print("Variáveis DJANGO_ADMIN_EMAIL/DJANGO_ADMIN_PASSWORD ausentes; criação de admin ignorada.")
elif not CustomUser.objects.filter(email=email).exists():
    CustomUser.objects.create_superuser(email=email, nome="Admin", password=password, user_type="admin")
    print(f"Admin {email} criado.")
else:
    print(f"Admin {email} já existe.")
EOF
fi

exec "$@"
