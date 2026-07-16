# Pluma — Documentação Completa do Sistema

> Data: Julho/2026 • Django 5.2 + DRF • PostgreSQL • OpenAI

---

## 1. PROJETO — Estrutura Geral

### 1.1 Gerenciamento de Dependências

- **Gerenciador exclusivo:** `uv` (uv sync, uv run). Sem `requirements.txt` ou `Pipfile`.
- `pyproject.toml` declara dependências em `[project.dependencies]`:
  - Django 5.2.3, djangorestframework 3.16.0, django-filter 25.1
  - PostgreSQL via `psycopg[binary]` 3.2
  - OpenAI 1.79+ (via `openai`), python-dotenv, django-q2
  - Outros: `requests`, `Pillow`, `markdown`, `bleach`, `python-dateutil`
- Dev: `pytest`, `pytest-django`, `pytest-cov`, `ruff`, `mypy`, `uvicorn`, `django-extensions`, `watchfiles`, `ipdb`
- Type hints: Python 3.12+ (typing, dataclasses, enums)

### 1.2 Arquivos Raiz

| Arquivo | Função |
|---|---|
| `manage.py` | Carrega `.env` via `load_dotenv()` antes de `execute_from_command_line` |
| `pyproject.toml` | Dependências, tool config (ruff, mypy, pytest) |
| `Dockerfile` | Docker multi-estágio (python:3.12-slim) |
| `docker-compose.yml` | Serviços: `db` (postgres:16, porta 5437), `web`, `worker` |
| `entrypoint.sh` | Produção: migrate → collectstatic → cria superadmin → qcluster (worker) ou gunicorn (web) |
| `.env.example` | Template com vars PostgreSQL + Django SECRET_KEY + OpenAI |

### 1.3 Configurações Django (`config/settings/`)

- **`base.py`** — Configurações compartilhadas, inclui `load_dotenv()` (para testes). PostgreSQL hardcoded.
- **`local.py`** — `DEBUG=True`, CORS e CSRF liberados para `localhost:5173` (Vite) e `0.0.0.0:8000`
- **`production.py`** — `DEBUG=False`, CSRF/CORS de `PRODUCTION_DOMAIN`, staticfiles S3

**Banco de Dados (base.py):**
```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT"),
    }
}
```

> ⚠️ PostgreSQL é **obrigatório**. Sem SQLite. O banco sobe via `docker compose up db -d` (porta 5437).

### 1.4 Aplicações Django

| App | Pasta `apps/` | Modelos Principais |
|---|---|---|
| `accounts` | `apps/accounts/` | `CustomUser` |
| `redacoes` | `apps/redacoes/` | `Redacao`, `PreferenciaRota`, `PreferenciaRotaCorretor` |
| `avaliacoes` | `apps/avaliacoes/` | `Avaliacao`, `Notificacao`, `Anotacao`, `Consolidacao` |
| `corretores` | `apps/corretores/` | `PoolCorrecao`, `PoolCorretor`, `CorretorLLM`, `PromptTemplate`, `Skill`, `Ferramenta`, `ProvedorLLM` |
| `dashboard` | `apps/dashboard/` | **Views (1412 linhas)**, forms, charts, context_processors, 33 templates |
| `api` | (inline no `urls.py` principal) | DRF Viewsets em cada app |

### 1.5 Core de Domínio (`src/essay_essay/`)

| Subpasta | Arquivo | Conteúdo |
|---|---|---|
| `domain/` | `enums.py` | `NivelDesempenho`, `NotaCompetencia`, `FaixaDesempenho` |
| `domain/` | `models.py` | `RedacaoModel` (dataclass), `Competencia` (dataclass), `CorrecaoModel`, `ConsolidacaoModel` |
| `evaluators/` | `config.py` | `EssayEssayConfig` (lê OPENAI_API_KEY, AVALIACAO_MODEL, AVALIACAO_USE_Q2, etc.) |
| `evaluators/` | `openai_client.py` | `OpenAIClient` — wrapper assíncrono da API OpenAI |
| `evaluators/` | `llm.py` | `LLMEvaluator` — avalia redação, conta tokens, extrai JSON |
| `evaluators/` | `orchestrator.py` | `OrquestradorAvaliacao` — executa 3 agentes, coleta resultados |
| `evaluators/` | `orchestrator_subagentes.py` | `SubAgenteFactory`, `SubAgenteCorretor` — framework para sub-agentes |
| `evaluators/` | `span_matcher.py` | `SpanMatcher` — matching de spans no texto da redação |
| `prompts/` | `templates.py` | Prompts para cada competência ENEM (C1–C5), agente consolidador |

