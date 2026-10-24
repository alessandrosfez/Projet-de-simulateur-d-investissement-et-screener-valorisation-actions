"""
Constructeurs de graphiques Plotly, indépendants de Dash (pas de callback ici). Ils reçoivent des
résultats déjà calculés par engine.py et des libellés déjà traduits : aucun calcul financier ici.
"""
import plotly.graph_objects as go

import chart_theme


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
        template=chart_theme.template(dark), title=title, showlegend=False,
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
        template=chart_theme.template(dark), title=title, xaxis=dict(title=labels["digit"], dtick=1),
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
        template=chart_theme.template(dark), title=title, yaxis_title=y_title,
        margin=dict(t=60), hovermode="x unified", xaxis=dict(type="category"), separators=separators,
    )
    return fig


def make_score_zone_chart(points: list[dict], zones: list[dict], title: str, value_text, dark: bool = False,
                          separators: str | None = None, note: str | None = None) -> go.Figure:
    """Score par exercice posé sur ses zones d'interprétation : une ligne par exercice (le plus récent en
    haut), un point sur le score, des bandes teintées et nommées derrière. On lit d'un coup d'oeil la
    zone de chaque année et la trajectoire, ce que le tableau des ratios ne montre pas.
    points : [{"label", "value", "hollow", "hover"}], hollow pour un score seulement indicatif.
    zones : [{"start", "end", "status", "label"}] dans l'ordre croissant, start ou end None pour une
    zone ouverte ; status est une clé de chart_theme.STATUS. note : sous-titre (sens du point creux)."""
    chrome = chart_theme.CHROME["dark" if dark else "light"]
    values = [point["value"] for point in points]
    bounds = values + [b for zone in zones for b in (zone["start"], zone["end"]) if b is not None]
    pad = (max(bounds) - min(bounds)) * 0.2 or 1.0
    low, high = min(bounds) - pad, max(bounds) + pad
    fig = go.Figure()
    for zone in zones:
        start = low if zone["start"] is None else zone["start"]
        end = high if zone["end"] is None else zone["end"]
        color = chart_theme.STATUS[zone["status"]]
        fig.add_vrect(x0=start, x1=end, fillcolor=color, opacity=0.16 if dark else 0.12, line_width=0, layer="below")
        # Le nom de la zone porte le sens ; la pastille colorée ne fait que le rappeler.
        fig.add_annotation(x=(start + end) / 2, y=1, yref="paper", yanchor="bottom", showarrow=False,
                           text=f"<span style='color:{color}'>●</span> {zone['label']}",
                           font=dict(size=11, color=chrome["muted"]))
        if zone["end"] is not None:
            fig.add_vline(x=zone["end"], line_width=1, line_dash="dot", line_color=chrome["axis"])
    status_of = [next(z["status"] for z in zones if (z["start"] is None or v >= z["start"])
                      and (z["end"] is None or v <= z["end"])) for v in values]
    fig.add_trace(go.Scatter(
        x=values, y=[point["label"] for point in points], mode="lines", showlegend=False, hoverinfo="skip",
        line=dict(color=chrome["axis"], width=1.5),
    ))
    fig.add_trace(go.Scatter(
        x=values, y=[point["label"] for point in points], mode="markers+text", showlegend=False,
        text=[value_text(v) for v in values], textposition="middle right", textfont=dict(size=11, color=chrome["ink"]),
        customdata=[point["hover"] for point in points], hovertemplate="%{customdata}<extra></extra>",
        marker=dict(size=13, symbol=["circle-open" if p["hollow"] else "circle" for p in points],
                    color=[chart_theme.STATUS[s] for s in status_of],
                    line=dict(width=[2.5 if p["hollow"] else 2 for p in points],
                              color=[chart_theme.STATUS[s] if p["hollow"] else chrome["surface"]
                                     for s, p in zip(status_of, points)])),
    ))
    fig.update_layout(
        template=chart_theme.template(dark),
        title=dict(text=title, font=dict(size=14), subtitle=dict(text=note or "", font=dict(size=11, color=chrome["muted"]))),
        xaxis=dict(range=[low, high], zeroline=False, showgrid=False),
        yaxis=dict(type="category", autorange="reversed", showgrid=False, ticklabelstandoff=8),
        height=(150 if note else 130) + 40 * len(points), margin=dict(t=98 if note else 78, l=16, r=24, b=36),
        separators=separators,
    )
    return fig


def make_income_vs_cfo_chart(years: list, net_income: list, cfo: list, labels: tuple[str, str], title: str,
                             value_formatter, unit_labels: tuple[str, str], dark: bool = False, palette=None,
                             separators: str | None = None) -> go.Figure:
    """Résultat net et flux de trésorerie d'exploitation côte à côte, exercices dans l'ordre
    chronologique : un résultat qui dépasse durablement le cash encaissé saute aux yeux. Montants
    abrégés sur l'axe (unit_labels : milliard, million), un None laisse la barre absente plutôt qu'à 0."""
    palette = palette or chart_theme.palette_for(None, dark)
    present = [abs(v) for v in net_income + cfo if v is not None]
    largest = max(present) if present else 0
    divisor, unit = (1e9, unit_labels[0]) if largest >= 1e9 else ((1e6, unit_labels[1]) if largest >= 1e6 else (1.0, ""))
    fig = go.Figure()
    for (name, series), color in zip(zip(labels, (net_income, cfo)), (palette[0], palette[1 % len(palette)])):
        fig.add_trace(go.Bar(
            x=years, y=[v / divisor if v is not None else None for v in series], name=name,
            marker=dict(color=color, cornerradius=4), customdata=[value_formatter(v) for v in series],
            hovertemplate=f"{name} : %{{customdata}}<extra></extra>",
        ))
    fig.update_layout(
        template=chart_theme.template(dark), title=dict(text=title, font=dict(size=14)), barmode="group",
        bargap=0.3, bargroupgap=0.08, xaxis=dict(type="category"), hovermode="x unified",
        yaxis=dict(ticksuffix=f" {unit}" if unit else "", zeroline=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0), margin=dict(t=80, b=40), height=360,
        separators=separators,
    )
    return fig


def empty_figure_with_message(message: str, dark: bool = False) -> go.Figure:
    """Graphique vide avec un message centré, pour un état 'pas encore de données' propre
    plutôt qu'une grille vide qui ressemble à une erreur. Recopié de stock_valuation."""
    fig = go.Figure()
    fig.update_layout(
        template=chart_theme.template(dark),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        annotations=[dict(
            text=message, xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=13, color="gray"),
        )],
        margin=dict(t=20, b=20, l=20, r=20),
    )
    return fig
