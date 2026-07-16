from __future__ import annotations

import os

from .base import *

DEBUG = True

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
        "level": os.getenv("LOG_LEVEL", "DEBUG"),
    },
    "loggers": {
        "essay_essay": {"level": "DEBUG", "handlers": ["console"], "propagate": False},
        "apps.avaliacoes": {"level": "DEBUG", "handlers": ["console"], "propagate": False},
        "apps.corretores": {"level": "DEBUG", "handlers": ["console"], "propagate": False},
    },
}
