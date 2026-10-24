"""
Constructeurs de graphiques Plotly, indépendants de Dash (pas de callback ici).
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

import chart_theme
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
        template=chart_theme.template(dark),
        title=L(lang, "corr_chart_title"), margin=dict(t=40, l=10, r=10),
    )
    return fig


def make_allocation_sunburst(ids: list, labels: list, parents: list, values: list, colors: list,
                             hover_names: list, title: str, value_suffix: str, dark: bool = False,
                             separators: str | None = None):
    """Répartition en « soleil » : au centre le total, anneau intérieur = indices suivis, anneau
    extérieur = lignes détenues, chacune dans une nuance de la couleur de son indice. Remplace les deux
    anneaux séparés (par ligne, par indice) : on voit d'un coup quelles lignes forment un même bloc.
    branchvalues="total" : la valeur d'un indice est la somme de ses lignes, jamais recomptée."""
    surface = chart_theme.surface_color(dark)
    fig = go.Figure(go.Sunburst(
        ids=ids, labels=labels, parents=parents, values=values, customdata=hover_names,
        branchvalues="total", sort=False, insidetextorientation="horizontal",
        marker=dict(colors=colors, line=dict(color=surface, width=2)),
        # Centre : le total seul (son « 100 % » n'apprend rien) ; parts : libellé et part du total.
        texttemplate=["%{label}"] + ["%{label}<br>%{percentRoot:.0%}"] * (len(ids) - 1),
        hovertemplate=f"%{{customdata}}<br>%{{value:,.0f}} {value_suffix}<br>%{{percentRoot:.1%}}<extra></extra>",
    ))
    fig.update_layout(
        template=chart_theme.template(dark), title=dict(text=title, font=dict(size=14)),
        uniformtext=dict(minsize=10, mode="hide"), margin=dict(t=48, b=8, l=8, r=8), height=420,
        separators=separators,
    )
    return fig


def make_sparkline(dates, values, color: str, dark: bool = False):
    """Mini-courbe sans axe ni grille pour une tuile de chiffre clé : seule la forme compte, le
    chiffre lui-même est écrit en grand à côté."""
    fig = go.Figure(go.Scatter(x=dates, y=values, mode="lines", line=dict(color=color, width=2),
                               fill="tozeroy", fillcolor=hex_to_rgba(color, 0.12), hoverinfo="skip"))
    lows = [v for v in values if v is not None]
    fig.update_layout(
        template=chart_theme.template(dark), height=56, margin=dict(t=2, b=2, l=0, r=0), showlegend=False,
        xaxis=dict(visible=False), yaxis=dict(visible=False, range=[min(lows) * 0.98, max(lows) * 1.02] if lows else None),
    )
    return fig


def make_target_vs_actual_rings(labels: list, actual: list, target: list, hover_names: list, colors: list,
                                title: str, actual_name: str, target_name: str, center_text: str,
                                dark: bool = False, separators: str | None = None):
    """Deux anneaux concentriques aux mêmes couleurs : extérieur = répartition actuelle, intérieur =
    répartition cible. Un écart se lit comme un décalage entre les deux anneaux d'une même couleur.
    La légende, partagée par libellé, n'apparaît qu'une fois."""
    surface = chart_theme.surface_color(dark)
    common = dict(labels=labels, customdata=hover_names, sort=False, direction="clockwise",
                  marker=dict(colors=colors, line=dict(color=surface, width=2)),
                  texttemplate="%{percent:.0%}", textposition="inside", insidetextorientation="horizontal")
    fig = go.Figure([
        go.Pie(values=actual, name=actual_name, hole=0.72, domain=dict(x=[0, 1], y=[0, 1]),
               hovertemplate=f"%{{customdata}}<br>{actual_name} : %{{percent:.1%}}<extra></extra>", **common),
        go.Pie(values=target, name=target_name, hole=0.62, domain=dict(x=[0.19, 0.81], y=[0.19, 0.81]),
               hovertemplate=f"%{{customdata}}<br>{target_name} : %{{percent:.1%}}<extra></extra>",
               showlegend=False, **common),
    ])
    fig.update_layout(
        template=chart_theme.template(dark), title=dict(text=title, font=dict(size=14)),
        annotations=[dict(text=center_text, x=0.5, y=0.5, showarrow=False, font=dict(size=12))],
        legend=dict(font=dict(size=11)), uniformtext=dict(minsize=9, mode="hide"),
        margin=dict(t=60, b=20, l=20, r=20), separators=separators,
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
        template=chart_theme.template(dark),
        title=dict(text=title, font=dict(size=14)),
        xaxis_title=L(lang, "date_axis") if view_mode == "historique" else L(lang, "years_axis"),
        yaxis_title=L(lang, "value_axis_base100") if view_mode == "historique" else L(lang, "value_axis"),
        hovermode="x unified",
        legend=dict(font=dict(size=9)),
        margin=dict(t=60),
    )
    return fig


