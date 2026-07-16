# Plano: Sistema de Agentes IA Configuráveis no Admin

## Arquitetura Geral

```
Novos Modelos (em apps/corretores/models.py):

  Habilidade (habilidades)
    ├── codigo: "C1", "C2"... (único)
    ├── nome: "Domínio da escrita formal"
    ├── criterios_avaliacao: JSON (rubrica detalhada)
    ├── nota_min/max: 0-200
    └── ordem, ativo

  ModeloPrompt (modelos_prompt)
    ├── nome: "Avaliador Detalhado"
    ├── codigo: "avaliador-detalhado" (slug único)
    ├── conteudo: TextField com {{variaveis}}
    ├── versao: int (auto-increment)
    ├── variaveis: JSON (["tema","texto","competencias"])
    └── ativo

  AgenteIA (agentes_ia) ← substitui CorretorLLM
    ├── nome, descricao
    ├── provedor → ProvedorLLM
    ├── modelo, temperatura, max_tokens
    ├── prompt_principal → ModeloPrompt
    ├── prompt_configuracao: JSON (valores das variáveis)
    └── ativo

  HabilidadeAgente (habilidades_agente) ← through M2M
    ├── agente → AgenteIA
    ├── habilidade → Habilidade
    ├── prompt_especifico: TextField (override opcional)
    ├── peso: Float (para nota final)
    └── ordem
```

## Fases de Implementação

### Fase 1 — Modelos e Migrações

Arquivos: `corretores/models.py`, migrations

1. Adicionar `Habilidade`, `ModeloPrompt`, `AgenteIA`, `HabilidadeAgente` em `corretores/models.py`
2. Adicionar FK nullable `agente` em `CorretorLLM` (para migração suave)
3. Adicionar FK nullable `agente` em `PoolCorretor`
4. Criar migration de dados que insere:
   - 5 competências ENEM (C1–C5) como Habilidades
   - 3 templates atuais (Detalhado, Conciso, Mínimo) como ModeloPrompt
   - 1 AgenteIA padrão (OpenAI + gpt-4o + Detalhado + C1–C5)
5. Registrar novos modelos no `admin.py`

### Fase 2 — Dashboard Admin

Arquivos: `dashboard/views.py`, `urls.py`, templates

Novas páginas no `/dashboard/configuracoes/`:

| Rota | Função | Template |
|------|--------|----------|
| `/agentes` | `admin_agentes()` | `admin_agentes.html` |
| `/agentes/adicionar` | `admin_agente_form()` | `admin_agente_form.html` |
| `/agentes/{id}/editar` | `admin_agente_form()` | (mesmo, com dados) |
| `/habilidades` | `admin_habilidades()` | `admin_habilidades.html` |
| `/habilidades/adicionar` | `admin_habilidade_form()` | `admin_habilidade_form.html` |
| `/habilidades/{id}/editar` | `admin_habilidade_form()` | (mesmo) |
| `/prompts` | `admin_prompts()` | `admin_prompts.html` |
| `/prompts/adicionar` | `admin_prompt_form()` | `admin_prompt_form.html` |
| `/prompts/{id}/editar` | `admin_prompt_form()` | (mesmo) |

Características:
- **Agente**: ao selecionar provedor, busca modelos disponíveis via API (já existe)
- **Agente**: ao selecionar prompt, mostra variáveis esperadas; ao selecionar habilidades, mostra checklist com peso e ordem
- **Prompt**: campo texto com highlight de variáveis `{{ }}`, versão auto-increment, botão "testar prompt" (renderiza com dados mock)
- **Habilidade**: JSON editor amigável para critérios

Atualizar `configuracoes.html` com novos cards para Agentes IA, Habilidades e Prompts.

### Fase 3 — API REST

Arquivos: `corretores/views.py`, `serializers.py`, `urls.py`

Endpoints novos:

```
/api/v1/admin/agentes          → AgenteIAViewSet (CRUD)
/api/v1/admin/habilidades      → HabilidadeViewSet (CRUD)
/api/v1/admin/prompts          → ModeloPromptViewSet (CRUD)
/api/v1/admin/prompts/{id}/renderizar  → renderiza prompt com variáveis
/api/v1/admin/agentes/{id}/testar      → testa agente contra uma redação
```

### Fase 4 — Integração com Pipeline de Avaliação

**`src/essay_essay/prompts/templates.py`**:
- Adicionar `carregar_prompt(agente_id) -> str`: busca ModeloPrompt do banco, renderiza variáveis, retorna prompt completo
- Fallback: se não achar no banco, usa os templates hardcoded atuais

**`apps/avaliacoes/services.py`**:
- `_criar_cliente_para_agente()`: cria LLMClient a partir de AgenteIA (pega provedor, modelo, temperatura)
- Atualizar `executar_avaliacao_llm()`: se a Redacao tiver um agente configurado, usa ele; senão, comportamento atual
- O prompt é montado dinamicamente: template principal + skills do agente + rubricas

**`apps/corretores/providers.py`**:
- Adicionar `renderizar_prompt(modelo_prompt, variaveis) -> str`
- Adicionar `testar_agente(agente, redacao_teste) -> dict`

### Fase 5 — Backward Compatibility & Limpeza

- `PoolCorretor` aceita tanto `corretor_llm` quanto `agente`
- Tela de `bancas.html` mostra ambos
- Adicionar "duplicar corretor → agente" no admin (helper)
- Não remover `CorretorLLM` ainda — deixar convivendo por segurança

## Decisões de Design

- **App**: tudo em `apps/corretores` (estende o app existente)
- **Agente substitui CorretorLLM** como entidade principal
- **C1–C5 existentes migrados** como seed data
- **3 prompts existentes migrados** como ModeloPrompt no banco
- Compatibilidade retroativa mantida (FKs nullable)
