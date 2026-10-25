"""
Callbacks de l'onglet « Portefeuille pondéré » : corrélations, poids suggérés (Sharpe,
volatilité minimale, parité de risque), simulation des allocations comparées et export CSV.
"""

import dash
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

import layout
from app_instance import app
from charts import make_correlation_heatmap, make_sequence_risk_figure
from constants import BACKTEST_ANCHORS, N_PORTFOLIOS_MAX, PEA_CONTRIBUTION_CAP, TICKER_KEYS, TICKERS
from engine import (
    inject_shock, simulate_portfolio_asset_returns, suggest_optimal_weights,
)
import chart_theme
from i18n import L
from market_data import (
    get_aligned_returns,
)
from results import (
    build_envelope_comparison_figure, build_historique_metrics_outputs, build_metric_cards,
    build_metrics_outputs, build_schedules, build_sequence_risk_series,
    compute_results, render_objective_result, render_rolling_backtest_result,
)


# ============================================================
# CALLBACKS :onglet 2 (portefeuille pondéré)
# ============================================================

@app.callback(
    Output("tab2-corr-heatmap", "figure"),
    Output("sharpe-weights-store", "data"),
    Output("vol-weights-store", "data"),
    Output("rp-weights-store", "data"),
    Output("tab2-sharpe-weights-display", "children"),
    Output("tab2-vol-weights-display", "children"),
    Output("tab2-rp-weights-display", "children"),
    Input("source-radio", "value"),
    Input("lookback-slider", "value"),
    Input("lang-radio", "value"),
    Input("shrinkage-slider", "value"),
    Input("risk-free-rate-slider", "value"),
    Input("weight-bounds-slider", "value"),
    Input("step-pct-slider", "value"),
    Input("dark-mode-switch", "value"),
    *[Input(f"mu-override-t{i}", "value") for i in range(len(TICKER_KEYS))],
)
def update_correlation_and_suggestions(source, lookback_years, lang, shrinkage_pct, risk_free_rate_pct,
                                        weight_bounds, step_pct, dark_mode, *mu_overrides):
    lang = lang or "fr"
    dark = bool(dark_mode)
    universe = list(TICKERS.keys())
    source_key = "etf" if source == "etf" else "indice"
    try:
        aligned = get_aligned_returns(universe, lookback_years, source_key)
    except ValueError as exc:
        return go.Figure(), {}, {}, {}, dbc.Alert(str(exc), color="danger"), "", ""

    if aligned.empty:
        return go.Figure(), {}, {}, {}, "", "", ""

    shrinkage = (shrinkage_pct if shrinkage_pct is not None else 50) / 100
    heatmap = make_correlation_heatmap(aligned.corr(), lang=lang, dark=dark)
    # step_pct réglable par l'utilisateur (curseur à marques fixes 5/10/15/20/25, jamais en-dessous
    # de 5 -- la grille exhaustive de suggest_optimal_weights est combinatoire en step_pct et en
    # nombre d'actifs : mesuré ~4s au pire avec 7 actifs à 5%, acceptable pour un réglage explicite
    # de l'utilisateur, contrairement à un défaut automatique qui tournerait à chaque rendu).
    min_weight, max_weight = weight_bounds if weight_bounds else (0, 100)
    sharpe_w, vol_w, rp_w = suggest_optimal_weights(
        aligned, step_pct=step_pct or 10, shrinkage=shrinkage, mu_override_pct=list(mu_overrides),
        risk_free_rate_pct=risk_free_rate_pct or 0.0, min_weight_pct=min_weight, max_weight_pct=max_weight,
    )
    if sharpe_w is None and vol_w is None and rp_w is None:
        infeasible_hint = html.Small(L(lang, "weights_infeasible_hint"), className="text-muted")
        return heatmap, {}, {}, {}, infeasible_hint, infeasible_hint, infeasible_hint
    sharpe_display = html.Ul([html.Li(f"{k}: {v:.0f}%") for k, v in sharpe_w.items()]) if sharpe_w else ""
    vol_display = html.Ul([html.Li(f"{k}: {v:.0f}%") for k, v in vol_w.items()]) if vol_w else ""
    rp_display = html.Ul([html.Li(f"{k}: {v:.0f}%") for k, v in rp_w.items()]) if rp_w else ""
    return heatmap, (sharpe_w or {}), (vol_w or {}), (rp_w or {}), sharpe_display, vol_display, rp_display