### 1.6 Testes (`tests_django/`)

| Arquivo | # Testes | O que testa |
|---|---|---|
| `test_base_integracao.py` | 7 | CRUD de redações via API, login, registro, criar/simular avaliação, consolidar |
| `test_corrigir_lista.py` | 7 | Corretor vê/esconde redações recusadas, re-notificação, filtro de status |
| `test_resubmeter.py` | 5 | Aluno notifica só suas redações; corretor re-notificado; bloqueio de já corrigida |
| `test_nav_counts.py` | 4 | Contadores de redações pendentes/concluídas por corretor e por aluno |

**Total: 23 testes — todos passando.**

### 1.7 CI (`.github/workflows/ci.yml`)

```yaml
steps: check → pytest --cov
```

- Ruff e mypy **não rodam no CI** (só localmente)
- Comando CI: `uv run python manage.py check && uv run pytest --cov=apps --cov=config --cov=src/essay_essay --cov-report=term-missing`

---

## 2. DOMAIN CORE (`src/essay_essay/`)

### 2.1 Dataclasses de Domínio (`domain/models.py`)

```python
@dataclass
class Competencia:
    numero: int  # 1-5
    titulo: str
    nivel: NivelDesempenho
    justificativa: str

@dataclass
class RedacaoModel:
    texto: str
    tema: str
    competencias: list[Competencia]
    nota_final: int
    metadata: dict

@dataclass
class CorrecaoModel:
    redacao: RedacaoModel
    corretor_nome: str
    timestamp: str

@dataclass
class ConsolidacaoModel:
    redacao: RedacaoModel
    correcoes: list[CorrecaoModel]
    nota_consolidada: int
    votos: dict
```

### 2.2 Enums (`domain/enums.py`)

- `NivelDesempenho`: `INSUFICIENTE`, `MEDIO`, `BOM`, `EXCELENTE`
- `NotaCompetencia`: valores 0–200 (mapeia NivelDesempenho → nota)
- `FaixaDesempenho`: `ABAIXO_600`, `MEDIO_600_700`, `BOM_700_800`, `EXCELENTE_800_1000`

### 2.3 Config (`config.py`)

Dataclass `EssayEssayConfig` lida de env vars:
- `OPENAI_API_KEY`, `AVALIACAO_MODEL` (default: `gpt-4o`)
- `AVALIACAO_TEMPERATURE`, `AVALIACAO_MAX_TOKENS`, `AVALIACAO_TIMEOUT`
- `AVALIACAO_USE_Q2`, `CONSOLIDACAO_MIN_VOTOS`, `CONSOLIDACAO_ESTRATEGIA`

### 2.4 Evaluators

**`OpenAIClient`** — cliente assíncrono (`asyncio`) para API OpenAI:
- `generate()` — chama chat completion com retry/backoff
- Contagem de tokens, parsing de resposta JSON

**`LLMEvaluator`** — avalia uma redação contra prompt de competência:
- `avaliar()` → retorna `Competencia` (numero, titulo, nivel, justificativa)
- Usa `OpenAIClient.generate()` para chamar LLM
- Faz pós-processamento: cálculo de nota, extração de spans

**`OrquestradorAvaliacao`** — executa pipeline multi-agente:
1. Cria 3 `SubAgenteCorretor` (simula 3 corretores humanos)
2. Cada sub-agente avalia C1–C5 via `LLMEvaluator`
3. Chama agente **consolidado** para gerar nota final única
4. Retorna `ConsolidacaoModel`

**`SpanMatcher`** — utilitário para encontrar spans de texto (citações) na redação e retornar posições (start/end). Usado para destacar no front-end os trechos avaliados.

### 2.5 Prompts (`prompts/templates.py`)

Templates Jinja2 para cada competência ENEM:
- `PROMPT_C1` — Domínio da escrita formal
- `PROMPT_C2` — Compreensão do tema
- `PROMPT_C3` — Seleção e organização de argumentos
- `PROMPT_C4` — Conhecimento dos mecanismos linguísticos
- `PROMPT_C5` — Proposta de intervenção
- `PROMPT_CONSOLIDADOR` — Prompt que junta correções parciais em nota consolidada

