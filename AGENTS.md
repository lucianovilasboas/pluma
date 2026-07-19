# Pluma — AGENTS.md

Sistema automatizado de correção de redações ENEM com IA (Django 5.2 + DRF).

## Comandos essenciais

```bash
uv sync                          # instalar dependências (não use pip)
docker compose up db -d          # PostgreSQL na porta 5437 (obrigatório p/ testes)
uv run python manage.py migrate  # só após banco rodando
uv run python manage.py runserver 0.0.0.0:8000
uv run python manage.py qcluster  # worker de fila (só faz sentido se AVALIACAO_USE_Q2=true)
uv run python manage.py check    # validação Django (roda no CI)
uv run ruff check .              # lint local, line-length=100, py312 target
uv run mypy apps/ config/ src/   # typecheck strict (exclui tests/ legacy)
uv run pytest                    # requer PostgreSQL rodando
uv run pytest tests_django/test_X.py -k "substring"   # teste único
uv run pytest --cov=apps --cov=config --cov=src/essay_essay --cov-report=term-missing
```

**Ordem CI** (`.github/workflows/ci.yml`): `uv sync --all-groups` → `manage.py check` → `pytest --cov`. Ruff e mypy **não** rodam no CI — rode-os localmente antes de commitar. **Atenção:** o CI **não** sobe um serviço PostgreSQL; os passos `check`/`pytest` dependem de banco disponível, então validações que tocam o banco só são confiáveis localmente com `docker compose up db -d`.

## Regras de trabalho (obrigatórias)

- **Sempre crie testes.** Toda correção ou feature precisa de teste unitário em `tests_django/` que primeiro reproduz o problema (falha), depois passa com a correção. Nunca entregue fix sem teste.
- **Testes devem ser críticos, NUNCA celebratórios.** Testes não existem para validar o código que você acabou de escrever ("anda, não quebra"). Eles existem para **pegar bugs**. Todo teste deve:
  1. Primeiro **reproduzir o problema** que motivou a mudança — se possível, escreva o teste antes do fix e veja-o falhar
  2. Buscar ativamente **regressões, edge cases, race conditions e vazamentos de recurso** — não apenas o happy path
  3. Usar **mocks/spies** para verificar que efeitos colaterais realmente aconteceram (ex: conexão foi fechada, arquivo foi liberado), não apenas que o código "não deu erro"
  4. Testar **cenários de falha**: o que acontece se o recurso já foi liberado? Se chamar close 2x? Se o event loop fechou antes do cleanup?
- **Relatório final obrigatório.** Ao terminar de rodar os testes, apresente um relatório com:
  - O que foi testado e quantos testes passaram/falharam
  - Bugs ou fragilidades encontrados (se houver)
  - O que **precisa** ser corrigido (decisão do usuário, não sua)
- **NUNCA corrija código sem autorização expressa do usuário.** Se os testes encontrarem erros, **reporte-os e PARE**. Liste o que precisa ser corrigido e aguarde o usuário autorizar explicitamente antes de fazer qualquer alteração. Não continue corrigindo em loop sem aprovação.
- **Nunca faça suposições ao investigar.** Quando o pedido for investigar um problema, vá até a causa raiz com evidência (logs, execução real, leitura do código). Reporte o que encontrou. Se não encontrar, diga explicitamente que não encontrou — não invente hipótese como se fosse fato.
- **Nunca misture config local com produção.** Alterações para rodar localmente (HTTP, cookies não-secure, settings de dev) NÃO podem alterar o comportamento de produção. Torne diferenças configuráveis por env var com padrão seguro para produção (ver quirks de cookies e fila). Antes de commitar, confirme que o push não muda o funcionamento em produção.
- **Respostas objetivas e baseadas em evidências, sem viés de defesa.** Ao responder perguntas ou avaliar código, seja direto e fundamente-se em evidências concretas do projeto (código, logs, comportamento observado). Não dê respostas bajulativas para agradar o usuário, nem defensivas para justificar implementações feitas pelo modelo. Crítica técnica honesta > autoelogio.

