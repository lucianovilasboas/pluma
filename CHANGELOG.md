# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Adicionado

- Nesta seção entram as mudanças ainda não lançadas.
- Ao fazer um release, mova as entradas para a versão correspondente.

## [0.2.0] - 2026-07-16

### Adicionado

- Dashboard: professor e admin veem avaliações individuais das IAs na redação do aluno
- Sistema de regras do revisor: desvio_padrão, diferença ENEM (total > 100 OU competência > 80) e personalizada
- UI de configuração de regras na tela de detalhe da banca (select regra_revisor + parâmetros dinâmicos)
- 3 novos arquivos de teste: 47+ testes para regras do revisor, dashboard professor, agente simplificado

### Alterado

- Tela de agente simplificada: skills e ferramentas removidas da UI, prompt + subagentes mantidos
- Fallbacks hardcoded de template removidos — prompts sempre via banco de dados
- Teste do agente agora respeita flags `incluir_base_conhecimento`, `incluir_protocolo_enem` e `output_json`
- Revisor sempre chama o LLM quando a regra é ativada (sem dupla verificação de desvio)
- `parecer_revisor` mais amigável: mostra qual regra foi violada, valores e limites
- Modelo `PoolCorrecao`: novos campos `regra_revisor` e `parametros_revisor`
- `output_json=False` não adiciona bloco de formato de saída no prompt
- Labels "Tema:" → "Título:" nos templates, fallback padronizado para "—" quando vazio
- Campos de nota (C1-C5) com step=40 nos formulários de correção
- Mensagens de notificação sem "sobre ''" quando tema vazio
- Foco do mouse não é mais roubado por JavaScript nas telas de correção

## [0.1.0] - 2026-07-15

### Adicionado

- Estrutura inicial Django 5.2 + DRF com PostgreSQL
- App `accounts`: CustomUser com UUID, email como USERNAME_FIELD, user_type (admin/professor/aluno/corretor)
- App `redacoes`: cadastro de redações, upload de texto, status (EM_AVALIACAO, CORRIGIDA, etc.)
- App `avaliacoes`: avaliações de redação com 5 competências ENEM (C1-C5), notas 0-200, consolidação unificada via QCluster
- App `corretores`: provedores LLM (CorretorLLM), pool de correção com config de corretores e limiar de desvio
- App `dashboard`: templates Bootstrap 5 + Plotly com 25+ views (home, redações, avaliações, consolidações, notificações)
- Core de domínio em `src/essay_essay/domain/`: dataclasses, enums para avaliação ENEM
- Evaluators LLM em `src/essay_essay/evaluators/`: cliente OpenAI, orquestrador multi-agente com 3 corretores
- Prompt templates ENEM em `src/essay_essay/prompts/`: templates C1-C5, consolidador (Detalhado/Conciso/Mínimo)
- API REST com DRF: `/api/v1/redacoes`, `/api/v1/avaliacoes`, `/api/v1/notificacoes`, `/api/v1/consolidacoes`
- Sistema de notificações com Notificacao model e dashboard integrado
- Fila de avaliação assíncrona com django-q2 (configurável via env var `AVALIACAO_USE_Q2`)
- Docker Compose: PostgreSQL (porta 5437), web (gunicorn), worker (qcluster), entrada Traefik/Let's Encrypt
- Dockerfile multi-estágio com uv, sem dev deps em produção
- Actions CI: `uv sync` → `manage.py check` → `pytest --cov`
- 400+ testes automatizados com pytest-django, APIClient, force_authenticate
- MCP server `mcp-brasil` integrado (consultas a dados públicos brasileiros)
- Config de lint/typecheck: Ruff (line-length=100, py312), mypy strict (excluindo tests/)
- Agentes `.github/agents/`: 5 agentes ENEM (avaliadores 1-3, data-analyst, programming-coach)
- Skills `.github/skills/`: run-tests e run-python
- Sistema de versionamento: SemVer + Conventional Commits + CHANGELOG + GitHub Release automático
