"""
Enregistrement de tous les callbacks Dash. Importer ce module (voir app.py) suffit à les enregistrer
sur l'instance `app` partagée (app_instance.py). Ce module ne calcule rien lui-même : il lit les
données (market_data.py), les fait passer par le moteur pur (engine.py) et met le résultat en forme
(layout.py).
"""
import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, dcc, html

import layout
from app_instance import app
from charts import empty_figure_with_message, make_bridge_waterfall, make_working_capital_days_chart
from constants import TYPICAL_YFINANCE_YEARS
from engine import (
    NormalizedStatements, cash_conversion, detect_sector_regime, market_values_in_reporting_currency, metric_trend,
    minor_unit_consistency, net_income_to_cfo_bridge, normalize_statements, sloan_accruals, split_currency_unit,
    working_capital_days,
)
from i18n import L, PALETTE, PALETTE_CODES, PALETTE_NAMES, PALETTES
from market_data import get_annual_statements, get_company_profile, get_fx_rate

EARNINGS_QUALITY_METRICS = ("cfo_to_net_income", "fcf_to_net_income", "sloan_accruals")
WORKING_CAPITAL_METRICS = ("dso", "dio", "dpo", "ccc")


def _load_normalized(ticker: str) -> NormalizedStatements:
    """États financiers normalisés d'un ticker : les téléchargements sont en cache (market_data),
    la normalisation est rapide, donc chaque callback peut la refaire plutôt que de faire transiter
    des DataFrames par le navigateur."""
    statements = get_annual_statements(ticker)
    return normalize_statements(statements["income"], statements["balance"], statements["cashflow"])

# ============================================================
# Habillage global (langue, palette, thème), même logique que stock_valuation
# ============================================================

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
    Output("main-content-container", "children"),
    Output("footer-container", "children"),
    Input("lang-radio", "value"),
    [State(cid, prop) for cid, prop in layout.TAB_STATE_FIELDS],
    prevent_initial_call=True,
)
def rebuild_on_language_change(lang, *state_values):
    v = dict(zip([cid for cid, _ in layout.TAB_STATE_FIELDS], state_values))
    return layout.build_header_text(lang), layout.build_main(lang, v), layout.build_footer(lang)


# ============================================================
# Choix de la société
# ============================================================

@app.callback(
    Output("ticker-input", "value"),
    Input("quick-pick-dropdown", "value"),
    prevent_initial_call=True,
)
def fill_ticker_from_quick_pick(ticker):
    if not ticker:
        raise dash.exceptions.PreventUpdate
    return ticker


@app.callback(
    Output("analysis-ticker-store", "data"),
    Input("analyze-btn", "n_clicks"),
    Input("ticker-input", "n_submit"),
    Input("quick-pick-dropdown", "value"),
    State("ticker-input", "value"),
    prevent_initial_call=True,
)
def submit_analysis(n_clicks, n_submit, picked_ticker, typed_ticker):
    # Les champs de saisie sont recréés à chaque changement de langue, et Dash rejoue alors ce
    # callback malgré prevent_initial_call : sans ces gardes, un simple changement de langue
    # relancerait (ou effacerait) l'analyse affichée.
    trigger = dash.ctx.triggered_id
    if trigger == "quick-pick-dropdown":
        if not picked_ticker:
            raise dash.exceptions.PreventUpdate
        return {"ticker": picked_ticker}
    if (trigger == "analyze-btn" and not n_clicks) or (trigger == "ticker-input" and not n_submit):
        raise dash.exceptions.PreventUpdate
    return {"ticker": (typed_ticker or "").strip().upper()}


# ============================================================
# Analyse
# ============================================================

def _not_applicable(regime: dict, lang: str):
    return dbc.Alert(L(lang, "section_not_applicable", regime=L(lang, f"regime_{regime['regime']}")),
                     color="secondary", className="py-2")


def _earnings_quality_section(normalized: NormalizedStatements, regime: dict, lang: str, dark: bool) -> list:
    section = [html.H5(L(lang, "section_earnings_quality"), className="section-title")]
    if not regime["applicable"]["earnings_quality"]:
        return section + [_not_applicable(regime, lang)]
    conversion, accruals = cash_conversion(normalized), sloan_accruals(normalized)
    merged = {year: {**conversion[year], "sloan_accruals": accruals[year]} for year in normalized.years}
    return section + [
        layout.ratio_table(merged, EARNINGS_QUALITY_METRICS, normalized.years, lang, dark, "table-earnings-quality"),
        html.H5(L(lang, "section_bridge"), className="section-title"),
        layout.bridge_controls(normalized.years, lang),
    ]


