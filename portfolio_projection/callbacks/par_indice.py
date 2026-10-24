"""
Callbacks de l'onglet « Par indice » : simulation de chaque indice isolément et export CSV
de ses métriques.
"""

import dash
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc

import layout
from app_instance import app
from charts import make_sequence_risk_figure
from constants import BACKTEST_ANCHORS, PEA_CONTRIBUTION_CAP, TICKER_KEYS, TICKERS
from engine import (
    inject_shock, simulate_index_returns,
)
import chart_theme
from i18n import L
from market_data import (
    get_monthly_returns,
)
from results import (
    build_envelope_comparison_figure, build_historique_metrics_outputs, build_metric_cards,
    build_metrics_outputs, build_schedules, build_sequence_risk_series,
    compute_results, render_objective_result, render_rolling_backtest_result,
)


# ============================================================
# CALLBACKS :onglet 1 (par indice)
# ============================================================

@app.callback(
    Output("tab1-graph-const", "figure"),
    Output("tab1-graph-prog", "figure"),
    Output("tab1-metric-cards", "children"),
    Output("tab1-metrics-table", "data"),
    Output("tab1-metrics-table", "columns"),
    Output("tab1-metrics-table", "style_header"),
    Output("tab1-metrics-table", "style_cell"),
    Output("tab1-metrics-table", "style_data"),
    Output("tab1-metrics-table", "tooltip_header"),
    Output("tab1-csv-store", "data"),
    Output("tab1-warning", "children"),
    Output("tab1-envelope-compare-container", "style"),
    Output("tab1-envelope-compare-chart", "figure"),
    Output("tab1-sequence-risk-container", "style"),
    Output("tab1-sequence-risk-chart", "figure"),
    Output("tab1-objective-result", "children"),
    Output("tab1-rolling-backtest-result", "children"),
    Output("tab1-trajectories-title", "children"),
    Output("tab1-graph-prog-container", "style"),
    Output("tab1-metrics-title", "children"),
    Input("indices-checklist", "value"),
    Input("source-radio", "value"),
    Input("lookback-slider", "value"),
    Input("horizon-slider", "value"),
    Input("view-mode-radio", "value"),
    Input("backtest-anchor-radio", "value"),
    Input("decumulation-checkbox", "value"),
    Input("decumulation-years-slider", "value"),
    Input("withdrawal-monthly-slider", "value"),
    Input("method-radio", "value"),
    Input("block-size-slider", "value"),
    Input("crisis-checkbox", "value"),
    Input("shock-pct-slider", "value"),
    Input("shock-duration-slider", "value"),
    Input("shock-timing-radio", "value"),
    Input("shock-year-slider", "value"),
    Input("apport-constant-slider", "value"),
    Input("apport-initial-slider", "value"),
    Input("apport-final-slider", "value"),
    Input("fee-slider", "value"),
    Input("inflation-slider", "value"),
    Input("display-radio", "value"),
    Input("tax-checkbox", "value"),
    Input("envelope-radio", "value"),
    Input("pea-cap-checkbox", "value"),
    Input("pea-overflow-checkbox", "value"),
    Input("cto-tax-method-radio", "value"),
    Input("cto-tmi-dropdown", "value"),
    Input("compare-envelopes-checkbox", "value"),
    Input("band-width-slider", "value"),
    Input("n-sims-slider", "value"),
    Input("seed-input", "value"),
    Input("lang-radio", "value"),
    Input("palette-dropdown", "value"),
    Input("dark-mode-switch", "value"),
    Input("objective-checkbox", "value"),
    Input("objective-amount-input", "value"),
    Input("objective-percentile-radio", "value"),
    *[Input(f"mu-override-t{i}", "value") for i in range(len(TICKER_KEYS))],
)
def update_tab1(indices, source, lookback_years, horizon_years, view_mode, backtest_anchor, decum_val, decumulation_years,
                 withdrawal_monthly, method, block_size, crisis_val, shock_pct, shock_duration,
                 shock_timing, shock_year, apport_constant, apport_initial, apport_final,
                 annual_fee_pct, inflation_pct, display_mode, tax_val, envelope, pea_cap_val, pea_overflow_val,
                 cto_method, cto_tmi, compare_val, band_width, n_sims, seed, lang, palette_code, dark_mode,
                 objective_val, objective_amount, objective_percentile, *mu_overrides):
    lang = lang or "fr"
    dark = bool(dark_mode)
    palette = chart_theme.palette_for(palette_code, dark)
    view_mode = view_mode or "prevision"
    style_header, style_cell, style_data = layout.table_style_overrides(dark)
    trajectories_title = L(lang, "historique_trajectory_title") if view_mode == "historique" else L(lang, "trajectories_title")
    prog_container_style = {"display": "none"} if view_mode == "historique" else {"flex": "1", "minWidth": "0"}
    metrics_title = L(lang, "historique_metrics_title") if view_mode == "historique" else L(lang, "metrics_title")
    empty_fig = go.Figure()
    empty_fig.update_layout(template=chart_theme.template(dark))
    if not indices:
        return (empty_fig, empty_fig, [], [], [], style_header, style_cell, style_data, {}, "",
                dbc.Alert(L(lang, "tab1_warning_select_index"), color="warning"), {"display": "none"}, empty_fig,
                {"display": "none"}, empty_fig, "", "", trajectories_title, prog_container_style, metrics_title)

    enable_decumulation = bool(decum_val and "on" in decum_val)
    inject_crisis = bool(crisis_val and "on" in crisis_val)
    apply_tax = bool(tax_val and "on" in tax_val)
    tax_rate = layout.compute_tax_rate(envelope, cto_method, cto_tmi)
    cto_rate = layout.compute_cto_tax_rate(cto_method, cto_tmi)
    compare_envelopes = bool(compare_val and "on" in compare_val)
    display_real = display_mode == "real"
    seed = int(seed or 42)
    pea_cap = PEA_CONTRIBUTION_CAP if (envelope == "pea" and pea_cap_val and "on" in pea_cap_val) else None
    # Ne peut être actif que si le plafond PEA lui-même l'est : sinon il n'y a jamais d'excédent à
    # router vers un CTO (layout.toggle_pea_overflow_container masque aussi cette case à cocher
    # dans ce cas, mais le garde ici aussi : State résiduel possible si la case a été cochée puis
    # le plafond décoché dans la même session, le composant caché gardant sa dernière valeur).
    route_overflow = bool(pea_cap and pea_overflow_val and "on" in pea_overflow_val)

    n_months, years_axis, phase_boundary_years, schedules, overflow_schedules = build_schedules(
        horizon_years, enable_decumulation, decumulation_years, withdrawal_monthly,
        inflation_pct, apport_constant, apport_initial, apport_final, pea_cap,
    )
    # Distinct de route_overflow (intention de l'utilisateur, décide si compute_results doit même
    # essayer) : ne sert qu'à afficher la note "valeurs combinées PEA+CTO" dans build_metric_cards,
    # uniquement quand le plafond a réellement été atteint sur au moins une stratégie — sinon la
    # case peut être cochée sans qu'aucun euro ne déborde jamais vers un CTO, et la note serait
    # trompeuse (vue en test : elle s'affichait même avec un capital investi sous le plafond).
    overflow_applied = route_overflow and any(np.any(sched > 0) for sched in overflow_schedules.values())
    lower_pct = (100 - band_width) / 2
    upper_pct = 100 - lower_pct

    rng_shock = np.random.default_rng(seed + 1)
    shock_start_month = shock_year * 12 if (inject_crisis and shock_timing == "fixed") else None
    anchor_key = backtest_anchor or "recent"
    anchor_raw = BACKTEST_ANCHORS.get(anchor_key)

    items, backtest_items, warnings = [], [], []
    first_shock_months = None
    for name in indices:
        ticker = TICKERS[name]["etf" if source == "etf" else "indice"]
        try:
            returns = get_monthly_returns(ticker, lookback_years)
        except ValueError as exc:
            warnings.append(str(exc))
            continue
        if anchor_raw is not None and returns.index.min() > pd.Timestamp(anchor_raw):
            warnings.append(L(
                lang, "backtest_anchor_truncated", label=name, anchor=L(lang, f"backtest_anchor_{anchor_key}"),
                available_from=returns.index.min().strftime("%Y-%m"),
            ))
        mu_override = mu_overrides[TICKER_KEYS.index(name)]
        monthly_returns = simulate_index_returns(
            returns, n_months, n_sims, seed, method, block_size=block_size, mu_override_pct=mu_override,
        )
        if inject_crisis:
            monthly_returns, shock_months = inject_shock(monthly_returns, shock_pct, shock_duration, shock_start_month, rng_shock)
            if first_shock_months is None:
                first_shock_months = shock_months
        items.append((name, monthly_returns))
        backtest_items.append((name, returns))

    if not items:
        msg = " ".join(warnings) or L(lang, "tab1_no_data")
        return (empty_fig, empty_fig, [], [], [], style_header, style_cell, style_data, {}, "",
                dbc.Alert(msg, color="danger"), {"display": "none"}, empty_fig,
                {"display": "none"}, empty_fig, "", "", trajectories_title, prog_container_style, metrics_title)

    all_metrics, figs, series_by_strategy, historique_metrics = compute_results(
        items, years_axis, schedules, annual_fee_pct, apply_tax, tax_rate, inflation_pct, display_real,
        lower_pct, upper_pct, enable_decumulation, phase_boundary_years, lang=lang, palette=palette, dark=dark,
        backtest_items=backtest_items, backtest_anchor_date=anchor_raw, view_mode=view_mode,
        overflow_schedules=overflow_schedules if route_overflow else None, cto_tax_rate=cto_rate,
    )
    if view_mode == "historique":
        cards = []
        table_data, table_columns, csv_data, table_tooltip_header = build_historique_metrics_outputs(historique_metrics, lang)
    else:
        cards = build_metric_cards(all_metrics, series_by_strategy, apply_tax, tax_rate, lang=lang,
                                    route_overflow=overflow_applied)
        table_data, table_columns, csv_data, table_tooltip_header = build_metrics_outputs(all_metrics, lang, lower_pct, upper_pct)
    if view_mode == "historique" and not backtest_items:
        warnings.append(L(lang, "historique_no_data"))
    warning_alert = dbc.Alert(" ".join(warnings), color="warning") if warnings else ""
    objective_result = "" if view_mode == "historique" else render_objective_result(
        all_metrics, schedules, items, objective_val, objective_amount, objective_percentile,
        horizon_years, enable_decumulation, lang,
    )
    rolling_backtest_result = "" if view_mode == "historique" else render_rolling_backtest_result(
        backtest_items, schedules["constant"], years_axis, annual_fee_pct, apply_tax, tax_rate,
        inflation_pct, display_real, objective_val, objective_amount, enable_decumulation, lang,
    )

    compare_style = {"display": "none"}
    compare_fig = empty_fig
    if compare_envelopes and view_mode != "historique":
        # Échéanciers dédiés à la comparaison, indépendants de celui de la simulation principale
        # ci-dessus : le CTO n'a pas de plafond légal de versements, contrairement au PEA — lui
        # appliquer le même échéancier plafonné sous-estimerait sa branche (voir
        # results.build_envelope_comparison_figure).
        pea_cap_checked = bool(pea_cap_val and "on" in pea_cap_val)
        _, _, _, pea_schedules_for_compare, _ = build_schedules(
            horizon_years, enable_decumulation, decumulation_years, withdrawal_monthly,
            inflation_pct, apport_constant, apport_initial, apport_final,
            PEA_CONTRIBUTION_CAP if pea_cap_checked else None,
        )
        _, _, _, cto_schedules_for_compare, _ = build_schedules(
            horizon_years, enable_decumulation, decumulation_years, withdrawal_monthly,
            inflation_pct, apport_constant, apport_initial, apport_final,
        )
        compare_fig = build_envelope_comparison_figure(
            items, pea_schedules_for_compare, cto_schedules_for_compare, annual_fee_pct, inflation_pct,
            display_real, years_axis, cto_rate, lang=lang, palette=palette, dark=dark,
        )
        compare_style = {"display": "block"}

    sequence_risk_style = {"display": "none"}
    sequence_risk_fig = empty_fig
    if view_mode != "historique" and inject_crisis and shock_timing == "random" and first_shock_months is not None:
        first_label, first_returns = items[0]
        shock_years, final_values, invested_final = build_sequence_risk_series(
            first_returns, schedules["constant"], annual_fee_pct, apply_tax, tax_rate, first_shock_months,
        )
        sequence_risk_fig = make_sequence_risk_figure(
            shock_years, final_values, invested_final, lang=lang, palette=palette, dark=dark,
        )
        sequence_risk_style = {"display": "block"}

    return (
        figs.get("constant", empty_fig),
        figs.get("progressive", empty_fig),
        cards, table_data, table_columns, style_header, style_cell, style_data, table_tooltip_header, csv_data,
        warning_alert, compare_style, compare_fig, sequence_risk_style, sequence_risk_fig, objective_result,
        rolling_backtest_result, trajectories_title, prog_container_style, metrics_title,
    )


@app.callback(
    Output("download-tab1", "data"),
    Input("btn-download-tab1", "n_clicks"),
    State("tab1-csv-store", "data"),
    prevent_initial_call=True,
)
def download_tab1(n_clicks, csv_data):
    if not csv_data:
        raise dash.exceptions.PreventUpdate
    return dcc.send_string(csv_data, "projection_pea_metriques_par_indice.csv")
