# Direcionamento: Revisor Humano + Versionamento

> Criado em: 14/07/2026 — Versão 0.1.0
> Status: planejado, não implementado

---

## Parte 1 — Revisor Humano

**Problema:** Hoje `PoolCorrecao.revisor_corretor` é FK exclusiva para `CorretorLLM`. Quando o
desvio entre corretores ultrapassa o `limiar_desvio`, um LLM é chamado para revisar — não existe
a opção de um humano fazer esse papel.

### O que muda

#### Fase 1 — Modelos e Migrações

| Arquivo | Mudança |
|---|---|
| `apps/corretores/models.py` | +`PoolCorrecao.revisor_usuario` (FK → `CustomUser`, nullable, `related_name="bancas_como_revisor_humano"`) |
| `apps/avaliacoes/models.py` | +`Consolidacao.status = "aguardando_revisor"`; +`revisor_usuario` (FK → `CustomUser`, nullable); +`usou_revisor_humano` (`BooleanField`, default=False) |
| `apps/corretores/migrations/` | Nova migração (campo `revisor_usuario` no `PoolCorrecao`) |
| `apps/avaliacoes/migrations/` | Nova migração (campos `revisor_usuario`, `usou_revisor_humano` e choice `aguardando_revisor`) |

#### Fase 2 — Services

| Arquivo | Mudança |
|---|---|
| `apps/avaliacoes/services.py:543` (`_preparar_revisor_se_configurado`) | Renomear para `_preparar_revisor()` — retornar dict com `tipo: "llm"\|"humano"\|None`, dados do cliente LLM, ou ID do usuário humano |
| `apps/avaliacoes/services.py:278` (`atualizar_consolidacao`) | Se revisor é humano e `desvio > limiar`: pular chamada LLM, criar Consolidacao com `status="aguardando_revisor"` e `revisor_usuario=usuario` |

#### Fase 3 — Tasks

| Arquivo | Mudança |
|---|---|
| `apps/avaliacoes/tasks.py:69` (`consolidar_avaliacao_job`) | Após `atualizar_consolidacao()`, se retornou `status="aguardando_revisor"`: criar `Notificacao(REVISAO_SOLICITADA)` para o revisor humano; não marcar `Redacao` como `CORRIGIDA` |

#### Fase 4 — API / Endpoints

| Arquivo | Mudança |
|---|---|
| `apps/avaliacoes/views.py` | +`GET /api/v1/revisoes/pendentes` — lista `Consolidacao` com `status="aguardando_revisor"` e `revisor_usuario=request.user` |
| `apps/avaliacoes/views.py` | +`POST /api/v1/revisoes/{id}/finalizar` — revisor submete notas finais C1-C5 + parecer textual |
| `apps/avaliacoes/serializers.py` | +`RevisaoHumanoSerializer` (c1_nota..c5_nota, c1_justificativa..c5_justificativa, parecer_revisor) |
| `apps/avaliacoes/urls.py` | Novas rotas no router |

#### Fase 5 — Dashboard (Views + Templates)

| Arquivo | Mudança |
|---|---|
| `apps/dashboard/views.py` | +`revisoes_pendentes()` — lista consolidações `aguardando_revisor` do usuário logado |
| `apps/dashboard/views.py` | +`revisar_consolidacao()` — GET: formulário de revisão; POST: salva notas + parecer, finaliza consolidação |
| `apps/dashboard/context_processors.py` | +`revisoes_pendentes_count` no navbar (contagem de revisões pendentes) |
| `apps/dashboard/urls.py` | +Rotas `/revisoes/` e `/revisoes/<id>/revisar/` |
| `apps/dashboard/templates/dashboard/revisoes_pendentes.html` | Lista de consolidações aguardando revisão (tabela com redação, pool, desvios) |
| `apps/dashboard/templates/dashboard/revisar.html` | Formulário: redação original, N avaliações com notas+justificativas lado a lado, desvios destacados visualmente, campos para revisor definir notas finais e parecer |

#### Fase 6 — Notificações

| Arquivo | Mudança |
|---|---|
| `apps/avaliacoes/notifications.py` | +`notificar_revisor_humano(redacao, revisor)` — cria `Notificacao` para o revisor |
| `apps/avaliacoes/models.py` | +`REVISAO_SOLICITADA` e `REVISAO_CONCLUIDA` nos choices de `Notificacao.Status` |

### Fase 7 — Testes (`tests_django/test_revisor_humano.py`)

Grupos de teste:

| Grupo | Cenários |
|---|---|
| A — Modelos | Consolidação aceita status `aguardando_revisor`; PoolCorrecao aceita `revisor_usuario` |
| B — Services | `_preparar_revisor()` retorna tipo correto; `atualizar_consolidacao()` com revisor humano cria status `aguardando_revisor` quando desvio > limiar |
| C — Tasks | `consolidar_avaliacao_job()` notifica revisor humano; não altera status da Redacao para `CORRIGIDA` |
| D — API | `GET /revisoes/pendentes` filtra por revisor; `POST /revisoes/{id}/finalizar` salva notas e finaliza |
| E — Dashboard | Views retornam apenas revisões do usuário logado; submissão do formulário atualiza consolidacao |
| F — Integração | Fluxo completo: LLMs avaliam → desvio alto → revisor humano notificado → revisor finaliza → Redacao `CORRIGIDA` |

