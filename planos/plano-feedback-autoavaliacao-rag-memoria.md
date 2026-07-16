# Plano Adaptado: Sistema de Feedback, Autoavaliação e Memória de Erros

> **Data**: 15/07/2026
> **Baseado no plano original**, adaptado para a arquitetura real do código (incluindo modo subagentes, `admin_feedback` existente, e `auditor_corretor` como campo separado).

---

## Problema Central

O Pluma é **stateless por avaliação**. Cada correção LLM é independente — o prompt é montado do zero com a Base de Conhecimento ENEM estática, sem consultar erros anteriores. Não há memória, RAG, fine-tuning, ou aprendizado contínuo.

A pergunta central: **o agente não deveria apenas consultar uma base de conhecimento sobre o ENEM; ele deveria consultar uma base de conhecimento sobre os próprios erros.**

---

## Diferenças do Plano Original para o Código Real

| # | Diferença | Impacto |
|---|-----------|---------|
| 1 | **Modo subagentes** (`orchestrator_subagentes.py`) existe e não é mencionado no plano original | RAG precisa injetar também em `_executar_subagente()` e `avaliar_com_subagentes()` |
| 2 | **`admin_feedback`** já existe em `Avaliacao` (bom/ruim/vazio) | 2ª fonte de divergência — admin marcar como "ruim" sem reavaliar |
| 3 | **`CorretorLLM.rating`** já existe (0-10) | Usado como peso no ranking de lições |
| 4 | **`PoolCorrecao.revisor_corretor`** existe (consenso entre avaliadores) | `auditor_corretor` é NOVO campo separado (auditar contra erros conhecidos) |
| 5 | **`avaliar_humano()`** na view não chama divergência | Precisa ser adicionado |
| 6 | Pipeline de divergência usa `modelo_llm="humano"` como filtro | Não há modelo separado para avaliação humana |
| 7 | **`_avaliar_competencia()`** não aceita `licoes_bloco` | Precisa adicionar parâmetro |
| 8 | **`_executar_avaliador()`** não aceita `licoes_bloco` | Precisa adicionar parâmetro |

---

## Arquitetura Proposta

```
              Redação
                  │
                  ▼
        Pré-processamento (ferramentas.py + regras)
                  │
                  ▼
     Recuperação de conhecimento (RAG)        ← UMA VEZ por redação
      ├── Matriz ENEM (estática)
      ├── Lições aprendidas (cresce continuamente)
      └── Estratégias de raciocínio
                  │
                  ▼
     Agente(s): um | pool | especialistas | subagentes
                  │
                  ▼
          Agente Auditor (opt-in por pool)   ← Release 2
                  │
                  ▼
      Correção para o usuário
                  │
                  ▼
        Corretor Humano (quando houver)
        OU admin_feedback='ruim'
                  │
                  ▼
     Analisador de Divergências
                  │
      ┌───────────┼───────────┐
      ▼           ▼           ▼
 Base de      Base de      Base de
 Divergências Lições       Regras
                  │
                  └──────────────► alimenta as próximas correções
```

### Pipeline de Injeção nos 4 Modos

```
Modo "um":
  services.py → avaliar_com_um(..., licoes_bloco)
    → _executar_avaliador(..., licoes_bloco)

Modo pool:
  services.py → _processar_avaliacao_pool(..., licoes_bloco)
    → avaliar_com_pool(..., licoes_bloco)
      → N × _executar_avaliador(..., licoes_bloco)

Modo especialistas:
  services.py → _avaliar_modo_especialistas(..., licoes_bloco)
    → avaliar_com_especialistas(..., licoes_bloco)
      → 5 × _avaliar_competencia(..., licoes_bloco)

Modo subagentes:
  services.py → _processar_avaliacao_pool(..., licoes_bloco)
    → avaliar_com_subagentes(..., licoes_bloco)
      → N × _executar_subagente(..., licoes_bloco)
```

