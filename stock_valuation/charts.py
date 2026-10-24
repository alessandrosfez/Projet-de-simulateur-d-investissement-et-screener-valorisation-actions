"""
Constructeurs de graphiques Plotly, indépendants de Dash (pas de callback ici).
"""
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
