## Plan: Sistema de Correcao de Redacoes Escalavel

Construir o sistema em fases curtas (MVP -> robustez -> controle de acesso -> escala), aproveitando os ativos ja existentes no repositorio (agentes, prompt de avaliacao, base de conhecimento e historico). A estrategia prioriza valor cedo com API + persistencia primeiro, depois paralelizacao de avaliadores, RBAC e observabilidade.

**Steps**
1. Fase 0 - Fundacao do MVP: definir dominio e contratos de dados (Redacao, Avaliacao, Competencia, Usuario futuro), padronizar formato de saida da avaliacao e criar API minima para envio/consulta de redacoes.
2. Fase 0 - Persistencia inicial: implementar SQLite com migracoes simples, gravando redação, notas por competencia, nota total, metadados de avaliador/modelo/timestamp. *depends on 1*
3. Fase 0 - Orquestracao inicial: encapsular chamada de 1 avaliador (Avaliador 1) com parser resiliente para extrair C1..C5 e total; registrar falhas e retorno de erro claro. *depends on 1,2*
4. Fase 0 - Validacao e testes base: validar entrada (texto ausente, curto, incompleto), criar testes unitarios de parser e teste E2E de envio/correcao/consulta. *depends on 3*
5. Fase 1 - Multiavaliador paralelo: acionar Avaliadores 1/2/3 em paralelo (asyncio), consolidar notas por competencia com regra definida (media/mediana e desvio padrao para confianca). *depends on 4*
6. Fase 1 - Painel e exportacao: adicionar endpoint/listagem para historico, filtros por usuario/periodo/tema e exportacao CSV/JSON para analise. *parallel with 5 after data model stable*
7. Fase 2 - Autenticacao e perfis: implementar login e RBAC (admin, professor, aluno, corretor), restringindo acesso a redacoes e relatorios por papel. *depends on 5,6*
8. Fase 2 - Relatorios por perfil: gerar relatorios por usuario, por competencia e por corretor, incluindo tendencia temporal e distribuicao de notas. *depends on 7*
9. Fase 3 - Escalabilidade: migrar para Postgres, incluir Redis para cache e fila de processamento assíncrono para suportar alto volume com controle de latencia. *depends on 8*
10. Fase 3 - Observabilidade e operacao: instrumentar logs estruturados, metricas (latencia por avaliador, taxa de erro, throughput), alertas e pipeline CI/CD com gates de teste. *depends on 9*

**Relevant files**
- `/mnt/DATA/Dev/python_projetos/essay/plano.md` — documento principal de produto/arquitetura a ser continuado com fases incrementais e criterios de aceite.
- `/mnt/DATA/Dev/python_projetos/essay/main.py` — ponto inicial para orquestracao (hoje stub) do fluxo de avaliacao.
- `/mnt/DATA/Dev/python_projetos/essay/.github/prompts/avaliar-redacao.prompt.md` — contrato de avaliacao (5 competencias, consulta obrigatoria da base, formato de saida).
- `/mnt/DATA/Dev/python_projetos/essay/.github/agents/enem-redacao-avaliador-1.agent.md` — avaliador especializado usado no MVP.
- `/mnt/DATA/Dev/python_projetos/essay/.github/agents/enem-redacao-avaliador-2.agent.md` — segundo avaliador para consenso na Fase 1.
- `/mnt/DATA/Dev/python_projetos/essay/.github/agents/enem-redacao-avaliador-3.agent.md` — terceiro avaliador para robustez estatistica na Fase 1.
- `/mnt/DATA/Dev/python_projetos/essay/base_de_conhecimento/` — corpus de referencia para suporte as avaliacoes.
- `/mnt/DATA/Dev/python_projetos/essay/avaliacoes/` — historico atual de saidas que deve migrar para estrutura consultavel.

**Verification**
1. MVP funcional: enviar redacao e receber JSON com C1..C5 e total em ate 1 chamada, persistindo em banco.
2. Confiabilidade de parser: 100% dos testes com formatos variados de saida (inclusive erros e campos faltantes).
3. Multiavaliador: confirmar execucao paralela de 3 avaliadores com consolidacao e desvio por competencia.
4. Seguranca de acesso: testes de autorizacao cobrindo papeis (aluno nao acessa dados de turma alheia, por exemplo).
5. Escala baseline: teste de carga inicial (ex.: 100/500 requisicoes) com latencia e erro dentro de meta definida.
6. Observabilidade: dashboard de metricas exibindo latencia p95, taxa de erro e volume processado.

**Decisions**
- Incluido no escopo: arquitetura incremental, API, persistencia, multiavaliador, RBAC, relatorios e escalabilidade.
- Excluido neste ciclo de plano: reescrita de UX completa e integracoes externas nao essenciais ao fluxo principal.
- Decisao de arquitetura: comecar simples (SQLite + 1 avaliador) para entregar valor rapido, depois evoluir para Postgres/Redis/fila.
- Decisao de qualidade: manter contrato fixo de saida por competencia para evitar parsing fragil.

**Further Considerations**
1. Consolidacao de notas: recomendacao inicial usar mediana por competencia (mais robusta a outlier) e mostrar media como apoio.
2. SLA de avaliacao: definir meta explicita (ex.: ate 30-60s por redacao em modo multiavaliador) antes da Fase 3.
3. Governanca de prompts/agentes: versionar prompt e agente por release para auditoria e comparabilidade de notas.