def make_actual_vs_simulated_figure(real_dates, real_values, sim_dates, sim_median, sim_p_low, sim_p_high,
                                     invested_capital, lang="fr", palette=None, dark: bool = False,
                                     purchases=None):
    """Portefeuille réel (courbe pleine, valeur de marché reconstruite depuis les transactions) vs
    ce que le même échéancier de versements aurait donné sous le moteur Monte Carlo existant
    (bande de percentiles) -- les deux sur un axe de vraies dates calendaires. Pas une variante de
    make_band_figure : ses modes "historique"/"prevision" sont volontairement mutuellement
    exclusifs (sémantiques d'axe différentes), alors qu'ici la courbe réelle et la bande simulée
    doivent apparaître ENSEMBLE sur le même axe calendaire -- un besoin différent, pas un troisième
    mode à ajouter à une fonction déjà chargée."""
    palette = palette or PALETTE
    real_color, sim_color = palette[0], palette[1 % len(palette)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sim_dates, y=sim_p_high, mode="lines", line=dict(width=0),
                              showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=sim_dates, y=sim_p_low, mode="lines", line=dict(width=0),
                              fill="tonexty", fillcolor=hex_to_rgba(sim_color, 0.15),
                              showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=sim_dates, y=sim_median, mode="lines", name=L(lang, "simulated_median_trace"),
                              line=dict(color=sim_color, dash="dash")))
    fig.add_trace(go.Scatter(x=real_dates, y=real_values, mode="lines", name=L(lang, "real_equity_trace"),
                              line=dict(color=real_color, width=2.5)))
    # Capital investi en escalier : il ne bouge qu'aux versements, pas entre deux.
    fig.add_trace(go.Scatter(x=sim_dates, y=invested_capital, mode="lines", line_shape="hv",
                              name=L(lang, "invested_capital_trace"),
                              line=dict(color="gray", dash="dot")))
    if purchases:
        # Un point par jour d'achat sur la courbe réelle, taille selon le montant : on lit d'où viennent
        # les marches de la courbe (versements) et ce qui relève du marché (entre deux points).
        dates, values, amounts = zip(*purchases)
        largest = max(amounts) or 1.0
        fig.add_trace(go.Scatter(
            x=list(dates), y=list(values), mode="markers", name=L(lang, "purchase_marker"),
            marker=dict(size=[8 + 10 * a / largest for a in amounts], color=real_color,
                        line=dict(color=chart_theme.surface_color(dark), width=2)),
            customdata=list(amounts), hovertemplate=f"{L(lang, 'purchase_marker')} : %{{customdata:,.0f}} €<extra></extra>",
        ))
    fig.update_layout(
        template=chart_theme.template(dark),
        title=dict(text=L(lang, "real_vs_simulated_chart_title"), font=dict(size=14)),
        xaxis_title=L(lang, "date_axis"), yaxis_title=L(lang, "value_axis"),
        hovermode="x unified", margin=dict(t=70),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1, font=dict(size=11)),
    )
    return fig


def make_pit_histogram(pit_values, title, lang="fr", palette=None, dark: bool = False, n_bins: int = 10):
    """Histogramme des PIT (probability integral transform) d'un backtest walk-forward (voir
    engine.walk_forward_calibration) : si le modèle est bien calibré, les barres doivent être
    proches de la ligne pointillée (hauteur attendue sous une répartition uniforme sur [0, 1]) --
    des barres plus hautes aux extrémités (0 ou 1) signalent des bandes de percentiles trop
    étroites (le réel surprend le modèle trop souvent), des barres plus hautes au centre signalent
    des bandes trop larges (trop prudentes)."""
    palette = palette or PALETTE
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=pit_values, xbins=dict(start=0, end=1, size=1 / n_bins),
        marker_color=palette[0], name=title, showlegend=False,
    ))
    if len(pit_values) > 0:
        expected_count = len(pit_values) / n_bins
        fig.add_hline(
            y=expected_count, line_dash="dash", line_color="gray",
            annotation_text=L(lang, "pit_expected_uniform_line"), annotation_position="top left",
        )
    fig.update_layout(
        template=chart_theme.template(dark),
        title=dict(text=title, font=dict(size=14)),
        xaxis_title=L(lang, "pit_x_axis"), yaxis_title=L(lang, "pit_y_axis"),
        bargap=0.05, margin=dict(t=60),
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
        template=chart_theme.template(dark),
        title=L(lang, "sequence_risk_chart_title"),
        xaxis_title=L(lang, "sequence_risk_x_axis"),
        yaxis_title=L(lang, "value_axis"),
        margin=dict(t=60),
    )
    return fig
