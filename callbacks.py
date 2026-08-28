"""
Enregistrement de tous les callbacks Dash. Importer ce module (voir app.py)
suffit à les enregistrer sur l'instance `app` partagée (app_instance.py) : les
fonctions ci-dessous ne sont pas appelées directement ailleurs, sauf les
helpers d'affichage conditionnel réutilisés par layout.py lui-même.
"""
import base64
import concurrent.futures
import json

import dash
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

import layout
from app_instance import app
from charts import empty_figure_with_message, make_correlation_heatmap, make_sequence_risk_figure
from constants import N_PORTFOLIOS_MAX, TICKER_KEYS, TICKERS, UNIVERSE_TICKERS
from engine import (
    compute_dcf_fair_value, inject_shock, simulate_index_returns, simulate_portfolio_asset_returns,
    suggest_optimal_weights,
)
from i18n import L, PALETTE, PALETTE_CODES, PALETTE_NAMES, PALETTES
from market_data import get_aligned_returns, get_dcf_inputs, get_monthly_returns, get_stock_pe_history, get_stock_valuation
from results import (
    build_envelope_comparison_figure, build_metric_cards, build_metrics_outputs, build_schedules,
    build_sequence_risk_series, compute_results, render_objective_result,
)

# ============================================================
# 6. CALLBACKS :affichage conditionnel
# ============================================================
# Chaque callback délègue à la fonction pure correspondante de layout.py, qui
# sert aussi à calculer l'état initial des composants au moment du build.

app.callback(Output("etf-info", "style"), Input("source-radio", "value"))(layout.toggle_etf_info)

app.callback(
    Output("cto-tax-method-container", "style"),
    Input("envelope-radio", "value"),
)(layout.toggle_cto_tax_method)

app.callback(
    Output("cto-tmi-container", "style"),
    Input("cto-tax-method-radio", "value"),
)(layout.toggle_cto_tmi)

app.callback(
    Output("tax-checkbox-label", "children"),
    Output("tax-checkbox-help", "children"),
    Input("envelope-radio", "value"),
    Input("cto-tax-method-radio", "value"),
    Input("cto-tmi-dropdown", "value"),
    Input("lang-radio", "value"),
)(layout.update_tax_label)

app.callback(
    Output("sidebar-col", "style"),
    Output("sidebar-col", "width"),
    Output("main-col", "width"),
    Input("main-tabs", "active_tab"),
)(layout.toggle_sidebar)

app.callback(Output("decumulation-options-container", "style"), Input("decumulation-checkbox", "value"))(layout.toggle_decumulation)

app.callback(Output("objective-options-container", "style"), Input("objective-checkbox", "value"))(layout.toggle_objective)

app.callback(Output("block-size-container", "style"), Input("method-radio", "value"))(layout.toggle_block_size)

app.callback(Output("crisis-options-container", "style"), Input("crisis-checkbox", "value"))(layout.toggle_crisis)

app.callback(Output("shock-year-container", "style"), Input("shock-timing-radio", "value"))(layout.toggle_shock_year)

app.callback(
    Output("shock-year-slider", "max"),
    Output("shock-year-slider", "value"),
    Input("horizon-slider", "value"),
    Input("decumulation-checkbox", "value"),
    Input("decumulation-years-slider", "value"),
    State("shock-year-slider", "value"),
)(layout.update_shock_year_bounds)

app.callback(
    [Output(f"portfolio-block-{p}", "style") for p in range(N_PORTFOLIOS_MAX)],
    Input("n-portfolios-input", "value"),
)(layout.toggle_portfolio_blocks)


for _p in range(N_PORTFOLIOS_MAX):
    def _make_caption_callback(p):
        @app.callback(
            Output(f"caption-p{p}", "children"),
            Input(f"weight-p{p}-t0", "value"),
            Input(f"weight-p{p}-t1", "value"),
            Input(f"weight-p{p}-t2", "value"),
            Input(f"weight-p{p}-t3", "value"),
            Input("lang-radio", "value"),
        )
        def _update_caption(w0, w1, w2, w3, lang="fr"):
            lang = lang or "fr"
            weights = [w0 or 0, w1 or 0, w2 or 0, w3 or 0]
            total = sum(weights)
            if total == 0:
                return L(lang, "caption_zero")
            return L(lang, "caption_normalized_prefix") + " · ".join(
                f"{k} {w / total * 100:.0f}%" for k, w in zip(TICKER_KEYS, weights)
            )
        return _update_caption
    _make_caption_callback(_p)


