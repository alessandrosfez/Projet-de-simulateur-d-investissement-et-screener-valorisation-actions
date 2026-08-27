"""
Constructeurs de graphiques Plotly, indépendants de Dash (pas de callback ici).
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from i18n import L, PALETTE


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def empty_figure_with_message(message: str) -> go.Figure:
    """Graphique vide avec un message centré, pour un état 'pas encore de données' propre
    plutôt qu'une grille vide qui ressemble à une erreur."""
    fig = go.Figure()
    fig.update_layout(
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        annotations=[dict(
            text=message, xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=13, color="gray"),
        )],
        margin=dict(t=20, b=20, l=20, r=20),
    )
    return fig


def make_correlation_heatmap(corr: pd.DataFrame, lang="fr"):
    z = corr.values
    fig = go.Figure(data=go.Heatmap(
        z=z, x=list(corr.columns), y=list(corr.columns),
        colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
        text=np.round(z, 2), texttemplate="%{text}",
    ))
    fig.update_layout(title=L(lang, "corr_chart_title"), margin=dict(t=40, l=10, r=10))
    return fig


def make_band_figure(series, years_axis, title, lang="fr", palette=None, invested_capital=None,
                      phase_boundary_years=None):
    """series: liste de (label, median, p_low, p_high)."""
    palette = palette or PALETTE
    fig = go.Figure()
    for i, (label, median, p_low, p_high) in enumerate(series):
        color = palette[i % len(palette)]
        fig.add_trace(go.Scatter(x=years_axis, y=p_high, mode="lines", line=dict(width=0),
                                  showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=years_axis, y=p_low, mode="lines", line=dict(width=0),
                                  fill="tonexty", fillcolor=hex_to_rgba(color, 0.15),
                                  showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=years_axis, y=median, mode="lines", name=label,
                                  line=dict(color=color)))
    if invested_capital is not None:
        fig.add_trace(go.Scatter(x=years_axis, y=invested_capital, mode="lines",
                                  name=L(lang, "invested_capital_trace"),
                                  line=dict(color="gray", dash="dash")))
    if phase_boundary_years is not None:
        fig.add_vline(x=phase_boundary_years, line_dash="dot", line_color="gray",
                      annotation_text=L(lang, "withdrawal_start_annotation"), annotation_position="top")
    fig.update_layout(
        title=dict(text=title, font=dict(size=14)),
        xaxis_title=L(lang, "years_axis"),
        yaxis_title=L(lang, "value_axis"),
        hovermode="x unified",
        legend=dict(font=dict(size=9)),
        margin=dict(t=60),
    )
    return fig
