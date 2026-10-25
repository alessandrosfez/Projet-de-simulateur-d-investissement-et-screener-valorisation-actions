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


# Paire divergente de la palette de référence : bleu (corrélation négative) <-> rouge (positive),
# milieu gris neutre (0 = pas de lien), propre à chaque mode.
DIVERGING = {"light": ("#2a78d6", "#f0efec", "#e34948"), "dark": ("#3987e5", "#383835", "#e66767")}


def make_correlation_heatmap(corr: pd.DataFrame, lang="fr", dark: bool = False):
    """Corrélations entre lignes en demi-matrice (la moitié haute répète la basse, la diagonale vaut
    toujours 1) : cases carrées séparées d'un liseré, couleur divergente centrée sur 0, valeur écrite
    dans chaque case avec une encre qui contraste avec son fond."""
    mode = "dark" if dark else "light"
    chrome = chart_theme.CHROME[mode]
    negative, neutral, positive = DIVERGING[mode]
    names = list(corr.columns)
    n = len(names)
    if n < 2:
        fig = go.Figure()
        fig.update_layout(template=chart_theme.template(dark), title=L(lang, "corr_chart_title"))
        return fig
    # Axes au nom court (« PSP5.PA », pas « PSP5.PA (S&P 500) ») : les libellés longs, tournés,
    # mangeaient la hauteur et réduisaient les cases. Le nom complet reste dans l'infobulle.
    short = [str(name).split(" (")[0] for name in names]
    rows, cols = short[1:], short[:-1]
    z = [[corr.iloc[i, j] if j < i else None for j in range(n - 1)] for i in range(1, n)]
    pairs = [[f"{names[i]}<br>{names[j]}" for j in range(n - 1)] for i in range(1, n)]
    fig = go.Figure(go.Heatmap(
        z=z, x=cols, y=rows, zmin=-1, zmid=0, zmax=1, xgap=3, ygap=3, hoverongaps=False, customdata=pairs,
        colorscale=[[0, negative], [0.5, neutral], [1, positive]],
        colorbar=dict(thickness=10, len=0.7, tickvals=[-1, 0, 1], outlinewidth=0,
                      ticktext=["-1", "0", "+1"], tickfont=dict(color=chrome["muted"])),
        hovertemplate="%{customdata}<br>r = %{z:.2f}<extra></extra>",
    ))
    for i, row_name in enumerate(rows):
        for j, col_name in enumerate(cols):
            value = z[i][j]
            if value is None or pd.isna(value):
                continue
            text = f"{value:.2f}".replace(".", ",") if lang == "fr" else f"{value:.2f}"
            # Texte blanc sur une case très colorée, encre normale sur une case pâle.
            fig.add_annotation(x=col_name, y=row_name, text=text, showarrow=False,
                               font=dict(size=12, color="#ffffff" if abs(value) > 0.55 else chrome["ink"]))
    fig.update_layout(
        template=chart_theme.template(dark), title=dict(text=L(lang, "corr_chart_title"), font=dict(size=14)),
        xaxis=dict(showgrid=False, side="bottom"),
        yaxis=dict(showgrid=False, autorange="reversed", scaleanchor="x", ticklabelstandoff=6),
        margin=dict(t=50, l=10, r=10, b=10), height=max(300, 110 + 64 * (n - 1)), separators=L(lang, "plotly_separators"),
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


def make_contribution_plan_figure(labels: list, current_pct: list, after_pct: list, target_pct: list,
                                  amount_texts: list, names: tuple[str, str, str], title: str,
                                  color: str, dark: bool = False, separators: str | None = None):
    """Répartition du prochain versement (portfolio_engine.allocate_contribution) : une ligne par
    ticker, la part actuelle (point creux) reliée à la part après versement (point plein), la cible
    en trait vertical, et le montant à verser à droite. Le chemin parcouru vers la cible se lit d'un
    coup d'oeil, ce qu'un tableau d'écarts en euros ne montre pas. names : (actuel, après, cible)."""
    chrome = chart_theme.CHROME["dark" if dark else "light"]
    current_name, after_name, target_name = names
    fig = go.Figure()
    for label, before, after in zip(labels, current_pct, after_pct):
        fig.add_trace(go.Scatter(x=[before, after], y=[label, label], mode="lines", showlegend=False,
                                 hoverinfo="skip", line=dict(color=hex_to_rgba(color, 0.45), width=3)))
    fig.add_trace(go.Scatter(
        x=current_pct, y=labels, mode="markers", name=current_name,
        marker=dict(symbol="circle-open", size=11, color=chrome["muted"], line=dict(width=2)),
        hovertemplate=f"%{{y}}<br>{current_name} : %{{x:.1f}} %<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=after_pct, y=labels, mode="markers+text", name=after_name, text=amount_texts,
        textposition="middle right", textfont=dict(color=chrome["ink"], size=12),
        marker=dict(size=12, color=color, line=dict(width=2, color=chart_theme.surface_color(dark))),
        hovertemplate=f"%{{y}}<br>{after_name} : %{{x:.1f}} %<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=target_pct, y=labels, mode="markers", name=target_name,
        marker=dict(symbol="line-ns", size=22, line=dict(width=3, color=chrome["ink"])),
        hovertemplate=f"%{{y}}<br>{target_name} : %{{x:.1f}} %<extra></extra>",
    ))
    top = max([*current_pct, *after_pct, *target_pct, 1])
    fig.update_layout(
        template=chart_theme.template(dark), title=dict(text=title, font=dict(size=14)),
        xaxis=dict(range=[0, top * 1.22], ticksuffix=" %", zeroline=False),
        yaxis=dict(type="category", autorange="reversed", showgrid=False, ticklabelstandoff=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
        height=150 + 46 * len(labels), margin=dict(t=90, l=16, r=24, b=40), separators=separators,
    )
    return fig


def make_line_contributions_figure(labels: list, gains: list, texts: list, hovers: list, title: str,
                                   dark: bool = False, separators: str | None = None):
    """Gain ou perte en euros de chaque ligne, barres horizontales partant de 0 : bleu pour un gain,
    rouge pour une perte (paire divergente de la palette de référence ; les couleurs d'état restent
    réservées aux états). Montant et pourcentage écrits au bout de chaque barre."""
    series = chart_theme.SERIES_DARK if dark else chart_theme.SERIES_LIGHT
    gain_color, loss_color = series[0], series[7]
    chrome = chart_theme.CHROME["dark" if dark else "light"]
    fig = go.Figure(go.Bar(
        x=gains, y=labels, orientation="h", text=texts, textposition="outside", cliponaxis=False,
        textfont=dict(color=chrome["ink"], size=12), customdata=hovers, hovertemplate="%{customdata}<extra></extra>",
        marker=dict(color=[gain_color if g >= 0 else loss_color for g in gains], cornerradius=4),
        width=0.55,
    ))
    span = max([abs(g) for g in gains] + [1])
    fig.update_layout(
        template=chart_theme.template(dark), title=dict(text=title, font=dict(size=14)), showlegend=False,
        xaxis=dict(range=[-span * 1.45 if min(gains) < 0 else 0, span * 1.45 if max(gains) > 0 else span * 0.2],
                   ticksuffix=" €", zeroline=True, zerolinecolor=chrome["axis"], zerolinewidth=1.5),
        yaxis=dict(autorange="reversed", showgrid=False, ticklabelstandoff=8),
        height=120 + 44 * len(labels), margin=dict(t=60, l=16, r=24, b=40), separators=separators,
    )
    return fig


def make_dividend_calendar_figure(calendar: pd.DataFrame, first_month, this_month, last_month, labels: dict,
                                  colors: dict, names: tuple[str, str], title: str, today_label: str,
                                  dark: bool = False, separators: str | None = None):
    """Dividendes par mois (portfolio_engine.dividend_calendar), empilés par ligne : perçus en plein,
    estimés hachurés et plus clairs, pour ne jamais confondre un montant encaissé et une estimation
    (texture en plus de la couleur). Trait vertical entre le mois en cours et le suivant. labels /
    colors : par ticker (la couleur suit la ligne, jamais son rang). names : (perçu, estimé)."""
    chrome = chart_theme.CHROME["dark" if dark else "light"]
    received_name, estimated_name = names
    fig = go.Figure()
    for ticker in sorted(calendar["ticker"].unique()):
        for kind, name in (("received", received_name), ("estimated", estimated_name)):
            rows = calendar[(calendar["ticker"] == ticker) & (calendar["kind"] == kind)]
            if rows.empty:
                continue
            estimated = kind == "estimated"
            fig.add_trace(go.Bar(
                x=rows["month"], y=rows["amount_eur"], name=labels[ticker], legendgroup=ticker,
                # Largeur fixe (24 jours, en millisecondes sur un axe de dates) : sinon Plotly la
                # calcule sur l'écart entre deux mois versants (un trimestre) et la barre déborde.
                xperiod="M1", xperiodalignment="middle", width=24 * 86_400_000,
                showlegend=not estimated or calendar[(calendar["ticker"] == ticker) & (calendar["kind"] == "received")].empty,
                marker=dict(color=hex_to_rgba(colors[ticker], 0.55) if estimated else colors[ticker], cornerradius=3,
                            pattern=dict(shape="/" if estimated else "", fgcolor=colors[ticker], size=6, solidity=0.3)),
                hovertemplate=f"{labels[ticker]}<br>%{{x|%m/%Y}} · {name} : %{{y:.2f}} €<extra></extra>",
            ))
    # Entrée de légende qui explique la texture, indépendante des lignes.
    fig.add_trace(go.Bar(x=[None], y=[None], name=estimated_name, hoverinfo="skip",
                         marker=dict(color=hex_to_rgba(chrome["muted"], 0.35),
                                     pattern=dict(shape="/", fgcolor=chrome["muted"], size=6, solidity=0.3))))
    # Chaque barre occupe son mois (xperiod) : le trait passe à la frontière entre le mois en cours
    # (perçu) et le suivant (estimé), sans mordre sur une barre.
    fig.add_vline(x=pd.Timestamp(this_month) + pd.DateOffset(months=1), line_dash="dot", line_width=1.5, line_color=chrome["muted"],
                  annotation_text=today_label, annotation_position="top", annotation_font=dict(color=chrome["muted"], size=11))
    fig.update_layout(
        template=chart_theme.template(dark), title=dict(text=title, font=dict(size=14)), barmode="stack",
        bargap=0.25, xaxis=dict(type="date", tickformat="%m/%Y", dtick="M2", ticklabelmode="period",
                                range=[pd.Timestamp(first_month), pd.Timestamp(last_month) + pd.DateOffset(months=1)]),
        yaxis=dict(ticksuffix=" €", rangemode="tozero"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), margin=dict(t=90, b=40), height=380,
        separators=separators,
    )
    return fig


def make_band_figure(series, years_axis, title, lang="fr", palette=None, invested_capital=None,
                      phase_boundary_years=None, dark: bool = False, backtest_series=None,
                      view_mode="prevision", inner_bands=None):
    """series: liste de (label, median, p_low, p_high) — bandes de percentiles Monte Carlo, tracées
    seulement en mode "prevision" (axe des x en années relatives depuis le début de l'horizon).
    backtest_series : liste optionnelle de (label, dates_bt, values_bt) : croissance brute réellement
    observée (achat unique, base 100, pas de simulation ni d'apports/frais/fiscalité — voir
    results._backtest_trajectory), tracée seulement en mode "historique" sur un axe de vraies dates
    calendaires (ex: 2008-2010), pas sur l'échelle relative de l'horizon de projection. Les deux
    modes sont mutuellement exclusifs sur ce graphique (bascule view-mode-radio) plutôt que
    superposés, pour que le graphique reste lisible et que les deux échelles d'axe (relative vs
    calendaire) ne se mélangent jamais sur le même tracé. inner_bands : liste optionnelle, alignée sur
    series, de (p25, p75) ou None, pour le cœur plus soutenu de l'éventail."""
    palette = palette or PALETTE
    chrome = chart_theme.CHROME["dark" if dark else "light"]
    fig = go.Figure()
    # Étiquettes directes (valeur finale au bout de chaque courbe) jusqu'à 4 séries : au-delà, elles
    # se chevauchent et la légende reste plus lisible.
    direct_labels = view_mode != "historique" and 0 < len(series) <= MAX_DIRECT_LABELS
    # Au-delà de 4 séries, les éventails superposés se brouillent : bande extérieure seule, plus légère.
    crowded = len(series) > MAX_DIRECT_LABELS
    if view_mode == "historique":
        for i, (label, bt_dates, bt_values) in enumerate(backtest_series or []):
            color = palette[i % len(palette)]
            fig.add_trace(go.Scatter(x=bt_dates, y=bt_values, mode="lines",
                                      name=label, line=dict(color=color, width=2)))
    else:
        for i, (label, median, p_low, p_high) in enumerate(series):
            color = palette[i % len(palette)]
            # Éventail en deux épaisseurs : bande choisie (P10-P90 par défaut) claire, cœur P25-P75
            # plus soutenu, médiane épaisse. On lit d'un coup le scénario central et sa dispersion.
            fig.add_trace(go.Scatter(x=years_axis, y=p_high, mode="lines", line=dict(width=0),
                                      showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=years_axis, y=p_low, mode="lines", line=dict(width=0),
                                      fill="tonexty", fillcolor=hex_to_rgba(color, 0.07 if crowded else 0.12),
                                      showlegend=False, hoverinfo="skip"))
            if not crowded and inner_bands and i < len(inner_bands) and inner_bands[i] is not None:
                q25, q75 = inner_bands[i]
                fig.add_trace(go.Scatter(x=years_axis, y=q75, mode="lines", line=dict(width=0),
                                          showlegend=False, hoverinfo="skip"))
                fig.add_trace(go.Scatter(x=years_axis, y=q25, mode="lines", line=dict(width=0),
                                          fill="tonexty", fillcolor=hex_to_rgba(color, 0.22),
                                          showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(
                x=years_axis, y=median, mode="lines", name=label, line=dict(color=color, width=2.5),
                customdata=np.column_stack([p_low, p_high]),
                hovertemplate=f"{label} : %{{y:,.0f}} € (%{{customdata[0]:,.0f}} – %{{customdata[1]:,.0f}})<extra></extra>",
            ))
            if direct_labels:
                fig.add_trace(go.Scatter(x=[years_axis[-1]], y=[median[-1]], mode="markers", showlegend=False,
                                          hoverinfo="skip", marker=dict(size=9, color=color,
                                                                        line=dict(width=2, color=chart_theme.surface_color(dark)))))
                fig.add_annotation(x=years_axis[-1], y=median[-1], text=f"<b>{_compact_eur(median[-1], lang)}</b>",
                                   xanchor="left", xshift=8, showarrow=False, font=dict(size=12, color=chrome["ink"]))
        if invested_capital is not None:
            fig.add_trace(go.Scatter(x=years_axis, y=invested_capital, mode="lines",
                                      name=L(lang, "invested_capital_trace"),
                                      line=dict(color=chrome["muted"], dash="dash", width=1.5),
                                      hovertemplate=f"{L(lang, 'invested_capital_trace')} : %{{y:,.0f}} €<extra></extra>"))
            if direct_labels:
                fig.add_annotation(x=years_axis[-1], y=invested_capital[-1], xanchor="left", xshift=8, showarrow=False,
                                   text=_compact_eur(invested_capital[-1], lang), font=dict(size=11, color=chrome["muted"]))
        if phase_boundary_years is not None:
            fig.add_vline(x=phase_boundary_years, line_dash="dot", line_color=chrome["muted"],
                          annotation_text=L(lang, "withdrawal_start_annotation"), annotation_position="top")
    fig.update_layout(
        template=chart_theme.template(dark),
        title=dict(text=title, font=dict(size=14)),
        xaxis_title=L(lang, "date_axis") if view_mode == "historique" else L(lang, "years_axis"),
        yaxis_title=L(lang, "value_axis_base100") if view_mode == "historique" else L(lang, "value_axis"),
        hovermode="x unified",
        legend=dict(font=dict(size=10), orientation="h", yanchor="top", y=-0.18, x=0),
        margin=dict(t=60, r=96 if direct_labels else 24), separators=L(lang, "plotly_separators"),
    )
    return fig


MAX_DIRECT_LABELS = 4


def _compact_eur(value: float, lang: str) -> str:
    """Montant final écrit au bout d'une courbe : « 470 k€ », « 1,2 M€ » (virgule en français)."""
    if abs(value) >= 1e6:
        text = f"{value / 1e6:.1f} M€"
    else:
        text = f"{value / 1e3:.0f} k€"
    return text.replace(".", ",") if lang == "fr" else text


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