@app.callback(Output("seed-input", "value"), Input("btn-reroll", "n_clicks"), prevent_initial_call=True)
def reroll_seed(n_clicks):
    return int(np.random.default_rng().integers(0, 1_000_000))


@app.callback(
    Output("palette-dropdown", "options"),
    Output("palette-label", "children"),
    Output("lang-label", "children"),
    Output("dark-mode-switch", "label"),
    Input("lang-radio", "value"),
)
def update_controls_language(lang):
    palette_options = [{"label": PALETTE_NAMES.get(lang, PALETTE_NAMES["fr"])[code], "value": code} for code in PALETTE_CODES]
    return palette_options, L(lang, "palette_label"), L(lang, "lang_label"), L(lang, "dark_mode_label")


@app.callback(
    Output("header-text-container", "children"),
    Output("sidebar-container", "children"),
    Output("tabs-container", "children"),
    Output("footer-container", "children"),
    Input("lang-radio", "value"),
    [State(cid, prop) for _, cid, prop in layout.CONFIG_FIELDS],
    [State(cid, prop) for cid, prop in layout.TAB_STATE_FIELDS],
    State("main-tabs", "active_tab"),
    prevent_initial_call=True,
)
def rebuild_on_language_change(lang, *state_values):
    n_sidebar = len(layout.CONFIG_FIELDS)
    n_tabs = len(layout.TAB_STATE_FIELDS)
    sidebar_values = dict(zip([cid for _, cid, _ in layout.CONFIG_FIELDS], state_values[:n_sidebar]))
    tab_values = dict(zip([cid for cid, _ in layout.TAB_STATE_FIELDS], state_values[n_sidebar:n_sidebar + n_tabs]))
    active_tab = state_values[n_sidebar + n_tabs]
    v = {**sidebar_values, **tab_values}
    return (
        layout.build_header_text(lang), layout.build_sidebar(lang, v), layout.build_tabs(lang, v, active_tab),
        layout.build_footer(lang),
    )


# ============================================================
# 7. CALLBACKS :configuration (export / import JSON)
# ============================================================

@app.callback(
    Output("download-config", "data"),
    Input("btn-download-config", "n_clicks"),
    [State(cid, prop) for _, cid, prop in layout.CONFIG_FIELDS],
    prevent_initial_call=True,
)
def download_config(n_clicks, *values):
    config = {key: val for (key, _, _), val in zip(layout.CONFIG_FIELDS, values)}
    return dcc.send_string(json.dumps(config, ensure_ascii=False, indent=2), "pea_forecast_config.json")


@app.callback(
    [Output(cid, prop, allow_duplicate=True) for _, cid, prop in layout.CONFIG_FIELDS],
    Input("upload-config", "contents"),
    prevent_initial_call=True,
)
def upload_config(contents):
    if contents is None:
        raise dash.exceptions.PreventUpdate
    _content_type, content_string = contents.split(",", 1)
    decoded = base64.b64decode(content_string)
    loaded = json.loads(decoded)
    return [loaded.get(key, dash.no_update) for key, _, _ in layout.CONFIG_FIELDS]


