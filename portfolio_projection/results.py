"""
Helpers partagés par les deux onglets de simulation (par indice / portefeuille
pondéré) : construction des apports, agrégation des métriques Monte Carlo en
figures et tableaux, comparaison PEA vs CTO.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import html

from constants import PEA_TAX_RATE
from engine import (
    apply_fee, apply_social_tax, compute_objective_contribution, constant_schedule,
    progressive_schedule, returns_to_dca, summarize, to_display_values, withdrawal_schedule,
)
from charts import make_band_figure
from i18n import L, PALETTE


def build_schedules(horizon_years, enable_decumulation, decumulation_years, withdrawal_monthly,
                     inflation_pct, apport_constant, apport_initial, apport_final):
    n_months_accum = horizon_years * 12
    n_months_decum = decumulation_years * 12 if enable_decumulation else 0
    n_months = n_months_accum + n_months_decum
    years_axis = np.arange(n_months) / 12
    phase_boundary_years = horizon_years if enable_decumulation else None

    withdrawals = withdrawal_schedule(n_months_decum, withdrawal_monthly, inflation_pct)
    schedules = {}
    for strat_name, accum in [
        ("constant", constant_schedule(n_months_accum, apport_constant)),
        ("progressive", progressive_schedule(n_months_accum, apport_initial, apport_final)),
    ]:
        schedules[strat_name] = np.concatenate([accum, -withdrawals]) if enable_decumulation else accum
    return n_months, years_axis, phase_boundary_years, schedules


def _backtest_trajectory(historical_returns, schedule, years_axis, annual_fee_pct, apply_tax, tax_rate,
                          inflation_pct, display_real):
    """Trajectoire réellement observée (une seule séquence historique, pas une simulation) : "si
    j'avais investi il y a n mois avec ce même plan d'apport, où en serais-je aujourd'hui ?".
    Utilise les n derniers mois de l'historique de calibration (les plus récents, jusqu'à
    aujourd'hui, pas les plus anciens) pour que la trajectoire se termine bien à la date
    actuelle. Tronquée à la plus courte des deux séries : un historique de calibration plus court
    que l'horizon de projection ne peut pas couvrir tout le graphique."""
    n = min(len(historical_returns), len(schedule))
    if n == 0:
        return None
    monthly_returns = np.asarray(historical_returns[-n:]).reshape(1, n)
    net_returns = apply_fee(monthly_returns, annual_fee_pct)
    portfolio_value, invested_capital = returns_to_dca(net_returns, schedule[:n])
    portfolio_value = apply_social_tax(portfolio_value, invested_capital, apply_tax, tax_rate)
    portfolio_value, _ = to_display_values(
        portfolio_value, invested_capital, years_axis[:n], inflation_pct, display_real
    )
    return years_axis[:n], portfolio_value[0]


def compute_results(items, years_axis, schedules, annual_fee_pct, apply_tax, tax_rate, inflation_pct,
                     display_real, lower_pct, upper_pct, enable_decumulation, phase_boundary_years,
                     lang="fr", palette=None, dark=False, backtest_items=None):
    """items: liste de (label, monthly_returns (n_sims, n_months)). all_metrics est indexé par le
    tuple (label, strat_name) : strat_name est une clé stable ("constant"/"progressive"), traduite
    uniquement à l'affichage. backtest_items : liste optionnelle de (label, rendements_historiques
    1D), même labels que items. La trajectoire réellement observée est superposée à la bande de
    percentiles correspondante ("qu'aurait donné cet historique réel ?")."""
    all_metrics = {}
    series_by_strategy = {name: [] for name in schedules}
    invested_by_strategy = {}

    for label, monthly_returns in items:
        for strat_name, schedule in schedules.items():
            net_returns = apply_fee(monthly_returns, annual_fee_pct)
            portfolio_value, invested_capital = returns_to_dca(net_returns, schedule)
            portfolio_value = apply_social_tax(portfolio_value, invested_capital, apply_tax, tax_rate)
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

    backtest_series_by_strategy = {name: [] for name in schedules}
    if backtest_items:
        backtest_map = dict(backtest_items)
        for label, _ in items:
            hist_returns = backtest_map.get(label)
            if hist_returns is None or len(hist_returns) == 0:
                continue
            for strat_name, schedule in schedules.items():
                result = _backtest_trajectory(
                    hist_returns, schedule, years_axis, annual_fee_pct, apply_tax, tax_rate,
                    inflation_pct, display_real,
                )
                if result is not None:
                    bt_years, bt_values = result
                    backtest_series_by_strategy[strat_name].append((label, bt_years, bt_values))

    figs = {}
    for strat_name, series in series_by_strategy.items():
        strat_display = L(lang, f"schedule_{strat_name}")
        figs[strat_name] = make_band_figure(
            series, years_axis,
            f"{strat_display}<br><sup>{L(lang, 'band_subtitle', lower=lower_pct, upper=upper_pct)}</sup>",
            lang=lang, palette=palette,
            invested_capital=invested_by_strategy.get(strat_name),
            phase_boundary_years=phase_boundary_years,
            dark=dark,
            backtest_series=backtest_series_by_strategy.get(strat_name),
        )
    return all_metrics, figs, series_by_strategy


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


