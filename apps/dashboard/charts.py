from __future__ import annotations

import json

import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder

COMPETENCIAS = [
    "C1 - Norma",
    "C2 - Tema",
    "C3 - Argumentação",
    "C4 - Coesão",
    "C5 - Intervenção",
]


def chart_json(fig: go.Figure) -> str:
    return json.dumps(fig, cls=PlotlyJSONEncoder)


def radar_chart(notas: dict[str, float], title: str = "") -> str:
    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=[notas.get(k, 0) for k in COMPETENCIAS],
            theta=COMPETENCIAS,
            fill="toself",
            name="Notas",
        )
    )
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 200])),
        margin=dict(l=40, r=40, t=30, b=20),
        height=350,
        title=dict(text=title, font=dict(size=14)),
    )
    return chart_json(fig)


def timeline_chart(
    datas: list[str], notas: list[int], title: str = "Evolução das notas",
) -> str:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=datas,
            y=notas,
            mode="lines+markers",
            line=dict(color="#4CAF50", width=3),
            marker=dict(size=10),
            name="Nota total",
        )
    )
    fig.add_hline(
        y=600,
        line_dash="dash",
        line_color="gray",
        annotation_text="Média ENEM",
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
        height=300,
        title=dict(text=title, font=dict(size=14)),
        xaxis_title="Data",
        yaxis_title="Nota total",
    )
    return chart_json(fig)


def histogram_chart(notas: list[int]) -> str:
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=notas, nbinsx=20, marker_color="#636EFA"))
    fig.add_vline(
        x=600,
        line_dash="dash",
        line_color="red",
        annotation_text="ENEM (600)",
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
        height=300,
        title=dict(text="Distribuição das notas", font=dict(size=14)),
        bargap=0.05,
    )
    return chart_json(fig)


def pie_chart(labels: list[str], values: list[int], title: str = "Redações por tema") -> str:
    fig = go.Figure()
    fig.add_trace(go.Pie(labels=labels, values=values))
    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
        height=300,
        title=dict(text=title, font=dict(size=14)),
    )
    return chart_json(fig)


def bar_chart(labels: list[str], values: list[float], title: str = "") -> str:
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=labels,
            y=values,
            marker_color="#636EFA",
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
        height=300,
        title=dict(text=title, font=dict(size=14)),
        xaxis_title="Aluno",
        yaxis_title="Média",
    )
    return chart_json(fig)


ERRO_CORES = {
    "ortografia": "#ef4444",
    "concordancia": "#f97316",
    "pontuacao": "#eab308",
    "coesao": "#a855f7",
    "vocabulario": "#3b82f6",
    "argumentacao": "#ec4899",
    "clareza": "#22c55e",
    "outro": "#94a3b8",
}

ERRO_LABELS = {
    "ortografia": "Ortografia",
    "concordancia": "Concordância",
    "pontuacao": "Pontuação",
    "coesao": "Coesão",
    "vocabulario": "Vocabulário",
    "argumentacao": "Argumentação",
    "clareza": "Clareza",
    "outro": "Outro",
}


def stacked_bar_chart(
    datas: list[str],
    tipos: list[str],
    valores_por_tipo: dict[str, list[int]],
    title: str = "",
) -> str:
    fig = go.Figure()
    for tipo in tipos:
        cor = ERRO_CORES.get(tipo, "#94a3b8")
        label = ERRO_LABELS.get(tipo, tipo)
        fig.add_trace(go.Bar(
            name=label,
            x=datas,
            y=valores_por_tipo.get(tipo, []),
            marker_color=cor,
        ))
    fig.update_layout(
        barmode="stack",
        margin=dict(l=20, r=20, t=30, b=20),
        height=300,
        title=dict(text=title, font=dict(size=14)),
        xaxis_title="Mês",
        yaxis_title="Quantidade de erros",
    )
    return chart_json(fig)


def scatter_chart(
    x_vals: list[int],
    y_vals: list[float],
    labels: list[str],
    title: str = "",
) -> str:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_vals,
        y=y_vals,
        mode="markers+text",
        text=labels,
        textposition="top center",
        marker=dict(size=10, color="#14b8a6", line=dict(width=1, color="#0d9488")),
    ))
    fig.add_hline(
        y=600,
        line_dash="dash",
        line_color="red",
        annotation_text="ENEM (600)",
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
        height=350,
        title=dict(text=title, font=dict(size=14)),
        xaxis_title="Total de erros",
        yaxis_title="Nota média",
    )
    return chart_json(fig)