# ============================================================
# 8. CALLBACKS :onglet 1 (par indice)
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
    Input("indices-checklist", "value"),
    Input("source-radio", "value"),
    Input("lookback-slider", "value"),
    Input("horizon-slider", "value"),
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
def update_tab1(indices, source, lookback_years, horizon_years, decum_val, decumulation_years,
                 withdrawal_monthly, method, block_size, crisis_val, shock_pct, shock_duration,
                 shock_timing, shock_year, apport_constant, apport_initial, apport_final,
                 annual_fee_pct, inflation_pct, display_mode, tax_val, envelope, cto_method, cto_tmi,
                 compare_val, band_width, n_sims, seed, lang, palette_code, dark_mode,
                 objective_val, objective_amount, objective_percentile, *mu_overrides):
    lang = lang or "fr"
    palette = PALETTES.get(palette_code, PALETTE)
    dark = bool(dark_mode)
    style_header, style_cell, style_data = layout.table_style_overrides(dark)
    empty_fig = go.Figure()
    empty_fig.update_layout(template="plotly_dark" if dark else "plotly")
    if not indices:
        return (empty_fig, empty_fig, [], [], [], style_header, style_cell, style_data, {}, "",
                dbc.Alert(L(lang, "tab1_warning_select_index"), color="warning"), {"display": "none"}, empty_fig,
                {"display": "none"}, empty_fig, "")

    enable_decumulation = bool(decum_val and "on" in decum_val)
    inject_crisis = bool(crisis_val and "on" in crisis_val)
    apply_tax = bool(tax_val and "on" in tax_val)
    tax_rate = layout.compute_tax_rate(envelope, cto_method, cto_tmi)
    compare_envelopes = bool(compare_val and "on" in compare_val)
    display_real = display_mode == "real"
    seed = int(seed or 42)

    n_months, years_axis, phase_boundary_years, schedules = build_schedules(
        horizon_years, enable_decumulation, decumulation_years, withdrawal_monthly,
        inflation_pct, apport_constant, apport_initial, apport_final,
    )
    lower_pct = (100 - band_width) / 2
    upper_pct = 100 - lower_pct

    rng_shock = np.random.default_rng(seed + 1)
    shock_start_month = shock_year * 12 if (inject_crisis and shock_timing == "fixed") else None

    items, backtest_items, warnings = [], [], []
    first_shock_months = None
    for name in indices:
        ticker = TICKERS[name]["etf" if source == "etf" else "indice"]
        try:
            returns = get_monthly_returns(ticker, lookback_years)
        except ValueError as exc:
            warnings.append(str(exc))
            continue
        mu_override = mu_overrides[TICKER_KEYS.index(name)]
        monthly_returns = simulate_index_returns(
            returns, n_months, n_sims, seed, method, block_size=block_size, mu_override_pct=mu_override,
        )
        if inject_crisis:
            monthly_returns, shock_months = inject_shock(monthly_returns, shock_pct, shock_duration, shock_start_month, rng_shock)
            if first_shock_months is None:
                first_shock_months = shock_months
        items.append((name, monthly_returns))
        backtest_items.append((name, returns.values))

    if not items:
        msg = " ".join(warnings) or L(lang, "tab1_no_data")
        return (empty_fig, empty_fig, [], [], [], style_header, style_cell, style_data, {}, "",
                dbc.Alert(msg, color="danger"), {"display": "none"}, empty_fig,
                {"display": "none"}, empty_fig, "")

    all_metrics, figs, series_by_strategy = compute_results(
        items, years_axis, schedules, annual_fee_pct, apply_tax, tax_rate, inflation_pct, display_real,
        lower_pct, upper_pct, enable_decumulation, phase_boundary_years, lang=lang, palette=palette, dark=dark,
        backtest_items=backtest_items,
    )
    cards = build_metric_cards(all_metrics, series_by_strategy, apply_tax, tax_rate, lang=lang)
    table_data, table_columns, csv_data, table_tooltip_header = build_metrics_outputs(all_metrics, lang, lower_pct, upper_pct)
    warning_alert = dbc.Alert(" ".join(warnings), color="warning") if warnings else ""
    objective_result = render_objective_result(
        all_metrics, schedules, items, objective_val, objective_amount, objective_percentile,
        horizon_years, enable_decumulation, lang,
    )

    compare_style = {"display": "none"}
    compare_fig = empty_fig
    if compare_envelopes:
        cto_rate_for_compare = layout.compute_cto_tax_rate(cto_method, cto_tmi)
        compare_fig = build_envelope_comparison_figure(
            items, schedules, annual_fee_pct, inflation_pct, display_real, years_axis, cto_rate_for_compare,
            lang=lang, palette=palette, dark=dark,
        )
        compare_style = {"display": "block"}

    sequence_risk_style = {"display": "none"}
    sequence_risk_fig = empty_fig
    if inject_crisis and shock_timing == "random" and first_shock_months is not None:
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