Cada prompt inclui a nota da redação, nível de desempenho esperado, e instruções para justificativa.

---

## 3. MODELOS DJANGO

### 3.1 `accounts.CustomUser` (`apps/accounts/models.py`)

```python
class CustomUser(AbstractUser):
    tipo = models.CharField(choices=TipoUsuario.choices, max_len=20, default='aluno')
    cpf = models.CharField(unique, null=True, blank=True)
    telefone = models.CharField(blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/')
    
    class TipoUsuario(models.TextChoices):
        ALUNO = 'aluno'
        CORRETOR = 'corretor'
        ADMIN = 'admin'
```

**Managers:** `CustomUserManager` com `create_user()` e `create_superuser()`.

### 3.2 `redacoes.Redacao` (`apps/redacoes/models.py`)

```python
class Redacao(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = 'rascunho'
        EM_ANALISE = 'em_analise'
        EM_AVALIACAO = 'em_avaliacao'
        CORRIGIDA = 'corrigida'

    titulo = models.CharField(max_len=200)
    tema = models.TextField()
    texto = models.TextField()
    usuario = ForeignKey(CustomUser, related_name='redacoes')
    status = models.CharField(choices=Status.choices, default=Status.RASCUNHO)
    nota_final = models.IntegerField(null=True, blank=True)
    feedback_geral = models.TextField(blank=True)
    versao = models.IntegerField(default=1)
    resubmetida_em = models.DateTimeField(null=True, blank=True)
    criada_em, atualizada_em, enviada_em = ...
```

**PreferenciaRota** — registra que o aluno prefere que a redação siga para um corretor específico.
**PreferenciaRotaCorretor** — junção many-to-many entre redação e corretor preferido.

### 3.3 `avaliacoes` Models (`apps/avaliacoes/models.py`)

```python
class Corretor(models.Model):
    usuario = OneToOneField(CustomUser)

class Notificacao(models.Model):
    class Status(models.TextChoices):
        CORRECAO_SOLICITADA = 'correcao_solicitada'
        CORRECAO_ACEITA = 'correcao_aceita'
        CORRECAO_RECUSADA = 'correcao_recusada'
        CORRECAO_CONCLUIDA = 'correcao_concluida'
        CORRECAO_RESUBMETIDA = 'correcao_resubmetida'
        LIDA = 'lida'

    redacao = ForeignKey(Redacao)
    corretor = ForeignKey(Corretor)
    status = models.CharField(choices=Status.choices)
    criada_em, lida_em = ...

class Avaliacao(models.Model):
    redacao = ForeignKey(Redacao, related_name='avaliacoes')
    corretor = ForeignKey(Corretor, related_name='avaliacoes')
    nota_final = models.IntegerField()
    feedback_geral = models.TextField()
    status = models.CharField(choices=['em_andamento', 'concluida', 'recusada'])
    concluida_em = ...

class Anotacao(models.Model):
    avaliacao = ForeignKey(Avaliacao, related_name='anotacoes')
    competencia = models.IntegerField()  # 1-5
    nota = models.IntegerField()         # 0-200
    justificativa = models.TextField()
    span_inicio, span_fim = models.IntegerField(null=True)

class Consolidacao(models.Model):
    redacao = OneToOneField(Redacao, related_name='consolidacao')
    nota_final = models.IntegerField()
    feedback_final = models.TextField()
    estrategia = models.CharField(default='media')
    votos = models.JSONField()
    concluida_em = ...
```

### 3.4 `corretores` Models (`apps/corretores/models.py`)