**Atenção**: o RAG é executado **UMA VEZ** por redação em `services.py`, antes do roteamento. O bloco de lições formatado é passado como parâmetro para cada função. Em especialistas, o filtro por competência é aplicado no retrieval.

---

## Estratégia de Embedding

**Escolha**: `sentence-transformers` local com modelo `paraphrase-multilingual-MiniLM-L12-v2`

- 384 dimensões, multilíngue (português incluso)
- Sem custo de API
- ~500MB de RAM, inferência ~50-200ms por texto
- Armazenamento: pgvector no PostgreSQL existente
- Singleton class-level lazy loading

---

## Plano de Implementação em 3 Releases

### Release 1 — Captura de Divergências + RAG de Lições

**Objetivo**: Detectar quando IA erra (por comparação humano × IA ou por `admin_feedback='ruim'`), extrair lição automaticamente, e injetar lições relevantes no prompt das próximas correções.

#### Arquivos a criar

| Arquivo | Conteúdo |
|---------|----------|
| `apps/aprendizado/models.py` | `Divergencia`, `LicaoAprendida`, `AplicacaoLicao`, `Regra` |
| `apps/aprendizado/divergencia.py` | `detectar_divergencias()` — compara IA vs humano + varre `admin_feedback='ruim'` |
| `apps/aprendizado/meta_avaliador.py` | `executar_meta_avaliacao()` — chama LLM para analisar divergência e gerar lição |
| `apps/aprendizado/admin.py` | Admin config com inline para divergências |
| `apps/aprendizado/apps.py` | AppConfig |
| `apps/aprendizado/__init__.py` | — |
| `apps/aprendizado/migrations/` | 0001_initial + 0002_pgvector_extension |
| `src/essay_essay/evaluators/embeddings.py` | `EmbeddingService` (singleton, gerar/buscar embeddings) |
| `src/essay_essay/prompts/meta_avaliador.py` | Prompt para o meta-avaliador |

#### Arquivos a alterar

| Arquivo | Mudança |
|---------|---------|
| **`apps/redacoes/views.py`** — `avaliar_humano()` | Após criar `Avaliacao`, chamar `detectar_divergencias(redacao_id, avaliacao_humana_id)` |
| **`apps/avaliacoes/admin.py`** | `save_model()` em `AvaliacaoAdmin`: se `admin_feedback` mudou para `'ruim'`, disparar divergência |
| **`apps/avaliacoes/tasks.py`** | Adicionar `agendar_meta_avaliacao(divergencia_id)` e `executar_meta_avaliacao_job()` |
| **`apps/avaliacoes/services.py`** | `executar_avaliacao_llm()`: carregar RAG de lições ANTES de rotear; passar `licoes_bloco` |
| **`apps/avaliacoes/services.py`** — `_avaliar_modo_especialistas()` | Aceitar e repassar `licoes_bloco` |
| **`apps/avaliacoes/services.py`** — `_processar_avaliacao_pool()` | Aceitar e repassar `licoes_bloco` |
| **`src/essay_essay/evaluators/orchestrator.py`** — `_executar_avaliador()` | Aceitar `licoes_bloco: str = ""`, concatenar ao `sistema` |
| **`src/essay_essay/evaluators/orchestrator.py`** — `avaliar_com_pool()` | Aceitar `licoes_bloco`, repassar |
| **`src/essay_essay/evaluators/orchestrator.py`** — `avaliar_com_um()` | Aceitar `licoes_bloco`, repassar |
| **`src/essay_essay/evaluators/orchestrator_especialistas.py`** — `_avaliar_competencia()` | Aceitar `licoes_bloco`, concatenar ao `sistema` |
| **`src/essay_essay/evaluators/orchestrator_especialistas.py`** — `avaliar_com_especialistas()` | Aceitar `licoes_bloco`, repassar |
| **`src/essay_essay/evaluators/orchestrator_subagentes.py`** — `_executar_subagente()` | Aceitar `licoes_bloco`, concatenar ao `sistema` |
| **`src/essay_essay/evaluators/orchestrator_subagentes.py`** — `avaliar_com_subagentes()` | Aceitar `licoes_bloco`, repassar |
| **`config/settings/base.py`** | Adicionar `apps.aprendizado` em `INSTALLED_APPS` |
| **`pyproject.toml`** | Adicionar `pgvector>=0.3.0`, `sentence-transformers>=3.4.0` |

