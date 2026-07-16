# Pluma

Sistema automatizado de correção de redações do ENEM com IA.

## Stack

- **Framework:** Django 5.2 + Django REST Framework
- **Frontend:** Django Templates (Bootstrap 5.3) + Plotly.js
- **Admin:** Django Admin
- **Fila assíncrona:** Django Q2
- **Autenticação:** JWT (SimpleJWT) + Sessão Django
- **Banco:** SQLite (`dados/essay_essay_django.db`) / PostgreSQL
- **Core de avaliação:** OpenAI GPT + domain services reutilizados do monolito original

## Estrutura

```
apps/                    # Aplicações Django
├── accounts/            # CustomUser, auth JWT + sessão
├── avaliacoes/          # Avaliacao, Consolidacao, services, tasks
├── corretores/          # CorretorLLM, PoolCorrecao, PoolCorretor
├── dashboard/           # Views, forms, templates + gráficos Plotly
└── redacoes/            # Redacao, API, paginação, filtros
config/                  # Settings (base/local/production), urls
src/essay_essay/         # Core de domínio reutilizado
├── domain/              # Modelos de domínio, value objects
├── evaluators/          # OpenAI client, orquestrador
└── prompts/             # Templates de prompt
```

## Rodando localmente

```bash
uv sync
cp .env.example .env
# Edite .env com suas chaves (OPENAI_API_KEY, DJANGO_SECRET_KEY, FERNET_KEY, etc.)
# Em desenvolvimento, mantenha AVALIACAO_USE_Q2=false para executar avaliação em thread local.
uv run python manage.py migrate
uv run python manage.py createsuperuser
```

Terminal 1 — worker de fila:
```bash
uv run python manage.py qcluster
```

Terminal 2 — servidor:
```bash
uv run python manage.py runserver 0.0.0.0:8000
```

## Docker

```bash
docker compose up --build
```

A aplicação estará em `http://localhost:1000/`.

No Docker Compose, o `web` e o `worker` (Django Q2) rodam em containers separados.
Em produção, use `AVALIACAO_USE_Q2=true`.

## Acessos

| URL | Descrição |
|-----|-----------|
| `/` | Home / Dashboard web |
| `/login` | Login (email + senha) |
| `/register` | Cadastro de aluno |
| `/admin/` | Django Admin |
| `/api/docs/` | Swagger / OpenAPI |
| `/api/schema/` | Schema OpenAPI (JSON) |

## Endpoints da API

### Auth
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/auth/registro` | Cadastro de usuário |
| POST | `/api/v1/auth/login` | Login (retorna JWT) |
| GET | `/api/v1/auth/me` | Dados do usuário autenticado |

### Redações
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/redacoes` | Listar (paginado, filtrável por `tema`, `search`, `ordering`) |
| POST | `/api/v1/redacoes` | Enviar redação |
| GET | `/api/v1/redacoes/{id}` | Detalhe com avaliações |
| GET | `/api/v1/redacoes/pendentes` | Redações pendentes do corretor |
| POST | `/api/v1/redacoes/{id}/avaliar` | Avaliar via LLM |
| POST | `/api/v1/redacoes/{id}/avaliar/humano` | Avaliação manual |

### Consultas
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/correcoes` | Correções do usuário |
| GET | `/api/v1/alunos/pendentes` | Alunos com pendências (admin/professor) |
| GET | `/api/v1/estatisticas` | Estatísticas globais (admin/professor) |
| GET | `/api/v1/estatisticas/usuario` | Estatísticas do usuário |

### Admin
| Método | Rota | Descrição |
|--------|------|-----------|
| CRUD | `/api/v1/admin/corretores-llm` | Gerenciar corretores LLM |
| CRUD | `/api/v1/admin/pools` | Gerenciar pools de correção |
| CRUD | `/api/v1/admin/pool-corretores` | Membros dos pools |