# ============================================================
# 9. CALLBACKS :onglet 2 (portefeuille pondéré)
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
    Input("dark-mode-switch", "value"),
    *[Input(f"mu-override-t{i}", "value") for i in range(len(TICKER_KEYS))],
)
def update_correlation_and_suggestions(source, lookback_years, lang, shrinkage_pct, dark_mode, *mu_overrides):
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
    sharpe_w, vol_w, rp_w = suggest_optimal_weights(
        aligned, step_pct=5, shrinkage=shrinkage, mu_override_pct=list(mu_overrides),
    )
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
    Output("tab2-metrics-table", "data"),
    Output("tab2-metrics-table", "columns"),
    Output("tab2-metrics-table", "style_header"),
    Output("tab2-metrics-table", "style_cell"),
    Output("tab2-metrics-table", "style_data"),
    Output("tab2-metrics-table", "tooltip_header"),
    Output("tab2-csv-store", "data"),
    Output("tab2-warning", "children"),
    Output("tab2-envelope-compare-container", "style"),
    Output("tab2-envelope-compare-chart", "figure"),
    Output("tab2-sequence-risk-container", "style"),
    Output("tab2-sequence-risk-chart", "figure"),
    Output("tab2-objective-result", "children"),
    Input("n-portfolios-input", "value"),
    *_tab2_name_inputs,
    *_tab2_weight_inputs,
    Input("source-radio", "value"),
    Input("lookback-slider", "value"),
    Input("horizon-slider", "value"),
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
    (source, lookback_years, horizon_years, decum_val, decumulation_years, withdrawal_monthly,
     method, block_size, crisis_val, shock_pct, shock_duration, shock_timing, shock_year,
     apport_constant, apport_initial, apport_final, annual_fee_pct, inflation_pct, display_mode,
     tax_val, envelope, cto_method, cto_tmi, compare_val, band_width, n_sims, seed, lang, palette_code) = rest
    lang = lang or "fr"
    palette = PALETTES.get(palette_code, PALETTE)
    dark = bool(dark_mode)
    style_header, style_cell, style_data = layout.table_style_overrides(dark)

    k = len(TICKER_KEYS)
    weights_raw = [flat_weights[p * k:(p + 1) * k] for p in range(N_PORTFOLIOS_MAX)]

    empty_fig = go.Figure()
    empty_fig.update_layout(template="plotly_dark" if dark else "plotly")
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
        return (empty_fig, empty_fig, [], [], [], style_header, style_cell, style_data, {}, "",
                dbc.Alert(L(lang, "portfolio_warning_zero"), color="warning"),
                {"display": "none"}, empty_fig, {"display": "none"}, empty_fig, "")

    source_key = "etf" if source == "etf" else "indice"
    try:
        aligned = get_aligned_returns(universe, lookback_years, source_key)
    except ValueError as exc:
        return (empty_fig, empty_fig, [], [], [], style_header, style_cell, style_data, {}, "",
                dbc.Alert(str(exc), color="danger"), {"display": "none"}, empty_fig,
                {"display": "none"}, empty_fig, "")
    if aligned.empty:
        return (empty_fig, empty_fig, [], [], [], style_header, style_cell, style_data, {}, "",
                dbc.Alert(L(lang, "no_aligned_data"), color="danger"), {"display": "none"}, empty_fig,
                {"display": "none"}, empty_fig, "")

    enable_decumulation = bool(decum_val and "on" in decum_val)
    inject_crisis = bool(crisis_val and "on" in crisis_val)
    apply_tax = bool(tax_val and "on" in tax_val)
    tax_rate = layout.compute_tax_rate(envelope, cto_method, cto_tmi)
    compare_envelopes = bool(compare_val and "on" in compare_val)
    display_real = display_mode == "real"
    seed = int(seed or 42)

    n_months, years_axis, phase_boundary_years, schedules = build_schedules(
        horizon_years, enable_decumulation, decumulation_years, withdrawal_monthly,
        inflation_pct, apport_constant, apport_initial, apport_final,
    )
    lower_pct = (100 - band_width) / 2
    upper_pct = 100 - lower_pct

    rng_shock = np.random.default_rng(seed + 1)
    shock_start_month = shock_year * 12 if (inject_crisis and shock_timing == "fixed") else None

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
        backtest_items.append((portfolio_name, aligned.values @ weights_vec))

    all_metrics, figs, series_by_strategy = compute_results(
        items, years_axis, schedules, annual_fee_pct, apply_tax, tax_rate, inflation_pct, display_real,
        lower_pct, upper_pct, enable_decumulation, phase_boundary_years, lang=lang, palette=palette, dark=dark,
        backtest_items=backtest_items,
    )
    cards = build_metric_cards(all_metrics, series_by_strategy, apply_tax, tax_rate, lang=lang)
    table_data, table_columns, csv_data, table_tooltip_header = build_metrics_outputs(all_metrics, lang, lower_pct, upper_pct)
    objective_result = render_objective_result(
        all_metrics, schedules, items, objective_val, objective_amount, objective_percentile,
        horizon_years, enable_decumulation, lang,
    )

    compare_style = {"display": "none"}
    compare_fig = empty_fig
    if compare_envelopes:
        cto_rate_for_compare = layout.compute_cto_tax_rate(cto_method, cto_tmi)
        compare_fig = build_envelope_comparison_figure(
            items, schedules, annual_fee_pct, inflation_pct, display_real, years_axis, cto_rate_for_compare,
            lang=lang, palette=palette, dark=dark,
        )
        compare_style = {"display": "block"}

    sequence_risk_style = {"display": "none"}
    sequence_risk_fig = empty_fig
    if inject_crisis and shock_timing == "random" and shock_months is not None:
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
        cards, table_data, table_columns, style_header, style_cell, style_data, table_tooltip_header, csv_data,
        "", compare_style, compare_fig, sequence_risk_style, sequence_risk_fig, objective_result,
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