@app.callback(
    [Output(f"weight-p0-t{i}", "value") for i in range(len(TICKER_KEYS))],
    Input("btn-apply-sharpe", "n_clicks"),
    State("sharpe-weights-store", "data"),
    prevent_initial_call=True,
)
def apply_sharpe_weights(n_clicks, sharpe_w):
    if not sharpe_w:
        raise dash.exceptions.PreventUpdate
    return [int(sharpe_w.get(k, 0)) for k in TICKER_KEYS]


@app.callback(
    [Output(f"weight-p0-t{i}", "value", allow_duplicate=True) for i in range(len(TICKER_KEYS))],
    Input("btn-apply-vol", "n_clicks"),
    State("vol-weights-store", "data"),
    prevent_initial_call=True,
)
def apply_vol_weights(n_clicks, vol_w):
    if not vol_w:
        raise dash.exceptions.PreventUpdate
    return [int(vol_w.get(k, 0)) for k in TICKER_KEYS]


@app.callback(
    [Output(f"weight-p0-t{i}", "value", allow_duplicate=True) for i in range(len(TICKER_KEYS))],
    Input("btn-apply-rp", "n_clicks"),
    State("rp-weights-store", "data"),
    prevent_initial_call=True,
)
def apply_rp_weights(n_clicks, rp_w):
    if not rp_w:
        raise dash.exceptions.PreventUpdate
    return [int(rp_w.get(k, 0)) for k in TICKER_KEYS]


