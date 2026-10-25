"""
Helpers partagés par les deux onglets de simulation (par indice / portefeuille
pondéré) : construction des apports, agrégation des métriques Monte Carlo en
figures et tableaux, comparaison PEA vs CTO.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import dcc, html

from constants import PEA_TAX_RATE
from engine import (
    apply_fee, apply_social_tax, cap_schedule, compute_objective_contribution, constant_schedule,
    overflow_schedule, progressive_schedule, returns_to_dca, rolling_backtest_final_values, summarize,
    summarize_historique, to_display_values, withdrawal_schedule,
)
from charts import MAX_DIRECT_LABELS, make_actual_vs_simulated_figure, make_band_figure, make_sparkline
import chart_theme
from i18n import L, PALETTE


def build_schedules(horizon_years, enable_decumulation, decumulation_years, withdrawal_monthly,
                     inflation_pct, apport_constant, apport_initial, apport_final, pea_cap=None):
    """pea_cap : plafond légal des versements PEA (150 000 €) à appliquer aux échéanciers, ou None
    pour ne pas plafonner (CTO, ou utilisateur qui a décoché l'option — voir engine.cap_schedule).
    Renvoie aussi overflow_schedules (même clés que schedules) : la part des versements qui
    dépasse ce plafond (engine.overflow_schedule), à tableaux de zéros quand pea_cap est None —
    utile pour simuler la suite des versements sur un CTO une fois le PEA plein (voir
    compute_results, paramètre overflow_schedules)."""
    n_months_accum = horizon_years * 12
    n_months_decum = decumulation_years * 12 if enable_decumulation else 0
    n_months = n_months_accum + n_months_decum
    years_axis = np.arange(n_months) / 12
    phase_boundary_years = horizon_years if enable_decumulation else None

    withdrawals = withdrawal_schedule(n_months_decum, withdrawal_monthly, inflation_pct)
    schedules = {}
    overflow_schedules = {}
    for strat_name, accum in [
        ("constant", constant_schedule(n_months_accum, apport_constant)),
        ("progressive", progressive_schedule(n_months_accum, apport_initial, apport_final)),
    ]:
        schedule = np.concatenate([accum, -withdrawals]) if enable_decumulation else accum
        schedules[strat_name] = cap_schedule(schedule, pea_cap) if pea_cap else schedule
        overflow_schedules[strat_name] = overflow_schedule(schedule, pea_cap) if pea_cap else np.zeros_like(schedule)
    return n_months, years_axis, phase_boundary_years, schedules, overflow_schedules


def _backtest_trajectory(historical_returns, anchor_date=None):
    """Croissance brute réellement observée (achat unique, "buy & hold"), base 100 au premier point
    de la fenêtre : le mode historique répond à "qu'a fait le marché ?", pas à "combien aurais-je
    accumulé avec tel plan d'apport ?" — apports, frais, fiscalité et retraits sont des réglages de
    planification hors-sujet ici (masqués dans la sidebar, voir layout.toggle_prevision_only) et ne
    sont donc plus appliqués à cette trajectoire.

    Par défaut (anchor_date=None), la fenêtre est tout l'historique de calibration téléchargé
    (lookback_years), jusqu'à aujourd'hui. Si anchor_date est fourni (ex: "2008-01-01"), la fenêtre
    démarre à cette date réelle à la place ("qu'a fait le marché depuis ce point précis ?") :
    `historical_returns` doit alors être un pd.Series avec un DatetimeIndex, pas un tableau brut.

    Renvoie les vraies dates calendaires de l'historique (pas des années relatives 0..horizon) :
    le mode historique doit se lire comme "qu'est-ce qui s'est passé en 2008-2010 ?", pas comme une
    projection simplement décalée dans le temps."""
    if anchor_date is not None:
        historical_returns = historical_returns[historical_returns.index >= pd.Timestamp(anchor_date)]
    if len(historical_returns) == 0:
        return None
    returns_arr = np.asarray(historical_returns)
    growth = 100 * np.cumprod(1 + returns_arr)
    return historical_returns.index, growth, summarize_historique(returns_arr)


def compute_results(items, years_axis, schedules, annual_fee_pct, apply_tax, tax_rate, inflation_pct,
                     display_real, lower_pct, upper_pct, enable_decumulation, phase_boundary_years,
                     lang="fr", palette=None, dark=False, backtest_items=None, backtest_anchor_date=None,
                     view_mode="prevision", overflow_schedules=None, cto_tax_rate=None):
    """items: liste de (label, monthly_returns (n_sims, n_months)). all_metrics est indexé par le
    tuple (label, strat_name) : strat_name est une clé stable ("constant"/"progressive"), traduite
    uniquement à l'affichage. backtest_items : liste optionnelle de (label, rendements_historiques),
    même labels que items ; si backtest_anchor_date est fourni, chaque série doit être un pd.Series
    avec un DatetimeIndex (voir _backtest_trajectory). En mode historique (view_mode="historique"),
    la trajectoire réellement observée remplace entièrement la bande de percentiles (croissance
    brute base 100, sans apports/frais/fiscalité — voir _backtest_trajectory). Renvoie en plus
    historique_metrics : {label: dict} des statistiques de cette trajectoire réelle (rendement
    annualisé, volatilité, max drawdown... voir engine.summarize_historique), vide si
    backtest_items n'est pas fourni.

    overflow_schedules (optionnel, mêmes clés que schedules, voir build_schedules) : quand fourni,
    la part des versements qui dépasse le plafond PEA est simulée en plus (mêmes rendements
    mensuels, donc même instrument sous-jacent) et imposée au taux cto_tax_rate (CTO) au lieu de
    tax_rate (PEA), puis additionnée à la valeur et au capital investi PEA avant les métriques —
    pour représenter la richesse totale réelle d'une stratégie "PEA jusqu'au plafond, puis CTO en
    complément" plutôt que de simplement arrêter les versements au plafond. None (par défaut) :
    comportement inchangé, pas de CTO complémentaire."""
    all_metrics = {}
    series_by_strategy = {name: [] for name in schedules}
    inner_by_strategy: dict = {}
    invested_by_strategy = {}

    for label, monthly_returns in items:
        for strat_name, schedule in schedules.items():
            net_returns = apply_fee(monthly_returns, annual_fee_pct)
            portfolio_value, invested_capital = returns_to_dca(net_returns, schedule)
            portfolio_value = apply_social_tax(portfolio_value, invested_capital, apply_tax, tax_rate)

            if overflow_schedules is not None and np.any(overflow_schedules[strat_name] > 0):
                overflow_value, overflow_invested = returns_to_dca(net_returns, overflow_schedules[strat_name])
                overflow_value = apply_social_tax(overflow_value, overflow_invested, apply_tax, cto_tax_rate)
                portfolio_value = portfolio_value + overflow_value
                invested_capital = invested_capital + overflow_invested

            portfolio_value, invested_capital = to_display_values(
                portfolio_value, invested_capital, years_axis, inflation_pct, display_real
            )
            all_metrics[(label, strat_name)] = summarize(
                portfolio_value, invested_capital, net_returns, lower_pct, upper_pct, enable_decumulation,
            )
            invested_by_strategy[strat_name] = invested_capital

            median = np.percentile(portfolio_value, 50, axis=0)
            p_low = np.percentile(portfolio_value, lower_pct, axis=0)
            p_high = np.percentile(portfolio_value, upper_pct, axis=0)
            series_by_strategy[strat_name].append((label, median, p_low, p_high))
            inner_by_strategy.setdefault(strat_name, []).append(_inner_band(portfolio_value, lower_pct, upper_pct))

    backtest_series_by_strategy = {name: [] for name in schedules}
    historique_metrics = {}
    if backtest_items:
        backtest_map = dict(backtest_items)
        for label, _ in items:
            hist_returns = backtest_map.get(label)
            if hist_returns is None or len(hist_returns) == 0:
                continue
            result = _backtest_trajectory(hist_returns, anchor_date=backtest_anchor_date)
            if result is None:
                continue
            bt_dates, bt_values, bt_metrics = result
            historique_metrics[label] = bt_metrics
            for strat_name in schedules:
                backtest_series_by_strategy[strat_name].append((label, bt_dates, bt_values))

    figs = {}
    for strat_name, series in series_by_strategy.items():
        if view_mode == "historique":
            # Un seul graphique affiché en mode historique (voir callbacks/par_indice.py) : pas besoin d'un
            # titre "Apport constant/progressif" qui n'a de sens que pour comparer deux stratégies
            # d'apport côte à côte, le H5 au-dessus du graphique porte déjà "Trajectoire historique".
            title = ""
        else:
            strat_display = L(lang, f"schedule_{strat_name}")
            # Le cœur P25-P75 n'est tracé que s'il tient dans la bande et qu'il y a au plus 4 séries.
            with_inner = len(series) <= MAX_DIRECT_LABELS and lower_pct < 25 and upper_pct > 75
            subtitle = L(lang, "band_subtitle_inner" if with_inner else "band_subtitle", lower=lower_pct, upper=upper_pct)
            title = f"{strat_display}<br><sup>{subtitle}</sup>"
        figs[strat_name] = make_band_figure(
            series, years_axis, title,
            lang=lang, palette=palette,
            invested_capital=invested_by_strategy.get(strat_name),
            phase_boundary_years=phase_boundary_years,
            dark=dark,
            backtest_series=backtest_series_by_strategy.get(strat_name),
            view_mode=view_mode, inner_bands=inner_by_strategy.get(strat_name),
        )
    return all_metrics, figs, series_by_strategy, historique_metrics


def _inner_band(portfolio_value, lower_pct, upper_pct):
    """Cœur de l'éventail (P25-P75), seulement s'il tient à l'intérieur de la bande choisie par
    l'utilisateur : avec une bande P30-P70, un cœur P25-P75 déborderait et se lirait à l'envers."""
    if lower_pct >= 25 or upper_pct <= 75:
        return None
    return np.percentile(portfolio_value, 25, axis=0), np.percentile(portfolio_value, 75, axis=0)


def build_sequence_risk_series(monthly_returns, schedule, annual_fee_pct, apply_tax, tax_rate,
                                shock_start_months):
    """Apparie la valeur finale du portefeuille, pour chaque simulation, au mois où le choc de
    marché a démarré pour cette simulation (nécessite un timing de choc aléatoire par simulation,
    voir engine.inject_shock). Visualise le risque de séquence des rendements : un krach précoce
    dans l'horizon pèse-t-il plus qu'un krach tardif sur le résultat final ?"""
    net_returns = apply_fee(monthly_returns, annual_fee_pct)
    portfolio_value, invested_capital = returns_to_dca(net_returns, schedule)
    portfolio_value = apply_social_tax(portfolio_value, invested_capital, apply_tax, tax_rate)
    shock_years = np.asarray(shock_start_months) / 12
    return shock_years, portfolio_value[:, -1], float(invested_capital[-1])


def build_metric_cards(all_metrics, series_by_strategy, apply_tax, tax_rate, lang="fr", route_overflow=False):
    blocks = []
    if apply_tax:
        blocks.append(html.Small(
            L(lang, "tax_net_note", rate=tax_rate * 100),
            className="text-muted d-block mb-2",
        ))
    if route_overflow:
        blocks.append(html.Small(
            L(lang, "overflow_note"),
            className="text-muted d-block mb-2",
        ))
    for strat_name, series in series_by_strategy.items():
        cards = []
        width = max(12 // max(len(series), 1), 3)
        for label, median, p_low, p_high in series:
            m = all_metrics[(label, strat_name)]
            gain = m["median"] - m["invested"]
            color = "success" if gain >= 0 else "danger"
            cards.append(dbc.Col(dbc.Card(dbc.CardBody([
                html.H6(label, className="card-subtitle text-muted mb-1"),
                html.H5(f"{m['median']:,.0f} €".replace(",", " "), className="mb-1"),
                html.P(f"{gain:+,.0f} €".replace(",", " "), className=f"text-{color} mb-1"),
                html.Small(f"{L(lang, 'prob_gain_prefix')}{_num(m['prob_gain'], '.1f', lang)} %", className="text-muted"),
            ]), className="h-100"), width=width, className="mb-2"))
        blocks.append(html.Div([html.H6(L(lang, f"schedule_{strat_name}"), className="mt-3"), dbc.Row(cards)]))
    return blocks


def build_envelope_comparison_figure(items, pea_schedules, cto_schedules, annual_fee_pct, inflation_pct,
                                      display_real, years_axis, cto_tax_rate, lang="fr", palette=None, dark=False):
    """Compare, pour chaque item/stratégie déjà simulé, la valeur finale médiane nette sous PEA
    (17,2 %) et sous CTO (taux fourni, flat tax ou barème + prélèvements sociaux). Réutilise les
    rendements déjà simulés : pas de nouvelle simulation Monte Carlo, juste deux fiscalités appliquées
    au même tirage aléatoire.

    pea_schedules et cto_schedules sont deux échéanciers distincts (mêmes clés de stratégie
    "constant"/"progressive") plutôt qu'un seul partagé : le CTO n'a pas de plafond légal de
    versements, contrairement au PEA (voir engine.cap_schedule) — leur donner le même échéancier
    plafonné sous-estimerait silencieusement la branche CTO de la comparaison dès que le plafond
    PEA est actif."""
    palette = palette or PALETTE
    labels, pea_values, cto_values = [], [], []
    for label, monthly_returns in items:
        for strat_name in pea_schedules:
            net_returns = apply_fee(monthly_returns, annual_fee_pct)
            pea_portfolio_value, pea_invested = returns_to_dca(net_returns, pea_schedules[strat_name])
            cto_portfolio_value, cto_invested = returns_to_dca(net_returns, cto_schedules[strat_name])
            pea_value = apply_social_tax(pea_portfolio_value, pea_invested, True, PEA_TAX_RATE)
            cto_value = apply_social_tax(cto_portfolio_value, cto_invested, True, cto_tax_rate)
            pea_value, _ = to_display_values(pea_value, pea_invested, years_axis, inflation_pct, display_real)
            cto_value, _ = to_display_values(cto_value, cto_invested, years_axis, inflation_pct, display_real)
            labels.append(f"{label} : {L(lang, f'schedule_{strat_name}')}")
            pea_values.append(float(np.percentile(pea_value[:, -1], 50)))
            cto_values.append(float(np.percentile(cto_value[:, -1], 50)))

    fig = go.Figure()
    fig.add_trace(go.Bar(name=L(lang, "pea_trace_label", rate=PEA_TAX_RATE * 100), x=labels, y=pea_values, marker_color=palette[0]))
    fig.add_trace(go.Bar(name=L(lang, "cto_trace_label", rate=cto_tax_rate * 100), x=labels, y=cto_values, marker_color=palette[1 % len(palette)]))
    fig.update_layout(
        template=chart_theme.template(dark),
        title=L(lang, "envelope_compare_title"),
        barmode="group", xaxis_title="", yaxis_title=L(lang, "value_axis"),
        margin=dict(t=60, b=120), xaxis=dict(tickangle=-30),
    )
    return fig


METRIC_DEFS = [
    ("invested", "metric_invested", "currency", False),
    ("median", "metric_median", "currency", False),
    ("p_low", "metric_p_low", "currency", True),
    ("p_high", "metric_p_high", "currency", True),
    ("prob_gain", "metric_prob_gain", "percent", False),
    ("volatility", "metric_volatility", "percent", False),
    ("sharpe", "metric_sharpe", "ratio", False),
    ("max_drawdown", "metric_max_drawdown", "percent", False),
    ("prob_ruin", "metric_prob_ruin", "percent", False),
]


def build_metrics_outputs(all_metrics: dict, lang: str, lower_pct: float, upper_pct: float):
    """all_metrics: {(label, strat_name): metrics_dict (clés stables, voir engine.summarize())}.
    Renvoie (table_data, table_columns, csv_data, tooltip_header) : la table affichée est
    traduite/formatée dans `lang`, le CSV exporte les mêmes libellés mais avec des valeurs
    numériques brutes, et tooltip_header alimente le survol (ⓘ) des en-têtes de colonnes
    (Sharpe, drawdown...) via le prop natif DataTable.tooltip_header."""
    has_ruin = any("prob_ruin" in m for m in all_metrics.values())
    col_defs = [
        (key, L(lang, label_key, pct=(f"{lower_pct:g}" if key == "p_low" else f"{upper_pct:g}") if needs_pct else None), fmt)
        for key, label_key, fmt, needs_pct in METRIC_DEFS
        if key != "prob_ruin" or has_ruin
    ]
    scenario_label = L(lang, "col_scenario")

    rows_raw = []
    for (label, strat_name), m in all_metrics.items():
        row = {scenario_label: f"{label} : {L(lang, f'schedule_{strat_name}')}"}
        for key, col_label, _ in col_defs:
            row[col_label] = m.get(key)
        rows_raw.append(row)
    raw_df = pd.DataFrame(rows_raw)

    display_df = raw_df.copy()
    for _, col_label, fmt in col_defs:
        if fmt == "currency":
            display_df[col_label] = raw_df[col_label].map(lambda v: f"{v:,.0f} €".replace(",", " "))
        elif fmt == "percent":
            display_df[col_label] = raw_df[col_label].map(lambda v: f"{_num(v, '.1f', lang)} %")
        elif fmt == "ratio":
            display_df[col_label] = raw_df[col_label].map(lambda v: _num(v, ".2f", lang))

    columns = [{"name": c, "id": c} for c in display_df.columns]
    table_data = display_df.to_dict("records")
    csv_data = raw_df.to_csv(index=False)
    tooltip_header = {
        col_label: {"type": "text", "value": L(lang, f"metric_{key}_help")}
        for key, col_label, _ in col_defs
    }
    return table_data, columns, csv_data, tooltip_header


METRIC_DEFS_HISTORIQUE = [
    ("n_years", "metric_historique_years", "years"),
    ("total_return", "metric_historique_total_return", "percent"),
    ("cagr", "metric_historique_cagr", "percent"),
    ("volatility", "metric_historique_volatility", "percent"),
    ("max_drawdown", "metric_historique_max_drawdown", "percent"),
    ("sharpe", "metric_historique_sharpe", "ratio"),
]


def build_historique_metrics_outputs(historique_metrics: dict, lang: str):
    """historique_metrics: {label: metrics_dict (clés stables, voir engine.summarize_historique())}.
    Même forme de retour que build_metrics_outputs (table_data, table_columns, csv_data,
    tooltip_header), mais pour la trajectoire réellement observée (une seule séquence, pas de
    percentiles) plutôt que pour les percentiles Monte Carlo : des libellés dédiés
    (metric_historique_*) évitent de reprendre le vocabulaire "médian"/"simulé" des métriques
    Monte Carlo, qui ne s'applique pas à une trajectoire unique."""
    col_defs = [(key, L(lang, label_key), fmt, label_key) for key, label_key, fmt in METRIC_DEFS_HISTORIQUE]
    label_col = L(lang, "col_index_portfolio")

    rows_raw = []
    for label, m in historique_metrics.items():
        row = {label_col: label}
        for key, col_label, _, _label_key in col_defs:
            row[col_label] = m.get(key)
        rows_raw.append(row)
    raw_df = pd.DataFrame(rows_raw)

    display_df = raw_df.copy()
    for _, col_label, fmt, _label_key in col_defs:
        if fmt == "percent":
            display_df[col_label] = raw_df[col_label].map(lambda v: f"{_num(v, '.1f', lang)} %" if v is not None else "—")
        elif fmt == "ratio":
            display_df[col_label] = raw_df[col_label].map(lambda v: _num(v, ".2f", lang) if v is not None else "—")
        elif fmt == "years":
            display_df[col_label] = raw_df[col_label].map(lambda v: _num(v, ".1f", lang))

    columns = [{"name": c, "id": c} for c in display_df.columns]
    table_data = display_df.to_dict("records")
    csv_data = raw_df.to_csv(index=False)
    tooltip_header = {
        col_label: {"type": "text", "value": L(lang, f"{label_key}_help")}
        for _, col_label, _, label_key in col_defs
    }
    return table_data, columns, csv_data, tooltip_header


def render_objective_result(all_metrics, schedules, items, objective_val, objective_amount,
                             objective_percentile, horizon_years, enable_decumulation, lang):
    if not (objective_val and "on" in objective_val):
        return ""
    if enable_decumulation:
        return dbc.Alert(L(lang, "objective_decumulation_note"), color="warning")
    target = float(objective_amount or 0)
    percentile_key = objective_percentile or "median"
    percentile_label_key = {"p_low": "objective_p_low", "median": "objective_median", "p_high": "objective_p_high"}[percentile_key]
    rows = compute_objective_contribution(all_metrics, schedules, items, target, percentile_key)
    if not rows:
        return dbc.Alert(L(lang, "objective_unavailable"), color="warning")
    lines = [
        L(lang, "objective_result_line", label=label, amount=amount, target=target,
          years=horizon_years, percentile=L(lang, percentile_label_key)).replace(",", " ")
        for label, amount in rows
    ]
    body = html.Ul([html.Li(line) for line in lines]) if len(lines) > 1 else lines[0]
    return dbc.Alert(body, color="info")


def render_rolling_backtest_result(backtest_items, schedule, years_axis, annual_fee_pct, apply_tax, tax_rate,
                                    inflation_pct, display_real, objective_val, objective_amount,
                                    enable_decumulation, lang):
    """"Si ce plan avait démarré n'importe quel mois de l'historique, quelle fraction aurait atteint
    l'objectif ?" — un résultat par item déjà simulé. N'a de sens que si le mode objectif est actif
    (c'est lui qui définit la cible) et hors décumulation (même hypothèse que
    render_objective_result : le calcul suppose une phase d'accumulation pure). Réutilise
    schedule=schedules["constant"], comme compute_objective_contribution."""
    if not (objective_val and "on" in objective_val) or enable_decumulation or not backtest_items:
        return ""
    target = float(objective_amount or 0)
    lines = []
    for label, hist_returns in backtest_items:
        if hist_returns is None or len(hist_returns) == 0:
            continue
        final_values = rolling_backtest_final_values(
            hist_returns, schedule, years_axis, annual_fee_pct, apply_tax, tax_rate, inflation_pct, display_real,
        )
        if final_values is None:
            lines.append(L(lang, "rolling_backtest_insufficient_data_line", label=label))
            continue
        rate = round(float((final_values >= target).mean() * 100), 1)
        lines.append(L(
            lang, "rolling_backtest_result_line", label=label, rate=rate, n_starts=len(final_values),
            target=target, min_val=float(final_values.min()), median_val=float(np.median(final_values)),
            max_val=float(final_values.max()),
        ).replace(",", " "))
    if not lines:
        return ""
    body = html.Ul([html.Li(line) for line in lines]) if len(lines) > 1 else lines[0]
    return dbc.Alert(body, color="info")


# ============================================================
# PORTEFEUILLE RÉEL (onglet 3) : glue entre portfolio_engine (calcul pur) et l'affichage. Aucun
# accès DB/yfinance ici (voir callbacks/portefeuille_reel.py, qui lit portfolio_db/market_data puis appelle ces
# fonctions) -- même convention que le reste de ce module.
# ============================================================

SPARKLINE_DAYS = 365


def build_portfolio_totals_cards(totals: dict, lang: str, real_series=None, dark: bool = False, palette=None):
    """Tuiles de chiffres clés du portefeuille réel (totals : voir portfolio_engine.compute_totals) :
    valeur actuelle en grand avec la mini-courbe des 12 derniers mois, plus-value avec une pastille
    ▲/▼ (couleur ET flèche ET signe : jamais la couleur seule), capital investi, dividendes et frais."""
    palette = palette or PALETTE

    def money(value, signed=False):
        return (f"{value:+,.0f} €" if signed else f"{value:,.0f} €").replace(",", " ")

    def tile(label_key, value_text, sub=None, extra=None):
        body = [html.Div(L(lang, label_key), className="kpi-label"), html.Div(value_text, className="kpi-value")]
        if extra is not None:
            body.append(extra)
        if sub:
            body.append(html.Div(sub, className="kpi-sub"))
        return dbc.Col(dbc.Card(dbc.CardBody(body), className="kpi-tile w-100"), xs=12, sm=6, xl=3, className="mb-3 d-flex")

    sparkline = None
    if real_series is not None and len(real_series) > 1:
        recent = real_series[real_series.index >= real_series.index.max() - pd.Timedelta(days=SPARKLINE_DAYS)]
        sparkline = dcc.Graph(figure=make_sparkline(recent.index, list(recent.values), palette[0], dark=dark),
                              config={"displayModeBar": False, "staticPlot": True}, className="mt-1")

    pnl = totals["pnl_eur"]
    direction = "up" if pnl >= 0 else "down"
    pct_text = f"{_num(totals['pnl_pct'], '+.1f', lang)} %" if totals["pnl_pct"] is not None else ""
    if lang != "fr":
        pct_text = pct_text.replace(",", ".")
    delta = html.Span([html.Span("▲" if pnl >= 0 else "▼"), html.Span(pct_text)], className=f"kpi-delta {direction}")
    tiles = [
        tile("metric_current_value", money(totals["current_value"]), extra=sparkline),
        tile("metric_pnl", money(pnl, signed=True), L(lang, "kpi_pnl_sub", invested=money(totals["total_invested"])),
             extra=delta),
        tile("metric_total_invested", money(totals["total_invested"]),
             L(lang, "kpi_fees_sub", fees=money(totals["total_fees"]))),
        tile("metric_total_dividends", money(totals["total_dividends"]), L(lang, "kpi_dividends_sub")),
    ]
    return dbc.Row(tiles, className="g-3")


def _num(value, spec: str, lang: str) -> str:
    """Nombre décimal selon spec, virgule décimale en français (« +2,77 % », pas « +2.77 % »)."""
    text = format(value, spec)
    return text.replace(".", ",") if lang == "fr" else text


def _pct_per_year(rate, lang):
    return f"{_num(rate * 100, '+.2f', lang)} {L(lang, 'pct_per_year_unit')}" if rate is not None else "N/A"


def _money(value, signed=False):
    return (f"{value:+,.0f} €" if signed else f"{value:,.0f} €").replace(",", " ")


def _info_card(lang, label_key, info_key, main_text, sub_text=None, color=None, extra=None, width=3):
    """Carte "libellé ⓘ / valeur / sous-texte" partagée par les sections Performance et Jalons PEA :
    même style que build_portfolio_totals_cards, plus une infobulle par concept. extra : composant
    optionnel inséré entre la valeur et le sous-texte (ex: barre de progression)."""
    info_id = f"card-{label_key}-info"
    # Même gabarit que les tuiles de chiffres clés (kpi-tile, assets/theme.css), en un cran plus petit.
    body = [
        html.Div([
            L(lang, label_key),
            html.Span(" ⓘ", id=info_id, style={"cursor": "help"}),
        ], className="kpi-label"),
        dbc.Tooltip(L(lang, info_key), target=info_id, placement="top"),
        html.Div(main_text, className=f"kpi-value kpi-value-sm text-{color}" if color else "kpi-value kpi-value-sm"),
    ]
    if extra is not None:
        body.append(extra)
    if sub_text:
        body.append(html.Div(sub_text, className="kpi-sub"))
    return dbc.Col(dbc.Card(dbc.CardBody(body), className="kpi-tile w-100"), xs=12, sm=6, xl=width,
                   className="mb-3 d-flex")


def _pct_period(rate, lang):
    """Pourcentage en grand, « sur la période » en petit à côté : l'unité en pleine taille faisait
    passer la valeur sur deux lignes dans une tuile."""
    if rate is None:
        return "N/A"
    return [f"{_num(rate * 100, '+.1f', lang)} %", html.Span(f" {L(lang, 'pct_period_unit')}", className="kpi-unit")]


def build_performance_cards(perf: dict, lang: str):
    """perf : {"xirr", "twr" (voir portfolio_engine.time_weighted_return), "real_value",
    "short_history", "gain", "benchmark_label", "benchmark_value", "benchmark_xirr",
    "benchmark_gain"} -- toutes les valeurs déjà calculées par les moteurs purs, cette fonction ne
    fait que les mettre en forme. Deux groupes nommés, ton portefeuille puis la référence, pour
    qu'on ne confonde plus ton XIRR avec celui de la référence. Avec moins d'un an d'historique
    (short_history), la valeur principale est le gain de la période et les taux annualisés passent
    en mention secondaire : sur quelques semaines, l'annualisation gonfle les écarts. Chaque
    concept porte son infobulle ⓘ, comme le reste de l'appli."""
    def card(label_key, info_key, main_text, sub_text=None, color=None):
        return _info_card(lang, label_key, info_key, main_text, sub_text, color, width=6)

    def sign_color(rate):
        if rate is None:
            return None
        return "success" if rate >= 0 else "danger"

    def annualized_note(name, rate):
        return L(lang, "annualized_short_sub", name=name, rate=_pct_per_year(rate, lang))

    def group(icon, title, cards):
        return dbc.Col(html.Div([
            html.Div([html.I(className=f"bi bi-{icon} me-2", **{"aria-hidden": "true"}), title],
                     className="perf-group-title"),
            dbc.Row(cards, className="g-3"),
        ], className="perf-group h-100"), xs=12, xl=6, className="mb-3")

    short = perf.get("short_history", False)
    xirr_real, twr, gain = perf.get("xirr"), perf.get("twr"), perf.get("gain")

    if short:
        own = [card("metric_own_return", "own_return_help", _pct_period(gain, lang),
                    annualized_note("XIRR", xirr_real), color=sign_color(gain))]
        if twr is not None:
            own.append(card("metric_twr", "twr_help", _pct_period(twr["twr"], lang),
                            annualized_note("TWR", twr["twr_annualized"]), color=sign_color(twr["twr"])))
        else:
            own.append(card("metric_twr", "twr_help", "N/A"))
    else:
        own = [card("metric_xirr", "xirr_help", _pct_per_year(xirr_real, lang), color=sign_color(xirr_real))]
        if twr is not None:
            own.append(card(
                "metric_twr", "twr_help", _pct_per_year(twr["twr_annualized"], lang),
                L(lang, "twr_cumulative_sub", pct=f"{_num(twr['twr'] * 100, '+.1f', lang)} %",
                  years=_num(twr['n_years'], '.1f', lang)),
                color=sign_color(twr["twr_annualized"]),
            ))
        else:
            own.append(card("metric_twr", "twr_help", "N/A"))
    groups = [group("wallet2", L(lang, "perf_group_own"), own)]

    bench_value = perf.get("benchmark_value")
    if bench_value is not None:
        real_value = perf.get("real_value", 0.0)
        reference = [card(
            "metric_benchmark_value", "benchmark_help", _money(bench_value),
            L(lang, "benchmark_value_sub", real=_money(real_value), diff=_money(real_value - bench_value, signed=True)),
        )]
        bench_xirr, bench_gain = perf.get("benchmark_xirr"), perf.get("benchmark_gain")
        if short:
            diff = (L(lang, "benchmark_return_sub", diff=_num((gain - bench_gain) * 100, "+.1f", lang))
                    if gain is not None and bench_gain is not None else None)
            sub = " · ".join(text for text in (diff, annualized_note("XIRR", bench_xirr)) if text)
            reference.append(card("metric_benchmark_return", "benchmark_return_help", _pct_period(bench_gain, lang),
                                  sub, color=sign_color(bench_gain)))
        else:
            diff_text = (
                L(lang, "benchmark_xirr_sub", diff=_num((xirr_real - bench_xirr) * 100, "+.2f", lang))
                if xirr_real is not None and bench_xirr is not None else None
            )
            reference.append(card("metric_benchmark_xirr", "benchmark_xirr_help", _pct_per_year(bench_xirr, lang),
                                  diff_text, color=sign_color(bench_xirr)))
        groups.append(group("bullseye", L(lang, "perf_group_benchmark", label=perf.get("benchmark_label", "")),
                            reference))
    return dbc.Row(groups)


def build_pea_milestone_cards(milestones: dict, cap: dict, tax: dict, opening_is_estimated: bool, lang: str):
    """milestones / cap / tax : voir portfolio_engine.pea_milestones, pea_cap_usage et
    latent_withdrawal_tax. Mise en forme seulement, aucun calcul fiscal ici."""
    date_fmt = L(lang, "date_format")

    if milestones["is_mature"]:
        maturity_sub = L(lang, "pea_mature_sub", years=_num(milestones['years_held'], '.1f', lang))
    else:
        days = milestones["days_remaining"]
        maturity_sub = L(lang, "pea_countdown_sub", days=days, years=days // 365, months=(days % 365) // 30)
    if opening_is_estimated:
        maturity_sub += " " + L(lang, "pea_opening_estimated_suffix")
    maturity_card = _info_card(
        lang, "pea_five_years_label", "pea_five_years_help", milestones["maturity_date"].strftime(date_fmt),
        maturity_sub, color="success" if milestones["is_mature"] else None, width=4,
    )

    if cap["excess"] > 0:
        cap_sub = L(lang, "pea_cap_excess_sub", excess=_money(cap["excess"]))
    elif cap["projected_cap_date"] is not None:
        cap_sub = L(lang, "pea_cap_projection_sub", remaining=_money(cap["remaining"]),
                    date=cap["projected_cap_date"].strftime(L(lang, "month_year_format")))
    else:
        cap_sub = L(lang, "pea_cap_remaining_sub", remaining=_money(cap["remaining"]))
    cap_card = _info_card(
        lang, "real_pea_cap_label", "real_pea_cap_help", f"{_money(cap['consumed'])} / {_money(cap['cap'])}", cap_sub,
        extra=dbc.Progress(value=min(cap["pct"], 100), label=f"{_num(cap['pct'], '.1f', lang)} %", className="mb-1",
                           style={"height": "14px"}),
        width=4,
    )

    if tax["is_loss"]:
        tax_sub = L(lang, "latent_tax_loss_sub", gain=_money(tax["gain"], signed=True))
    else:
        tax_sub = L(lang, "latent_tax_sub", rate=_num(tax['rate'] * 100, '.1f', lang), gain=_money(tax["gain"], signed=True),
                    net=_money(tax["net_value"]))
    rule_key = "latent_tax_rule_mature" if milestones["is_mature"] else "latent_tax_rule_early"
    tax_card = _info_card(
        lang, "latent_tax_label", "latent_tax_help", _money(tax["tax"]), f"{L(lang, rule_key)} -- {tax_sub}",
        color=None if milestones["is_mature"] or tax["is_loss"] else "warning", width=4,
    )
    return dbc.Row([maturity_card, cap_card, tax_card])


def build_rebalancing_table_data(rebalancing_df: pd.DataFrame, lang: str):
    """rebalancing_df : voir portfolio_engine.compute_rebalancing_plan(). Même forme de retour que
    build_metrics_outputs (table_data, table_columns) : delta_eur toujours affiché avec un signe
    explicite et jamais présenté comme une instruction de vente (voir i18n rebalancing_hint,
    affiché à côté du tableau par layout.py)."""
    if rebalancing_df.empty:
        return [], []
    col_ticker = L(lang, "rebalancing_col_ticker")
    col_target = L(lang, "rebalancing_col_target_pct")
    col_current = L(lang, "rebalancing_col_current_pct")
    col_value = L(lang, "rebalancing_col_current_value")
    col_delta = L(lang, "rebalancing_col_delta")
    rows = [
        {
            col_ticker: r["ticker"],
            col_target: f"{_num(r['target_pct'], '.1f', lang)} %",
            col_current: f"{_num(r['current_pct'], '.1f', lang)} %",
            col_value: f"{r['current_value_eur']:,.0f} €".replace(",", " "),
            col_delta: f"{r['delta_eur']:+,.0f} €".replace(",", " "),
        }
        for _, r in rebalancing_df.iterrows()
    ]
    columns = [{"name": c, "id": c} for c in [col_ticker, col_target, col_current, col_value, col_delta]]
    return rows, columns


def build_real_vs_simulated_figure(portfolio_returns, monthly_amounts, monthly_dates, real_series,
                                    annual_fee_pct, lower_pct, upper_pct, lang="fr", palette=None, dark=False,
                                    purchases=None):
    """portfolio_returns : (n_sims, n_months), rendements simulés du portefeuille réel à sa
    composition/pondération ACTUELLE (voir callbacks/portefeuille_reel.py : simulate_portfolio_asset_returns @
    weights_vec, même combinaison que l'onglet 2). Mêmes étapes que chaque item de compute_results
    (frais -> DCA -> percentiles), mais pour un seul "item" et l'échéancier RÉEL de versements
    (monthly_amounts, voir portfolio_engine.monthly_contribution_schedule) plutôt qu'un échéancier
    constant/progressif simulé. real_series : valeur de marché réelle reconstruite (voir
    portfolio_engine.reconstruct_equity_curve), tracée sur le même axe calendaire que
    monthly_dates (qui démarre à la date de la 1ère transaction)."""
    net_returns = apply_fee(portfolio_returns, annual_fee_pct)
    portfolio_value, invested_capital = returns_to_dca(net_returns, monthly_amounts)
    median = np.percentile(portfolio_value, 50, axis=0)
    p_low = np.percentile(portfolio_value, lower_pct, axis=0)
    p_high = np.percentile(portfolio_value, upper_pct, axis=0)
    return make_actual_vs_simulated_figure(
        real_dates=real_series.index, real_values=real_series.values,
        sim_dates=monthly_dates, sim_median=median, sim_p_low=p_low, sim_p_high=p_high,
        invested_capital=invested_capital, lang=lang, palette=palette, dark=dark, purchases=purchases,
    )


def build_real_portfolio_future_figure(portfolio_returns, current_value_total, monthly_pace,
                                        annual_fee_pct, apply_tax, tax_rate, lower_pct, upper_pct,
                                        lang="fr", palette=None, dark=False):
    """portfolio_returns : (n_sims, n_months), rendements simulés du portefeuille réel à sa
    pondération ACTUELLE (même combinaison actifs/poids que build_real_vs_simulated_figure),
    mais projetés à partir d'AUJOURD'HUI plutôt que rejoués sur l'historique passé : répond à
    "où ça m'emmène si je continue comme ça ?", pas à "qu'aurait donné le marché sur ma période
    passée ?". Échéancier : toute la valeur actuelle au mois 0 (convention déjà utilisée partout
    ailleurs dans ce moteur pour un premier versement -- voir engine.returns_to_dca, la valeur ne
    grossit pas encore pendant son propre mois d'entrée), puis le rythme réel moyen de versement
    chaque mois suivant (portfolio_engine.monthly_contribution_schedule)."""
    n_sims, n_months = portfolio_returns.shape
    monthly_amounts = np.full(n_months, monthly_pace)
    monthly_amounts[0] = current_value_total
    net_returns = apply_fee(portfolio_returns, annual_fee_pct)
    portfolio_value, invested_capital = returns_to_dca(net_returns, monthly_amounts)
    portfolio_value = apply_social_tax(portfolio_value, invested_capital, apply_tax, tax_rate)
    years_axis = np.arange(n_months) / 12
    median = np.percentile(portfolio_value, 50, axis=0)
    p_low = np.percentile(portfolio_value, lower_pct, axis=0)
    p_high = np.percentile(portfolio_value, upper_pct, axis=0)
    title = L(lang, "real_portfolio_projection_chart_title")
    return make_band_figure(
        [(L(lang, "real_portfolio_projection_trace"), median, p_low, p_high)], years_axis, title,
        lang=lang, palette=palette, invested_capital=invested_capital, dark=dark,
        inner_bands=[_inner_band(portfolio_value, lower_pct, upper_pct)],
    )
