"""
Enregistrement de tous les callbacks Dash. Importer ce module (voir app.py) suffit à les enregistrer
sur l'instance `app` partagée (app_instance.py). Ce module ne calcule rien lui-même : il lit les
données (market_data.py), les fait passer par le moteur pur (engine.py) et met le résultat en forme
(layout.py).
"""
import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, html

import layout
from app_instance import app
from constants import TYPICAL_YFINANCE_YEARS
from engine import (
    detect_sector_regime, market_values_in_reporting_currency, minor_unit_consistency, normalize_statements,
    split_currency_unit,
)
from i18n import L, PALETTE_CODES, PALETTE_NAMES
from market_data import get_annual_statements, get_company_profile, get_fx_rate

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

@app.callback(
    Output("results-container", "children"),
    Input("analysis-ticker-store", "data"),
    Input("lang-radio", "value"),
    Input("dark-mode-switch", "value"),
)
def render_analysis(store, lang, dark_mode):
    lang = lang or "fr"
    dark = bool(dark_mode)
    if not store:
        return html.Div(L(lang, "results_placeholder"), className="text-muted")
    ticker = store.get("ticker") or ""
    if not ticker:
        return dbc.Alert(L(lang, "error_empty_ticker"), color="warning")

    statements = get_annual_statements(ticker)
    normalized = normalize_statements(statements["income"], statements["balance"], statements["cashflow"])
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
    return html.Div([
        layout.company_card(ticker, profile, regime, market, lang),
        *layout.analysis_alerts(profile, regime, market, consistency, lang),
        html.H5(L(lang, "section_statements"), className="section-title"),
        dbc.Alert(L(lang, "coverage_note", typical=TYPICAL_YFINANCE_YEARS, n=len(normalized.years), years=years_text),
                  color="light", className="py-2"),
        html.Small(L(lang, "amounts_unit", currency=reporting), className="text-muted d-block"),
        html.Small(L(lang, "statements_legend"), className="text-muted d-block mb-2"),
        *statement_blocks,
    ])
