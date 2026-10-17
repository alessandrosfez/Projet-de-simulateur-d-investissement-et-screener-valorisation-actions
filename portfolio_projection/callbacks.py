"""
Enregistrement de tous les callbacks Dash. Importer ce module (voir app.py)
suffit à les enregistrer sur l'instance `app` partagée (app_instance.py) : les
fonctions ci-dessous ne sont pas appelées directement ailleurs, sauf les
helpers d'affichage conditionnel réutilisés par layout.py lui-même.
"""
import base64
import io
import json
import time

import dash
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

import layout
import portfolio_db
import portfolio_engine
from app_instance import app
from charts import make_correlation_heatmap, make_pit_histogram, make_sequence_risk_figure
from constants import BACKTEST_ANCHORS, N_PORTFOLIOS_MAX, PEA_CONTRIBUTION_CAP, PEA_TAX_RATE, TICKER_KEYS, TICKERS
from engine import (
    inject_shock, simulate_index_returns, simulate_portfolio_asset_returns, suggest_optimal_weights,
    summarize_calibration, walk_forward_calibration,
)
from i18n import L, PALETTE, PALETTE_CODES, PALETTE_NAMES, PALETTES
from market_data import (
    data_freshness, get_aligned_returns, get_aligned_returns_for_tickers, get_current_price,
    get_daily_price_history, get_daily_total_return_history, get_monthly_returns, get_served_download_times,
    get_ticker_name, resolve_isin_to_ticker,
)
from results import (
    build_envelope_comparison_figure, build_historique_metrics_outputs, build_metric_cards,
    build_metrics_outputs, build_pea_milestone_cards, build_performance_cards, build_portfolio_totals_cards,
    build_real_portfolio_future_figure,
    build_rebalancing_table_data, build_real_vs_simulated_figure, build_schedules, build_sequence_risk_series,
    compute_results, render_objective_result, render_rolling_backtest_result,
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
    Output("pea-cap-container", "style"),
    Input("envelope-radio", "value"),
)(layout.toggle_pea_cap_container)

app.callback(
    Output("pea-overflow-container", "style"),
    Input("pea-cap-checkbox", "value"),
)(layout.toggle_pea_overflow_container)

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

app.callback(Output("horizon-slider-container", "style"), Input("view-mode-radio", "value"))(layout.toggle_prevision_only)

app.callback(Output("backtest-anchor-container", "style"), Input("view-mode-radio", "value"))(layout.toggle_historique_only)