def timeline_comp_chart(datas: list[str], comp_data: dict[str, list[int]]) -> str:
    """5 linhas (C1-C5) evoluindo ao longo de várias redações."""
    cores_comp = {
        "C1": "#ef4444", "C2": "#f97316", "C3": "#eab308",
        "C4": "#a855f7", "C5": "#22c55e",
    }
    ordem = ["C1", "C2", "C3", "C4", "C5"]
    fig = go.Figure()
    for comp in ordem:
        if comp in comp_data and comp_data[comp]:
            fig.add_trace(
                go.Scatter(
                    x=datas,
                    y=comp_data[comp],
                    mode="lines+markers",
                    name=comp,
                    line=dict(color=cores_comp.get(comp, "#94a3b8"), width=2),
                    marker=dict(size=6),
                )
            )
    fig.add_hline(
        y=120, line_dash="dash", line_color="gray", annotation_text="Mínimo (120)"
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
        height=350,
        title=dict(text="Evolução por Competência", font=dict(size=14)),
        yaxis=dict(range=[0, 200], title="Nota"),
        xaxis=dict(title="Redação"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
    )
    return chart_json(fig)


def fake_wordcloud_chart(words: list[str], sizes: list[int]) -> str:
    """Nuvem de palavras simulada com texto em tamanhos variados."""
    import math

    if not words or max(sizes) == 0:
        return chart_json(go.Figure())

    n = len(words)
    max_s = max(sizes) if sizes else 1
    font_sizes = [12 + (s / max_s) * 36 for s in sizes]
    cores_palavras = [
        "#ef4444", "#f97316", "#eab308", "#a855f7",
        "#3b82f6", "#ec4899", "#22c55e", "#14b8a6",
    ]

    angulos = [i * (2 * math.pi / n) + 0.3 for i in range(n)]
    raios = [0.12 + 0.38 * (i / max(n - 1, 1)) for i in range(n)]

    fig = go.Figure()
    for i in range(n):
        x = 0.5 + raios[i] * math.cos(angulos[i])
        y = 0.5 + raios[i] * math.sin(angulos[i])
        fig.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="text",
                text=[words[i]],
                textfont=dict(
                    size=font_sizes[i],
                    color=cores_palavras[i % len(cores_palavras)],
                ),
                hovertext=[f"{words[i]}: {sizes[i]} ocorrências"],
                hoverinfo="text",
                showlegend=False,
            )
        )

    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        height=350,
        title=dict(
            text="Palavras mais frequentes nas justificativas", font=dict(size=14)
        ),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, 1]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, 1]),
    )
    return chart_json(fig)


def heatmap_chart(
    z: list[list[float]],
    x_labels: list[str],
    y_labels: list[str],
    title: str = "",
) -> str:
    """Heatmap (matriz de calor) — ex.: corretor × competência."""
    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=x_labels,
            y=y_labels,
            colorscale="RdBu",
            zmid=0,
            text=[["{:.0f}".format(v) if v is not None else "" for v in row] for row in z],
            texttemplate="%{text}",
            textfont=dict(size=10),
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
        height=max(250, 40 + 28 * len(y_labels)),
        title=dict(text=title, font=dict(size=14)),
        xaxis=dict(side="top"),
    )
    return chart_json(fig)


CORES_GRUPO = [
    "#3b82f6", "#f97316", "#22c55e", "#a855f7",
    "#ef4444", "#14b8a6", "#ec4899", "#eab308",
]


def _compute_rolling_stats(
    values: list[float], window: int
) -> tuple[list[float], list[float]]:
    means: list[float] = []
    stds: list[float] = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = values[start : i + 1]
        mean = sum(chunk) / len(chunk)
        variance = sum((x - mean) ** 2 for x in chunk) / len(chunk)
        std = variance ** 0.5
        means.append(round(mean, 1))
        stds.append(round(std, 1))
    return means, stds


def timeline_mean_std_chart(
    dates_by_group: dict[str, list[str]],
    values_by_group: dict[str, list[float]],
    window: int = 5,
    title: str = "",
    yaxis_title: str = "Nota",
    yaxis_range: list | None = None,
) -> str:
    fig = go.Figure()

    for idx, (grupo, valores) in enumerate(values_by_group.items()):
        if len(valores) < 2:
            continue

        datas = dates_by_group.get(grupo, [str(i) for i in range(len(valores))])
        cor = CORES_GRUPO[idx % len(CORES_GRUPO)]
        r, g, b = int(cor[1:3], 16), int(cor[3:5], 16), int(cor[5:7], 16)

        means, stds = _compute_rolling_stats(valores, window)
        upper = [means[i] + stds[i] for i in range(len(means))]
        lower = [max(0, means[i] - stds[i]) for i in range(len(means))]

        fig.add_trace(
            go.Scatter(
                x=list(datas) + list(reversed(datas)),
                y=upper + list(reversed(lower)),
                fill="toself",
                fillcolor=f"rgba({r},{g},{b},0.15)",
                line=dict(color="rgba(255,255,255,0)"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

        fig.add_trace(
            go.Scatter(
                x=datas,
                y=means,
                mode="lines",
                line=dict(color=cor, width=2.5),
                name=grupo,
                hovertemplate=(
                    f"<b>{grupo}</b><br>"
                    "Data: %{x}<br>"
                    f"Média móvel (n≤{window}): %{{y:.0f}}<br>"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        margin=dict(l=40, r=20, t=40, b=20),
        height=420,
        title=dict(text=title, font=dict(size=14)),
        xaxis_title="Data",
        yaxis_title=yaxis_title,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )

    if yaxis_range:
        fig.update_yaxes(range=yaxis_range)

    return chart_json(fig)


def barh_chart(
    labels: list[str],
    values: list[float],
    title: str = "",
    color: str = "#14b8a6",
) -> str:
    """Barras horizontais ordenadas (ranking)."""
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=labels,
            x=values,
            orientation="h",
            marker_color=color,
            text=[f"{v:.0f}" for v in values],
            textposition="outside",
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=60, t=30, b=20),
        height=max(200, 30 * len(labels)),
        title=dict(text=title, font=dict(size=14)),
        yaxis=dict(autorange="reversed"),
        xaxis=dict(title=""),
    )
    return chart_json(fig)