def build_metric_cards(all_metrics, series_by_strategy, apply_tax, tax_rate, lang="fr"):
    blocks = []
    if apply_tax:
        blocks.append(html.Small(
            L(lang, "tax_net_note", rate=tax_rate * 100),
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
                html.Small(f"{L(lang, 'prob_gain_prefix')}{m['prob_gain']:.1f} %", className="text-muted"),
            ]), className="h-100"), width=width, className="mb-2"))
        blocks.append(html.Div([html.H6(L(lang, f"schedule_{strat_name}"), className="mt-3"), dbc.Row(cards)]))
    return blocks


def build_envelope_comparison_figure(items, schedules, annual_fee_pct, inflation_pct, display_real,
                                      years_axis, cto_tax_rate, lang="fr", palette=None, dark=False):
    """Compare, pour chaque item/stratégie déjà simulé, la valeur finale médiane nette sous PEA
    (17,2 %) et sous CTO (taux fourni, flat tax ou barème + prélèvements sociaux). Réutilise les
    rendements déjà simulés : pas de nouvelle simulation Monte Carlo, juste deux fiscalités appliquées
    au même tirage aléatoire."""
    palette = palette or PALETTE
    labels, pea_values, cto_values = [], [], []
    for label, monthly_returns in items:
        for strat_name, schedule in schedules.items():
            net_returns = apply_fee(monthly_returns, annual_fee_pct)
            portfolio_value, invested_capital = returns_to_dca(net_returns, schedule)
            pea_value = apply_social_tax(portfolio_value, invested_capital, True, PEA_TAX_RATE)
            cto_value = apply_social_tax(portfolio_value, invested_capital, True, cto_tax_rate)
            pea_value, _ = to_display_values(pea_value, invested_capital, years_axis, inflation_pct, display_real)
            cto_value, _ = to_display_values(cto_value, invested_capital, years_axis, inflation_pct, display_real)
            labels.append(f"{label} : {L(lang, f'schedule_{strat_name}')}")
            pea_values.append(float(np.percentile(pea_value[:, -1], 50)))
            cto_values.append(float(np.percentile(cto_value[:, -1], 50)))

    fig = go.Figure()
    fig.add_trace(go.Bar(name=L(lang, "pea_trace_label", rate=PEA_TAX_RATE * 100), x=labels, y=pea_values, marker_color=palette[0]))
    fig.add_trace(go.Bar(name=L(lang, "cto_trace_label", rate=cto_tax_rate * 100), x=labels, y=cto_values, marker_color=palette[1 % len(palette)]))
    fig.update_layout(
        template="plotly_dark" if dark else "plotly",
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
            display_df[col_label] = raw_df[col_label].map(lambda v: f"{v:.1f} %")
        elif fmt == "ratio":
            display_df[col_label] = raw_df[col_label].map(lambda v: f"{v:.2f}")

    columns = [{"name": c, "id": c} for c in display_df.columns]
    table_data = display_df.to_dict("records")
    csv_data = raw_df.to_csv(index=False)
    tooltip_header = {
        col_label: {"type": "text", "value": L(lang, f"metric_{key}_help")}
        for key, col_label, _ in col_defs
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
