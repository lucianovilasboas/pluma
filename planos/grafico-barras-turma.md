# Restaurar gráfico de barras na tela da turma

## Motivo
O gráfico foi removido temporariamente porque dependia de annotations na query
de listagem que estavam causando bug (alunos não aparecendo). A query foi
simplificada, e o gráfico precisa ser restaurado com query independente.

## Arquivos
- `apps/dashboard/views.py` — adicionar query separada para o chart
- `apps/dashboard/templates/dashboard/turma.html` — restaurar bloco do gráfico

## View (trecho a adicionar após `alunos = ...filter(...).order_by(...)`)

```python
from django.db.models import Q

alunos_stats = alunos.annotate(
    media_nota=Avg(
        "redacoes__avaliacoes__nota_total",
        filter=Q(redacoes__avaliacoes__rascunho=False)
        & Q(redacoes__excluida_em__isnull=True),
    )
).filter(media_nota__isnull=False)

nomes = [a.nome_exibicao for a in alunos_stats]
medias = [float(a.media_nota) for a in alunos_stats]
barras_json = bar_chart(nomes, medias, title="Média dos Alunos") if nomes else None
```

Adicionar `barras_json` de volta ao dicionário de contexto do `render()`.

## Template (substituir onde estava o gráfico)

```django
{% if barras_json %}
<div class="card border-0 shadow-sm mb-3">
  <div class="card-body">
    <div id="barras-chart" style="min-height:320px;visibility:hidden"></div>
  </div>
</div>
<script>
  document.addEventListener("DOMContentLoaded", function() {
    var barras = {{ barras_json|safe }};
    Plotly.newPlot("barras-chart", barras.data, barras.layout, {responsive: true})
      .then(function() {
        document.getElementById("barras-chart").style.visibility = "visible";
      });
  });
</script>
{% endif %}
```

## Vantagens
- Query de chart é independente da query de listagem — se falhar, só o chart some
- `visibility: hidden` evita flicker do Plotly
- `Avg` com `filter` gera `CASE WHEN` otimizado, sem subquery complexa

## Status
Pendente — a implementar em sprint futura.