```python
class ProvedorLLM(models.Model):
    nome = models.CharField(unique)  # "OpenAI", "Anthropic"
    api_key = models.CharField()
    modelo_padrao = models.CharField()

class Skill(models.Model):
    nome, descricao, prompt_padrao = ...
    competencias = ArrayField(IntegerField)

class Ferramenta(models.Model):
    nome, descricao, tipo = ...
    config = models.JSONField()

class PromptTemplate(models.Model):
    nome, descricao, template = ...
    skill = ForeignKey(Skill)
    versao = models.IntegerField()

class CorretorLLM(models.Model):
    nome = models.CharField()
    provedor = ForeignKey(ProvedorLLM)
    prompt_base = ForeignKey(PromptTemplate)
    skills = ManyToManyField(Skill)
    ferramentas = ManyToManyField(Ferramenta)
    config = models.JSONField()
    ativo = models.BooleanField(default=True)

class PoolCorrecao(models.Model):
    nome, descricao = ...
    ativo = models.BooleanField(default=True)
    estrategia_distribuicao = models.CharField(default='round_robin')

class PoolCorretor(models.Model):
    pool = ForeignKey(PoolCorrecao)
    content_type = ForeignKey(ContentType)
    object_id = PositiveIntegerField()
    corretor = GenericForeignKey('content_type', 'object_id')
    peso = models.IntegerField(default=1)
```

---

## 4. API (DRF)

### 4.1 Rotas (`config/urls.py`)

```python
router.register(r'users', UserViewSet)
router.register(r'redacoes', RedacaoViewSet)
router.register(r'notificacoes', NotificacaoViewSet)
router.register(r'avaliacoes', AvaliacaoViewSet)
router.register(r'consolidacoes', ConsolidacaoViewSet)
router.register(r'corretores/pools', PoolCorrecaoViewSet)
router.register(r'corretores/corretores-llm', CorretorLLMViewSet)
router.register(r'corretores/provedores', ProvedorLLMViewSet)
router.register(r'corretores/skills', SkillViewSet)
router.register(r'corretores/ferramentas', FerramentaViewSet)

urlpatterns += [
    path('api/register/', RegisterView.as_view()),
    path('api/auth/', include('rest_framework.urls')),
    path('api/schema/', get_schema_view(title='Pluma API')),
    path('api/docs/', schema_view.with_ui('swagger')),
]
```

### 4.2 Principais Serializers

- `RegisterSerializer` — cria `CustomUser` com validação de senha/senha2
- `UserSerializer` — campos básicos + `tipo`
- `RedacaoSerializer` — todos campos + `nota_final` + `competencias` (aninhado)
- `RedacaoListSerializer` — versão simplificada para listagem
- `NotificacaoSerializer` — com `redacao_titulo`, `corretor_nome` (via `SerializerMethodField`)
- `AvaliacaoSerializer` — com anotações aninhadas
- `ConsolidacaoSerializer` — apenas leitura

### 4.3 Autenticação e Permissões

- **API:** Token-based via `rest_framework.authentication.TokenAuthentication`
- **Dashboard:** Session-based via Django `login`/`logout`
- Permissões customizadas: `IsAluno`, `IsCorretor`, `IsAdmin` (checam `user.tipo`)

---

## 5. DASHBOARD — VIEWS (`apps/dashboard/views.py` — 1412 linhas)

### 5.1 Autenticação (4 views)

| View | Rota | Métodos | Funcionalidade |
|---|---|---|---|
| `login_view` | `login/` | GET, POST | Login com credenciais; se já autenticado redireciona para `dashboard:home` |
| `logout_view` | `logout/` | GET | Logout + redirect para login |
| `register_view` | `register/` | GET, POST | Registro de novo usuário (`form`), redireciona para login |
| `custom_logout` | `custom_logout/` | GET | Logout + redirect para login |

### 5.2 Home / Dashboard (1 view)

| View | Rota | Funcionalidade |
|---|---|---|
| `home` | `` | Redireciona por tipo: aluno → `minhas_redacoes`, corretor → `pendentes_admin`, admin → `admin_dashboard` |

### 5.3 Aluno — Redações (5 views)

| View | Rota | Funcionalidade |
|---|---|---|
| `minhas_redacoes` | `minhas-redacoes/` | Lista redações do aluno; cards com status, nota, ações; gráfico de evolução |
| `criar_redacao` | `criar-redacao/` | GET (form) / POST (salva `RASCUNHO`) |
| `detalhe_redacao` | `detalhe-redacao/<id>/` | Detalhes + resultado da correção + gráfico radar C1-C5 |
| `editar_redacao` | `editar-redacao/<id>/` | Altera rascunho (redireciona se já enviada) |
| `submeter` | `submeter-redacao/<id>/` | Muda status `RASCUNHO → EM_ANALISE`; cria `Notificacao(CORRECAO_SOLICITADA)` para todos corretores |

