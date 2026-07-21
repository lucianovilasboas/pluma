# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Adicionado

- Nesta seção entram as mudanças ainda não lançadas.
- Ao fazer um release, mova as entradas para a versão correspondente.

## [0.4.0] - 2026-07-20

### Adicionado

- Gestão de turmas CRUD no dashboard (professor e admin): criar, editar, excluir, listar
- Campo `codigo_convite` na Turma (8 caracteres, gerado automaticamente)
- Aluno entra na turma via código (`/entrar-turma/<codigo>`)
- Modal "Entrar em turma" com campo de código no menu do aluno
- Verificação de email: token enviado no registro, ativação via link
- Template `register_success.html` pós-registro
- Chip input com busca textual para adicionar alunos (substitui select múltiplo)
- Checkboxes + remoção em lote de alunos da turma
- Botão Voltar (`history.back()`) nos formulários de: turma, copiloto, atividade, tema, provedor, corretor, skill, ferramenta, membro, agente, prompt, rubrica
- Autocomplete de escola e município (IBGE) no formulário de nova turma

### Modificado

- Registro simplificado: todos os perfis (aluno/professor/corretor) usam mesmo form (nome, email, senha)
- Campos `escola_nome`, `escola_municipio`, `escola_uf`, `turma_*` removidos do registro web e API
- `RegisterForm` unificado: sem campos condicionais por tipo de usuário
- Regra de negócio: 1 aluno = 1 turma, bloqueio de movimentação para admin também
- `alunos_disponiveis` filtrado por `turma__isnull=True` para todos os perfis

### Corrigido

- Bug: formulários individuais de remoção eram engolidos pelo form do batch remove
- Bug: listagem de alunos quebrava com annotations complexas — query simplificada
- Bug: `request.user` com `turma_id` stale ao entrar por código — adicionado `refresh_from_db()`

## [0.3.0] - 2026-07-18

### Adicionado

- Professor ↔ Turma M2M (migration accounts.0003): professores vinculados a múltiplas turmas
- Modelo `AtividadeAvaliativa`: turmas M2M, copiloto SET_NULL/optional, feedback_professor, liberada_em
- Campo `Redacao.atividade` FK (SET_NULL)
- Modelo `CorrecaoCopiloto`: armazena pré-correção LLM por redação
- CRUD completo de copilotos e atividades avaliativas (list, form, delete) com autorização
- Pipeline de pré-correção assíncrona (`disparar_pre_correcao_copiloto` → Q2/thread)
- Página do aluno para submissão por atividade (`atividade_aluno`)
- Fluxo de revisão docente: lista de pendências, tela de revisão com edição de anotações, liberação
- Card de comparação "IA → Prof" na revisão: accordion mostra nota original vs revisada
- Feedback do professor (`feedback_professor` JSON) é lido/escrito nos GET/POST da revisão
- Redações com atividade vinculada redirecionam aluno para `atividade-aluno` e staff para `copiloto-pendentes`
- Lista `minhas_redacoes` filtra atividades (`atividade__isnull=True`)
- Tela unificada de correção para o aluno (sem filtro IA/Humano, sem badges de copiloto)
- Função `renderizar_texto_com_anotacoes` para exibição do texto corrigido com marcações
- Notificação de nova atividade (Notificacao.Tipo.NOVA_ATIVIDADE + migration)
- Notificação por email + in-app ao criar atividade disparam para alunos das turmas
- Badge de pré-correções pendentes no navbar (`pre_correcoes_count` via context_processor)
- Navbar reorganizado em dropdowns com hover (desktop) / click (mobile)
- Turma overview cards com "Criar atividade" (?turma_id= pre-select)
- Cards de atividade com badge de status (Ativa/Encerrada/Aberta), contagem de submissões e stats (enviados/pendentes)
- Destaque visual "card-recente" para atividade mais nova na lista

### Alterado

- `AtividadeAvaliativa.copiloto` FK passa de CASCADE+required para SET_NULL+optional
- Migration 0009 migra dados de FK para M2M em `atividades_avaliativas.turmas`
- Total de alunos conhecidos via `Count("turmas__alunos", distinct=True)`
- Formulários de copilato usam `novalidate` (inputs required dentro de accordion panels)
- Template `copiloto_form.html` usa `|stringformat:"s"` em ambos os lados do UUID compare
- `llm.aclose()` RuntimeError no Q2 worker é logado com `exc_info=True` (não silenciado)
- Tela `atividade_aluno.html` redesign single-column idêntico a `detalhe_redacao.html`

### Corrigido

- LLM JSON extraction failure: `formato_saida` vazio no prompt template — garantido preenchido na base
- `detalhe_redacao` redireciona corretamente com base em `atividade_id`
- `copiloto_revisar` GET lê nota/justificativa/sugestões/comentário de `feedback_professor`
- Total final na revisão usa `total_professor` (soma das notas revisadas)

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