#### Feature flags

- `PLUMA_CAPTURAR_DIVERGENCIAS` (bool, default true)
- `PLUMA_USAR_RAG_LICOES` (bool, default true)

#### Pipeline de divergência — 2 fontes

**Fonte A — Humano reavalia (POST `/avaliar/humano`):**
```
POST /redacoes/{id}/avaliar/humano
  → cria Avaliacao (modelo_llm="humano")
  → detectar_divergencias(redacao_id, avaliacao_humana_id)
    → busca TODAS Avaliacao IA da redação (modelo_llm != "humano")
    → para cada IA × cada C1-C5:
        se |nota_ia - nota_humano| >= 40:
          cria Divergencia
    → para cada Divergencia:
        agendar_meta_avaliacao(divergencia_id) via Q2
```

**Fonte B — Admin marca como 'ruim' (admin ou API):**
```
Admin altera Avaliacao.admin_feedback = "ruim"
  → save_model() dispara detectar_divergencias_por_feedback(avaliacao_id)
    → busca a redação
    → encontra avaliações IA da mesma redação (se houver)
    → se houver IA: compara e gera divergência
    → se não houver IA: divergência sem nota_ia (origem=admin_feedback)
    → agendar_meta_avaliacao(divergencia_id)
```

#### Schema detalhado dos modelos

**Divergencia** — com campo `origem` adicional:
```python
class Divergencia(models.Model):
    class Origem(models.TextChoices):
        HUMANO_VS_IA = "humano_vs_ia"
        ADMIN_FEEDBACK = "admin_feedback"

    class Status(models.TextChoices):
        PENDENTE       = "pendente"
        ANALISADA      = "analisada"
        LICAO_EXTRAIDA = "licao_extraida"
        IGNORADA       = "ignorada"

    id               = UUIDField(primary_key=True, default=uuid4)
    redacao          = ForeignKey(Redacao)
    avaliacao_humana = ForeignKey(Avaliacao, CASCADE, related_name="divergencias")
    avaliacao_ia     = ForeignKey(Avaliacao, null=True, SET_NULL)
    corretor_llm     = ForeignKey(CorretorLLM, null=True, SET_NULL)

    competencia      = CharField(max_length=2, choices=C1_C5)
    nota_ia          = IntegerField(default=0)
    nota_humano      = IntegerField(default=0)
    diferenca        = IntegerField(default=0)
    origem           = CharField(max_length=20, choices=Origem, default=Origem.HUMANO_VS_IA)

    status           = CharField(choices=Status)
    analise_meta     = JSONField(default=dict)
    licao            = ForeignKey(LicaoAprendida, null=True)
    limiar_utilizado = IntegerField(default=40)
    criada_em / atualizada_em

    constraints:
      unique (avaliacao_humana, competencia, corretor_llm)
      # corretor_llm pode ser None quando origem=admin_feedback (sem IA para apontar)
```

**LicaoAprendida**:
```python
class LicaoAprendida(models.Model):
    class Competencia(models.TextChoices):
        GERAL = "geral"
        C1..C5 = "c1".."c5"

    id          = UUIDField
    competencia = CharField(choices=Competencia, db_index=True)
    corretor_llm = ForeignKey(CorretorLLM, null=True)
    texto_licao = TextField()
    raciocinio_incorreto = JSONField(default=list)
    raciocinio_correto   = JSONField(default=list)
    embedding   = VectorField(dimensions=384, null=True)
    confianca   = FloatField(default=0.0)
    total_aplicacoes = IntegerField(default=0)
    total_acertos    = IntegerField(default=0)
    ativa       = BooleanField(default=True, db_index=True)
    criada_em / atualizada_em
```