# ============================================================
# 10. CALLBACKS :onglet 3 (valorisation d'actions individuelles)
# ============================================================

def _format_market_cap(value):
    """Formate une capitalisation dans la devise locale de cotation (EUR, GBP ou USD selon le marché)."""
    if not value or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    for threshold, suffix in [(1e12, "T"), (1e9, "Md"), (1e6, "M")]:
        if value >= threshold:
            return f"{value / threshold:.1f} {suffix}"
    return f"{value:,.0f}".replace(",", " ")


@app.callback(
    Output("stocks-raw-store", "data"),
    Output("stocks-warning", "children"),
    Input("btn-load-stocks", "n_clicks"),
    State("universe-checklist", "value"),
    State("lang-radio", "value"),
    prevent_initial_call=True,
)
def load_stock_valuations(n_clicks, universes, lang):
    lang = lang or "fr"
    if not universes:
        return [], dbc.Alert(L(lang, "select_market_warning"), color="warning")

    tickers = {}
    for code in universes:
        tickers.update(UNIVERSE_TICKERS[code])

    rows, failures = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        future_to_stock = {executor.submit(get_stock_valuation, ticker): (name, ticker) for name, ticker in tickers.items()}
        for future in concurrent.futures.as_completed(future_to_stock):
            name, ticker = future_to_stock[future]
            try:
                data = future.result()
            except Exception:
                failures.append(name)
                continue
            data["Entreprise"] = name
            data["Ticker"] = ticker
            rows.append(data)

    warning = ""
    if failures:
        warning = dbc.Alert(L(lang, "unavailable_tickers", names=", ".join(sorted(failures))), color="warning")
    if not rows:
        warning = dbc.Alert(L(lang, "no_data_fetched"), color="danger")
    return rows, warning


@app.callback(
    Output("sector-filter", "options"),
    Output("sector-filter", "value"),
    Input("stocks-raw-store", "data"),
    Input("lang-radio", "value"),
)
def update_sector_filter_options(rows, lang):
    lang = lang or "fr"
    if not rows:
        return [{"label": L(lang, "sector_all"), "value": "all"}], "all"
    sectors = sorted({r.get("sector") for r in rows if r.get("sector") and r.get("sector") != "N/A"})
    options = [{"label": L(lang, "sector_all"), "value": "all"}] + [{"label": s, "value": s} for s in sectors]
    return options, "all"