## Setup

1. `cp .env.example .env` e preencha `OPENAI_API_KEY`, `DJANGO_SECRET_KEY`, `FERNET_KEY`
2. `docker compose up db -d` (porta 5437 local)
3. `uv sync && uv run python manage.py migrate`

**`.env` é carregado 2x** (por `manage.py` e por `config/settings/base.py`), sempre com `load_dotenv()` padrão (`override=False`): variáveis já presentes no ambiente **nunca** são sobrescritas pelo `.env`. `manage.py` faz `setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")`.

## Estrutura

- **`apps/`** — apps Django: `accounts` (CustomUser UUID, email=USERNAME_FIELD), `redacoes`, `avaliacoes`, `corretores` (LLM providers), `dashboard` (templates Bootstrap + Plotly)
- **`config/settings/`** — `base.py` → `local.py` / `production.py`. Ambos usam **PostgreSQL exclusivamente** (sem SQLite). `base.py` insere `src/` no `sys.path`, chama `load_dotenv()` e **não** define `DATABASES` (isso é responsabilidade de local/production).
- **`src/essay_essay/`** — core de domínio puro: `domain/` (dataclasses/enums), `evaluators/` (OpenAI client, Gemini client, factory, multi-agent orquestradores, ferramentas, extrator, conhecimento_loader), `prompts/` (templates)
- **`base_de_conhecimento/`** — textos de redações exemplares ENEM + KB JSON (carregado pelo `conhecimento_loader.py`)
- **`tests_django/`** — testes ativos com pytest-django (~600 testes). `tests/` é legado (ignorado pelo mypy).
- **`legacy/`** — código FastAPI antigo, não faz parte do app ativo.
- **`planos/`** — planos de feature futuros (não implementados). `api/` está vazio.
- **`.github/agents/`** — 5 agentes ENEM (avaliadores 1-3, data-analyst, programming-coach)
- **`.github/prompts/`** — prompts auxiliares (avaliar-redacao, planos, debug/explain/generate)
- **`.github/skills/`** — skills `run-tests` e `run-python`
- **`.github/instructions/customizacoes-ptbr.instructions.md`** — convenções PT-BR do time

## Quirks

- **Gerenciador:** `uv` exclusivamente. Sem `requirements.txt` ou `Pipfile`.
- **Banco:** PostgreSQL sempre via Docker (`docker compose up db -d`). Porta local **5437**.
- **Imagem Docker sem dev deps:** o `Dockerfile` roda `uv sync --frozen --no-dev` — **não há pytest/mypy/ruff dentro dos containers**. Rode ferramentas de qualidade no host.
- **Código vai por `COPY` no build:** alterações em código **não** entram no container com `--force-recreate` sozinho. Rode `docker compose build web` (ou `docker compose up --build`) para a imagem pegar o código novo.
- **Compose `environment` > `.env`:** no `docker-compose.yml`, o bloco `environment` sobrescreve o `env_file: .env`. Ex.: mesmo com `AVALIACAO_USE_Q2=false` no `.env`, o compose força `"true"`. Não confie no `.env` para prever o comportamento dentro dos containers.
- **Fila / `AVALIACAO_USE_Q2`:**
  - `runserver` puro (dev sem compose): usa o valor do `.env`. `false` = avaliação LLM roda **inline** em thread.
  - `docker compose`: `web` e `worker` recebem `AVALIACAO_USE_Q2=true` via `environment` → avaliação vai para a fila do `qcluster`.
  - **Motivo:** com `false` no Docker, a chamada LLM roda inline no worker gunicorn e bloqueia >120s → **`WORKER TIMEOUT` + SIGKILL**. Em produção use sempre `true` + container `worker`.