### Fluxo final esperado

```
LLMs avaliam → consolidar_avaliacao_job()
    → atualizar_consolidacao()
        → calcula desvios > limiar
        → revisor_humano configurado no pool?
            SIM → Consolidacao.status = "aguardando_revisor"
                → Notificacao(REVISAO_SOLICITADA) para revisor
                → Redacao.status permanece EM_AVALIACAO
                ↓
            [humano acessa /revisoes/, analisa, submete]
                → Consolidacao atualizada com notas do revisor
                → Consolidacao.status = "final"
                → usou_revisor_humano = True
                → parecer_revisor = texto do humano
                → Redacao.status = CORRIGIDA
```

### Decisões de design

- **Revisor humano não corrige do zero.** Ele recebe as N avaliações já feitas (LLM e/ou humanos), os desvios por competência destacados, e decide a nota final.
- **PoolCorrecao aceita apenas UM revisor** (seja LLM via `revisor_corretor` ou humano via `revisor_usuario`) — campos mutuamente exclusivos.
- **Limiar de desvio é o mesmo** para revisor LLM ou humano (campo `limiar_desvio` do pool).
- **Status `aguardando_revisor` é temporário** — se o revisor nunca responder, a redação fica `EM_AVALIACAO` indefinidamente. (Podemos adicionar timeout/expiração depois.)
- **Revisor pode ser qualquer usuário com `user_type="corretor"`** (não precisa de campo `tipo` separado para "revisor").
- **Não altera o fluxo existente para revisor LLM** — se `revisor_corretor` estiver configurado e `revisor_usuario` não, comportamento atual é preservado.

---

## Parte 2 — Versionamento

**Diagnóstico:** `pyproject.toml` declara `version = "0.1.0"` mas o repositório git está vazio
(zero commits). Não há `CHANGELOG.md`, tags, nem qualquer mecanismo de versionamento.

### Proposta: SemVer + Git Tags + Changelog

#### Política de versionamento

| Incremento | Quando usar |
|---|---|
| **MAJOR** (`1.0.0` → `2.0.0`) | Quebra de compatibilidade: API removida/renomeada, migração destrutiva, mudança de schema que exige intervenção manual |
| **MINOR** (`0.1.0` → `0.2.0`) | Nova funcionalidade compatível: revisor humano, agentes configuráveis, novos endpoints |
| **PATCH** (`0.1.0` → `0.1.1`) | Correção de bug, refactor sem mudança de comportamento, ajuste de documentação |

#### Onde a versão vive

- **`pyproject.toml`** → campo `version` (fonte da verdade)
- **Git tags** → `v0.1.0`, `v0.2.0`, etc. (espelho da versão)
- **`CHANGELOG.md`** → histórico de mudanças por versão (formato Keep a Changelog)

**NÃO usar arquivo `VERSION` separado** — manter só no `pyproject.toml` para evitar dessincronização.

#### Conventional Commits obrigatório

Todo commit deve seguir o formato:
```
<tipo>[escopo opcional]: <descrição>

feat: adiciona revisor humano nas consolidações
fix: corrige condição de corrida na fila de avaliação
refactor: extrai _criar_cliente_para_corretor para módulo separado
chore: atualiza dependências
docs: documenta política de versionamento
test: adiciona testes para consolidação unificada
```

#### Processo de release

1. Atualizar `CHANGELOG.md`: mover entradas de `[Unreleased]` para `[X.Y.Z]`
2. `uv run hatch version patch|minor|major` (incrementa `pyproject.toml`)
3. `git add pyproject.toml CHANGELOG.md`
4. `git commit -m "chore: release vX.Y.Z"`
5. `git tag -a vX.Y.Z -m "vX.Y.Z"`
6. `git push && git push --tags`
7. GitHub Actions (`.github/workflows/release.yml`) faz o resto

#### Próximos passos imediatos

- [x] Criar este documento (`planos/direcionamento-revisor-humano-versionamento.md`)
- [ ] Fazer primeiro commit (`git add -A && git commit`)
- [ ] Criar tag `v0.1.0`
- [ ] Criar `CHANGELOG.md` na raiz, documentando o que já existe
- [ ] Criar `.github/workflows/release.yml` para GitHub Release automático
- [ ] Atualizar `AGENTS.md` com seção sobre versionamento

#### Estrutura do `CHANGELOG.md`

```markdown
# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Unreleased]

## [0.1.0] - 2026-07-14

### Added
- Estrutura inicial Django 5.2 + DRF com PostgreSQL
- Apps: accounts (CustomUser UUID), redacoes, avaliacoes, corretores, dashboard
- Core de domínio em `src/essay_essay/`: dataclasses, enums, evaluators LLM
- Orquestrador multi-agente com 3 corretores LLM simulados
- Sistema de consolidação unificada via QCluster
- Prompt templates ENEM (C1-C5, consolidador, templates Detalhado/Conciso/Mínimo)
- Dashboard Bootstrap 5 + Plotly com 25+ views
- API REST com DRF (redações, avaliações, notificações, consolidações)
- 400+ testes automatizados com pytest-django
- Docker Compose com PostgreSQL, web (gunicorn) e worker (qcluster)
```
