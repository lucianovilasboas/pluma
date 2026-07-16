FROM python:3.12-slim AS build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY apps/ ./apps/
COPY config/ ./config/
COPY manage.py ./
RUN uv sync --frozen --no-dev


FROM python:3.12-slim

WORKDIR /app

COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
COPY --from=build /app/apps /app/apps
COPY --from=build /app/config /app/config
COPY --from=build /app/manage.py /app/manage.py
COPY pyproject.toml uv.lock ./
COPY base_de_conhecimento/ ./base_de_conhecimento/
COPY entrypoint.sh /entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /app/dados && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