@app.callback(
    Output("stocks-sector-bar", "figure"),
    Output("stocks-sector-box", "figure"),
    Output("stocks-top-cards", "children"),
    Output("stocks-pe-chart", "figure"),
    Output("stocks-table", "data"),
    Output("stocks-table", "columns"),
    Output("stocks-table", "style_header"),
    Output("stocks-table", "style_cell"),
    Output("stocks-table", "style_data"),
    Output("stocks-csv-store", "data"),
    Input("stocks-raw-store", "data"),
    Input("sector-filter", "value"),
    Input("lang-radio", "value"),
    Input("palette-dropdown", "value"),
    Input("dark-mode-switch", "value"),
)
def render_stock_views(rows, sector_value, lang, palette_code, dark_mode):
    lang = lang or "fr"
    palette = PALETTES.get(palette_code, PALETTE)
    dark = bool(dark_mode)
    style_header, style_cell, style_data = layout.table_style_overrides(dark)
    if not rows:
        placeholder = empty_figure_with_message(L(lang, "load_hint_placeholder"), dark=dark)
        return placeholder, placeholder, "", placeholder, [], [], style_header, style_cell, style_data, ""

    # Noms de colonnes internes gardés stables (français) : ce sont des clés de travail, pas du
    # texte affiché : seul le libellé de colonne du tableau final ("name") est traduit plus bas.
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "sector": "Secteur", "currency": "Devise", "price": "Prix",
        "trailing_pe": "P/E (trailing)", "forward_pe": "P/E (prévisionnel)",
        "price_to_book": "P/B", "dividend_yield": "Rendement dividende (%)",
        "market_cap": "Capitalisation",
        "pe_5y_mean": "P/E moyen 5 ans (approx.)", "pe_5y_percentile": "Position vs historique 5 ans (percentile)",
    })
    priced_all = df.dropna(subset=["P/E (trailing)"]).copy()
    priced_all = priced_all[priced_all["P/E (trailing)"] > 0]

    # --- Comparatif par secteur : toujours calculé sur l'ensemble chargé, pas filtré ---
    sector_bar = go.Figure()
    sector_box = go.Figure()
    if not priced_all.empty:
        sector_means = priced_all.groupby("Secteur")["P/E (trailing)"].mean().sort_values()
        sector_bar.add_trace(go.Bar(
            x=sector_means.index, y=sector_means.values, marker_color=palette[1 % len(palette)],
        ))
        sector_bar.update_layout(
            template="plotly_dark" if dark else "plotly",
            title=L(lang, "sector_avg_pe_title"), xaxis_title="", yaxis_title=L(lang, "axis_pe_avg"),
            margin=dict(t=60, b=100), xaxis=dict(tickangle=-45),
        )
        for i, sector in enumerate(sector_means.index):
            values = priced_all.loc[priced_all["Secteur"] == sector, "P/E (trailing)"]
            sector_box.add_trace(go.Box(y=values, name=sector, marker_color=palette[i % len(palette)]))
        sector_box.update_layout(
            template="plotly_dark" if dark else "plotly",
            title=L(lang, "sector_dist_pe_title"), showlegend=False, yaxis_title="P/E",
            margin=dict(t=60, b=100), xaxis=dict(tickangle=-45),
        )

    # --- Détail (cartes, graphique, tableau) : filtré sur le secteur choisi ---
    detail_df = df if sector_value == "all" else df[df["Secteur"] == sector_value]
    priced = detail_df.dropna(subset=["P/E (trailing)"]).copy()
    priced = priced[priced["P/E (trailing)"] > 0]

    cards = []
    if not priced.empty:
        cheapest = priced.nsmallest(5, "P/E (trailing)")
        priciest = priced.nlargest(5, "P/E (trailing)")
        for title, subset, color in [
            (L(lang, "cheapest_title"), cheapest, "success"),
            (L(lang, "priciest_title"), priciest, "danger"),
        ]:
            items = [
                html.Li(f"{row['Entreprise']} : P/E {row['P/E (trailing)']:.1f} ({row['Secteur']})")
                for _, row in subset.iterrows()
            ]
            cards.append(dbc.Col(dbc.Card(dbc.CardBody([
                html.H6(title, className=f"text-{color}"),
                html.Ul(items, style={"fontSize": "0.85rem"}),
            ])), width=6))
    cards_row = dbc.Row(cards, className="mb-2") if cards else ""

    own_history = priced.dropna(subset=["Position vs historique 5 ans (percentile)"])
    history_cards = []
    if not own_history.empty:
        below_own_history = own_history.nsmallest(5, "Position vs historique 5 ans (percentile)")
        above_own_history = own_history.nlargest(5, "Position vs historique 5 ans (percentile)")
        for title, subset, color in [
            (L(lang, "below_history_title"), below_own_history, "success"),
            (L(lang, "above_history_title"), above_own_history, "danger"),
        ]:
            items = [
                html.Li(
                    f"{row['Entreprise']} : P/E actuel {row['P/E (trailing)']:.1f} vs moyenne 5 ans "
                    f"{row['P/E moyen 5 ans (approx.)']:.1f} (percentile {row['Position vs historique 5 ans (percentile)']:.0f})"
                )
                for _, row in subset.iterrows()
            ]
            history_cards.append(dbc.Col(dbc.Card(dbc.CardBody([
                html.H6(title, className=f"text-{color}"),
                html.Ul(items, style={"fontSize": "0.85rem"}),
            ])), width=6))
    history_cards_row = dbc.Row(history_cards, className="mb-2") if history_cards else ""
    cards_row = html.Div([cards_row, history_cards_row]) if (cards or history_cards) else ""

    plot_df = priced.sort_values("P/E (trailing)")
    fig = go.Figure()
    if not plot_df.empty:
        fig.add_trace(go.Bar(
            x=plot_df["Entreprise"], y=plot_df["P/E (trailing)"],
            marker_color=palette[0],
            text=plot_df["Secteur"], hovertemplate="%{x}<br>P/E: %{y:.1f}<br>%{text}<extra></extra>",
        ))
        fig.add_hline(
            y=plot_df["P/E (trailing)"].mean(), line_dash="dot", line_color="gray",
            annotation_text=L(lang, "basket_avg_annotation"), annotation_position="top left",
        )
    fig.update_layout(
        template="plotly_dark" if dark else "plotly",
        title=L(lang, "pe_by_stock_chart_title"),
        xaxis_title="", yaxis_title="P/E",
        margin=dict(t=60, b=120), xaxis=dict(tickangle=-60),
    )

    table_df = detail_df[[
        "Entreprise", "Ticker", "Secteur", "Devise", "Prix", "P/E (trailing)", "P/E (prévisionnel)",
        "P/B", "Rendement dividende (%)",
        "P/E moyen 5 ans (approx.)", "Position vs historique 5 ans (percentile)", "Capitalisation",
    ]].copy()
    table_df["Capitalisation"] = table_df["Capitalisation"].map(_format_market_cap)
    for col in ["Prix", "P/E (trailing)", "P/E (prévisionnel)", "P/B", "Rendement dividende (%)",
                "P/E moyen 5 ans (approx.)", "Position vs historique 5 ans (percentile)"]:
        table_df[col] = table_df[col].round(2)
    table_df = table_df.sort_values("P/E (trailing)")

    column_label_keys = {
        "Entreprise": "col_company", "Ticker": "col_ticker", "Secteur": "col_sector", "Devise": "col_currency",
        "Prix": "col_price", "P/E (trailing)": "col_pe_trailing", "P/E (prévisionnel)": "col_pe_forward",
        "P/B": "col_pb", "Rendement dividende (%)": "col_div_yield",
        "P/E moyen 5 ans (approx.)": "col_pe_5y_mean", "Position vs historique 5 ans (percentile)": "col_pe_5y_pct",
        "Capitalisation": "col_market_cap",
    }
    columns = [{"name": L(lang, column_label_keys.get(c, c)), "id": c} for c in table_df.columns]
    csv_data = table_df.to_csv(index=False)
    # NaN -> None : sinon un JSON NaN (invalide) part vers le DataTable et s'affiche mal.
    table_df = table_df.astype(object).where(pd.notnull(table_df), None)

    return (sector_bar, sector_box, cards_row, fig, table_df.to_dict("records"), columns,
            style_header, style_cell, style_data, csv_data)


