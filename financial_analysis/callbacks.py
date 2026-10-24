"""
Enregistrement de tous les callbacks Dash. Importer ce module (voir app.py) suffit à les enregistrer
sur l'instance `app` partagée (app_instance.py). Ce module ne calcule rien lui-même : il lit les
données (market_data.py), les fait passer par le moteur pur (engine.py) et met le résultat en forme
(layout.py).
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, dcc, html

import layout
from app_instance import app
from databook import build_databook
from charts import (
    empty_figure_with_message, make_bridge_waterfall, make_income_vs_cfo_chart, make_score_zone_chart,
    make_working_capital_days_chart,
)
from constants import CAC40_TICKERS, TYPICAL_YFINANCE_YEARS
from engine import (
    ALTMAN_MODELS, BENEISH_THRESHOLD, DEFAULT_BENFORD_MIN_AMOUNT, FIELD_KEYS, IMPORT_MARKET_CAP_KEY, MIN_SECTOR_PEERS, PEER_METRICS, NormalizedStatements,
    adjusted_ebitda, peer_distribution, peer_metrics, percentile_rank, select_peers,
    benford_first_digit_test, financial_statement_amounts, guess_amount_column, read_ledger_csv,
    select_benford_amounts, altman_default_model, altman_z_score, beneish_m_score, beneish_verdict, cash_conversion,
    consecutive_pairs, detect_sector_regime, imported_market_caps, imported_statement_amounts, market_value_of_equity,
    market_values_in_reporting_currency, metric_trend, minor_unit_consistency, net_debt_bridge,
    net_income_to_cfo_bridge, normalize_imported, normalize_statements, parse_statements_csv, parse_user_items,
    piotroski_f_score, price_on_or_before, regime_from_import, sloan_accruals, split_currency_unit,
    statements_csv_template, transaction_multiples, working_capital_days,
)
import chart_theme
from i18n import L, PALETTE_CODES, PALETTE_NAMES
from market_data import fx_symbol, get_annual_statements, get_company_profile, get_daily_closes, get_fx_rate

EARNINGS_QUALITY_METRICS = ("cfo_to_net_income", "fcf_to_net_income", "sloan_accruals")
WORKING_CAPITAL_METRICS = ("dso", "dio", "dpo", "ccc")


def _load_normalized(ticker: str) -> NormalizedStatements:
    """États financiers normalisés d'un ticker : les téléchargements sont en cache (market_data),
    la normalisation est rapide, donc chaque callback peut la refaire plutôt que de faire transiter
    des DataFrames par le navigateur."""
    statements = get_annual_statements(ticker)
    return normalize_statements(statements["income"], statements["balance"], statements["cashflow"])


@dataclass
class AnalysisContext:
    """Ce dont chaque callback d'analyse a besoin, que les comptes viennent de Yahoo (ticker) ou d'un
    fichier importé (dataset, voir engine.parse_statements_csv). key identifie la société dans
    adjustments-store ; market suit la forme de engine.market_values_in_reporting_currency."""
    key: str
    normalized: NormalizedStatements
    profile: dict
    regime: dict
    market: dict
    ticker: str | None = None
    dataset: dict | None = None
    filename: str | None = None

    @property
    def imported(self) -> bool:
        return self.dataset is not None


def _load_context(store: dict | None) -> AnalysisContext | None:
    """Contexte de l'analyse demandée, None si rien n'est à analyser. Un fichier importé remplace
    entièrement Yahoo : pas de cours ni de change, la seule donnée de marché est la capitalisation
    déclarée à chaque clôture (ligne market_cap), celle de la dernière clôture servant aux multiples."""
    if not store:
        return None
    if store.get("source") == "import":
        dataset, filename = store["dataset"], store.get("filename") or ""
        meta = dataset["meta"]
        normalized = normalize_imported(dataset)
        latest_cap = imported_market_caps(dataset).get(normalized.years[0]) if normalized.years else None
        profile = {"name": meta.get("company") or filename, "sector": meta.get("sector"),
                   "industry": meta.get("industry"), "quote_currency": None, "reporting_currency": meta.get("currency"),
                   "price": None, "market_cap": latest_cap, "shares_outstanding": None, "trailing_pe": None,
                   "trailing_eps": None}
        market = {"price": None, "market_cap": latest_cap, "fx_rate": None, "divisor": 1.0,
                  "quote_major_currency": None, "reporting_currency": meta.get("currency"), "reason": None}
        return AnalysisContext(key=f"import:{filename}", normalized=normalized, profile=profile,
                               regime=regime_from_import(meta), market=market, dataset=dataset, filename=filename)
    ticker = store.get("ticker")
    if not ticker:
        return None
    profile = get_company_profile(ticker)
    return AnalysisContext(key=ticker, normalized=_load_normalized(ticker), profile=profile,
                           regime=detect_sector_regime(profile["sector"], profile["industry"]),
                           market=_market_in_reporting_currency(profile), ticker=ticker)

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
    Output("benford-container", "children"),
    Output("footer-container", "children"),
    Input("lang-radio", "value"),
    State("benford-file-store", "data"),
    [State(cid, prop) for cid, prop in layout.TAB_STATE_FIELDS],
    prevent_initial_call=True,
)
def rebuild_on_language_change(lang, benford_file, *state_values):
    v = dict(zip([cid for cid, _ in layout.TAB_STATE_FIELDS], state_values))
    return (layout.build_header_text(lang), layout.build_main(lang, v), layout.build_benford(lang, v, benford_file),
            layout.build_footer(lang))


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


def _income_vs_cfo_figure(normalized: NormalizedStatements, conversion: dict, lang: str, dark: bool, palette):
    """Barres groupées résultat net / CFO, avec les montants déjà retenus pour le ratio CFO / résultat
    net (résultat y compris minoritaires, ou part du groupe en repli). None si rien à montrer."""
    chronological = sorted(normalized.years)
    components = [conversion[year]["cfo_to_net_income"]["components"] for year in chronological]
    net_income = [c["net_income"] for c in components]
    cfo = [c["cfo"] for c in components]
    if all(v is None for v in net_income + cfo):
        return None
    fallback = any("group_share_fallback" in conversion[y]["cfo_to_net_income"]["flags"] for y in chronological)
    labels = (L(lang, "field_net_income" if fallback else "field_net_income_incl_minorities"), L(lang, "field_cfo"))
    return make_income_vs_cfo_chart(
        [layout.format_year(year, lang) for year in chronological], net_income, cfo, labels,
        L(lang, "income_vs_cfo_title"), lambda value: layout.format_amount(value, lang),
        (L(lang, "unit_billion"), L(lang, "unit_million")), dark=dark, palette=palette,
        separators=L(lang, "plotly_separators"),
    )


def _earnings_quality_section(normalized: NormalizedStatements, regime: dict, lang: str, dark: bool, palette) -> list:
    section = [html.H5(L(lang, "section_earnings_quality"), className="section-title")]
    if not regime["applicable"]["earnings_quality"]:
        return section + [_not_applicable(regime, lang)]
    conversion, accruals = cash_conversion(normalized), sloan_accruals(normalized)
    merged = {year: {**conversion[year], "sloan_accruals": accruals[year]} for year in normalized.years}
    figure = _income_vs_cfo_figure(normalized, conversion, lang, dark, palette)
    return section + [
        layout.ratio_table(merged, EARNINGS_QUALITY_METRICS, normalized.years, lang, dark, "table-earnings-quality"),
        *([dcc.Graph(figure=figure, config=layout.GRAPH_CONFIG)] if figure is not None else []),
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
        separators=L(lang, "plotly_separators"),
    )
    return section + [
        layout.ratio_table(days, WORKING_CAPITAL_METRICS, normalized.years, lang, dark, "table-working-capital",
                           trends=trends),
        dcc.Graph(figure=figure, config=layout.GRAPH_CONFIG),
    ]


def _score_heading(text_key: str, help_key: str, lang: str):
    return html.H6([L(lang, text_key)] + layout.info_tooltip(f"{text_key}-info", L(lang, help_key)), className="mt-3")


def _beneish_zone_figure(results: list[dict], lang: str, dark: bool):
    """M-score de chaque couple sur ses deux zones. Un M-score officiel n.d. mais calculable en variante
    indicative apparaît en point creux, pour ne pas le lire comme un score officiel."""
    points = []
    for result in results:
        official, indicative = result["m_score"]["value"], result["m_score_indicative"]
        value = official if official is not None else (indicative["value"] if indicative else None)
        if value is None:
            continue
        verdict = beneish_verdict(value)
        hover = (f"<b>{layout.pair_label(result['pair'], lang)}</b><br>M = {layout.format_number(value, '.2f', lang)}"
                 f" · {L(lang, f'beneish_zone_{verdict}')}")
        if official is None:
            hover += f"<br>{L(lang, 'beneish_point_indicative')}"
        points.append({"label": layout.pair_label(result["pair"], lang), "value": value,
                       "hollow": official is None, "hover": hover})
    if not points:
        return None
    zones = [
        {"start": None, "end": BENEISH_THRESHOLD, "status": "good", "label": L(lang, "beneish_zone_no_signal")},
        {"start": BENEISH_THRESHOLD, "end": None, "status": "critical",
         "label": L(lang, "beneish_zone_manipulation_risk")},
    ]
    note = f"○ {L(lang, 'beneish_point_indicative')}" if any(point["hollow"] for point in points) else None
    return make_score_zone_chart(points, zones, L(lang, "beneish_chart_title"),
                                 lambda value: layout.format_number(value, ".2f", lang), dark=dark,
                                 separators=L(lang, "plotly_separators"), note=note)


def _altman_zone_figure(results: list[dict], model: str, lang: str, dark: bool):
    """Z-score de chaque exercice sur les trois zones du modèle retenu (seuils de engine.ALTMAN_MODELS)."""
    points = [
        {"label": layout.format_year(r["year"], lang), "value": r["value"], "hollow": False,
         "hover": (f"<b>{layout.format_year(r['year'], lang)}</b><br>Z = {layout.format_number(r['value'], '.2f', lang)}"
                   f" · {L(lang, 'altman_zone')} {L(lang, 'zone_' + r['zone'])}")}
        for r in results if r["value"] is not None
    ]
    if not points:
        return None
    distress, safe = ALTMAN_MODELS[model]["zones"]
    zones = [
        {"start": None, "end": distress, "status": "critical", "label": L(lang, "zone_distress")},
        {"start": distress, "end": safe, "status": "warning", "label": L(lang, "zone_grey")},
        {"start": safe, "end": None, "status": "good", "label": L(lang, "zone_safe")},
    ]
    return make_score_zone_chart(points, zones, L(lang, "altman_chart_title"),
                                 lambda value: layout.format_number(value, ".2f", lang), dark=dark,
                                 separators=L(lang, "plotly_separators"))


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
        figure = _beneish_zone_figure(results, lang, dark)
        if figure is not None:
            section.append(dcc.Graph(figure=figure, config=layout.GRAPH_CONFIG))

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


def _peers_section(regime: dict, lang: str) -> list:
    """Bouton plutôt que calcul automatique : la première comparaison télécharge les comptes d'une
    quarantaine de sociétés (ensuite en cache 24 h), ce qu'on n'impose pas à chaque analyse."""
    section = [html.H5([L(lang, "section_peers")] + layout.info_tooltip("peers-info", L(lang, "peers_help")),
                       className="section-title")]
    if regime["regime"] != "general":
        return section + [_not_applicable(regime, lang)]
    return section + [
        dbc.Button(L(lang, "peers_btn"), id="peers-btn", color="secondary", outline=True, size="sm", className="mb-2"),
        dcc.Loading(type="circle", color="#636efa", children=[html.Div(id="peers-container")]),
    ]


PEER_DOWNLOAD_WORKERS = 8
# Écart (en années) entre le dernier exercice de la société et celui de la plupart de ses pairs au-delà
# duquel la comparaison est signalée comme portant sur des périodes différentes.
PEER_YEAR_GAP_WARNING = 2


def _peer_universe() -> dict[str, dict]:
    """Secteur, régime et indicateurs de chaque société du CAC 40, téléchargés en parallèle (les
    appels yfinance attendent surtout le réseau). Une société indisponible garde des indicateurs n.d.,
    sans bloquer les autres."""
    def load(ticker: str) -> tuple[str, dict]:
        profile = get_company_profile(ticker)
        regime = detect_sector_regime(profile["sector"], profile["industry"])
        return ticker, {"name": profile["name"], "sector": profile["sector"], "regime": regime["regime"],
                        "metrics": peer_metrics(_load_normalized(ticker), regime)}

    with ThreadPoolExecutor(max_workers=PEER_DOWNLOAD_WORKERS) as executor:
        return dict(executor.map(load, CAC40_TICKERS.values()))


@app.callback(
    Output("peers-container", "children"),
    Input("peers-btn", "n_clicks"),
    State("analysis-ticker-store", "data"),
    State("lang-radio", "value"),
    State("dark-mode-switch", "value"),
    prevent_initial_call=True,
)
def compare_to_peers(n_clicks, store, lang, dark_mode):
    lang = lang or "fr"
    ctx = _load_context(store) if n_clicks else None
    if ctx is None or not ctx.normalized.years:
        raise dash.exceptions.PreventUpdate
    comparison = peer_comparison(ctx, lang)
    if comparison is None or not comparison["peers"]:
        return dbc.Alert(L(lang, "peers_none"), color="secondary", className="py-2")
    return html.Div([
        dbc.Alert(comparison["scope_text"], color="light" if comparison["scope"] == "sector" else "warning",
                  className="py-2"),
        layout.peers_table(comparison["target"], comparison["stats"], comparison["ranks"], comparison["indicative"],
                           lang, bool(dark_mode)),
        html.Div([html.Div(note) for note in comparison["notes"]], className="text-muted mt-2",
                 style={"fontSize": "0.8rem"}),
    ])


def peer_comparison(ctx: AnalysisContext, lang: str) -> dict | None:
    """Comparaison aux pairs du CAC 40, partagée par l'écran et le databook : périmètre retenu,
    indicateurs de la société, statistiques et rang centile par indicateur, notes de lecture. None
    pour une banque ou un assureur (indicateurs sans objet) ; peers vide si aucun pair n'est
    disponible."""
    if ctx.regime["regime"] != "general":
        return None
    universe = _peer_universe()
    peers, scope = select_peers(ctx.ticker, ctx.profile["sector"], universe)
    target = peer_metrics(ctx.normalized, ctx.regime)
    stats, ranks = {}, {}
    for metric in PEER_METRICS:
        values = [universe[ticker]["metrics"]["values"][metric] for ticker in peers]
        stats[metric] = peer_distribution(values)
        ranks[metric] = percentile_rank(target["values"][metric], values)
    names = ", ".join(universe[ticker]["name"] for ticker in peers)
    scope_text = L(lang, f"peers_scope_{scope}", sector=ctx.profile["sector"] or L(lang, "na"), n=len(peers),
                   names=names, threshold=MIN_SECTOR_PEERS)
    indicative = [universe[ticker]["name"] for ticker in peers if universe[ticker]["metrics"]["indicative"]]
    notes = [L(lang, "peers_years_note")]
    peer_years = sorted(universe[t]["metrics"]["year"].year for t in peers if universe[t]["metrics"]["year"] is not None)
    if peer_years and target["year"] is not None:
        median_year = peer_years[len(peer_years) // 2]
        if abs(target["year"].year - median_year) >= PEER_YEAR_GAP_WARNING:
            # Cas typique : société radiée importée (Wirecard 2018) face aux comptes récents des pairs.
            notes.insert(0, L(lang, "peers_year_gap", target=target["year"].year, peers=median_year))
    if target["indicative"]:
        notes.append(L(lang, "peers_target_indicative"))
    if indicative:
        notes.append(L(lang, "peers_beneish_note", n=len(indicative)))
    return {
        "scope": scope, "scope_text": scope_text, "target": target, "stats": stats, "ranks": ranks,
        "indicative": indicative, "notes": notes,
        "peers": [{"ticker": t, "name": universe[t]["name"], "sector": universe[t]["sector"],
                   "year": universe[t]["metrics"]["year"]} for t in peers],
    }


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
    ctx = _load_context(store)
    if ctx is None or not ctx.normalized.years:
        raise dash.exceptions.PreventUpdate
    normalized, profile = ctx.normalized, ctx.profile
    children = []
    if not model_choice or model_choice == "auto":
        model = altman_default_model(profile["sector"])
        choice_key = "altman_auto_choice_import" if ctx.imported else "altman_auto_choice"
        children.append(html.Small(L(lang, choice_key, model=L(lang, f"altman_model_{model}"),
                                     sector=profile["sector"] or L(lang, "na")), className="text-muted d-block mb-2"))
    else:
        model = model_choice
    market_values = {}
    if model == "original":
        market_values = (imported_market_caps(ctx.dataset) if ctx.imported
                         else _market_values_at_year_end(ctx.ticker, normalized, profile))
    results = [altman_z_score(normalized, year, model, market_values.get(year)) for year in normalized.years]
    children.append(layout.altman_table(results, lang, bool(dark_mode), imported=ctx.imported))
    figure = _altman_zone_figure(results, model, lang, bool(dark_mode))
    if figure is not None:
        children.append(dcc.Graph(figure=figure, config=layout.GRAPH_CONFIG))
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
    ctx = _load_context(store)
    if ctx is None or not ctx.normalized.years:
        raise dash.exceptions.PreventUpdate
    currency = ctx.profile["reporting_currency"] or L(lang, "na")
    figures = _transaction_figures(ctx, net_debt_rows, ebitda_rows, pension_tax_pct)
    bridge, ebitda = figures["bridge"], figures["ebitda"]
    effects = layout.effects_table(
        {"ebitda": ebitda["published"], "net_debt": bridge["net_debt_data"], **figures["published"]},
        {"ebitda": ebitda["adjusted"], "net_debt": bridge["adjusted_net_debt"], **figures["adjusted"]}, lang, dark,
    )
    notes = [html.Div(note) for note in _transaction_notes(ctx, figures, currency, lang)]
    warnings = []
    for rows in (figures["invalid_debt_rows"], figures["invalid_ebitda_rows"]):
        if rows:
            warnings.append(dbc.Alert(L(lang, "invalid_rows", rows=", ".join(map(str, rows))), color="warning",
                                      className="py-1 px-2 mb-2"))

    saved_store = dict(saved_store or {})
    saved_store[ctx.key] = {"net_debt_items": net_debt_rows, "ebitda_adjustments": ebitda_rows,
                           "pension_tax_rate_pct": pension_tax_pct}
    return (layout.net_debt_bridge_table(bridge, currency, lang, dark),
            html.Div([effects, html.Div(notes, className="text-muted mt-2", style={"fontSize": "0.8rem"})]),
            warnings, saved_store)


def _transaction_figures(ctx: AnalysisContext, net_debt_rows, ebitda_rows, pension_tax_pct) -> dict:
    """Pont de dette nette, EBITDA ajusté et multiples du dernier exercice, à partir des saisies (lignes
    du tableau en millions, taux d'impôt en %). Partagé par l'écran et le databook, pour qu'ils
    affichent les mêmes chiffres."""
    normalized = ctx.normalized
    year = normalized.years[0]
    tax_rate = (pension_tax_pct if pension_tax_pct is not None else 25) / 100
    net_debt_items, invalid_debt = parse_user_items(net_debt_rows)
    ebitda_items, invalid_ebitda = parse_user_items(ebitda_rows)
    bridge = net_debt_bridge(normalized, year, pension_tax_rate=tax_rate, user_items=net_debt_items)
    ebitda = adjusted_ebitda(normalized.get("ebitda", year), ebitda_items)
    market_cap = ctx.market["market_cap"]
    minorities = normalized.get("minority_interest", year)
    return {
        "year": year, "bridge": bridge, "ebitda": ebitda, "market_cap": market_cap,
        "published": transaction_multiples(market_cap, minorities, bridge["net_debt_data"], ebitda["published"]),
        "adjusted": transaction_multiples(market_cap, minorities, bridge["adjusted_net_debt"], ebitda["adjusted"]),
        "invalid_debt_rows": invalid_debt, "invalid_ebitda_rows": invalid_ebitda,
    }


def _transaction_notes(ctx: AnalysisContext, figures: dict, currency: str, lang: str) -> list[str]:
    bridge = figures["bridge"]
    notes = []
    if bridge["adjusted_net_debt_excl_ifrs16"] is not None:
        notes.append(L(lang, "ifrs16_note",
                       value=f"{layout.format_amount(bridge['adjusted_net_debt_excl_ifrs16'], lang)} {currency}"))
    notes += [L(lang, f"flag_{flag}") for flag in bridge["flags"] + figures["published"]["flags"]]
    if figures["market_cap"] is None:
        notes.append(L(lang, "market_cap_unavailable_import" if ctx.imported else "market_cap_unavailable"))
    elif ctx.imported:
        notes.append(L(lang, "import_market_cap_note", year=layout.format_year(figures["year"], lang)))
    return notes


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
    palette = chart_theme.palette_for(palette_code, dark)
    if not store:
        return html.Div(L(lang, "results_placeholder"), className="text-muted")
    ctx = _load_context(store)
    if ctx is None:
        return dbc.Alert(L(lang, "error_empty_ticker"), color="warning")
    normalized, profile, regime, market = ctx.normalized, ctx.profile, ctx.regime, ctx.market
    if not normalized.years:
        return dbc.Alert(L(lang, "error_no_data", ticker=ctx.ticker), color="danger")

    years_text = ", ".join(layout.format_year(year, lang) for year in normalized.years)
    reporting = profile["reporting_currency"] or L(lang, "na")
    if ctx.imported:
        # Ni cours ni BPA pour un fichier importé : pas de contrôle de sous-unité à faire.
        consistency = {"empirical_ratio": None, "expected_divisor": 1.0, "consistent": None}
        card = layout.import_card(ctx.filename, ctx.dataset["meta"], regime, market["market_cap"], normalized.years[0], lang)
        coverage = L(lang, "import_coverage_note", n=len(normalized.years), years=years_text, filename=ctx.filename)
    else:
        consistency = minor_unit_consistency(
            profile["price"], profile["trailing_pe"], profile["trailing_eps"], market["divisor"],
        )
        card = layout.company_card(ctx.ticker, profile, regime, market, lang)
        coverage = L(lang, "coverage_note", typical=TYPICAL_YFINANCE_YEARS, n=len(normalized.years), years=years_text)
    statement_blocks = []
    for statement in ("income", "balance", "cashflow"):
        statement_blocks += [
            html.H6(L(lang, f"statement_{statement}"), className="mt-3"),
            layout.statement_table(normalized, statement, lang, dark, f"table-{statement}"),
        ]
    # Couverture rappelée AVANT les analyses : toutes reposent sur ces ~4 exercices.
    return html.Div([
        card,
        html.Div([dbc.Button(L(lang, "databook_btn"), id="databook-btn", color="primary", outline=True, size="sm")]
                 + layout.info_tooltip("databook-info", L(lang, "databook_help")), className="mb-3"),
        *layout.analysis_alerts(profile, regime, market, consistency, lang),
        dbc.Alert(coverage, color="light", className="py-2"),
        *_earnings_quality_section(normalized, regime, lang, dark, palette),
        *_working_capital_section(normalized, regime, lang, dark, palette),
        *_scores_section(normalized, regime, lang, dark),
        *_peers_section(regime, lang),
        *_transaction_section(normalized, regime, (saved_store or {}).get(ctx.key, {}), reporting, lang, dark),
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
    ctx = _load_context(store) if year_value else None
    if ctx is None:
        raise dash.exceptions.PreventUpdate
    normalized = ctx.normalized
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
        lambda value: layout.format_amount(value, lang), dark=dark, palette=chart_theme.palette_for(palette_code, dark),
    )
    notes = [html.Div(L(lang, f"flag_{flag}")) for flag in bridge["flags"]]
    if bridge["missing_items"]:
        notes.append(html.Div(L(lang, "bridge_missing_items",
                                items=", ".join(L(lang, f"field_{key}") for key in bridge["missing_items"]))))
    return figure, notes


# ============================================================
# Loi de Benford
# ============================================================

def _decode_upload(contents: str) -> str | None:
    """Contenu d'un dcc.Upload (data URL base64) -> texte. UTF-8 d'abord (avec ou sans BOM), puis
    Windows-1252, l'encodage des exports Excel français."""
    try:
        raw = base64.b64decode(contents.split(",", 1)[1])
    except Exception:
        return None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


@app.callback(
    Output("benford-file-store", "data"),
    Output("benford-file-info", "children"),
    Output("benford-column-dropdown", "options"),
    Output("benford-column-dropdown", "value"),
    Input("benford-upload", "contents"),
    State("benford-upload", "filename"),
    State("lang-radio", "value"),
    prevent_initial_call=True,
)
def store_benford_file(contents, filename, lang):
    lang = lang or "fr"
    if not contents:
        raise dash.exceptions.PreventUpdate
    text = _decode_upload(contents)
    frame = read_ledger_csv(text) if text is not None else None
    if frame is None:
        return None, dbc.Alert(L(lang, "benford_file_unreadable"), color="danger", className="py-1 px-2"), [], None
    columns = {str(name): frame[name].tolist() for name in frame.columns}
    file_store = {"filename": filename or "", "columns": columns, "n_rows": len(frame),
                  "guessed_column": guess_amount_column(columns)}
    options = [{"label": name, "value": name} for name in columns]
    return file_store, layout.benford_file_info(file_store, lang), options, file_store["guessed_column"]


@app.callback(
    Output("benford-result", "children"),
    Input("benford-source-radio", "value"),
    Input("benford-column-dropdown", "value"),
    Input("benford-sign-radio", "value"),
    Input("benford-min-amount-input", "value"),
    Input("benford-file-store", "data"),
    Input("analysis-ticker-store", "data"),
    Input("lang-radio", "value"),
    Input("dark-mode-switch", "value"),
    Input("palette-dropdown", "value"),
)
def update_benford(source, column, sign, min_amount, file_store, analysis_store, lang, dark_mode, palette_code):
    lang = lang or "fr"
    dark = bool(dark_mode)
    palette = chart_theme.palette_for(palette_code, dark)
    min_amount = float(min_amount) if min_amount is not None else DEFAULT_BENFORD_MIN_AMOUNT
    if source == "statements":
        ctx = _load_context(analysis_store)
        if ctx is None:
            return html.Div(L(lang, "benford_no_ticker"), className="text-muted")
        raw_values = (imported_statement_amounts(ctx.dataset) if ctx.imported
                      else financial_statement_amounts(get_annual_statements(ctx.ticker)))
        demo = True
    else:
        if not file_store or not column or column not in file_store["columns"]:
            return html.Div(L(lang, "benford_no_file"), className="text-muted")
        raw_values = file_store["columns"][column]
        demo = False
    amounts, counts = select_benford_amounts(raw_values, sign=sign or "positive", min_amount=min_amount)
    return layout.benford_result_view(benford_first_digit_test(amounts), counts, demo, lang, dark, palette)


# ============================================================
# Import d'états financiers (CSV)
# ============================================================

@app.callback(
    Output("analysis-ticker-store", "data", allow_duplicate=True),
    Output("statements-import-feedback", "children"),
    Input("statements-upload", "contents"),
    State("statements-upload", "filename"),
    State("lang-radio", "value"),
    prevent_initial_call=True,
)
def import_statements(contents, filename, lang):
    """Un fichier valide devient la société analysée (remplace Yahoo) ; un fichier en erreur est refusé
    en entier, avec la liste des erreurs, et l'analyse affichée reste inchangée. Le dataset voyage dans
    analysis-ticker-store : quelques centaines de montants, et tous les callbacks d'analyse le lisent
    déjà."""
    lang = lang or "fr"
    if not contents:  # composant recréé au changement de langue
        raise dash.exceptions.PreventUpdate
    text = _decode_upload(contents)
    result = parse_statements_csv(text) if text is not None else None
    feedback = layout.import_feedback(result, filename or "", lang)
    if result is None or result["errors"]:
        return dash.no_update, feedback
    return {"source": "import", "filename": filename or "", "dataset": result["dataset"]}, feedback


TEMPLATE_META_KEYS = {"fr": ("societe", "devise", "unite", "regime", "secteur", "industrie"),
                      "en": ("company", "currency", "unit", "regime", "sector", "industry")}
TEMPLATE_META_DEFAULTS = ("", "EUR", "millions", "general", "", "")
TEMPLATE_YEARS = 4


@app.callback(
    Output("statements-template-download", "data"),
    Input("statements-template-btn", "n_clicks"),
    State("lang-radio", "value"),
    prevent_initial_call=True,
)
def download_statements_template(n_clicks, lang):
    lang = lang or "fr"
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    labels = {"_key": L(lang, "import_col_key"), "_label": L(lang, "import_col_label"),
              **{key: L(lang, f"field_{key}") for key in FIELD_KEYS},
              IMPORT_MARKET_CAP_KEY: L(lang, "field_market_cap_import")}
    comments = [L(lang, f"import_template_comment_{i}") for i in range(1, 6)]
    meta_lines = list(zip(TEMPLATE_META_KEYS.get(lang, TEMPLATE_META_KEYS["fr"]), TEMPLATE_META_DEFAULTS))
    last_closed = pd.Timestamp.today().year - 1
    years = [f"{year}-12-31" for year in range(last_closed, last_closed - TEMPLATE_YEARS, -1)]
    text = statements_csv_template(labels, comments, meta_lines, years)
    # BOM UTF-8 : sans lui, Excel ouvre le fichier en Windows-1252 et abîme les accents des libellés.
    return dcc.send_string("﻿" + text, L(lang, "import_template_filename"))


# ============================================================
# Databook Excel
# ============================================================

def databook_inputs(ctx: AnalysisContext, saved: dict | None, lang: str) -> dict:
    """Tous les résultats du moteur pour le databook, calculés comme à l'écran. Une analyse non
    applicable (banque, assureur) vaut None ; une liste vide signifie « applicable, mais aucun couple
    d'exercices disponible ». Altman est calculé avec les deux modèles : le databook ne dépend pas de
    la bascule affichée à l'écran, et indique le modèle retenu par défaut pour le secteur."""
    normalized, regime = ctx.normalized, ctx.regime
    applicable = regime["applicable"]
    pairs = consecutive_pairs(normalized)
    earnings = None
    if applicable["earnings_quality"]:
        conversion, accruals = cash_conversion(normalized), sloan_accruals(normalized)
        earnings = {year: {**conversion[year], "sloan_accruals": accruals[year]} for year in normalized.years}
    altman = None
    if applicable["altman"]:
        market_values = (imported_market_caps(ctx.dataset) if ctx.imported
                         else _market_values_at_year_end(ctx.ticker, normalized, ctx.profile))
        altman = {
            "original": [altman_z_score(normalized, year, "original", market_values.get(year)) for year in normalized.years],
            "z_double_prime": [altman_z_score(normalized, year, "z_double_prime") for year in normalized.years],
        }
    piotroski = None
    if applicable["piotroski"]:
        piotroski = [r for r in (piotroski_f_score(normalized, year) for year, _prior in pairs) if r["n_available"] > 0]
    transaction = None
    if applicable["transaction_services"]:
        saved = saved or {}
        currency = ctx.profile["reporting_currency"] or L(lang, "na")
        figures = _transaction_figures(ctx, saved.get("net_debt_items"), saved.get("ebitda_adjustments"),
                                       saved.get("pension_tax_rate_pct"))
        transaction = {**figures, "notes": _transaction_notes(ctx, figures, currency, lang)}
    return {
        "company": ctx.profile["name"], "identifier": ctx.filename if ctx.imported else ctx.ticker,
        "imported": ctx.imported, "currency": ctx.profile["reporting_currency"], "regime": regime,
        "normalized": normalized, "export_date": pd.Timestamp.today().strftime(L(lang, "date_format")),
        "earnings": earnings,
        "wc_days": working_capital_days(normalized) if applicable["working_capital"] else None,
        "beneish": [beneish_m_score(normalized, year, prior) for year, prior in pairs] if applicable["beneish"] else None,
        "altman": altman, "altman_default_model": altman_default_model(ctx.profile["sector"]),
        "piotroski": piotroski, "transaction": transaction,
        # Comparaison aux pairs recalculée à l'export : le cache (24 h) la rend quasi instantanée si elle a
        # déjà été lancée à l'écran, sinon le premier export télécharge les comptes du CAC 40.
        "peers": peer_comparison(ctx, lang),
    }


@app.callback(
    Output("databook-download", "data"),
    Input("databook-btn", "n_clicks"),
    State("analysis-ticker-store", "data"),
    State("adjustments-store", "data"),
    State("lang-radio", "value"),
    prevent_initial_call=True,
)
def download_databook(n_clicks, store, saved_store, lang):
    lang = lang or "fr"
    ctx = _load_context(store) if n_clicks else None
    if ctx is None or not ctx.normalized.years:
        raise dash.exceptions.PreventUpdate
    content = build_databook(databook_inputs(ctx, (saved_store or {}).get(ctx.key), lang), lang)
    name = (ctx.filename.rsplit(".", 1)[0] if ctx.imported else ctx.ticker) or "analyse"
    return dcc.send_bytes(content, L(lang, "databook_filename", name=name.replace(" ", "_")))
