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
    NormalizedStatements, adjusted_ebitda, altman_default_model, altman_z_score, beneish_m_score, cash_conversion,
    consecutive_pairs, detect_sector_regime, market_value_of_equity, market_values_in_reporting_currency, metric_trend,
    minor_unit_consistency, net_debt_bridge, net_income_to_cfo_bridge, normalize_statements, parse_user_items,
    piotroski_f_score, price_on_or_before, sloan_accruals, split_currency_unit, transaction_multiples,
    working_capital_days,
)
from i18n import L, PALETTE, PALETTE_CODES, PALETTE_NAMES, PALETTES
from market_data import fx_symbol, get_annual_statements, get_company_profile, get_daily_closes, get_fx_rate

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


def _score_heading(text_key: str, help_key: str, lang: str):
    return html.H6([L(lang, text_key)] + layout.info_tooltip(f"{text_key}-info", L(lang, help_key)), className="mt-3")


def _scores_section(normalized: NormalizedStatements, regime: dict, lang: str, dark: bool) -> list:
    section = [
        html.H5(L(lang, "section_scores"), className="section-title"),
        html.Small(L(lang, "scores_caveat"), className="text-muted d-block mb-2"),
        _score_heading("section_beneish", "beneish_help", lang),
    ]
    applicable = regime["applicable"]
    pairs = consecutive_pairs(normalized)
    if not applicable["beneish"]:
        section.append(_not_applicable(regime, lang))
    elif pairs:
        results = [beneish_m_score(normalized, year, prior) for year, prior in pairs]
        section += [layout.beneish_table(results, lang, dark), layout.beneish_summary(results[0], lang)]

    section.append(_score_heading("section_altman", "altman_help", lang))
    section.append(layout.altman_controls(lang) if applicable["altman"] else _not_applicable(regime, lang))

    section.append(_score_heading("section_piotroski", "piotroski_help", lang))
    if not applicable["piotroski"]:
        section.append(_not_applicable(regime, lang))
    else:
        results = [piotroski_f_score(normalized, year) for year, _prior in pairs]
        results = [r for r in results if r["n_available"] > 0]
        if results:
            section.append(layout.piotroski_table(results, lang, dark))
    return section


def _market_values_at_year_end(ticker: str, normalized: NormalizedStatements, profile: dict) -> dict:
    """Capitalisation à chaque date de clôture, dans la devise des comptes : cours de clôture de ce
    jour-là (ou du dernier jour coté avant) x nombre d'actions du bilan x taux de change de ce même
    jour. None pour un exercice si l'un des trois manque."""
    quote_major, divisor = split_currency_unit(profile["quote_currency"])
    reporting = profile["reporting_currency"]
    if quote_major is None or not reporting or not normalized.years:
        return {year: None for year in normalized.years}
    start = (min(normalized.years) - pd.Timedelta(days=20)).strftime("%Y-%m-%d")
    closes = get_daily_closes(ticker, start)
    fx_closes = None if quote_major == reporting else get_daily_closes(fx_symbol(quote_major, reporting), start)
    values = {}
    for year in normalized.years:
        fx = 1.0 if fx_closes is None else price_on_or_before(fx_closes, year)
        values[year] = market_value_of_equity(price_on_or_before(closes, year),
                                              normalized.get("shares_outstanding", year), divisor, fx)
    return values


@app.callback(
    Output("altman-container", "children"),
    Input("altman-model-radio", "value"),
    Input("lang-radio", "value"),
    Input("dark-mode-switch", "value"),
    State("analysis-ticker-store", "data"),
)
def update_altman(model_choice, lang, dark_mode, store):
    lang = lang or "fr"
    if not store or not store.get("ticker"):
        raise dash.exceptions.PreventUpdate
    ticker = store["ticker"]
    normalized = _load_normalized(ticker)
    if not normalized.years:
        raise dash.exceptions.PreventUpdate
    profile = get_company_profile(ticker)
    children = []
    if not model_choice or model_choice == "auto":
        model = altman_default_model(profile["sector"])
        children.append(html.Small(L(lang, "altman_auto_choice", model=L(lang, f"altman_model_{model}"),
                                     sector=profile["sector"] or L(lang, "na")), className="text-muted d-block mb-2"))
    else:
        model = model_choice
    market_values = _market_values_at_year_end(ticker, normalized, profile) if model == "original" else {}
    results = [altman_z_score(normalized, year, model, market_values.get(year)) for year in normalized.years]
    children.append(layout.altman_table(results, lang, bool(dark_mode)))
    return children


def _market_in_reporting_currency(profile: dict) -> dict:
    quote_major, _divisor = split_currency_unit(profile["quote_currency"])
    fx_rate = get_fx_rate(quote_major, profile["reporting_currency"])
    return market_values_in_reporting_currency(
        profile["price"], profile["market_cap"], profile["quote_currency"], profile["reporting_currency"], fx_rate,
    )


def _transaction_section(normalized: NormalizedStatements, regime: dict, saved: dict, currency: str, lang: str,
                         dark: bool) -> list:
    section = [html.H5(L(lang, "section_transaction"), className="section-title")]
    if not regime["applicable"]["transaction_services"]:
        return section + [_not_applicable(regime, lang)]
    return section + [layout.transaction_controls(normalized.years[0], saved, currency, lang, dark)]