@app.callback(
    Output("stocks-pe-history-chart", "figure"),
    Output("stocks-pe-history-title", "children"),
    Input("stocks-table", "derived_virtual_selected_rows"),
    Input("lang-radio", "value"),
    Input("palette-dropdown", "value"),
    Input("dark-mode-switch", "value"),
    State("stocks-table", "derived_virtual_data"),
)
def update_pe_history_chart(selected_rows, lang, palette_code, dark_mode, virtual_data):
    lang = lang or "fr"
    palette = PALETTES.get(palette_code, PALETTE)
    dark = bool(dark_mode)
    if not selected_rows or not virtual_data:
        return empty_figure_with_message(L(lang, "history_hint_default"), dark=dark), ""

    row = virtual_data[selected_rows[0]]
    ticker, name = row["Ticker"], row["Entreprise"]
    pe_series = get_stock_pe_history(ticker)
    if pe_series.empty:
        return (
            empty_figure_with_message(L(lang, "history_unavailable", name=name), dark=dark),
            L(lang, "history_unavailable_full", name=name),
        )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pe_series.index, y=pe_series.values, mode="lines",
        line=dict(color=palette[0]), name="P/E",
    ))
    fig.add_hline(
        y=float(pe_series.mean()), line_dash="dot", line_color="gray",
        annotation_text=L(lang, "history_mean_annotation"), annotation_position="top left",
    )
    current_pe = row.get("P/E (trailing)")
    if current_pe is not None:
        fig.add_hline(
            y=current_pe, line_dash="dash", line_color=palette[2 % len(palette)],
            annotation_text=L(lang, "history_current_annotation"), annotation_position="bottom left",
        )
    fig.update_layout(
        template="plotly_dark" if dark else "plotly",
        title=L(lang, "history_chart_title", name=name),
        xaxis_title="", yaxis_title="P/E", margin=dict(t=60),
    )
    return fig, ""