### 5.4 Corretor — Correções (5 views)

| View | Rota | Funcionalidade |
|---|---|---|
| `pendentes_admin` | `pendentes/` | Lista redações `EM_ANALISE`/`EM_AVALIACAO` exceto recusadas; chart |
| `corrigir` | `corrigir/<id>/` | GET: form de correção; POST: salva avaliação + notifica conclusão |
| `redacoes_corrigidas` | `corrigidas/` | Lista de redações corrigidas pelo corretor |
| `resubmeter` | `resubmeter-redacao/<id>/` | Volta status para `EM_AVALIACAO` ou `EM_ANALISE`; re-notifica corretores recusados |
| `minhas_correcoes` | `minhas-correcoes/` | Lista de correções feitas pelo corretor |

### 5.5 Notificações (2 views)

| View | Rota | Funcionalidade |
|---|---|---|
| `notificacoes` | `notificacoes/` | Lista notificações do usuário logado; marca como lidas |
| `notificacoes_nao_lidas` | `notificacoes-nao-lidas/` | JSON: contagem de não lidas (usado via XHR no navbar) |

### 5.6 Admin (4 views)

| View | Rota | Funcionalidade |
|---|---|---|
| `admin_dashboard` | `admin/` | KPIs + gráficos do sistema |
| `gerenciar_usuarios` | `admin/usuarios/` | Lista/gerencia usuários |
| `gerenciar_corretores` | `admin/corretores/` | Lista/gerencia corretores |
| `gerenciar_redacoes` | `admin/redacoes/` | Lista/gerencia redações |

### 5.7 Área Pública (2 views)

| View | Rota | Funcionalidade |
|---|---|---|
| `landing_page` | `landing/` | Página institucional do produto |
| `api_docs_view` | `api-docs/` | Template `api_docs.html` (documentação da API) |

### 5.8 Utilitários (2 views)

| View | Rota | Funcionalidade |
|---|---|---|
| `account_settings` | `configuracoes/` | Formulário de alteração de dados do perfil |
| `health_check` | `health/` | Retorna JSON `{"status": "ok"}` |

---

## 6. WORKFLOWS COMPLETOS

### 6.1 Submeter Redação

```
Aluno → submeter-redacao/<id>/
  1. Verifica: redação existe, pertence ao usuário, status == RASCUNHO
  2. Muda redacao.status = EM_ANALISE
  3. Se AVALIACAO_USE_Q2 == true:
       → dispara task async (disparar_avaliacao_llm)
     Senão:
       → chama sync: executar_avaliacao_llm()
  4. Cria Notificacao(CORRECAO_SOLICITADA) para cada corretor ativo
  5. Redireciona para minhas_redacoes com mensagem de sucesso
```

### 6.2 Corrigir (Corretor)

```
Corretor → corrigir/<id>/
  GET:
    1. Verifica: redação EM_ANALISE ou EM_AVALIACAO
    2. Redações onde corretor tem CORRECAO_RECUSADA são escondidas
    3. Renderiza form com campos: nota_final, competências (C1-C5), feedback

  POST:
    1. Se status == CORRIGIDA → warning e redirect
    2. Cria Avaliacao + 5 Anotacao (uma por competência)
    3. Muda notificação para CORRECAO_CONCLUIDA
    4. Se pool de corretores atingiu (2+ avaliações):
       → chama consolidar (atualizar_consolidacao)
    5. Se todas correções concluídas:
       → redacao.status = CORRIGIDA
    6. Redireciona para pendentes
```

### 6.3 Resubmeter (Aluno)

```
Aluno → resubmeter-redacao/<id>/
  1. Verifica: redação pertence ao usuário
  2. Deleta notificações antigas do usuário para esta redação
  3. Avalia status:
     - Se CORRIGIDA → muda para EM_AVALIACAO (mantém avaliação anterior)
     - Se EM_AVALIACAO → muda para EM_ANALISE
     - Caso contrário → EM_ANALISE
  4. Re-notifica corretores recusados:
     - Busca Notificacao(CORRECAO_RECUSADA) desta redação
     - Para cada: cria nova Notificacao(CORRECAO_SOLICITADA), apaga antiga
  5. Redireciona para detalhe_redacao com mensagem
  ⚠️ NÃO chama LLM novamente
  ⚠️ NÃO mexe em PreferenciaRota
```

