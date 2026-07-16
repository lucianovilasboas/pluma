from __future__ import annotations

import os

from .base import *

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "essay_essay"),
        "USER": os.getenv("POSTGRES_USER", "essay_essay"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "essay_essay"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

CSRF_TRUSTED_ORIGINS = [
    orig.strip()
    for orig in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if orig.strip()
]


def _env_bool(nome: str, padrao: str = "True") -> bool:
    return os.getenv(nome, padrao).strip().lower() in ("true", "1", "yes", "on")


# Padrão True (seguro atrás de Traefik/HTTPS). Defina como "false" no ambiente
# ao rodar o container via HTTP puro (ex.: docker compose local sem TLS),
# senão os cookies Secure não trafegam por HTTP e o login não persiste a sessão.
CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE")
# CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE")
SESSION_COOKIE_HTTPONLY = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname:<7} {name:<42} {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "essay_essay": {
            "level": os.getenv("LOG_LEVEL_ESSAY", "INFO"),
            "handlers": ["console"],
            "propagate": False,
        },
        "apps.avaliacoes": {
            "level": os.getenv("LOG_LEVEL_APPS", "INFO"),
            "handlers": ["console"],
            "propagate": False,
        },
        "apps.corretores": {
            "level": os.getenv("LOG_LEVEL_APPS", "INFO"),
            "handlers": ["console"],
            "propagate": False,
        },
    },
}