def _working_capital_section(normalized: NormalizedStatements, regime: dict, lang: str, dark: bool, palette) -> list:
    section = [html.H5(L(lang, "section_working_capital"), className="section-title")]
    if not regime["applicable"]["working_capital"]:
        return section + [_not_applicable(regime, lang)]
    days = working_capital_days(normalized)
    trends = {metric: metric_trend(days, metric) for metric in WORKING_CAPITAL_METRICS}
    chronological = sorted(normalized.years)
    figure = make_working_capital_days_chart(
        [layout.format_year(year, lang) for year in chronological],
        {metric: [days[year][metric]["value"] for year in chronological] for metric in WORKING_CAPITAL_METRICS},
        {metric: L(lang, f"ratio_{metric}") for metric in WORKING_CAPITAL_METRICS},
        L(lang, "days_chart_title"), L(lang, "days_axis"), dark=dark, palette=palette,
    )
    return section + [
        layout.ratio_table(days, WORKING_CAPITAL_METRICS, normalized.years, lang, dark, "table-working-capital",
                           trends=trends),
        dcc.Graph(figure=figure, config=layout.GRAPH_CONFIG),
    ]


@app.callback(
    Output("results-container", "children"),
    Input("analysis-ticker-store", "data"),
    Input("lang-radio", "value"),
    Input("dark-mode-switch", "value"),
    Input("palette-dropdown", "value"),
)
def render_analysis(store, lang, dark_mode, palette_code):
    lang = lang or "fr"
    dark = bool(dark_mode)
    palette = PALETTES.get(palette_code, PALETTE)
    if not store:
        return html.Div(L(lang, "results_placeholder"), className="text-muted")
    ticker = store.get("ticker") or ""
    if not ticker:
        return dbc.Alert(L(lang, "error_empty_ticker"), color="warning")

    normalized = _load_normalized(ticker)
    if not normalized.years:
        return dbc.Alert(L(lang, "error_no_data", ticker=ticker), color="danger")

    profile = get_company_profile(ticker)
    regime = detect_sector_regime(profile["sector"], profile["industry"])
    quote_major, _divisor = split_currency_unit(profile["quote_currency"])
    fx_rate = get_fx_rate(quote_major, profile["reporting_currency"])
    market = market_values_in_reporting_currency(
        profile["price"], profile["market_cap"], profile["quote_currency"], profile["reporting_currency"], fx_rate,
    )
    consistency = minor_unit_consistency(
        profile["price"], profile["trailing_pe"], profile["trailing_eps"], market["divisor"],
    )

    years_text = ", ".join(layout.format_year(year, lang) for year in normalized.years)
    reporting = profile["reporting_currency"] or L(lang, "na")
    statement_blocks = []
    for statement in ("income", "balance", "cashflow"):
        statement_blocks += [
            html.H6(L(lang, f"statement_{statement}"), className="mt-3"),
            layout.statement_table(normalized, statement, lang, dark, f"table-{statement}"),
        ]
    # Couverture rappelée AVANT les analyses : toutes reposent sur ces ~4 exercices.
    return html.Div([
        layout.company_card(ticker, profile, regime, market, lang),
        *layout.analysis_alerts(profile, regime, market, consistency, lang),
        dbc.Alert(L(lang, "coverage_note", typical=TYPICAL_YFINANCE_YEARS, n=len(normalized.years), years=years_text),
                  color="light", className="py-2"),
        *_earnings_quality_section(normalized, regime, lang, dark),
        *_working_capital_section(normalized, regime, lang, dark, palette),
        html.H5(L(lang, "section_statements"), className="section-title"),
        html.Small(L(lang, "amounts_unit", currency=reporting), className="text-muted d-block"),
        html.Small(L(lang, "statements_legend"), className="text-muted d-block mb-2"),
        *statement_blocks,
    ])


@app.callback(
    Output("bridge-graph", "figure"),
    Output("bridge-notes", "children"),
    Input("bridge-year-dropdown", "value"),
    Input("lang-radio", "value"),
    Input("dark-mode-switch", "value"),
    Input("palette-dropdown", "value"),
    State("analysis-ticker-store", "data"),
)
def update_bridge(year_value, lang, dark_mode, palette_code, store):
    lang = lang or "fr"
    dark = bool(dark_mode)
    if not year_value or not store or not store.get("ticker"):
        raise dash.exceptions.PreventUpdate
    normalized = _load_normalized(store["ticker"])
    year = pd.Timestamp(year_value)
    if year not in normalized.years:
        raise dash.exceptions.PreventUpdate
    bridge = net_income_to_cfo_bridge(normalized, year)
    if not bridge["available"]:
        missing = ", ".join(L(lang, f"field_{key}") for key in bridge["missing"])
        return empty_figure_with_message(L(lang, "bridge_unavailable", missing=missing), dark=dark), ""

    labels = {key: L(lang, f"bridge_step_{key}") for key in ("net_income", "d_and_a", "change_in_working_capital", "other_items")}
    if "group_share_fallback" in bridge["flags"]:
        labels["net_income"] = L(lang, "field_net_income")
    figure = make_bridge_waterfall(
        bridge["steps"], bridge["cfo"], labels, L(lang, "bridge_cfo"),
        L(lang, "bridge_title", year=layout.format_year(year, lang)),
        lambda value: layout.format_amount(value, lang), dark=dark, palette=PALETTES.get(palette_code, PALETTE),
    )
    notes = [html.Div(L(lang, f"flag_{flag}")) for flag in bridge["flags"]]
    if bridge["missing_items"]:
        notes.append(html.Div(L(lang, "bridge_missing_items",
                                items=", ".join(L(lang, f"field_{key}") for key in bridge["missing_items"]))))
    return figure, notes