### 6.4 Ciclo de Vida de uma Redação

```
RASCUNHO → (submeter) → EM_ANALISE → (corretor aceita) → EM_AVALIACAO
  → (corretor corrige) → CORRIGIDA
  ↑                                        ↓
  └──── (resubmeter) ←─────────────────────┘

Estados de Notificação:
  CORRECAO_SOLICITADA → CORRECAO_ACEITA → CORRECAO_CONCLUIDA
                      → CORRECAO_RECUSADA → (resubmeter) → CORRECAO_SOLICITADA
                                              ↓
                                        CORRECAO_RESUBMETIDA
```

---

## 7. TEMPLATES (33 arquivos)

### 7.1 Layout

| Template | Descrição |
|---|---|
| `base.html` | Base com Bootstrap 5.3.7 + Plotly 3.0.1 + tema escuro |
| `navbar.html` | Navbar responsiva com contadores de notificações |
| `footer.html` | Footer simples |
| `sidebar.html` | Sidebar para área logada |

### 7.2 Páginas Públicas

| Template | View Associada |
|---|---|
| `landing_page.html` | `landing_page` |
| `api_docs.html` | `api_docs_view` |

### 7.3 Autenticação

| Template | View Associada |
|---|---|
| `login.html` | `login_view` |
| `register.html` | `register_view` |
| `custom_logout.html` | `custom_logout` |

### 7.4 Aluno

| Template | View Associada |
|---|---|
| `minhas_redacoes.html` | `minhas_redacoes` |
| `criar_redacao.html` | `criar_redacao` |
| `detalhe_redacao.html` | `detalhe_redacao` |
| `editar_redacao.html` | `editar_redacao` |

### 7.5 Corretor

| Template | View Associada |
|---|---|
| `corrigir.html` | `corrigir` (formulário completo de correção) |
| `redacoes_corrigidas.html` | `redacoes_corrigidas` |
| `minhas_correcoes.html` | `minhas_correcoes` |

### 7.6 Admin

| Template | View Associada |
|---|---|
| `admin/admin_dashboard.html` | `admin_dashboard` |
| `admin/gerenciar_usuarios.html` | `gerenciar_usuarios` |
| `admin/gerenciar_redacoes.html` | `gerenciar_redacoes` |
| `admin/gerenciar_corretores.html` | `gerenciar_corretores` |

### 7.7 Notificações

| Template | View Associada |
|---|---|
| `notificacoes.html` | `notificacoes` |

### 7.8 Configurações

| Template | View Associada |
|---|---|
| `account_settings.html` | `account_settings` |

### 7.9 Componentes Reutilizáveis

| Template | Descrição |
|---|---|
| `includes/redacao_card.html` | Card de redação (reusado em várias listas) |
| `includes/form_errors.html` | Renderização de erros de formulário |
| `includes/charts/competencia_radar.html` | Gráfico radar C1-C5 |
| `includes/charts/evolucao_notas.html` | Evolução temporal de notas |
| `includes/charts/distribuicao_notas.html` | Distribuição de notas |
| `includes/charts/comparativo.html` | Comparativo entre corretores |
| `includes/charts/progresso.html` | Progresso do aluno |

### 7.10 Features CSS/JS

- **Dark mode** via `[data-bs-theme="dark"]` no `<html>`
- **Ícones:** Bootstrap Icons
- **Gráficos:** Plotly.js 3.0.1 (renderização no cliente)
- **Formulários:** Bootstrap 5 validation + select2-style (manual, inline)
- **Navbar:** contador de notificações atualizado via XHR (`notificacoes_nao_lidas`)

---

## 8. GRÁFICOS (`apps/dashboard/charts.py`)

| Função | Tipo de Gráfico | Uso |
|---|---|---|
| `grafico_radar_competencias` | Radar (Plotly) | Perfil C1-C5 de uma redação |
| `grafico_evolucao_notas` | Linha (Plotly) | Evolução do aluno ao longo do tempo |
| `grafico_distribuicao_notas` | Histograma (Plotly) | Distribuição de notas do sistema |
| `grafico_comparativo_corretores` | Barras (Plotly) | Comparação entre corretores |
| `grafico_progresso_aluno` | Área (Plotly) | Progresso cumulativo do aluno |
| `grafico_competencias_radar` | Radar (Plotly) | (versão alternativa) |
| `grafico_barras_competencias` | Barras (Plotly) | Notas por competência (visão geral) |
| `grafico_pizza_status` | Pizza (Plotly) | Distribuição de status das redações |

