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


def make_correlation_heatmap(corr: pd.DataFrame, lang="fr", dark: bool = False):
    z = corr.values
    fig = go.Figure(data=go.Heatmap(
        z=z, x=list(corr.columns), y=list(corr.columns),
        colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
        text=np.round(z, 2), texttemplate="%{text}",
    ))
    fig.update_layout(
        template="plotly_dark" if dark else "plotly",
        title=L(lang, "corr_chart_title"), margin=dict(t=40, l=10, r=10),
    )
    return fig


def make_band_figure(series, years_axis, title, lang="fr", palette=None, invested_capital=None,
                      phase_boundary_years=None, dark: bool = False, backtest_series=None,
                      view_mode="prevision"):
    """series: liste de (label, median, p_low, p_high) — bandes de percentiles Monte Carlo, tracées
    seulement en mode "prevision" (axe des x en années relatives depuis le début de l'horizon).
    backtest_series : liste optionnelle de (label, dates_bt, values_bt) : croissance brute réellement
    observée (achat unique, base 100, pas de simulation ni d'apports/frais/fiscalité — voir
    results._backtest_trajectory), tracée seulement en mode "historique" sur un axe de vraies dates
    calendaires (ex: 2008-2010), pas sur l'échelle relative de l'horizon de projection. Les deux
    modes sont mutuellement exclusifs sur ce graphique (bascule view-mode-radio) plutôt que
    superposés, pour que le graphique reste lisible et que les deux échelles d'axe (relative vs
    calendaire) ne se mélangent jamais sur le même tracé."""
    palette = palette or PALETTE
    fig = go.Figure()
    if view_mode == "historique":
        for i, (label, bt_dates, bt_values) in enumerate(backtest_series or []):
            color = palette[i % len(palette)]
            fig.add_trace(go.Scatter(x=bt_dates, y=bt_values, mode="lines",
                                      name=label, line=dict(color=color, width=2)))
    else:
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
        template="plotly_dark" if dark else "plotly",
        title=dict(text=title, font=dict(size=14)),
        xaxis_title=L(lang, "date_axis") if view_mode == "historique" else L(lang, "years_axis"),
        yaxis_title=L(lang, "value_axis_base100") if view_mode == "historique" else L(lang, "value_axis"),
        hovermode="x unified",
        legend=dict(font=dict(size=9)),
        margin=dict(t=60),
    )
    return fig


def make_sequence_risk_figure(shock_years, final_values, invested_capital, lang="fr", palette=None,
                               dark: bool = False):
    """Nuage de points : valeur finale du portefeuille (une simulation Monte Carlo = un point) vs
    l'année où le choc de marché a démarré pour cette simulation. Visualise le risque de séquence
    des rendements : un krach précoce dans l'horizon pèse-t-il plus qu'un krach tardif ?"""
    palette = palette or PALETTE
    colors = [palette[0] if v >= invested_capital else palette[1 % len(palette)] for v in final_values]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=shock_years, y=final_values, mode="markers",
        marker=dict(color=colors, size=6, opacity=0.5),
        showlegend=False,
    ))
    fig.add_hline(y=invested_capital, line_dash="dash", line_color="gray",
                  annotation_text=L(lang, "invested_capital_trace"), annotation_position="top left")
    fig.update_layout(
        template="plotly_dark" if dark else "plotly",
        title=L(lang, "sequence_risk_chart_title"),
        xaxis_title=L(lang, "sequence_risk_x_axis"),
        yaxis_title=L(lang, "value_axis"),
        margin=dict(t=60),
    )
    return fig