**AplicacaoLicao**:
```python
class AplicacaoLicao(models.Model):
    licao             = ForeignKey(LicaoAprendida)
    avaliacao         = ForeignKey(Avaliacao)
    competencia_alvo  = CharField(max_length=10, blank=True)
    resultou_bem      = BooleanField(null=True)
    criada_em

    unique: (licao, avaliacao)
```

**Regra**:
```python
class Regra(models.Model):
    class AcaoTipo(models.TextChoices):
        LIMITAR_NOTA_MAX = "limitar_nota_max"
        LIMITAR_NOTA_MIN = "limitar_nota_min"
        ZERAR_COMPETENCIA = "zerar_competencia"
        BLOQUEAR = "bloquear"

    id          = UUIDField
    competencia = CharField(choices=LicaoAprendida.Competencia)
    titulo      = CharField(max_length=200)
    descricao   = TextField()
    condicao    = JSONField()
    acao_tipo   = CharField(choices=AcaoTipo)
    acao_valor  = IntegerField(default=0)
    licao_origem = ForeignKey(LicaoAprendida, null=True)
    ativa       = BooleanField(default=False)
    criada_em / atualizada_em
```

#### EmbeddingService — Design

```python
class EmbeddingService:
    _model = None  # class-level singleton

    def __init__(self, modelo="paraphrase-multilingual-MiniLM-L12-v2")
    def gerar_embedding(texto) -> list[float]
    def gerar_embedding_lote(textos, batch_size=32) -> list[list[float]]
    def buscar_licoes_similares(texto, top_k=5, competencia=None, confianca_min=0.0) -> list[dict]
    def buscar_licoes_por_competencia(competencia, top_k=3, confianca_min=0.6) -> list[dict]
    def recriar_embeddings_em_lote(batch_size=100) -> int
```

Query pgvector:
```python
from pgvector.django import CosineDistance

LicaoAprendida.objects.filter(ativa=True, embedding__isnull=False)
    .alias(distance=CosineDistance("embedding", embedding_vetor))
    .filter(distance__lte=0.6)
    .order_by("distance")[:top_k]
```

#### Testes

| Arquivo | O que testa |
|---------|-------------|
| `tests_django/test_aprendizado_models.py` | Criar Divergencia (ambas origens), LicaoAprendida, AplicacaoLicao, Regra |
| `tests_django/test_divergencias.py` | `detectar_divergencias()` mockada; divergência IA vs humano; divergência por admin_feedback='ruim' |
| `tests_django/test_rag_licoes.py` | RAG mockado retorna lições similares; formatação do bloco no prompt |
| `tests_django/test_injecao_rag.py` | `licoes_bloco` aparece no system prompt em cada modo (um, pool, especialistas, subagentes) |

---

### Release 2 — Auditor + Regras Pré-LLM

**Objetivo**: Agente auditor opcional que verifica a correção contra erros conhecidos; regras aplicadas antes/depois do LLM.

#### Arquivos a criar

| Arquivo | Conteúdo |
|---------|----------|
| `src/essay_essay/evaluators/orchestrator_auditor.py` | `auditar_correcao()` — agente que verifica correção contra erros conhecidos |
| `src/essay_essay/evaluators/regras.py` | `aplicar_regras(av_domain, resultados_ferramentas, regras_ativas) -> av_domain` |

#### Arquivos a alterar