Todos usam Plotly.js, modo escuro, com template `plotly_dark`.

---

## 9. CONTEXT PROCESSORS (`apps/dashboard/context_processors.py`)

- `notificacoes_nao_lidas_count` — contagem total para o badge do navbar
- `is_corretor`/`is_aluno`/`is_admin` — booleanos para condicionais no template

---

## 10. FORMULÁRIOS (`apps/dashboard/forms.py`)

| Form | Campos | View |
|---|---|---|
| `RedacaoForm` | titulo, tema, texto | criar/editar redação |
| `AvaliacaoForm` | nota_final, c1..c5 (nota+justificativa), feedback_geral | corrigir |
| `RegisterForm` | username, email, password, password2, tipo | register |
| `UserSettingsForm` | email, cpf, telefone, data_nascimento, avatar | account_settings |

---

## 11. FILAS E TAREFAS

### 11.1 `executar_avaliacao_llm` (`apps/avaliacoes/services.py`)

```python
def executar_avaliacao_llm(redacao_id):
    config = EssayEssayConfig.from_env()
    redacao = Redacao.objects.get(id=redacao_id)
    orquestrador = OrquestradorAvaliacao(config)
    resultado = orquestrador.avaliar(redacao.texto, redacao.tema)
    # Cria Anotacao para cada competência
    for comp in resultado.redacao.competencias:
        Anotacao.objects.create(...)
    # Cria ou atualiza Consolidacao
    atualizar_consolidacao(redacao)
    return resultado
```

### 11.2 `atualizar_consolidacao` (`apps/avaliacoes/services.py`)

- Busca todas `Avaliacao.concluida` da redação
- Calcula nota consolidada (estratégia: média, mediana, ou min_votos)
- Cria/atualiza `Consolidacao`
- Atualiza `redacao.nota_final` e `redacao.feedback_geral`

### 11.3 Tasks Django Q2 (`apps/avaliacoes/tasks.py`)

```python
@async_task
def disparar_avaliacao_llm(redacao_id):
    config = EssayEssayConfig.from_env()
    if not config.use_q2:
        return executar_avaliacao_llm(redacao_id)
```

### 11.4 Notification Helpers (`apps/avaliacoes/notifications.py`)

- `notificar_corretor_humano(redacao, corretor, status)` — cria `Notificacao`
- `notificar_correcao_concluida(redacao)` — notifica aluno que correção terminou

---

## 12. TESTES — Detalhamento

### `test_base_integracao.py` (7 tests)

| Teste | O que verifica |
|---|---|
| `test_criar_redacao_api` | POST `/api/redacoes/` autenticado cria redação |
| `test_listar_redacoes_api` | GET `/api/redacoes/` retorna lista |
| `test_registrar_usuario_api` | POST `/api/register/` cria usuário |
| `test_fazer_login_api` | POST `/api/auth/login/` retorna token |
| `test_criar_avaliacao_api` | POST `/api/avaliacoes/` cria avaliação |
| `test_simular_avaliacao_completa` | Fluxo completo: registro → login → criar redação → submeter → avaliar |
| `test_criar_consolidacao_api` | POST `/api/consolidacoes/` cria consolidação |

### `test_corrigir_lista.py` (7 tests)

| Teste | O que verifica |
|---|---|
| `test_corretor_nao_ve_redacao_recusada` | Redação com `CORRECAO_RECUSADA` não aparece na lista |
| `test_corretor_ve_redacao_apos_renotificacao` | Após `CORRECAO_RESUBMETIDA`, reaparece |
| `test_corretor_ve_suas_redacoes_pendentes` | Redações sem notificação aparecem normalmente |
| `test_corretor_nao_ve_redacao_com_aceite` | Redação com `CORRECAO_ACEITA` não aparece |
| `test_corretor_nao_ve_redacao_de_outro_corretor` | Aceita por outro corretor não aparece |
| `test_corrigir_redirect_anonimo` | GET não autenticado redireciona para login |
| `test_corrigir_redirect_aluno` | GET de aluno redireciona para home |

