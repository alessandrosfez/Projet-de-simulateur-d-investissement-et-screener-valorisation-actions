"""
Constructeurs de graphiques Plotly, indépendants de Dash (pas de callback ici).
"""
import pandas as pd
import plotly.graph_objects as go

import chart_theme


def empty_figure_with_message(message: str, dark: bool = False) -> go.Figure:
    """Graphique vide avec un message centré, pour un état 'pas encore de données' propre
    plutôt qu'une grille vide qui ressemble à une erreur."""
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


def make_football_field(rows: list[dict], labels: dict, colors: dict, price: float | None, price_label: str,
                        title: str, value_text, hover_words: tuple[str, str, str], dark: bool = False,
                        separators: str | None = None) -> go.Figure:
    """« Football field » des banques d'affaires : une barre horizontale par méthode de valorisation,
    du bas au haut de sa fourchette, un trait sur sa valeur centrale, et le cours actuel en trait
    vertical. On lit d'un coup d'oeil si le titre est sous ou sur-évalué selon chaque méthode, et à
    quel point les méthodes s'accordent. rows : voir engine.football_field_ranges ; value_text met un
    montant en forme (devise comprise)."""
    chrome = chart_theme.CHROME["dark" if dark else "light"]
    fig = go.Figure()
    low_word, mid_word, high_word = hover_words
    for row in rows:
        label, color = labels[row["method"]], colors[row["method"]]
        texts = [value_text(row["low"]), value_text(row["mid"]), value_text(row["high"])]
        fig.add_trace(go.Bar(
            y=[label], x=[max(row["high"] - row["low"], 1e-9)], base=[row["low"]], orientation="h",
            width=0.46, marker=dict(color=color, cornerradius=6), showlegend=False, customdata=[texts],
            hovertemplate=(f"<b>{label}</b><br>{low_word} %{{customdata[0]}} · {mid_word} %{{customdata[1]}} · "
                           f"{high_word} %{{customdata[2]}}<extra></extra>"),
        ))
        fig.add_trace(go.Scatter(
            y=[label], x=[row["mid"]], mode="markers", showlegend=False, hoverinfo="skip",
            marker=dict(symbol="line-ns", size=26, line=dict(width=3, color=chrome["ink"])),
        ))
        for x, anchor, shift, text in ((row["low"], "right", -8, texts[0]), (row["high"], "left", 8, texts[2])):
            # Fond de la couleur de la surface : le montant reste lisible quand le trait du cours le croise.
            fig.add_annotation(x=x, y=label, text=text, xanchor=anchor, xshift=shift, showarrow=False,
                               font=dict(size=11, color=chrome["muted"]), bgcolor=chart_theme.surface_color(dark))
    if price:
        fig.add_vline(x=price, line_dash="dash", line_width=2, line_color=chrome["ink"],
                      annotation_text=f"{price_label} : {value_text(price)}", annotation_position="top",
                      annotation_font=dict(size=12, color=chrome["ink"]))
    # Marge explicite de part et d'autre : sans elle, les montants posés aux extrémités des barres
    # débordent sur les libellés des méthodes ou sortent du cadre.
    bounds = [row["low"] for row in rows] + [row["high"] for row in rows] + ([price] if price else [])
    pad = (max(bounds) - min(bounds)) * 0.18 or abs(max(bounds)) * 0.1 or 1
    fig.update_layout(
        template=chart_theme.template(dark), title=dict(text=title, font=dict(size=14)), barmode="overlay",
        yaxis=dict(autorange="reversed", showgrid=False, showline=False, ticklabelstandoff=10),
        xaxis=dict(zeroline=False, range=[min(bounds) - pad, max(bounds) + pad]),
        height=150 + 72 * len(rows), margin=dict(t=80, l=16, r=90, b=40), separators=separators,
    )
    return fig


def make_pe_history_figure(dates, values, current_pe: float | None, low_pe: float, high_pe: float, labels: dict,
                           color: str, title: str, dark: bool = False, separators: str | None = None) -> go.Figure:
    """P/E historique d'un titre posé sur ses zones : sous le 20e percentile de sa propre histoire
    (« décoté », teinte verte), au-dessus du 80e (« tendu », teinte rouge), entre les deux rien. Même
    règle que la couleur du P/E dans le tableau de criblage (layout.CELL_CLASS_RULES), pour que le
    graphique et la case disent la même chose. Le P/E actuel est marqué d'un point au bout de la
    courbe. labels : low_zone, high_zone, mean, current, current_hover (textes déjà mis en forme)."""
    chrome = chart_theme.CHROME["dark" if dark else "light"]
    span = max(values) - min(values) if len(values) else 1.0
    bottom = min(min(values), current_pe or min(values)) - span * 0.06
    top = max(max(values), current_pe or max(values)) + span * 0.06
    fig = go.Figure()
    for y0, y1, status, text, anchor in ((bottom, low_pe, "good", labels["low_zone"], "bottom"),
                                         (high_pe, top, "critical", labels["high_zone"], "top")):
        fig.add_hrect(y0=y0, y1=y1, fillcolor=chart_theme.STATUS[status], opacity=0.14 if dark else 0.1,
                      line_width=0, layer="below")
        fig.add_annotation(xref="paper", x=0.005, y=y0 if anchor == "bottom" else y1, yanchor=anchor, xanchor="left",
                           showarrow=False, font=dict(size=11, color=chrome["muted"]),
                           text=f"<span style='color:{chart_theme.STATUS[status]}'>●</span> {text}")
    fig.add_trace(go.Scatter(x=dates, y=values, mode="lines", line=dict(color=color, width=2), name="P/E",
                             hovertemplate="%{x|%d/%m/%Y} · P/E %{y:.1f}<extra></extra>"))
    fig.add_hline(y=float(sum(values) / len(values)), line_dash="dot", line_width=1.5, line_color=chrome["muted"],
                  annotation_text=labels["mean"], annotation_position="top right",
                  annotation_font=dict(size=11, color=chrome["muted"]))
    if current_pe is not None:
        # Posé à la date du jour, pas sur le dernier point de la courbe : la courbe divise par le BPA
        # annuel publié, le P/E actuel par le BPA des 12 derniers mois, d'où un léger écart possible.
        today = pd.Timestamp.today().normalize()
        fig.add_trace(go.Scatter(
            x=[today], y=[current_pe], mode="markers", showlegend=False,
            hovertemplate=f"{labels['current_hover']}<extra></extra>",
            marker=dict(size=12, color=color, line=dict(width=3, color=chart_theme.surface_color(dark))),
        ))
        fig.add_annotation(x=today, y=current_pe, text=f"<b>{labels['current']}</b>", xanchor="right",
                           xshift=-10, yshift=14, showarrow=False, font=dict(size=12, color=chrome["ink"]),
                           bgcolor=chart_theme.surface_color(dark))
    fig.update_layout(
        template=chart_theme.template(dark), title=dict(text=title, font=dict(size=14)), showlegend=False,
        xaxis=dict(title="", tickformat="%m/%Y"), yaxis=dict(title="P/E", range=[bottom, top]), margin=dict(t=60, r=24),
        separators=separators,
    )
    return fig