| Arquivo | Mudança |
|---------|---------|
| **`apps/corretores/models.py`** — `PoolCorrecao` | Adicionar `auditor_corretor = ForeignKey(CorretorLLM, null=True, blank=True, related_name="bancas_como_auditor")` |
| **`src/essay_essay/prompts/templates.py`** | Adicionar classe `PromptAuditor` com sistema + `montar_contexto_auditoria()` |
| **`apps/avaliacoes/services.py`** — `executar_avaliacao_llm()` | Após consolidação/correção, se `pool.auditor_corretor` existir, chamar auditoria |
| **`apps/avaliacoes/services.py`** — `_validar_notas_pos_llm()` | Chamar `aplicar_regras()` no início, antes das validações existentes |
| **`src/essay_essay/evaluators/ferramentas.py`** — `executar_ferramentas()` | Chamar `aplicar_regras()` com regras bloqueantes antes de prosseguir |

#### Feature flags

- Auditor: ativado **apenas quando `PoolCorrecao.auditor_corretor` está configurado** (opcional por banca)
- Regras: controladas pelo campo `Regra.ativa` (default false, exigem revisão manual)

#### Fluxo do auditor

```
Pool configurado com auditor_corretor?
  → SIM: após consolidar/criar avaliação:
    → Monta contexto: redação + avaliação final + lições relevantes
    → Chama LLM auditor com PromptAuditor
    → Resultado: alertas salvos em debug_info da Avaliacao
    → Se alerta crítico: cria Divergencia para revisão humana
  → NÃO: pipeline normal (sem custo adicional)
```

#### Testes

| Arquivo | O que testa |
|---------|-------------|
| `tests_django/test_auditor.py` | Auditor mockado detecta erro conhecido; não acusa falso positivo |
| `tests_django/test_regras.py` | Regra limita C2; regra zera competência; regra bloqueia |
| `tests_django/test_auditor_pool.py` | Auditor configurado executa; sem auditor, não executa |

---

### Release 3 — Raciocínio + Confiança + Inferência

**Objetivo**: RAG de estratégias de raciocínio (não apenas erros); pesos de confiança; inferência automática de regras.

#### Arquivos a criar

| Arquivo | Conteúdo |
|---------|----------|
| `src/essay_essay/evaluators/inferencia_regras.py` | `inferir_regras()` — agrupa lições por padrão e propõe `Regra` nova |

#### Arquivos a alterar

| Arquivo | Mudança |
|---------|---------|
| **`src/essay_essay/evaluators/embeddings.py`** | Modo `raciocinio_only` no retrieval |
| **`src/essay_essay/prompts/templates.py`** | Formatação do bloco de raciocínio (não apenas texto_licao) |
| **`apps/avaliacoes/services.py`** | Feedback loop: `AplicacaoLicao.resultou_bem` recalcula `confianca` |
| **`apps/dashboard/views.py`** | Gráficos: confiança das lições, top-10 aplicadas |
| **`apps/dashboard/charts.py`** | Precisão do RAG ao longo do tempo |

#### Cálculo de confiança

```python
confianca = total_acertos / total_aplicacoes  # se total_aplicacoes > 0

# No retrieval: filtrar por confianca_min
# Lições com total_aplicacoes < 3 têm peso reduzido no ranking
```

#### Testes

| Arquivo | O que testa |
|---------|-------------|
| `tests_django/test_confianca_licoes.py` | Cálculo de confiança; filtro por confiança mínima |
| `tests_django/test_inferencia_regras.py` | Inferência de regras a partir de lições similares |
| `tests_django/test_feedback_loop.py` | `resultou_bem` recalcula confiança corretamente |

---

## Tabela de Validação por Modo