@app.callback(
    Output("weights-explain-collapse", "is_open"),
    Input("btn-toggle-weights-explain", "n_clicks"),
    State("weights-explain-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_weights_explain(n_clicks, is_open):
    return not is_open


@app.callback(
    Output("mu-override-collapse", "is_open"),
    Input("btn-toggle-mu-override", "n_clicks"),
    State("mu-override-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_mu_override(n_clicks, is_open):
    return not is_open


_tab2_weight_inputs = [
    Input(f"weight-p{p}-t{i}", "value")
    for p in range(N_PORTFOLIOS_MAX)
    for i in range(len(TICKER_KEYS))
]
_tab2_name_inputs = [Input(f"name-p{p}", "value") for p in range(N_PORTFOLIOS_MAX)]


@app.callback(
    Output("tab2-graph-const", "figure"),
    Output("tab2-graph-prog", "figure"),
    Output("tab2-metric-cards", "children"),
    Output("tab2-metrics-table", "rowData"),
    Output("tab2-metrics-table", "columnDefs"),
    Output("tab2-csv-store", "data"),
    Output("tab2-warning", "children"),
    Output("tab2-envelope-compare-container", "style"),
    Output("tab2-envelope-compare-chart", "figure"),
    Output("tab2-sequence-risk-container", "style"),
    Output("tab2-sequence-risk-chart", "figure"),
    Output("tab2-objective-result", "children"),
    Output("tab2-rolling-backtest-result", "children"),
    Output("tab2-trajectories-title", "children"),
    Output("tab2-graph-prog-container", "style"),
    Output("tab2-metrics-title", "children"),
    Input("n-portfolios-input", "value"),
    *_tab2_name_inputs,
    *_tab2_weight_inputs,
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
def update_tab2(n_portfolios, *args):
    n_names = N_PORTFOLIOS_MAX
    n_weights = N_PORTFOLIOS_MAX * len(TICKER_KEYS)
    names = list(args[:n_names])
    flat_weights = list(args[n_names:n_names + n_weights])
    rest = args[n_names + n_weights:]
    mu_overrides = list(rest[-len(TICKER_KEYS):])
    rest = rest[:-len(TICKER_KEYS)]
    objective_val, objective_amount, objective_percentile = rest[-3:]
    rest = rest[:-3]
    dark_mode = rest[-1]
    rest = rest[:-1]
    (source, lookback_years, horizon_years, view_mode, backtest_anchor, decum_val, decumulation_years, withdrawal_monthly,
     method, block_size, crisis_val, shock_pct, shock_duration, shock_timing, shock_year,
     apport_constant, apport_initial, apport_final, annual_fee_pct, inflation_pct, display_mode,
     tax_val, envelope, pea_cap_val, pea_overflow_val, cto_method, cto_tmi, compare_val, band_width, n_sims, seed,
     lang, palette_code) = rest
    view_mode = view_mode or "prevision"
    lang = lang or "fr"
    dark = bool(dark_mode)
    palette = chart_theme.palette_for(palette_code, dark)
    trajectories_title = L(lang, "historique_trajectory_title") if view_mode == "historique" else L(lang, "trajectories_title")
    prog_container_style = {"display": "none"} if view_mode == "historique" else {"flex": "1", "minWidth": "0"}
    metrics_title = L(lang, "historique_metrics_title") if view_mode == "historique" else L(lang, "metrics_title_portfolio")

    k = len(TICKER_KEYS)
    weights_raw = [flat_weights[p * k:(p + 1) * k] for p in range(N_PORTFOLIOS_MAX)]

    empty_fig = go.Figure()
    empty_fig.update_layout(template=chart_theme.template(dark))
    n_portfolios = int(n_portfolios or 1)

    universe = list(TICKERS.keys())
    portfolios = []
    for i in range(n_portfolios):
        raw = weights_raw[i]
        total = sum(w or 0 for w in raw)
        if total == 0:
            continue
        normalized = {k_name: (w or 0) / total for k_name, w in zip(universe, raw)}
        portfolios.append((names[i] or L(lang, "portfolio_default_name", n=i + 1), normalized))

    if not portfolios:
        return (empty_fig, empty_fig, [], [], [], "",
                dbc.Alert(L(lang, "portfolio_warning_zero"), color="warning"),
                {"display": "none"}, empty_fig, {"display": "none"}, empty_fig, "", "",
                trajectories_title, prog_container_style, metrics_title)

    source_key = "etf" if source == "etf" else "indice"
    try:
        aligned = get_aligned_returns(universe, lookback_years, source_key)
    except ValueError as exc:
        return (empty_fig, empty_fig, [], [], [], "",
                dbc.Alert(str(exc), color="danger"), {"display": "none"}, empty_fig,
                {"display": "none"}, empty_fig, "", "", trajectories_title, prog_container_style, metrics_title)
    if aligned.empty:
        return (empty_fig, empty_fig, [], [], [], "",
                dbc.Alert(L(lang, "no_aligned_data"), color="danger"), {"display": "none"}, empty_fig,
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

    tab2_warnings = []
    if anchor_raw is not None and aligned.index.min() > pd.Timestamp(anchor_raw):
        tab2_warnings.append(L(
            lang, "backtest_anchor_truncated", label=L(lang, "tab_portefeuille"),
            anchor=L(lang, f"backtest_anchor_{anchor_key}"), available_from=aligned.index.min().strftime("%Y-%m"),
        ))

    asset_returns = simulate_portfolio_asset_returns(
        aligned, n_months, n_sims, seed, method, block_size=block_size, mu_override_pct=mu_overrides,
    )
    shock_months = None
    if inject_crisis:
        asset_returns, shock_months = inject_shock(asset_returns, shock_pct, shock_duration, shock_start_month, rng_shock)

    items, backtest_items = [], []
    for portfolio_name, normalized in portfolios:
        weights_vec = np.array([normalized.get(name, 0.0) for name in aligned.columns])
        portfolio_returns = asset_returns @ weights_vec
        items.append((portfolio_name, portfolio_returns))
        backtest_items.append((portfolio_name, pd.Series(aligned.values @ weights_vec, index=aligned.index)))

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
        tab2_warnings.append(L(lang, "historique_no_data"))
    tab2_warning_alert = dbc.Alert(" ".join(tab2_warnings), color="warning") if tab2_warnings else ""
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
    if view_mode != "historique" and inject_crisis and shock_timing == "random" and shock_months is not None:
        first_label, first_returns = items[0]
        shock_years, final_values, invested_final = build_sequence_risk_series(
            first_returns, schedules["constant"], annual_fee_pct, apply_tax, tax_rate, shock_months,
        )
        sequence_risk_fig = make_sequence_risk_figure(
            shock_years, final_values, invested_final, lang=lang, palette=palette, dark=dark,
        )
        sequence_risk_style = {"display": "block"}

    return (
        figs.get("constant", empty_fig),
        figs.get("progressive", empty_fig),
        cards, table_data, layout.grid_columns(table_columns, table_tooltip_header, table_data), csv_data,
        tab2_warning_alert, compare_style, compare_fig, sequence_risk_style, sequence_risk_fig, objective_result,
        rolling_backtest_result, trajectories_title, prog_container_style, metrics_title,
    )


@app.callback(
    Output("download-tab2", "data"),
    Input("btn-download-tab2", "n_clicks"),
    State("tab2-csv-store", "data"),
    prevent_initial_call=True,
)
def download_tab2(n_clicks, csv_data):
    if not csv_data:
        raise dash.exceptions.PreventUpdate
    return dcc.send_string(csv_data, "projection_pea_metriques_portefeuille.csv")