### `test_resubmeter.py` (5 tests)

| Teste | O que verifica |
|---|---|
| `test_resubmeter_aluno_notifica_proprias_redacoes` | Aluno só vê notificações das suas redações |
| `test_resubmeter_renotifica_corretores_recusados` | Corretor recusado recebe nova `CORRECAO_SOLICITADA` |
| `test_resubmeter_nao_duplica_recusas` | Recusados antigos não geram duplicatas |
| `test_resubmeter_redacao_corrigida_bloqueada` | Redação `CORRIGIDA` não pode ser resubmetida |
| `test_resubmeter_altera_status_em_avaliacao` | Status muda para `EM_AVALIACAO` |

### `test_nav_counts.py` (4 tests)

| Teste | O que verifica |
|---|---|
| `test_corretor_conta_pendentes` | Contagem correta de redações pendentes |
| `test_aluno_conta_redacoes` | Contagem correta de redações do aluno |
| `test_corretor_conta_zero_quando_sem_pendentes` | Zero quando não há pendências |
| `test_aluno_conta_zero_quando_sem_redacoes` | Zero quando não há redações |

---

## 13. PADRÕES E CONVENÇÕES

### 13.1 Código

- **Linguagem:** Python 3.12+, Type hints obrigatórios
- **Estilo:** Ruff (default rules), MyPy (strict opcional)
- **Imports:** `apps.app_name.models import ModelName`
- **Views:** Function-based views (FBV) no dashboard; Class-based views (ViewSets) na API
- **Templates:** Django Template Language, herança via `{% extends "base.html" %}`

### 13.2 Navegação (Templates)

- `base.html` carrega Bootstrap 5.3.7 + Plotly 3.0.1 + Bootstrap Icons
- Navbar usa `{% include "navbar.html" %}` com badge de notificações
- Sidebar incluída condicionalmente (`{% if user.is_authenticated %}`)
- Mensagens flash via `{% if messages %}`

### 13.3 Segurança

- `login_required` e `user_passes_test` decorators em todas as views do dashboard
- `IsAuthenticated` + permissões customizadas na API
- Senhas: hashed via Django auth
- `.env` excluído do repositório (`.gitignore`)
- `python-dotenv` para leitura de env vars

---

## 14. PONTOS DE ATENÇÃO / NOTAS TÉCNICAS

1. **LLM só roda na submissão inicial.** O `resubmeter()` não chama `disparar_avaliacao_llm` nem `executar_avaliacao_llm` — a reavaliação é puramente humana.
2. **Consolidação automática** ocorre quando 2+ avaliações `concluida` existem para a mesma redação (disparada por `atualizar_consolidacao()` chamada após cada `Avaliacao` salva).
3. **Pool de corretores** usa GenericForeignKey para suportar tanto `CorretorLLM` quanto `accounts.Corretor` (humano). No momento, apenas corretores humanos são usados na prática.
4. **Q2** configurado mas `AVALIACAO_USE_Q2=false` por padrão — LLM roda inline.
5. **Tema escuro** é fixo (`[data-bs-theme="dark"]`). Não há toggle.
6. **Plotly** renderiza no cliente (JS) — sem server-side rendering.
7. **Notificações duplicadas:** o `submeter()` cria notificações para todos corretores, independente de preferência de rota. O `resubmeter()` só re-notifica quem recusou.
8. **Corretores sem notificação:** a lista de pendentes mostra redações onde o corretor não tem nenhuma notificação (novas no sistema), mas esconde aquelas com `CORRECAO_RECUSADA`.
9. **`manage.py` e `base.py`** ambos chamam `load_dotenv()` — necessário para pytest captar `.env`.
10. **SQLite removido.** Banco exclusivamente PostgreSQL via Docker (porta 5437).

---

## 15. MÉTRICAS DO PROJETO

| Métrica | Valor |
|---|---|
| **Views (dashboard)** | 25+ (1412 linhas) |
| **Templates** | 33 arquivos HTML |
| **Modelos** | ~20 models em 5 apps |
| **Testes** | 23 (4 arquivos) — todos passando |
| **Dependências Python** | ~30 diretas |
| **Core de domínio** | 9 arquivos Python |
| **Endpoints API** | ~14 ViewSets + views |
| **URLs do dashboard** | 22+ rotas nomeadas |
