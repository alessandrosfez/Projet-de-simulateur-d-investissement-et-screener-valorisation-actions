"""
Constructeurs de graphiques Plotly, indépendants de Dash (pas de callback ici). Ils reçoivent des
résultats déjà calculés par engine.py et des libellés déjà traduits : aucun calcul financier ici.
"""
import plotly.graph_objects as go


def make_bridge_waterfall(steps: list[dict], cfo: float, labels: dict[str, str], cfo_label: str, title: str,
                          value_formatter, dark: bool = False, palette=None) -> go.Figure:
    """Cascade du résultat net au CFO (voir engine.net_income_to_cfo_bridge) : la première barre est le
    résultat net (point de départ absolu), les suivantes des variations, la dernière le CFO publié
    (total). value_formatter met chaque montant en forme pour l'étiquette (abréviation Md/M)."""
    palette = palette or ["#636EFA", "#EF553B", "#00CC96"]
    x = [labels[step["key"]] for step in steps] + [cfo_label]
    y = [step["value"] for step in steps] + [cfo]
    measure = ["absolute"] + ["relative"] * (len(steps) - 1) + ["total"]
    fig = go.Figure(go.Waterfall(
        x=x, y=y, measure=measure,
        text=[value_formatter(v) for v in y], textposition="outside",
        increasing={"marker": {"color": palette[2 % len(palette)]}},
        decreasing={"marker": {"color": palette[1 % len(palette)]}},
        totals={"marker": {"color": palette[0]}},
        connector={"line": {"color": "gray", "dash": "dot"}},
        hovertemplate="%{x}<br>%{text}<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_dark" if dark else "plotly", title=title, showlegend=False,
        margin=dict(t=60, b=40), yaxis=dict(showticklabels=False),
    )
    return fig


def make_benford_chart(observed: dict[int, float], expected: dict[int, float], labels: dict[str, str], title: str,
                       dark: bool = False, palette=None, separators: str | None = None) -> go.Figure:
    """Fréquences observées du premier chiffre (barres) contre la loi de Benford (courbe), en %.
    separators : séparateurs décimal et de milliers de Plotly (« , » en français), None par défaut."""
    palette = palette or ["#636EFA", "#EF553B"]
    digits = sorted(expected)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=digits, y=[observed[d] * 100 if observed[d] is not None else None for d in digits],
        name=labels["observed"], marker_color=palette[0],
        hovertemplate=f"{labels['digit']} %{{x}} : %{{y:.1f}} %<extra>{labels['observed']}</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=digits, y=[expected[d] * 100 for d in digits], name=labels["expected"], mode="lines+markers",
        line=dict(color=palette[1 % len(palette)], width=2),
        hovertemplate=f"{labels['digit']} %{{x}} : %{{y:.1f}} %<extra>{labels['expected']}</extra>",
    ))
    fig.update_layout(
        template="plotly_dark" if dark else "plotly", title=title, xaxis=dict(title=labels["digit"], dtick=1),
        yaxis_title=labels["frequency"], margin=dict(t=60), legend=dict(orientation="h", y=-0.2),
        separators=separators,
    )
    return fig


def make_working_capital_days_chart(years: list, series: dict[str, list], labels: dict[str, str], title: str,
                                    y_title: str, dark: bool = False, palette=None,
                                    separators: str | None = None) -> go.Figure:
    """Évolution des jours de BFR, exercices dans l'ordre chronologique (gauche -> droite). series :
    {indicateur: [valeur ou None par exercice]} ; un None laisse un trou dans la courbe plutôt que de
    la faire passer par 0."""
    palette = palette or ["#636EFA", "#EF553B", "#00CC96", "#AB63FA"]
    fig = go.Figure()
    for i, (metric, values) in enumerate(series.items()):
        dashed = metric == "ccc"
        fig.add_trace(go.Scatter(
            x=years, y=values, mode="lines+markers", name=labels[metric], connectgaps=False,
            line=dict(color=palette[i % len(palette)], width=3 if dashed else 2, dash="dash" if dashed else "solid"),
            hovertemplate=f"{labels[metric]} : %{{y:.0f}}<extra></extra>",
        ))
    fig.update_layout(
        template="plotly_dark" if dark else "plotly", title=title, yaxis_title=y_title,
        margin=dict(t=60), hovermode="x unified", xaxis=dict(type="category"), separators=separators,
    )
    return fig


def empty_figure_with_message(message: str, dark: bool = False) -> go.Figure:
    """Graphique vide avec un message centré, pour un état 'pas encore de données' propre
    plutôt qu'une grille vide qui ressemble à une erreur. Recopié de stock_valuation."""
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark" if dark else "plotly",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        annotations=[dict(
            text=message, xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=13, color="gray"),
        )],
        margin=dict(t=20, b=20, l=20, r=20),
    )
    return fig
