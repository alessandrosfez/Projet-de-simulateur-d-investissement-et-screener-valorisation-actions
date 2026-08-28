"""
Enregistrement de tous les callbacks Dash. Importer ce module (voir app.py)
suffit à les enregistrer sur l'instance `app` partagée (app_instance.py) : les
fonctions ci-dessous ne sont pas appelées directement ailleurs, sauf les
helpers d'affichage conditionnel réutilisés par layout.py lui-même.
"""
import base64
import json

import dash
import dash_bootstrap_components as dbc
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

import layout
from app_instance import app
from charts import make_correlation_heatmap, make_sequence_risk_figure
from constants import N_PORTFOLIOS_MAX, TICKER_KEYS, TICKERS
from engine import inject_shock, simulate_index_returns, simulate_portfolio_asset_returns, suggest_optimal_weights
from i18n import L, PALETTE, PALETTE_CODES, PALETTE_NAMES, PALETTES
from market_data import get_aligned_returns, get_monthly_returns
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