| Modo | Divergência | RAG | Auditor | Regras |
|------|-------------|-----|---------|--------|
| Pool só-IA (2+ LLMs) | ✅ IA vs Humano + admin_feedback | ✅ Único por redação, repassado | ✅ Opt-in por pool | ✅ |
| Pool misto (IA + humano) | ✅ Compara IA individual, ignora Consolidacao | ✅ Idem | ✅ Opt-in | ✅ |
| Especialistas (C1-C5) | ✅ Por competência, vinculado ao agente C_X | ✅ Único, filtrado por competência | ✅ Opt-in | ✅ |
| Subagentes (M2M) | ✅ Vinculado ao subagente | ✅ Único, repassado a _executar_subagente() | ✅ Opt-in | ✅ |
| Só humano (sem IA) | ❌ Sem IA para comparar (só admin_feedback) | ❌ Sem LLM para aplicar lições | ❌ | ✅ |
| Só IA modo "um" | ✅ Se humano reavaliar ou admin_feedback='ruim' | ✅ | ✅ Opt-in | ✅ |

---

## Pontos de Injeção no Pipeline Existente

```
Pipeline futuro (todos os modos):

Redação → executar_ferramentas() → 
  [aplicar_regras() se regras bloqueantes] →
  EmbeddingService.RAG (UMA VEZ) →
  
  modo "um":
    avaliar_com_um(..., licoes_bloco)
      → _executar_avaliador(sistema=KB + licoes_bloco + ferramentas)
  
  modo pool:
    _processar_avaliacao_pool(..., licoes_bloco)
      → avaliar_com_pool(..., licoes_bloco)
        → N × _executar_avaliador(..., licoes_bloco)
  
  modo especialistas:
    _avaliar_modo_especialistas(..., licoes_bloco)
      → avaliar_com_especialistas(..., licoes_bloco)
        → 5 × _avaliar_competencia(..., licoes_bloco)
  
  modo subagentes (dentro de pool):
    → avaliar_com_subagentes(..., licoes_bloco)
      → N × _executar_subagente(..., licoes_bloco)

  → _validar_notas_pos_llm() [incluindo aplicar_regras()]
  → Consolidacao (se pool)
  → [Auditor se configurado]
  → Divergencia (se humano reavaliar ou admin_feedback='ruim')
  → Meta-avaliador (Q2) → LicaoAprendida
```

**Nenhum arquivo existente precisa ser reescrito.** Todos os hooks são aditivos.

---

## Riscos e Mitigações

| Risco | Mitigação |
|---|---|
| **Custo de tokens**: meta-avaliador + auditor = +2 chamadas LLM | Feature flags por pool; auditor só com `auditor_corretor` configurado |
| **Cold start**: zero lições nas primeiras semanas | Seed inicial de ~20 lições sintéticas; RAG desativado até N ≥ 50 |
| **pgvector performance** >100k lições | Índice IVFFlat com probes; particionamento por competência |
| **Embedding: sentence-transformers ~500MB RAM** | Lazy loading singleton; degradação graciosa (RAG vazio se falhar) |
| **Ruído em lições automáticas** | Confiança mínima 60% no retrieval; lições < 3 aplicações têm peso reduzido |
| **admin_feedback sem IA para comparar** | Divergencia com `origem=admin_feedback` e `corretor_llm=null` — meta-avaliador ainda consegue analisar |

---

## Decisões de Design

1. **Embedding**: sentence-transformers local (sem custo de API, offline)
2. **Auditor**: opt-in por `PoolCorrecao.auditor_corretor` (não ativo por padrão)
3. **Entrega**: incremental (Release 1 → 2 → 3)
4. **Armazenamento vetorial**: pgvector no PostgreSQL existente (sem nova infraestrutura)
5. **Meta-avaliação**: assíncrona via Q2 (não bloqueia o fluxo de correção)
6. **Divergencia por competência**: cada linha representa UM par (humano, IA, competência)
7. **NUNCA comparar contra Consolidacao**: comparar sempre contra avaliações IA individuais
8. **RAG executado UMA vez por redação**: o bloco formatado é passado para todos os agentes
9. **admin_feedback como gatilho**: não substitui comparação IA vs humano; ambas as fontes coexistem
10. **`admin_feedback` por agente, não por competência**: o meta-avaliador faz o diagnóstico fino; evita atrito cognitivo do admin