- **Cookies Secure quebram login via HTTP:** `production.py` lê `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` de env var (padrão `True`). O `docker-compose.yml` define ambos como `false` (`${VAR:-false}`) porque o acesso local é HTTP puro em `http://host:1000` — cookie `Secure` não trafega por HTTP e o login não persiste (302 em loop para a landing). **Atrás de Traefik/HTTPS em produção, deixe `True`** (não sobrescreva no `.env` de produção).
- **Docker Compose:** expõe em `http://localhost:1000/`. Containers separados: `web` (gunicorn, 3 workers) + `worker` (qcluster). Labels de Traefik/Let's Encrypt são para o deploy de produção, não ativos no compose local.
- **Entrypoint (`entrypoint.sh`):** roda `migrate` + `collectstatic` + cria superadmin via `DJANGO_ADMIN_EMAIL`/`DJANGO_ADMIN_PASSWORD`. O container `worker` pula tudo isso com `SKIP_MIGRATE=true` (só roda `migrate django_q` + `qcluster`).
- **API docs:** `/api/docs/` (Swagger) e `/api/schema/` (JSON OpenAPI).
- **URLs sem barra final:** `APPEND_SLASH = False`. Rotas da API são `/api/v1/redacoes` (sem `/`).
- **Testes:** `APIClient`/`Client`, `force_authenticate`/`force_login`, `pytest.mark.django_db`. **Sem fixtures globais** (sem `conftest.py`) — cada teste cria dados inline. Requerem PostgreSQL. `testpaths=tests_django`; `tests/` é legado.
- **Testes não chamam a OpenAI:** a suíte ativa simula `Avaliacao` no banco (testa `/avaliar/humano`, não `/avaliar` via LLM). `pytest` **não** precisa de `OPENAI_API_KEY` real; ela só é necessária para rodar avaliação LLM de verdade.
- **Modelo:** `CustomUser` com `id=UUIDField`, `email` como `USERNAME_FIELD`, `user_type` (admin/professor/aluno/corretor). Tabela: `usuarios`.
- **LLM Providers:** `LLM_MODEL` lê de env var (fallback `gpt-4o`). Suporta OpenAI, Gemini (via `factory.py`), e qualquer API compatível com OpenAI (DeepSeek, etc.) via `base_url`. O `openai_client.py` lista contextos conhecidos para vários modelos.
- **Lint/Typecheck:** Ruff line-length=100, select=E/F/I/N/W/UP, target py312 (base tem ~238 erros pré-existentes; foque só nos arquivos que você tocar). Mypy `strict=true` excluindo `tests/`.
- **README.md desatualizado:** cita SQLite/`dados/*.db` (o backend é PostgreSQL em ambos os settings) e sugere rodar `qcluster` em dev. Ignore — confie em `pyproject.toml`, settings e compose.

## Versionamento

- **SemVer:** `MAJOR.minor.patch` — MAJOR quebra compatibilidade, MINOR adiciona funcionalidade, PATCH corrige bug.
- **Fonte da verdade:** `version` no `pyproject.toml` (espelhado em git tag `vX.Y.Z` e CHANGELOG.md).
- **Incrementar versão:** `uv run hatch version <patch|minor|major>` (atualiza `pyproject.toml` automaticamente).
- **Conventional Commits obrigatório:** `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- **Fluxo de release:**
  1. Mover entradas de `[Unreleased]` para `[X.Y.Z]` no `CHANGELOG.md`
  2. `uv run hatch version patch|minor|major`
  3. `git add pyproject.toml CHANGELOG.md`
  4. `git commit -m "chore: release vX.Y.Z"`
  5. `git tag -a vX.Y.Z -m "vX.Y.Z"`
  6. `git push && git push --tags`
  7. GitHub Actions (`.github/workflows/release.yml`) cria o Release automaticamente

## Telegram

- **Chat ID:** `1627668730` (Luciano Espiridião) — configurado no Composio para notificações automáticas.
- **Regra:** Ao finalizar qualquer tarefa de implementação, enviar resumo via Telegram com o status (sucesso/falha), arquivos alterados e contagem de testes.

## Idioma

Instruções e mensagens ao usuário em **português brasileiro (PT-BR)**.