@app.callback(
    Output("dcf-result", "children"),
    Output("dcf-chart", "figure"),
    Input("stocks-table", "derived_virtual_selected_rows"),
    Input("dcf-growth-slider", "value"),
    Input("dcf-discount-slider", "value"),
    Input("dcf-terminal-growth-slider", "value"),
    Input("dcf-horizon-slider", "value"),
    Input("lang-radio", "value"),
    Input("palette-dropdown", "value"),
    Input("dark-mode-switch", "value"),
    State("stocks-table", "derived_virtual_data"),
)
def update_dcf(selected_rows, growth_pct, discount_pct, terminal_growth_pct, horizon_years,
                lang, palette_code, dark_mode, virtual_data):
    lang = lang or "fr"
    palette = PALETTES.get(palette_code, PALETTE)
    dark = bool(dark_mode)
    empty_fig = empty_figure_with_message("", dark=dark)
    if not selected_rows or not virtual_data:
        return L(lang, "dcf_hint_default"), empty_fig

    row = virtual_data[selected_rows[0]]
    ticker, name = row["Ticker"], row["Entreprise"]
    inputs = get_dcf_inputs(ticker)
    if not inputs.get("fcf") or not inputs.get("shares_outstanding"):
        msg = L(lang, "dcf_unavailable", name=name)
        return dbc.Alert(msg, color="warning"), empty_figure_with_message(msg, dark=dark)
    if discount_pct <= terminal_growth_pct:
        return dbc.Alert(L(lang, "dcf_invalid_assumptions"), color="warning"), empty_fig

    net_debt = inputs["total_debt"] - inputs["total_cash"]
    result = compute_dcf_fair_value(
        inputs["fcf"], growth_pct, discount_pct, terminal_growth_pct, int(horizon_years),
        net_debt, inputs["shares_outstanding"],
    )
    if result is None:
        return dbc.Alert(L(lang, "dcf_invalid_assumptions"), color="warning"), empty_fig

    fair_value = result["fair_value_per_share"]
    price = inputs.get("price")
    currency = inputs["currency"]
    upside_pct = (fair_value / price - 1) * 100 if price else None

    stat_cols = [
        dbc.Col([html.Small(L(lang, "dcf_fair_value_label"), className="text-muted d-block"),
                 html.H5(f"{fair_value:,.2f} {currency}".replace(",", " "))]),
        dbc.Col([html.Small(L(lang, "dcf_current_price_label"), className="text-muted d-block"),
                 html.H5(f"{price:,.2f} {currency}".replace(",", " ") if price else "N/A")]),
    ]
    if upside_pct is not None:
        stat_cols.append(dbc.Col([
            html.Small(L(lang, "dcf_upside_label"), className="text-muted d-block"),
            html.H5(f"{upside_pct:+.1f} %", className="text-success" if upside_pct >= 0 else "text-danger"),
        ]))
    card = dbc.Card(dbc.CardBody([html.H6(name, className="card-subtitle text-muted mb-2"), dbc.Row(stat_cols)]))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[L(lang, "dcf_fair_value_label"), L(lang, "dcf_current_price_label")],
        y=[fair_value, price or 0],
        marker_color=[palette[0], palette[1 % len(palette)]],
    ))
    fig.update_layout(
        template="plotly_dark" if dark else "plotly",
        title=L(lang, "dcf_chart_title", name=name), yaxis_title=currency, margin=dict(t=60),
    )
    return card, fig


@app.callback(
    Output("download-stocks", "data"),
    Input("btn-download-stocks", "n_clicks"),
    State("stocks-csv-store", "data"),
    prevent_initial_call=True,
)
def download_stocks(n_clicks, csv_data):
    if not csv_data:
        raise dash.exceptions.PreventUpdate
    return dcc.send_string(csv_data, "valorisation_actions.csv")