@app.callback(
    Output("ts-bridge-container", "children"),
    Output("ts-effects-container", "children"),
    Output("ts-input-warnings", "children"),
    Output("adjustments-store", "data"),
    Input("ts-net-debt-items", "data"),
    Input("ts-ebitda-adjustments", "data"),
    Input("ts-pension-tax-input", "value"),
    Input("lang-radio", "value"),
    Input("dark-mode-switch", "value"),
    State("analysis-ticker-store", "data"),
    State("adjustments-store", "data"),
)
def update_transaction_view(net_debt_rows, ebitda_rows, pension_tax_pct, lang, dark_mode, store, saved_store):
    """Recalcule le pont, l'EBITDA ajusté et les multiples à chaque saisie, et conserve les saisies de la
    société dans adjustments-store. Les tableaux sont pré-remplis depuis ce même Store à leur création
    (voir layout.transaction_controls) : la ré-émission qui suit un changement de langue réécrit donc
    les mêmes valeurs, sans rien effacer."""
    lang = lang or "fr"
    dark = bool(dark_mode)
    if not store or not store.get("ticker"):
        raise dash.exceptions.PreventUpdate
    ticker = store["ticker"]
    normalized = _load_normalized(ticker)
    if not normalized.years:
        raise dash.exceptions.PreventUpdate
    year = normalized.years[0]
    profile = get_company_profile(ticker)
    currency = profile["reporting_currency"] or L(lang, "na")
    tax_rate = (pension_tax_pct if pension_tax_pct is not None else 25) / 100

    net_debt_items, invalid_debt = parse_user_items(net_debt_rows)
    ebitda_items, invalid_ebitda = parse_user_items(ebitda_rows)
    bridge = net_debt_bridge(normalized, year, pension_tax_rate=tax_rate, user_items=net_debt_items)
    ebitda = adjusted_ebitda(normalized.get("ebitda", year), ebitda_items)
    market = _market_in_reporting_currency(profile)
    minorities = normalized.get("minority_interest", year)
    published = transaction_multiples(market["market_cap"], minorities, bridge["net_debt_data"], ebitda["published"])
    adjusted = transaction_multiples(market["market_cap"], minorities, bridge["adjusted_net_debt"], ebitda["adjusted"])

    effects = layout.effects_table(
        {"ebitda": ebitda["published"], "net_debt": bridge["net_debt_data"], **published},
        {"ebitda": ebitda["adjusted"], "net_debt": bridge["adjusted_net_debt"], **adjusted}, lang, dark,
    )
    notes = []
    if bridge["adjusted_net_debt_excl_ifrs16"] is not None:
        notes.append(html.Div(L(lang, "ifrs16_note",
                                value=f"{layout.format_amount(bridge['adjusted_net_debt_excl_ifrs16'], lang)} {currency}")))
    notes += [html.Div(L(lang, f"flag_{flag}")) for flag in bridge["flags"] + published["flags"]]
    if market["market_cap"] is None:
        notes.append(html.Div(L(lang, "market_cap_unavailable")))
    warnings = []
    for rows in (invalid_debt, invalid_ebitda):
        if rows:
            warnings.append(dbc.Alert(L(lang, "invalid_rows", rows=", ".join(map(str, rows))), color="warning",
                                      className="py-1 px-2 mb-2"))

    saved_store = dict(saved_store or {})
    saved_store[ticker] = {"net_debt_items": net_debt_rows, "ebitda_adjustments": ebitda_rows,
                           "pension_tax_rate_pct": pension_tax_pct}
    return (layout.net_debt_bridge_table(bridge, currency, lang, dark),
            html.Div([effects, html.Div(notes, className="text-muted mt-2", style={"fontSize": "0.8rem"})]),
            warnings, saved_store)


def _append_empty_row(n_clicks, rows):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    return (rows or []) + [{"label": "", "amount": ""}]


app.callback(
    Output("ts-net-debt-items", "data", allow_duplicate=True),
    Input("ts-add-net-debt-item", "n_clicks"),
    State("ts-net-debt-items", "data"),
    prevent_initial_call=True,
)(_append_empty_row)

app.callback(
    Output("ts-ebitda-adjustments", "data", allow_duplicate=True),
    Input("ts-add-ebitda-adjustment", "n_clicks"),
    State("ts-ebitda-adjustments", "data"),
    prevent_initial_call=True,
)(_append_empty_row)


@app.callback(
    Output("results-container", "children"),
    Input("analysis-ticker-store", "data"),
    Input("lang-radio", "value"),
    Input("dark-mode-switch", "value"),
    Input("palette-dropdown", "value"),
    State("adjustments-store", "data"),
)
def render_analysis(store, lang, dark_mode, palette_code, saved_store):
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
    market = _market_in_reporting_currency(profile)
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
        *_scores_section(normalized, regime, lang, dark),
        *_transaction_section(normalized, regime, (saved_store or {}).get(ticker, {}), reporting, lang, dark),
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