# Réglages qui n'ont d'effet que sur la simulation Monte Carlo (méthode, choc injecté, bandes de
# percentiles, nombre de simulations/seed, comparatif PEA/CTO) ou qui relèvent de la planification
# future plutôt que de la simple relecture d'un historique (retraits, apports, frais/fiscalité,
# mode objectif) : masqués en mode historique pour garder la sidebar concentrée sur ce qui compte
# vraiment pour "qu'est-ce qui s'est passé ?" (source, historique de calibration, point de départ).
for _container_id in (
    "method-section-container", "mu-override-container", "crisis-section-container",
    "sim-settings-container", "compare-envelopes-option-container",
    "withdrawals-section-container", "contrib-section-container", "fees-tax-section-container",
    "objective-section-container",
    # Onglets entiers de l'accordéon devenus vides en mode historique (leur seul contenu est l'un
    # des containers ci-dessus) : masqués en entier (en-tête compris), pas juste vidés.
    "accordion-item-retraits-crise", "accordion-item-contrib", "accordion-item-fees", "accordion-item-sim",
):
    app.callback(Output(_container_id, "style"), Input("view-mode-radio", "value"))(layout.toggle_prevision_only)

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
    palette = PALETTES.get(palette_code, PALETTE)
    dark = bool(dark_mode)
    view_mode = view_mode or "prevision"
    style_header, style_cell, style_data = layout.table_style_overrides(dark)
    trajectories_title = L(lang, "historique_trajectory_title") if view_mode == "historique" else L(lang, "trajectories_title")
    prog_container_style = {"display": "none"} if view_mode == "historique" else {"flex": "1", "minWidth": "0"}
    metrics_title = L(lang, "historique_metrics_title") if view_mode == "historique" else L(lang, "metrics_title")
    empty_fig = go.Figure()
    empty_fig.update_layout(template="plotly_dark" if dark else "plotly")
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
    palette = PALETTES.get(palette_code, PALETTE)
    dark = bool(dark_mode)
    style_header, style_cell, style_data = layout.table_style_overrides(dark)
    trajectories_title = L(lang, "historique_trajectory_title") if view_mode == "historique" else L(lang, "trajectories_title")
    prog_container_style = {"display": "none"} if view_mode == "historique" else {"flex": "1", "minWidth": "0"}
    metrics_title = L(lang, "historique_metrics_title") if view_mode == "historique" else L(lang, "metrics_title_portfolio")

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
                {"display": "none"}, empty_fig, {"display": "none"}, empty_fig, "", "",
                trajectories_title, prog_container_style, metrics_title)

    source_key = "etf" if source == "etf" else "indice"
    try:
        aligned = get_aligned_returns(universe, lookback_years, source_key)
    except ValueError as exc:
        return (empty_fig, empty_fig, [], [], [], style_header, style_cell, style_data, {}, "",
                dbc.Alert(str(exc), color="danger"), {"display": "none"}, empty_fig,
                {"display": "none"}, empty_fig, "", "", trajectories_title, prog_container_style, metrics_title)
    if aligned.empty:
        return (empty_fig, empty_fig, [], [], [], style_header, style_cell, style_data, {}, "",
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
        cards, table_data, table_columns, style_header, style_cell, style_data, table_tooltip_header, csv_data,
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


# ============================================================
# 10. CALLBACKS :onglet 3 (portefeuille réel)
# ============================================================
# Seul endroit de l'appli où des callbacks ont un effet de bord en écriture (insertion/suppression
# en base, voir portfolio_db.py) : tous les autres callbacks de ce fichier sont de purs
# lecture/calcul/rendu. Pattern retenu : chaque callback d'écriture écrit en base puis incrémente
# "tab3-refresh-trigger" (horodatage, toujours différent -> toujours un "vrai" changement côté
# Dash), qu'un unique callback de lecture/rendu consomme pour tout recalculer depuis la base. Sans
# ce détour par un Store, relier directement la suppression de ligne d'un tableau (son propre prop
# "data" en Input) au rendu de CE MÊME tableau (son prop "data" en Output) créerait une dépendance
# circulaire refusée par Dash.


def _ticker_display_label(ticker: str) -> str:
    """Libellé affiché pour un ticker dans les menus déroulants de l'onglet 3 : priorité au nom
    d'indice connu (constants.TICKERS, voir portfolio_engine.ticker_display_label), repli sur le
    nom du fonds/de l'entreprise renvoyé par Yahoo Finance (market_data.get_ticker_name) pour un
    ticker hors de cet univers -- ex: "PAASI.PA (Amundi PEA Asie Emergente (MSCI...)". Fait un
    appel réseau (caché 24h) uniquement ici, pas dans layout.build_tab3, pour garder le premier
    rendu de page sans attente réseau (voir refresh_tab3, qui tourne aussi au chargement initial
    et écrase ces options juste après)."""
    curated = portfolio_engine.ticker_display_label(ticker)
    if curated != ticker:
        return curated
    name = get_ticker_name(ticker)
    return f"{ticker} ({name})" if name else ticker


def _validated_ticker(ticker: str):
    """None si le ticker est vide ou si aucun prix n'est disponible pour lui (typo, délisting) --
    sert de garde-fou à la saisie plutôt que de laisser une valeur invalide entrer en base et
    échouer silencieusement plus tard dans la reconstruction de la courbe de valeur."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return None, None
    price = get_current_price(ticker)
    return (ticker, price) if price is not None else (ticker, None)


_CSV_ERROR_TO_FORM_ERROR_KEY = {
    "missing_ticker": "form_error_invalid_ticker",
    "missing_date": "form_error_missing_field",
    "invalid_date": "form_error_missing_field",
    "missing_amount": "form_error_missing_field",
    "invalid_amount": "form_error_invalid_amount",
}


@app.callback(
    Output("tab3-refresh-trigger", "data", allow_duplicate=True),
    Output("tab3-tx-form-error", "children"),
    Input("tab3-btn-add-tx", "n_clicks"),
    State("tab3-tx-ticker-input", "value"),
    State("tab3-tx-date-input", "date"),
    State("tab3-tx-amount-input", "value"),
    State("tab3-tx-price-input", "value"),
    State("tab3-tx-fee-input", "value"),
    State("lang-radio", "value"),
    prevent_initial_call=True,
)
def add_transaction(n_clicks, ticker, date, amount, price, fee, lang):
    lang = lang or "fr"
    ticker, ticker_price = _validated_ticker(ticker)
    if not ticker or ticker_price is None:
        return dash.no_update, L(lang, "form_error_invalid_ticker", ticker=ticker or "")
    # Même validation structurelle que l'import CSV (voir portfolio_engine.validate_transactions_rows),
    # appliquée à une unique ligne -- une seule source de vérité pour "qu'est-ce qu'une transaction
    # valide", que la donnée arrive du formulaire ou d'un fichier.
    row_df = pd.DataFrame([{"ticker": ticker, "date": date, "amount_eur": amount, "price": price, "fee_eur": fee}])
    valid_rows, errors = portfolio_engine.validate_transactions_rows(row_df)
    if errors:
        return dash.no_update, L(lang, _CSV_ERROR_TO_FORM_ERROR_KEY[errors[0][1]])
    row = valid_rows[0]
    portfolio_db.insert_transaction(row["ticker"], row["date"], row["amount_eur"], row["price"], row["fee_eur"])
    return time.time(), ""


@app.callback(
    Output("tab3-refresh-trigger", "data", allow_duplicate=True),
    Output("tab3-div-form-error", "children"),
    Input("tab3-btn-add-div", "n_clicks"),
    State("tab3-div-ticker-input", "value"),
    State("tab3-div-date-input", "date"),
    State("tab3-div-amount-input", "value"),
    State("lang-radio", "value"),
    prevent_initial_call=True,
)
def add_dividend(n_clicks, ticker, date, amount, lang):
    lang = lang or "fr"
    ticker, ticker_price = _validated_ticker(ticker)
    if not ticker or ticker_price is None:
        return dash.no_update, L(lang, "form_error_invalid_ticker", ticker=ticker or "")
    row_df = pd.DataFrame([{"ticker": ticker, "date": date, "amount_eur": amount}])
    valid_rows, errors = portfolio_engine.validate_dividends_rows(row_df)
    if errors:
        return dash.no_update, L(lang, _CSV_ERROR_TO_FORM_ERROR_KEY[errors[0][1]])
    row = valid_rows[0]
    portfolio_db.insert_dividend(row["ticker"], row["date"], row["amount_eur"])
    return time.time(), ""


@app.callback(
    Output("tab3-refresh-trigger", "data", allow_duplicate=True),
    Output("tab3-weight-form-error", "children"),
    Input("tab3-btn-add-weight", "n_clicks"),
    State("tab3-weight-ticker-input", "value"),
    State("tab3-weight-pct-input", "value"),
    State("lang-radio", "value"),
    prevent_initial_call=True,
)
def add_weight(n_clicks, ticker, weight_pct, lang):
    lang = lang or "fr"
    ticker, ticker_price = _validated_ticker(ticker)
    if not ticker or ticker_price is None:
        return dash.no_update, L(lang, "form_error_invalid_ticker", ticker=ticker or "")
    if weight_pct is None:
        return dash.no_update, L(lang, "form_error_missing_field")
    if float(weight_pct) < 0:
        return dash.no_update, L(lang, "form_error_invalid_amount")
    portfolio_db.upsert_target_weight(ticker, float(weight_pct))
    return time.time(), ""


@app.callback(
    Output("tab3-refresh-trigger", "data", allow_duplicate=True),
    Output("tab3-csv-import-result", "children"),
    Input("tab3-upload-csv", "contents"),
    State("lang-radio", "value"),
    prevent_initial_call=True,
)
def import_csv(contents, lang):
    lang = lang or "fr"
    if contents is None:
        raise dash.exceptions.PreventUpdate
    _content_type, content_string = contents.split(",", 1)
    decoded = base64.b64decode(content_string)
    try:
        df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))
    except Exception:
        return dash.no_update, L(lang, "csv_import_unreadable_file")

    kind = portfolio_engine.detect_csv_kind(df)
    if kind is None:
        return dash.no_update, L(lang, "csv_import_unknown_format")

    unresolved_isins = []
    if kind == "trade_republic":
        # Trade Republic identifie les instruments par ISIN (colonne "symbol"), pas par ticker
        # boursier : résolution réseau avant de pouvoir réutiliser le même chemin que le schéma
        # maison (get_current_price attend un ticker Yahoo, pas un ISIN).
        raw_rows, errors = portfolio_engine.extract_trade_republic_buys(df)
        unique_isins = sorted({r["isin"] for r in raw_rows})
        isin_to_ticker = {isin: resolve_isin_to_ticker(isin) for isin in unique_isins}
        unresolved_isins = [isin for isin, ticker in isin_to_ticker.items() if ticker is None]
        valid_rows = [
            {"ticker": isin_to_ticker[r["isin"]], "date": r["date"], "amount_eur": r["amount_eur"],
             "price": r["price"], "fee_eur": r["fee_eur"]}
            for r in raw_rows if isin_to_ticker[r["isin"]] is not None
        ]
        kind = "transactions"  # même chemin d'insertion que le schéma maison à partir d'ici
    else:
        valid_rows, errors = (
            portfolio_engine.validate_transactions_rows(df) if kind == "transactions"
            else portfolio_engine.validate_dividends_rows(df)
        )

    # Tickers validés un par un (uniques), pas ligne par ligne : la plupart des imports répètent
    # une poignée de tickers, et get_current_price est caché (cached_ttl) -- évite des appels
    # réseau redondants pour un fichier de centaines de lignes sur quelques titres.
    unique_tickers = sorted({row["ticker"] for row in valid_rows})
    invalid_tickers = [t for t in unique_tickers if get_current_price(t) is None]
    insertable_rows = [row for row in valid_rows if row["ticker"] not in invalid_tickers]
    skipped_for_ticker = len(valid_rows) - len(insertable_rows)

    if not insertable_rows:
        return dash.no_update, L(lang, "csv_import_no_valid_rows")

    if kind == "transactions":
        n_inserted = portfolio_db.insert_transactions_bulk(
            [(r["ticker"], r["date"], r["amount_eur"], r["price"], r["fee_eur"]) for r in insertable_rows]
        )
    else:
        n_inserted = portfolio_db.insert_dividends_bulk(
            [(r["ticker"], r["date"], r["amount_eur"]) for r in insertable_rows]
        )

    messages = [html.Div(L(lang, "csv_import_success", n=n_inserted))]
    details = [L(lang, f"csv_error_{code}", line=line) for line, code in errors]
    details += [f"{t} ({L(lang, 'csv_import_invalid_ticker_reason')})" for t in invalid_tickers]
    details += [f"{isin} ({L(lang, 'csv_import_unresolved_isin_reason')})" for isin in unresolved_isins]
    n_skipped = len(errors) + skipped_for_ticker + len(unresolved_isins)
    if details:
        messages.append(html.Div(L(lang, "csv_import_skipped", n=n_skipped, details="; ".join(details))))
    return time.time(), html.Div(messages)


@app.callback(
    Output("tab3-download-tx-template", "data"),
    Input("tab3-btn-download-tx-template", "n_clicks"),
    prevent_initial_call=True,
)
def send_transactions_template(n_clicks):
    return dcc.send_string("ticker,date,amount_eur,price,fee_eur\nMC.PA,2024-01-15,1000.0,650.0,5.0\n",
                            "modele_transactions.csv")


@app.callback(
    Output("tab3-download-div-template", "data"),
    Input("tab3-btn-download-div-template", "n_clicks"),
    prevent_initial_call=True,
)
def send_dividends_template(n_clicks):
    return dcc.send_string("ticker,date,amount_eur\nMC.PA,2024-12-01,20.0\n", "modele_dividendes.csv")


@app.callback(
    Output("tab3-refresh-trigger", "data", allow_duplicate=True),
    Input("tab3-tx-table", "data"),
    prevent_initial_call=True,
)
def delete_removed_transactions(table_data):
    current_ids = set(portfolio_db.get_transactions()["id"].tolist())
    submitted_ids = {row["id"] for row in (table_data or []) if "id" in row}
    removed = current_ids - submitted_ids
    if not removed:
        raise dash.exceptions.PreventUpdate
    for row_id in removed:
        portfolio_db.delete_transaction(int(row_id))
    return time.time()


@app.callback(
    Output("tab3-refresh-trigger", "data", allow_duplicate=True),
    Input("tab3-div-table", "data"),
    prevent_initial_call=True,
)
def delete_removed_dividends(table_data):
    current_ids = set(portfolio_db.get_dividends()["id"].tolist())
    submitted_ids = {row["id"] for row in (table_data or []) if "id" in row}
    removed = current_ids - submitted_ids
    if not removed:
        raise dash.exceptions.PreventUpdate
    for row_id in removed:
        portfolio_db.delete_dividend(int(row_id))
    return time.time()


@app.callback(
    Output("tab3-refresh-trigger", "data", allow_duplicate=True),
    Input("tab3-weights-table", "data"),
    prevent_initial_call=True,
)
def delete_removed_weights(table_data):
    current_tickers = set(portfolio_db.get_target_weights()["ticker"].tolist())
    submitted_tickers = {row["ticker"] for row in (table_data or []) if "ticker" in row}
    removed = current_tickers - submitted_tickers
    if not removed:
        raise dash.exceptions.PreventUpdate
    for ticker in removed:
        portfolio_db.delete_target_weight(ticker)
    return time.time()


@app.callback(
    Output("tab3-totals-cards", "children"),
    Output("tab3-real-pace-display", "children"),
    Output("tab3-real-vs-sim-graph", "figure"),
    Output("tab3-projection-graph", "figure"),
    Output("tab3-corr-heatmap", "figure"),
    Output("tab3-rebalancing-table", "data"),
    Output("tab3-rebalancing-table", "columns"),
    Output("tab3-rebalancing-table", "style_header"),
    Output("tab3-rebalancing-table", "style_cell"),
    Output("tab3-rebalancing-table", "style_data"),
    Output("tab3-rebalancing-warning", "children"),
    Output("tab3-weights-table", "data"),
    Output("tab3-weights-table", "style_header"),
    Output("tab3-weights-table", "style_cell"),
    Output("tab3-weights-table", "style_data"),
    Output("tab3-tx-table", "data"),
    Output("tab3-tx-table", "style_header"),
    Output("tab3-tx-table", "style_cell"),
    Output("tab3-tx-table", "style_data"),
    Output("tab3-div-table", "data"),
    Output("tab3-div-table", "style_header"),
    Output("tab3-div-table", "style_cell"),
    Output("tab3-div-table", "style_data"),
    Output("tab3-tx-ticker-input", "options"),
    Output("tab3-div-ticker-input", "options"),
    Output("tab3-weight-ticker-input", "options"),
    Input("tab3-refresh-trigger", "data"),
    Input("lang-radio", "value"),
    Input("dark-mode-switch", "value"),
    Input("lookback-slider", "value"),
    Input("method-radio", "value"),
    Input("n-sims-slider", "value"),
    Input("seed-input", "value"),
    Input("horizon-slider", "value"),
    Input("fee-slider", "value"),
    Input("tax-checkbox", "value"),
)
def refresh_tab3(_trigger, lang, dark_mode, lookback_years, method, n_sims, seed, horizon_years, annual_fee_pct,
                  apply_tax):
    lang = lang or "fr"
    dark = bool(dark_mode)
    apply_tax = bool(apply_tax and "on" in apply_tax)
    style_header, style_cell, style_data = layout.table_style_overrides(dark)
    table_styles = (style_header, style_cell, style_data)

    transactions = portfolio_db.get_transactions()
    dividends = portfolio_db.get_dividends()
    target_weights = portfolio_db.get_target_weights()

    holdings = portfolio_engine.reconstruct_holdings(transactions)
    current_values = pd.Series(dtype=float)
    price_histories = {}
    if not holdings.empty:
        first_date = pd.to_datetime(transactions["date"]).min().strftime("%Y-%m-%d")
        for _, row in holdings.iterrows():
            ticker = row["ticker"]
            price = get_current_price(ticker)
            if price is not None:
                current_values[ticker] = row["quantity"] * price
            history = get_daily_price_history(ticker, first_date)
            if not history.empty:
                price_histories[ticker] = history

    current_value_total = float(current_values.sum()) if not current_values.empty else 0.0
    totals = portfolio_engine.compute_totals(transactions, dividends, current_value_total)
    totals_cards = build_portfolio_totals_cards(totals, lang)

    real_series = portfolio_engine.reconstruct_equity_curve(transactions, price_histories)

    rebalancing_df = portfolio_engine.compute_rebalancing_plan(target_weights, current_values)
    rebalancing_data, rebalancing_columns = build_rebalancing_table_data(rebalancing_df, lang)
    rebalancing_warning = ""
    if target_weights.empty:
        # Sans pondération cible, le tableau lui-même n'a ni data ni columns (voir
        # build_rebalancing_table_data) et ne s'affiche donc pas du tout -- un texte explicite ici
        # évite que la section ait l'air cassée/vide sans raison apparente.
        rebalancing_warning = html.Div(L(lang, "rebalancing_no_weights_hint"), className="text-muted")
    elif abs(target_weights["weight_pct"].sum() - 100) > 1:
        rebalancing_warning = dbc.Alert(
            L(lang, "rebalancing_weights_not_100_warning"), color="warning", className="py-1 px-2 mb-2",
        )

    empty_fig = go.Figure()
    empty_fig.update_layout(template="plotly_dark" if dark else "plotly")
    real_vs_sim_fig = empty_fig
    projection_fig = empty_fig
    corr_fig = empty_fig

    monthly_amounts = portfolio_engine.monthly_contribution_schedule(transactions)
    monthly_pace = float(monthly_amounts.mean()) if not monthly_amounts.empty else 0.0
    real_pace_display = (
        L(lang, "real_pace_label", amount=f"{monthly_pace:,.0f}".replace(",", " "))
        if not monthly_amounts.empty else L(lang, "real_pace_no_data")
    )
    if not holdings.empty and not current_values.empty:
        tickers = list(holdings["ticker"])
        try:
            aligned = get_aligned_returns_for_tickers(tickers, lookback_years or 10)
        except Exception:
            aligned = pd.DataFrame()

        if not aligned.empty and list(aligned.columns) == tickers:
            if len(tickers) >= 2:
                corr_matrix = aligned.corr()
                labels = [_ticker_display_label(t) for t in corr_matrix.columns]
                corr_matrix = corr_matrix.set_axis(labels, axis=0).set_axis(labels, axis=1)
                corr_fig = make_correlation_heatmap(corr_matrix, lang=lang, dark=dark)

            weights_vec = current_values.reindex(tickers).fillna(0.0).to_numpy()
            total_w = weights_vec.sum()
            if total_w > 0:
                weights_vec = weights_vec / total_w

                # Poids actuels ("à l'instant t") figés pour toute la projection -- pas de
                # rééquilibrage simulé dans le temps, même simplification que les pondérations
                # suggérées de l'onglet 2.
                n_months_forward = (horizon_years or 20) * 12
                asset_returns_forward = simulate_portfolio_asset_returns(
                    aligned, n_months_forward, n_sims or 500, seed or 42, method or "bootstrap",
                )
                portfolio_returns_forward = asset_returns_forward @ weights_vec
                projection_fig = build_real_portfolio_future_figure(
                    portfolio_returns_forward, current_value_total, monthly_pace,
                    annual_fee_pct=annual_fee_pct or 0.0, apply_tax=apply_tax, tax_rate=PEA_TAX_RATE,
                    lower_pct=10, upper_pct=90, lang=lang, palette=PALETTE, dark=dark,
                )

                if not monthly_amounts.empty:
                    n_months = len(monthly_amounts)
                    asset_returns = simulate_portfolio_asset_returns(
                        aligned, n_months, n_sims or 500, seed or 42, method or "bootstrap",
                    )
                    portfolio_returns = asset_returns @ weights_vec
                    real_vs_sim_fig = build_real_vs_simulated_figure(
                        portfolio_returns, monthly_amounts.values, monthly_amounts.index, real_series,
                        annual_fee_pct=0.0, lower_pct=10, upper_pct=90, lang=lang, palette=PALETTE, dark=dark,
                    )
        elif not real_series.empty:
            # Historique insuffisant pour aligner tous les tickers détenus (voir
            # get_aligned_returns_for_tickers) : on affiche quand même la courbe réelle seule,
            # plutôt que rien, la comparaison simulée n'étant qu'un complément.
            real_vs_sim_fig.add_trace(go.Scatter(
                x=real_series.index, y=real_series.values, mode="lines",
                name=L(lang, "real_equity_trace"), line=dict(color=PALETTE[0], width=2),
            ))
            real_vs_sim_fig.update_layout(
                title=dict(text=L(lang, "real_vs_simulated_chart_title"), font=dict(size=14)),
                xaxis_title=L(lang, "date_axis"), yaxis_title=L(lang, "value_axis"), margin=dict(t=60),
            )

    weights_data = target_weights.to_dict("records")
    tx_data = transactions.to_dict("records")
    div_data = dividends.to_dict("records")
    ticker_options = [
        {"label": _ticker_display_label(t), "value": t}
        for t in portfolio_engine.known_tickers(transactions, dividends, target_weights)
    ]

    return (
        totals_cards, real_pace_display, real_vs_sim_fig, projection_fig, corr_fig,
        rebalancing_data, rebalancing_columns, *table_styles, rebalancing_warning,
        weights_data, *table_styles,
        tx_data, *table_styles,
        div_data, *table_styles,
        ticker_options, ticker_options, ticker_options,
    )


@app.callback(
    Output("apport-constant-slider", "value", allow_duplicate=True),
    Input("tab3-btn-use-real-pace", "n_clicks"),
    prevent_initial_call=True,
)
def apply_real_pace_to_simulator(n_clicks):
    # apport-constant-slider est dans CONFIG_FIELDS (layout.py) et upload_config y écrit déjà avec
    # allow_duplicate=True -- pas de conflit. Survit à un changement de langue : CONFIG_FIELDS
    # alimente les State de rebuild_on_language_change, dont gv() relit la valeur courante du
    # curseur, pas un défaut codé en dur (voir layout.build_sidebar).
    schedule = portfolio_engine.monthly_contribution_schedule(portfolio_db.get_transactions())
    if schedule.empty:
        raise dash.exceptions.PreventUpdate
    return portfolio_engine.clamp_to_slider(float(schedule.mean()), 100, 1000, 10)


@app.callback(
    Output("tab3-pea-milestones", "children"),
    Input("tab3-pea-opening-date", "date"),
    Input("tab3-refresh-trigger", "data"),
    Input("lang-radio", "value"),
)
def refresh_pea_milestones(opening_date, _trigger, lang):
    lang = lang or "fr"
    # Enregistre seulement si c'est le sélecteur de date qui a déclenché ET que la valeur diffère
    # de la base : le composant est reconstruit (donc ré-émis) à chaque changement de langue, mais
    # il est pré-rempli depuis la base (voir layout.build_tab3), donc cette ré-émission ne change
    # rien -- jamais d'écriture pour un simple re-rendu.
    if dash.ctx.triggered_id == "tab3-pea-opening-date":
        new_date = opening_date[:10] if opening_date else None
        if new_date != portfolio_db.get_pea_opening_date():
            portfolio_db.set_pea_opening_date(new_date)

    transactions = portfolio_db.get_transactions()
    dividends = portfolio_db.get_dividends()
    stored_date = portfolio_db.get_pea_opening_date()
    opening_is_estimated = stored_date is None
    if opening_is_estimated:
        if transactions.empty:
            return html.Div(L(lang, "pea_milestones_no_data"), className="text-muted")
        opening = pd.to_datetime(transactions["date"]).min()
    else:
        opening = pd.Timestamp(stored_date)

    today = pd.Timestamp.today().normalize()
    milestones = portfolio_engine.pea_milestones(opening, today)
    current_value = 0.0
    for _, row in portfolio_engine.reconstruct_holdings(transactions).iterrows():
        price = get_current_price(row["ticker"])
        if price is not None:
            current_value += row["quantity"] * price
    totals = portfolio_engine.compute_totals(transactions, dividends, current_value)
    schedule = portfolio_engine.monthly_contribution_schedule(transactions)
    cap = portfolio_engine.pea_cap_usage(
        transactions, monthly_pace=float(schedule.mean()) if not schedule.empty else 0.0, today=today,
    )
    tax = portfolio_engine.latent_withdrawal_tax(
        totals["current_value"], totals["total_dividends"], totals["total_invested"] + totals["total_fees"],
        milestones["is_mature"],
    )
    return build_pea_milestone_cards(milestones, cap, tax, opening_is_estimated, lang)


@app.callback(
    Output("tab3-performance-cards", "children"),
    Input("tab3-refresh-trigger", "data"),
    Input("tab3-benchmark-ticker-input", "value"),
    Input("lang-radio", "value"),
)
def refresh_performance(_trigger, benchmark_ticker, lang):
    # Callback séparé de refresh_tab3 (déjà très chargé) : changer de référence ne doit recalculer
    # que cette section. Les prix et historiques réels sont mis en cache (cached_ttl), donc les
    # relire ici ne refait pas d'appel réseau.
    lang = lang or "fr"
    transactions = portfolio_db.get_transactions()
    dividends = portfolio_db.get_dividends()
    if transactions.empty:
        return html.Div(L(lang, "performance_no_data"), className="text-muted")

    holdings = portfolio_engine.reconstruct_holdings(transactions)
    first_date = pd.to_datetime(transactions["date"]).min().strftime("%Y-%m-%d")
    current_value_total = 0.0
    price_histories = {}
    for _, row in holdings.iterrows():
        price = get_current_price(row["ticker"])
        if price is not None:
            current_value_total += row["quantity"] * price
        history = get_daily_price_history(row["ticker"], first_date)
        if not history.empty:
            price_histories[row["ticker"]] = history

    today = pd.Timestamp.today().normalize()
    perf = {
        "xirr": portfolio_engine.xirr(
            portfolio_engine.portfolio_cash_flows(transactions, dividends, current_value_total, today)
        ),
        "twr": portfolio_engine.time_weighted_return(
            portfolio_engine.reconstruct_equity_curve(transactions, price_histories), transactions, dividends,
        ),
        "real_value": current_value_total,
    }

    warning = None
    if benchmark_ticker:
        benchmark_curve = portfolio_engine.benchmark_equity_curve(
            transactions, get_daily_total_return_history(benchmark_ticker, first_date),
        )
        if benchmark_curve.empty:
            warning = dbc.Alert(
                L(lang, "benchmark_unavailable", ticker=benchmark_ticker), color="warning", className="py-1 px-2 mb-2",
            )
        else:
            benchmark_value = float(benchmark_curve.iloc[-1])
            perf["benchmark_label"] = _ticker_display_label(benchmark_ticker)
            perf["benchmark_value"] = benchmark_value
            perf["benchmark_xirr"] = portfolio_engine.xirr(portfolio_engine.benchmark_cash_flows(
                transactions, benchmark_value, benchmark_curve.index[-1],
            ))

    return html.Div([warning, build_performance_cards(perf, lang)] if warning else [build_performance_cards(perf, lang)])


# ============================================================
# 11. CALLBACKS : onglet 4 (validation du modèle, backtest walk-forward)
# ============================================================
# Un seul n_sims par origine, modeste (300) et non réglable par l'utilisateur : situer un point
# réel dans une distribution simulée n'a pas besoin de la précision fine utilisée ailleurs pour
# afficher des bandes de percentiles, et ce nombre est multiplié par chaque date d'origine testée
# (des dizaines à des centaines) -- un curseur exposé inviterait à le monter sans que ça change le
# diagnostic, au prix d'un calcul bien plus lent.
VALIDATION_N_SIMS = 300
VALIDATION_SEED = 42
VALIDATION_MIN_CALIBRATION_MONTHS = 24
# Historique propre au test, indépendant du curseur lookback-slider (plafonné à 30 ans) : le nombre
# de dates d'origine testables, donc la valeur du diagnostic, croît directement avec la longueur
# de l'historique -- yfinance renvoie simplement tout ce qui existe s'il y en a moins.
VALIDATION_LOOKBACK_YEARS = 50


@app.callback(
    Output("validation-pit-graph-normal", "figure"),
    Output("validation-pit-graph-bootstrap", "figure"),
    Output("validation-coverage-table", "data"),
    Output("validation-coverage-table", "columns"),
    Output("validation-info-caption", "children"),
    Output("validation-error", "children"),
    Input("validation-run-btn", "n_clicks"),
    State("validation-ticker-dropdown", "value"),
    State("validation-source-radio", "value"),
    State("validation-horizon-radio", "value"),
    State("validation-step-radio", "value"),
    State("lang-radio", "value"),
    State("dark-mode-switch", "value"),
    prevent_initial_call=True,
)
def run_model_validation(n_clicks, index_name, source, horizon_months, step_months, lang, dark_mode):
    lang = lang or "fr"
    dark = bool(dark_mode)
    empty_fig = go.Figure()
    empty_fig.update_layout(template="plotly_dark" if dark else "plotly")

    ticker = TICKERS[index_name][source or "indice"]
    try:
        returns_hist = get_monthly_returns(ticker, VALIDATION_LOOKBACK_YEARS)
    except Exception:
        return empty_fig, empty_fig, [], [], "", L(lang, "validation_insufficient_history")

    results_by_method = {}
    for method in ("normal", "bootstrap"):
        results_by_method[method] = walk_forward_calibration(
            returns_hist, horizon_months, VALIDATION_N_SIMS, VALIDATION_SEED, method,
            step_months=step_months or 12, min_calibration_months=VALIDATION_MIN_CALIBRATION_MONTHS,
        )

    n_origins = results_by_method["normal"]["n_origins"]
    if n_origins == 0:
        return empty_fig, empty_fig, [], [], "", L(lang, "validation_insufficient_history")

    pit_normal = results_by_method["normal"]["pit"]
    pit_bootstrap = results_by_method["bootstrap"]["pit"]
    fig_normal = make_pit_histogram(
        pit_normal, L(lang, "pit_histogram_title_normal"), lang=lang, palette=PALETTE, dark=dark,
    )
    fig_bootstrap = make_pit_histogram(
        pit_bootstrap, L(lang, "pit_histogram_title_bootstrap"), lang=lang, palette=PALETTE, dark=dark,
    )

    bands = ((5, 95), (25, 75))
    summary_normal = {row["lower_pct"]: row for row in summarize_calibration(pit_normal, bands=bands)}
    summary_bootstrap = {row["lower_pct"]: row for row in summarize_calibration(pit_bootstrap, bands=bands)}
    col_band = L(lang, "validation_col_band")
    col_nominal = L(lang, "validation_col_nominal")
    col_normal = L(lang, "validation_col_observed_normal")
    col_bootstrap = L(lang, "validation_col_observed_bootstrap")
    table_data = [
        {
            col_band: f"{lo}-{hi} %",
            col_nominal: summary_normal[lo]["nominal_pct"],
            col_normal: summary_normal[lo]["observed_pct"],
            col_bootstrap: summary_bootstrap[lo]["observed_pct"],
        }
        for lo, hi in bands
    ]
    table_columns = [{"name": c, "id": c} for c in [col_band, col_nominal, col_normal, col_bootstrap]]

    n_effective = results_by_method["normal"]["n_effective"]
    info_caption = html.Div([
        html.Div(L(lang, "validation_n_origins_label", n=n_origins)),
        html.Div(L(lang, "validation_n_effective_label", n=n_effective)),
        html.Div(L(lang, "validation_overlap_warning"), className="fst-italic mt-1"),
    ])

    return fig_normal, fig_bootstrap, table_data, table_columns, info_caption, ""


# ============================================================
# 12. CALLBACKS : fraîcheur des données de marché (badge de l'en-tête)
# ============================================================

@app.callback(
    Output("data-freshness-badge", "children"),
    Input("data-freshness-interval", "n_intervals"),
    Input("lang-radio", "value"),
)
def refresh_data_freshness(_n_intervals, lang):
    lang = lang or "fr"
    freshness = data_freshness(get_served_download_times(), time.time())
    if freshness is None:
        return None
    date_text = freshness["oldest"].strftime(L(lang, "freshness_date_format"))
    if freshness["is_stale"]:
        label = L(lang, "freshness_badge_stale", date=date_text)
        tooltip = L(lang, "freshness_help_stale", days=int(freshness["age_days"]))
        color = "warning"
    else:
        label = L(lang, "freshness_badge", date=date_text)
        tooltip = L(lang, "freshness_help")
        color = "secondary"
    return [
        dbc.Badge(label, id="data-freshness-pill", color=color, className="fw-normal", style={"cursor": "help"}),
        dbc.Tooltip(tooltip, target="data-freshness-pill", placement="bottom"),
    ]
