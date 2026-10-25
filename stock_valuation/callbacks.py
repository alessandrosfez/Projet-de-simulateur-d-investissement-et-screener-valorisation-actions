"""
Enregistrement de tous les callbacks Dash. Importer ce module (voir app.py)
suffit à les enregistrer sur l'instance `app` partagée (app_instance.py) : les
fonctions ci-dessous ne sont pas appelées directement ailleurs, sauf les
helpers réutilisés par layout.py lui-même.
"""
import concurrent.futures
import math
import threading

import dash
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

import layout
from app_instance import app
from charts import empty_figure_with_message, make_football_field, make_pe_history_figure, make_sector_strip_figure
from constants import UNIVERSE_TICKERS
from engine import (
    FOOTBALL_FIELD_METHODS, WATCHLIST_ALERTS, WATCHLIST_PE_HISTORY_LOW_PCT, annualized_return, annualized_volatility,
    compute_comparables_ev_ebitda_fair_value, compute_comparables_fair_value, compute_dcf_fair_value,
    compute_dcf_sensitivity_grid, compute_scenario_dcf_fair_values, football_field_ranges, max_drawdown,
    pe_signal_forward_returns, peer_quartile_multiples, sharpe_ratio, summarize_pe_signal_backtest, watchlist_alerts,
)
import chart_theme
from i18n import L, PALETTE_CODES, PALETTE_NAMES, num
from market_data import (
    get_dcf_inputs, get_stock_pe_history, get_stock_price_history, get_stock_quality_metrics, get_stock_valuation,
    major_currency,
)

# Hauteur du tableau de criblage : en-tête (libellés sur deux ou trois lignes) puis lignes du thème
# AG Grid, en pixels.
GRID_HEADER_PX, GRID_ROW_PX = 96, 42

# ============================================================
# Habillage global (langue, palette, thème) : identique dans l'esprit à
# portfolio_projection, mais reconstruit ici son propre sous-ensemble de
# contenu (pas de sidebar, pas d'onglets à cet outil).
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
    return layout.build_header_text(lang), layout.build_tab3(lang, v), layout.build_footer(lang)


# ============================================================
# CALLBACKS : valorisation d'actions individuelles
# ============================================================

def _format_market_cap(value, lang="fr"):
    """Formate une capitalisation (montant abrégé, sans devise : l'appelant ajoute la devise principale,
    voir market_data.major_currency)."""
    if not value or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    for threshold, suffix in [(1e12, "T"), (1e9, "Md"), (1e6, "M")]:
        if value >= threshold:
            return f"{num(value / threshold, '.1f', lang)} {suffix}"
    return num(value, ",.0f", lang)


def _format_abbreviated(value, lang="fr"):
    """Nombre abrégé (M/Md), signe conservé, sans unité (à ajouter par l'appelant si besoin) :
    utilisé pour le détail du calcul DCF, où les montants (FCF, dette, valeur d'entreprise...)
    sont trop grands pour s'afficher lisiblement en entier."""
    sign = "-" if value < 0 else ""
    abs_value = abs(value)
    for threshold, suffix in [(1e9, "Md"), (1e6, "M")]:
        if abs_value >= threshold:
            return f"{sign}{num(abs_value / threshold, '.2f', lang)} {suffix}"
    return f"{sign}{num(abs_value, ',.0f', lang)}"


def _format_dcf_amount(value, currency, lang="fr"):
    return f"{_format_abbreviated(value, lang)} {currency}"


# État de progression du chargement en cours, partagé entre load_stock_valuations (qui l'écrit,
# sur le thread du serveur de dev qui traite la requête "Charger" — threaded=True dans app.py,
# voir ce fichier) et update_load_progress ci-dessous (qui le lit, sur un thread différent à
# chaque tic de dcc.Interval). total=0 veut dire "rien en cours" : c'est ce que lit l'intervalle
# la plupart du temps, pas de round-trip Dash coûteux pour autant (juste une lecture de dict sous
# verrou). Alternative à un vrai callback "background" de Dash (qui aurait demandé une nouvelle
# dépendance, diskcache, pour un gain purement cosmétique ici).
_load_progress_lock = threading.Lock()
_load_progress = {"done": 0, "total": 0}


def _load_full_stock_data(ticker):
    """get_stock_valuation + qualité + rendement/risque réalisés, en un seul dict par ticker : les
    trois alimentent le score composite (voir render_stock_views), qui a besoin de ces métriques
    pour TOUTES les actions chargées, pas seulement la ligne sélectionnée (contrairement à
    update_quality_metrics/update_track_record, lazy sur la ligne sélectionnée). Soumis au même
    ThreadPoolExecutor que get_stock_valuation ci-dessous : triple à peu près les appels yfinance
    par ticker au premier chargement à froid, accepté pour avoir un score sur tout le tableau."""
    data = get_stock_valuation(ticker)
    data.update(get_stock_quality_metrics(ticker))
    prices = get_stock_price_history(ticker)
    returns = prices.pct_change().dropna().to_numpy() if len(prices) > 1 else np.array([])
    data["cagr"] = annualized_return(returns)
    data["volatility"] = annualized_volatility(returns)
    data["max_drawdown"] = max_drawdown(returns)
    data["sharpe"] = sharpe_ratio(data["cagr"], data["volatility"])
    return data


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

    with _load_progress_lock:
        _load_progress["done"] = 0
        _load_progress["total"] = len(tickers)

    rows, failures = [], []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            future_to_stock = {executor.submit(_load_full_stock_data, ticker): (name, ticker) for name, ticker in tickers.items()}
            for future in concurrent.futures.as_completed(future_to_stock):
                name, ticker = future_to_stock[future]
                try:
                    data = future.result()
                except Exception:
                    failures.append(name)
                else:
                    data["Entreprise"] = name
                    data["Ticker"] = ticker
                    rows.append(data)
                finally:
                    with _load_progress_lock:
                        _load_progress["done"] += 1
    finally:
        with _load_progress_lock:
            _load_progress["total"] = 0

    warning = ""
    if failures:
        warning = dbc.Alert(L(lang, "unavailable_tickers", names=", ".join(sorted(failures))), color="warning")
    if not rows:
        warning = dbc.Alert(L(lang, "no_data_fetched"), color="danger")
    return rows, warning


@app.callback(
    Output("stocks-load-progress", "children"),
    Input("load-progress-interval", "n_intervals"),
    State("lang-radio", "value"),
)
def update_load_progress(_n_intervals, lang):
    lang = lang or "fr"
    with _load_progress_lock:
        done, total = _load_progress["done"], _load_progress["total"]
    if total == 0:
        return ""
    return L(lang, "load_progress_text", done=done, total=total)


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
    Output("watchlist-dropdown", "options"),
    Input("stocks-raw-store", "data"),
)
def update_watchlist_options(rows):
    if not rows:
        return []
    return [{"label": f"{r['Entreprise']} ({r['Ticker']})", "value": r["Ticker"]} for r in rows]


# Icône de chaque alerte de la liste de suivi : l'icône et le libellé portent le sens ensemble.
WATCHLIST_ALERT_ICONS = {"pe_history_low": "graph-down-arrow", "below_comparables": "people",
                         "below_dcf": "calculator", "high_score": "star"}


def _default_dcf_fair_value(ticker: str):
    """Valeur intrinsèque DCF aux hypothèses par défaut des curseurs (layout.DCF_DEFAULTS), ou None
    quand le DCF n'a pas de sens (FCF négatif, données manquantes) : dans ce cas pas d'alerte, jamais
    une valeur inventée."""
    inputs = get_dcf_inputs(ticker)
    if not inputs or inputs.get("fcf") is None or inputs["fcf"] < 0 or not inputs.get("shares_outstanding"):
        return None
    defaults = layout.DCF_DEFAULTS
    result = compute_dcf_fair_value(
        inputs["fcf"], defaults["growth_pct"], defaults["discount_pct"], defaults["terminal_growth_pct"],
        defaults["horizon_years"], inputs["total_debt"] - inputs["total_cash"], inputs["shares_outstanding"],
    )
    return result["fair_value_per_share"] if result else None


@app.callback(
    Output("watchlist-alerts", "children"),
    Input("stocks-raw-store", "data"),
    Input("watchlist-dropdown", "value"),
    Input("lang-radio", "value"),
)
def update_watchlist_alerts(rows, watchlist, lang):
    """Signaux des titres suivis (engine.watchlist_alerts), calculés sur tout l'univers chargé
    (pairs du même secteur, score) et donc indépendants des filtres du tableau. Les titres sans
    signal sont regroupés en une ligne : l'absence d'alerte n'est pas un avis contraire."""
    lang = lang or "fr"
    if not rows or not watchlist:
        return ""
    df = _scored_frame(rows)
    cards, quiet = [], []
    for ticker in watchlist:
        match = df[df["Ticker"] == ticker]
        if match.empty:
            continue
        row = match.iloc[0]
        peers = df[(df["Ticker"] != ticker) & (df["Secteur"] == row["Secteur"])]["P/E (trailing)"].dropna().tolist()

        def value(column, row=row):
            return None if column not in row or pd.isna(row[column]) else float(row[column])

        alerts = watchlist_alerts(value("Prix"), value("P/E (trailing)"),
                                  value("Position vs historique 5 ans (percentile)"), value("Score"), peers,
                                  _default_dcf_fair_value(ticker))
        name = f"{row['Entreprise']} ({ticker})"
        if not alerts:
            quiet.append(name)
            continue
        badges = [
            html.Span([html.I(className=f"bi bi-{WATCHLIST_ALERT_ICONS[key]} me-1", **{"aria-hidden": "true"}),
                       # Percentile arrondi vers le bas : « 19,6 » affiché « 20 » contredirait la règle « sous 20 ».
                       L(lang, f"watch_alert_{key}",
                         value=math.floor(alerts[key]) if key == "pe_history_low" else alerts[key])],
                      className="watch-badge")
            for key in WATCHLIST_ALERTS if key in alerts
        ]
        cards.append(html.Div([html.Div(name, className="watch-name"), html.Div(badges, className="watch-badges")],
                              className="watch-card"))
    children = [html.Div([html.I(className="bi bi-bell me-2", **{"aria-hidden": "true"}), L(lang, "watch_alerts_title")]
                         + layout.info_tooltip("watch-alerts-info", L(
        lang, "watch_alerts_help", growth=layout.DCF_DEFAULTS["growth_pct"],
        discount=layout.DCF_DEFAULTS["discount_pct"], terminal=layout.DCF_DEFAULTS["terminal_growth_pct"],
        horizon=layout.DCF_DEFAULTS["horizon_years"])), className="watch-title")]
    children += cards
    if quiet:
        children.append(html.Div(L(lang, "watch_alerts_quiet", names=", ".join(quiet)), className="watch-quiet"))
    return html.Div(children, className="watch-panel")


@app.callback(
    Output("pe-backtest-result", "children"),
    Input("stocks-raw-store", "data"),
    Input("lang-radio", "value"),
)
def render_pe_backtest(rows, lang):
    """Backtest du signal "P/E décoté/tendu vs historique propre" (voir engine.
    pe_signal_forward_returns) : calculé sur l'ensemble du panier chargé, pas filtré par secteur
    ni par la watchlist (même convention que le comparatif sectoriel ci-dessus). get_stock_pe_history
    est déjà appelé pour chaque ticker pendant load_stock_valuations (calcul de pe_5y_percentile) :
    son cache (voir market_data.cached_ttl) rend ce second appel ici gratuit, pas de nouvel appel
    réseau."""
    lang = lang or "fr"
    if not rows:
        return L(lang, "pe_backtest_hint_default")

    per_stock = []
    for row in rows:
        pe_history = get_stock_pe_history(row["Ticker"])
        if pe_history is None or len(pe_history) == 0:
            continue
        per_stock.append(pe_signal_forward_returns(pe_history.to_numpy()))

    summary = summarize_pe_signal_backtest(per_stock)
    if all(summary[bucket]["n"] == 0 for bucket in ("low", "mid", "high")):
        return L(lang, "pe_backtest_insufficient_data")

    def _card(label_key, stats):
        if stats["n"] == 0:
            body = [
                html.H6(L(lang, label_key), className="card-subtitle text-muted mb-1"),
                html.P(L(lang, "pe_backtest_no_data"), className="text-muted mb-0"),
            ]
        else:
            color = "success" if stats["mean"] >= 0 else "danger"
            body = [
                html.H6(L(lang, label_key), className="card-subtitle text-muted mb-1"),
                html.H5(f"{num(stats['mean'] * 100, '+.1f', lang)} %", className=f"text-{color} mb-1"),
                html.Small(
                    L(lang, "pe_backtest_stats_caption", median=f"{num(stats['median'] * 100, '+.1f', lang)} %", n=stats["n"]),
                    className="text-muted",
                ),
            ]
        return dbc.Col(dbc.Card(dbc.CardBody(body), className="h-100"), width=4)

    return html.Div([
        dbc.Row([
            _card("pe_backtest_low_label", summary["low"]),
            _card("pe_backtest_mid_label", summary["mid"]),
            _card("pe_backtest_high_label", summary["high"]),
        ], className="mb-2"),
        html.P(L(lang, "pe_backtest_caveat"), className="text-muted", style={"fontSize": "0.78rem"}),
    ])




def _scored_frame(rows) -> pd.DataFrame:
    """Données chargées sous les noms de colonnes du tableau, avec le score composite calculé sur
    tout l'univers chargé. Partagé par le tableau (render_stock_views) et les alertes de la liste
    de suivi (update_watchlist_alerts), pour qu'une alerte « score >= 70 » corresponde toujours au
    score affiché, quels que soient les filtres."""
    # Noms de colonnes internes gardés stables (français) : ce sont des clés de travail, pas du
    # texte affiché : seul le libellé de colonne du tableau final ("name") est traduit plus bas.
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "sector": "Secteur", "currency": "Devise", "price": "Prix",
        "trailing_pe": "P/E (trailing)", "forward_pe": "P/E (prévisionnel)",
        "peg_ratio": "PEG", "ev_to_ebitda": "EV/EBITDA",
        "price_to_book": "P/B", "dividend_yield": "Rendement dividende (%)",
        "market_cap": "Capitalisation",
        "pe_5y_mean": "P/E moyen 5 ans (approx.)", "pe_5y_percentile": "Position vs historique 5 ans (percentile)",
    })

    # --- Score composite : calculé sur l'ensemble CHARGÉ (df), jamais sur detail_df (filtré par
    # secteur/filtres/watchlist plus bas) -- sinon le score d'une action changerait juste parce que
    # l'utilisateur modifie un filtre sans rapport, même principe que le comparatif sectoriel
    # ci-dessous. Trois piliers également pondérés, chacun une moyenne de rangs percentiles (0-100,
    # 100 = meilleur) au sein de l'univers chargé : valorisation (P/E et PEG, plus bas = meilleur,
    # valeurs négatives/nulles exclues car elles signalent des pertes, pas une décote), qualité
    # (ROIC et marge nette, plus haut = meilleur), track record (Sharpe réalisé, qui combine déjà
    # rendement et risque, pas besoin de re-classer CAGR/volatilité séparément). Une action sans
    # aucune des trois données a un score NaN -> "N/A" à l'affichage (voir plus bas).
    pe_valid = df["P/E (trailing)"].where(df["P/E (trailing)"] > 0)
    peg_valid = df["PEG"].where(df["PEG"] > 0) if "PEG" in df.columns else pd.Series(dtype=float, index=df.index)
    valuation_pillar = pd.concat([
        pe_valid.rank(pct=True, ascending=False) * 100,
        peg_valid.rank(pct=True, ascending=False) * 100,
    ], axis=1).mean(axis=1, skipna=True)
    quality_pillar = pd.concat([
        df.get("roic", pd.Series(dtype=float, index=df.index)).rank(pct=True, ascending=True) * 100,
        df.get("profit_margin", pd.Series(dtype=float, index=df.index)).rank(pct=True, ascending=True) * 100,
    ], axis=1).mean(axis=1, skipna=True)
    track_record_pillar = df.get("sharpe", pd.Series(dtype=float, index=df.index)).rank(pct=True, ascending=True) * 100
    df["Score"] = pd.concat([valuation_pillar, quality_pillar, track_record_pillar], axis=1).mean(axis=1, skipna=True)
    return df


@app.callback(
    Output("stocks-sector-strip", "figure"),
    Output("stocks-top-cards", "children"),
    Output("stocks-pe-chart", "figure"),
    Output("stocks-table", "rowData"),
    Output("stocks-table", "columnDefs"),
    Output("stocks-table", "style"),
    Output("stocks-csv-store", "data"),
    Output("stocks-results-container", "style"),
    Output("stocks-empty-state", "style"),
    Input("stocks-raw-store", "data"),
    Input("sector-filter", "value"),
    Input("filter-pe-max", "value"),
    Input("filter-peg-max", "value"),
    Input("filter-div-min", "value"),
    Input("filter-score-min", "value"),
    Input("watchlist-dropdown", "value"),
    Input("watchlist-only-switch", "value"),
    Input("lang-radio", "value"),
    Input("palette-dropdown", "value"),
    Input("dark-mode-switch", "value"),
)
def render_stock_views(rows, sector_value, pe_max, peg_max, div_min, score_min, watchlist_tickers, watchlist_only,
                        lang, palette_code, dark_mode):
    lang = lang or "fr"
    dark = bool(dark_mode)
    palette = chart_theme.palette_for(palette_code, dark)
    column_label_keys = {
        "Entreprise": "col_company", "Ticker": "col_ticker", "Score": "col_score", "Secteur": "col_sector",
        "Devise": "col_currency", "Prix": "col_price", "P/E (trailing)": "col_pe_trailing",
        "P/E (prévisionnel)": "col_pe_forward", "PEG": "col_peg", "EV/EBITDA": "col_ev_ebitda", "P/B": "col_pb",
        "Rendement dividende (%)": "col_div_yield", "P/E moyen 5 ans (approx.)": "col_pe_5y_mean",
        "Position vs historique 5 ans (percentile)": "col_pe_5y_pct", "Capitalisation": "col_market_cap",
    }
    # Infobulle d'en-tête indexée par colonne interne : survol d'un en-tête -> définition/formule.
    # Seules les colonnes avec une clé "..._help" dans i18n.py en ont une (L() retombe sur la clé
    # elle-même si absente, d'où le test d'égalité).
    help_texts = {}
    for c, label_key in column_label_keys.items():
        help_key = f"{label_key}_help"
        help_text = L(lang, help_key)
        if help_text != help_key:
            help_texts[c] = help_text
    if not rows:
        placeholder = empty_figure_with_message(L(lang, "load_hint_placeholder"), dark=dark)
        return (placeholder, "", placeholder, [], [], {"height": "70vh"}, "", {"display": "none"},
                {"display": "block"})

    df = _scored_frame(rows)

    priced_all = df.dropna(subset=["P/E (trailing)"]).copy()
    priced_all = priced_all[priced_all["P/E (trailing)"] > 0]

    # --- Comparatif par secteur : toujours calculé sur l'ensemble chargé, pas filtré ---
    # Un seul nuage de points (un point par action, médiane du secteur, titres suivis nommés) à la
    # place de l'ancien duo barres des moyennes + boîtes : tout se lit sur un même graphique.
    sector_strip = empty_figure_with_message("", dark=dark)
    if not priced_all.empty:
        medians = priced_all.groupby("Secteur")["P/E (trailing)"].median().sort_values()
        watched = set(watchlist_tickers or [])
        points = [
            {"sector": r["Secteur"], "pe": float(r["P/E (trailing)"]), "name": r["Entreprise"],
             "highlight": r["Ticker"] in watched}
            for _, r in priced_all.iterrows() if pd.notna(r["Secteur"])
        ]
        # Secteur absent chez Yahoo (« N/A ») : intitulé explicite plutôt qu'un sigle.
        unknown = L(lang, "sector_unknown")
        for point in points:
            point["sector"] = unknown if point["sector"] in ("N/A", "") else point["sector"]
        medians.index = [unknown if s in ("N/A", "") else s for s in medians.index]
        sector_strip = make_sector_strip_figure(
            list(medians.index), points, medians.to_dict(), palette[0], palette[1 % len(palette)],
            L(lang, "sector_strip_title"), L(lang, "sector_median_label"), dark=dark,
            separators=L(lang, "plotly_separators"),
        )

    # --- Détail (cartes, graphique, tableau) : filtré sur le secteur choisi, puis sur les
    # filtres de sélection et la watchlist (ces derniers n'affectent jamais le comparatif
    # sectoriel ci-dessus, calculé sur l'ensemble chargé). Une valeur sans donnée sur le critère
    # filtré (NaN) est exclue plutôt que gardée par défaut : on ne peut pas garantir qu'elle
    # respecte le seuil.
    detail_df = df if sector_value == "all" else df[df["Secteur"] == sector_value]
    if pe_max not in (None, ""):
        detail_df = detail_df[detail_df["P/E (trailing)"] <= float(pe_max)]
    if peg_max not in (None, "") and "PEG" in detail_df.columns:
        detail_df = detail_df[detail_df["PEG"] <= float(peg_max)]
    if div_min not in (None, "") and "Rendement dividende (%)" in detail_df.columns:
        detail_df = detail_df[detail_df["Rendement dividende (%)"] >= float(div_min)]
    if score_min not in (None, "") and "Score" in detail_df.columns:
        detail_df = detail_df[detail_df["Score"] >= float(score_min)]
    if watchlist_only and "only" in watchlist_only and watchlist_tickers:
        detail_df = detail_df[detail_df["Ticker"].isin(watchlist_tickers)]
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
                html.Li(f"{row['Entreprise']} : P/E {num(row['P/E (trailing)'], '.1f', lang)} "
                        f"({L(lang, 'sector_unknown') if row['Secteur'] in ('N/A', '') else row['Secteur']})")
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
                # Libellé traduit : cette phrase restait en français dans l'interface anglaise.
                html.Li(L(
                    lang, "history_card_item", name=row["Entreprise"], pe=row["P/E (trailing)"],
                    mean=row["P/E moyen 5 ans (approx.)"], pct=row["Position vs historique 5 ans (percentile)"],
                ))
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
        # Points sur tige plutôt que barres : sur une échelle logarithmique une barre part d'un zéro qui
        # n'existe pas, et Plotly en dessine mal les graduations. Échelle logarithmique nécessaire : un
        # P/E extrême (STMicroelectronics à plus de 1 300) écrasait sinon tous les autres à zéro.
        values = plot_df["P/E (trailing)"].astype(float).tolist()
        names = plot_df["Entreprise"].tolist()
        floor = min(values) / 1.5
        stem_x, stem_y = [], []
        for name, value in zip(names, values):
            stem_x += [name, name, None]
            stem_y += [floor, value, None]
        fig.add_trace(go.Scatter(x=stem_x, y=stem_y, mode="lines", hoverinfo="skip", showlegend=False,
                                 line=dict(color=palette[0], width=2)))
        fig.add_trace(go.Scatter(
            x=names, y=values, mode="markers", showlegend=False, customdata=plot_df["Secteur"],
            marker=dict(size=10, color=palette[0], line=dict(width=2, color=chart_theme.surface_color(dark))),
            hovertemplate="%{x}<br>P/E : %{y:.1f}<br>%{customdata}<extra></extra>",
        ))
        # Moyenne du panier tracée comme une courbe, pas avec add_hline : sur un axe logarithmique,
        # Plotly lit la position d'un trait horizontal en puissance de 10 (y = 60 devenait 10^60).
        mean_pe = float(plot_df["P/E (trailing)"].mean())
        fig.add_trace(go.Scatter(
            x=[names[0], names[-1]], y=[mean_pe, mean_pe], mode="lines+text", showlegend=False, hoverinfo="skip",
            line=dict(color="gray", dash="dot", width=1.5), text=[L(lang, "basket_avg_annotation"), ""],
            textposition="top right", textfont=dict(size=11, color="gray"),
        ))
    fig.update_layout(
        separators=L(lang, "plotly_separators"),
        template=chart_theme.template(dark),
        title=L(lang, "pe_by_stock_chart_title"),
        xaxis=dict(title="", tickangle=-60, type="category"),
        yaxis=dict(title="P/E", type="log", dtick="D2"),
        margin=dict(t=60, b=120),
    )

    # reindex plutôt qu'un simple df[[...]] : tolère une colonne absente (ex. cache disque écrit
    # par une version antérieure du code, avant l'ajout d'un champ) en la remplissant de NaN plutôt
    # que de lever une KeyError.
    table_df = detail_df.reindex(columns=[
        "Entreprise", "Ticker", "Score", "Secteur", "Devise", "Prix", "P/E (trailing)", "P/E (prévisionnel)",
        "PEG", "EV/EBITDA", "P/B", "Rendement dividende (%)",
        "P/E moyen 5 ans (approx.)", "Position vs historique 5 ans (percentile)", "Capitalisation",
    ]).copy()
    # Devise principale accolée : à Londres, la colonne Devise affiche GBp (cours en pence) alors que
    # la capitalisation Yahoo est en livres, ce qu'un « 221.9 Md » nu à côté de « GBp » cachait.
    table_df["Capitalisation"] = [
        f"{_format_market_cap(cap, lang)} {major_currency(cur)}" if _format_market_cap(cap, lang) != "N/A" and cur not in (None, "N/A")
        else _format_market_cap(cap, lang)
        for cap, cur in zip(table_df["Capitalisation"], table_df["Devise"])
    ]
    for col in ["Score", "Prix", "P/E (trailing)", "P/E (prévisionnel)", "PEG", "EV/EBITDA", "P/B",
                "Rendement dividende (%)", "P/E moyen 5 ans (approx.)", "Position vs historique 5 ans (percentile)"]:
        table_df[col] = table_df[col].round(2)
    table_df = table_df.sort_values("P/E (trailing)")

    column_defs = layout.stocks_column_defs(
        {c: L(lang, column_label_keys.get(c, c)) for c in table_df.columns}, help_texts, lang,
    )
    csv_data = table_df.to_csv(index=False)
    # NaN -> None : un NaN JSON est invalide ; None s'affiche « N/A » et n'est jamais colorié.
    table_df = table_df.astype(object).where(pd.notnull(table_df), None)
    # Hauteur ajustée au nombre de lignes, plafonnée à 70 % de l'écran (au-delà, défilement interne
    # avec en-tête et première colonne figés) : un filtre qui ne garde que 3 titres ne laisse pas un
    # grand cadre vide.
    grid_style = {"height": f"min(70vh, {GRID_HEADER_PX + GRID_ROW_PX * max(len(table_df), 1)}px)"}

    return (sector_strip, cards_row, fig, table_df.to_dict("records"), column_defs, grid_style,
            csv_data, {"display": "block"}, {"display": "none"})


@app.callback(
    Output("stocks-pe-history-chart", "figure"),
    Output("stocks-pe-history-title", "children"),
    Input("stocks-table", "selectedRows"),
    Input("lang-radio", "value"),
    Input("palette-dropdown", "value"),
    Input("dark-mode-switch", "value"),
    State("stocks-table", "rowData"),
)
def update_pe_history_chart(selected_rows, lang, palette_code, dark_mode, grid_rows):
    lang = lang or "fr"
    dark = bool(dark_mode)
    palette = chart_theme.palette_for(palette_code, dark)
    if not selected_rows or not grid_rows:
        return empty_figure_with_message(L(lang, "history_hint_default"), dark=dark), ""

    row = selected_rows[0]
    ticker, name = row["Ticker"], row["Entreprise"]
    pe_series = get_stock_pe_history(ticker)
    if pe_series.empty:
        return (
            empty_figure_with_message(L(lang, "history_unavailable", name=name), dark=dark),
            L(lang, "history_unavailable_full", name=name),
        )

    # Zones aux 20e et 80e percentiles de l'histoire du titre (mêmes seuils que la couleur du P/E dans
    # le tableau et que l'alerte « P/E bas vs son historique »).
    values = pe_series.to_numpy(dtype=float)
    low_pe = float(np.percentile(values, WATCHLIST_PE_HISTORY_LOW_PCT))
    high_pe = float(np.percentile(values, 100 - WATCHLIST_PE_HISTORY_LOW_PCT))
    current_pe = row.get("P/E (trailing)")
    percentile = row.get("Position vs historique 5 ans (percentile)")
    current_text = (L(lang, "history_current_point", pe=current_pe, pct=percentile) if percentile is not None
                    else L(lang, "history_current_point_no_pct", pe=current_pe)) if current_pe is not None else ""
    fig = make_pe_history_figure(
        list(pe_series.index), list(values), current_pe, low_pe, high_pe,
        {"low_zone": L(lang, "history_low_zone", pe=low_pe), "high_zone": L(lang, "history_high_zone", pe=high_pe),
         "mean": L(lang, "history_mean_value", pe=float(values.mean())), "current": current_text,
         "current_hover": L(lang, "history_current_hover")},
        palette[0], L(lang, "history_chart_title", name=name), dark=dark, separators=L(lang, "plotly_separators"),
    )
    method_key = "history_method_current_eps" if pe_series.attrs.get("method") == "current_eps" else "history_method_annual_eps"
    return fig, L(lang, method_key)


@app.callback(
    Output("dcf-scenario-collapse", "is_open"),
    Input("btn-toggle-dcf-scenarios", "n_clicks"),
    State("dcf-scenario-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_dcf_scenarios(n_clicks, is_open):
    return not is_open


@app.callback(
    Output("intro-details-collapse", "is_open"),
    Input("btn-toggle-intro-details", "n_clicks"),
    State("intro-details-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_intro_details(n_clicks, is_open):
    return not is_open


@app.callback(
    Output("dcf-scenario-weights-caption", "children"),
    Input("dcf-weight-bear-input", "value"),
    Input("dcf-weight-base-input", "value"),
    Input("dcf-weight-bull-input", "value"),
    Input("lang-radio", "value"),
)
def update_dcf_scenario_weights_caption(weight_bear, weight_base, weight_bull, lang):
    lang = lang or "fr"
    weights = [weight_bear or 0, weight_base or 0, weight_bull or 0]
    total = sum(weights)
    if total == 0:
        return ""
    bear, base, bull = (w / total * 100 for w in weights)
    return L(lang, "dcf_scenario_weights_caption", bear=bear, base=base, bull=bull)


@app.callback(
    Output("quality-metrics-card", "children"),
    Input("stocks-table", "selectedRows"),
    Input("lang-radio", "value"),
    State("stocks-table", "rowData"),
)
def update_quality_metrics(selected_rows, lang, grid_rows):
    lang = lang or "fr"
    if not selected_rows or not grid_rows:
        return html.Div(L(lang, "quality_hint_default"), className="text-muted")

    row = selected_rows[0]
    ticker = row["Ticker"]
    m = get_stock_quality_metrics(ticker)

    def stat(label_key, value, suffix=""):
        text = f"{num(value, '.1f', lang)}{suffix}" if value is not None else "N/A"
        return dbc.Col([
            html.Small(L(lang, label_key), className="text-muted d-block"),
            html.H6(text),
        ], width=3, className="mb-2")

    stats = [
        stat("quality_roic_label", m["roic"], " %"),
        stat("quality_roe_label", m["return_on_equity"], " %"),
        stat("quality_roa_label", m["return_on_assets"], " %"),
        stat("quality_revenue_growth_label", m["revenue_growth"], " %"),
        stat("quality_gross_margin_label", m["gross_margin"], " %"),
        stat("quality_operating_margin_label", m["operating_margin"], " %"),
        stat("quality_profit_margin_label", m["profit_margin"], " %"),
        stat("quality_debt_to_equity_label", m["debt_to_equity"]),
        stat("quality_current_ratio_label", m["current_ratio"]),
        stat("quality_quick_ratio_label", m["quick_ratio"]),
    ]
    return dbc.Card(dbc.CardBody(dbc.Row(stats)))


@app.callback(
    Output("track-record-card", "children"),
    Input("stocks-table", "selectedRows"),
    Input("lang-radio", "value"),
    State("stocks-table", "rowData"),
)
def update_track_record(selected_rows, lang, grid_rows):
    lang = lang or "fr"
    if not selected_rows or not grid_rows:
        return html.Div(L(lang, "track_record_hint_default"), className="text-muted")

    row = selected_rows[0]
    ticker = row["Ticker"]
    prices = get_stock_price_history(ticker)
    returns = prices.pct_change().dropna().to_numpy() if len(prices) > 1 else np.array([])

    cagr = annualized_return(returns)
    volatility = annualized_volatility(returns)
    drawdown = max_drawdown(returns)
    sharpe = sharpe_ratio(cagr, volatility)

    if len(returns) == 0:
        return html.Div(L(lang, "track_record_hint_default"), className="text-muted")

    def stat(label_key, value, suffix=""):
        text = f"{num(value, '.1f', lang)}{suffix}" if value is not None else "N/A"
        return dbc.Col([
            html.Small(L(lang, label_key), className="text-muted d-block"),
            html.H6(text),
        ], width=3, className="mb-2")

    stats = [
        stat("track_record_cagr_label", cagr * 100 if cagr is not None else None, " %"),
        stat("track_record_volatility_label", volatility * 100 if volatility is not None else None, " %"),
        stat("track_record_max_drawdown_label", drawdown * 100 if drawdown is not None else None, " %"),
        stat("track_record_sharpe_label", sharpe),
    ]
    return html.Div([
        dbc.Card(dbc.CardBody(dbc.Row(stats))),
        html.Small(L(lang, "track_record_methodology_hint"), className="text-muted d-block mt-1"),
    ])


@app.callback(
    Output("dcf-result", "children"),
    Output("dcf-chart", "figure"),
    Input("stocks-table", "selectedRows"),
    Input("dcf-growth-slider", "value"),
    Input("dcf-discount-slider", "value"),
    Input("dcf-terminal-growth-slider", "value"),
    Input("dcf-horizon-slider", "value"),
    Input("dcf-growth-offset-slider", "value"),
    Input("dcf-discount-offset-slider", "value"),
    Input("dcf-weight-bear-input", "value"),
    Input("dcf-weight-base-input", "value"),
    Input("dcf-weight-bull-input", "value"),
    Input("lang-radio", "value"),
    Input("palette-dropdown", "value"),
    Input("dark-mode-switch", "value"),
    State("stocks-table", "rowData"),
)
def update_dcf(selected_rows, growth_pct, discount_pct, terminal_growth_pct, horizon_years,
                growth_offset_pct, discount_offset_pct, weight_bear, weight_base, weight_bull,
                lang, palette_code, dark_mode, grid_rows):
    lang = lang or "fr"
    dark = bool(dark_mode)
    palette = chart_theme.palette_for(palette_code, dark)
    empty_fig = empty_figure_with_message("", dark=dark)
    if not selected_rows or not grid_rows:
        return L(lang, "dcf_hint_default"), empty_fig

    row = selected_rows[0]
    ticker, name = row["Ticker"], row["Entreprise"]
    inputs = get_dcf_inputs(ticker)
    price = inputs.get("price")
    currency = inputs["currency"]

    if not inputs.get("fcf") or not inputs.get("shares_outstanding"):
        return dbc.Alert(L(lang, "dcf_unavailable", name=name), color="warning"), empty_fig

    # FCF négatif (TTM) : projeter/actualiser un flux négatif ne donne pas une valeur intrinsèque
    # exploitable (le résultat "s'aggrave" avec la croissance au lieu de converger), fréquent pour
    # une valeur capitalistique en pleine phase d'investissement (énergie, télécoms...) sans que ce
    # soit un signe de difficulté. On le signale au lieu d'afficher un chiffre trompeur, mais on
    # garde les comparables ci-dessous : eux ne dépendent pas du FCF.
    growth_offset_pct = growth_offset_pct if growth_offset_pct is not None else 5
    discount_offset_pct = discount_offset_pct if discount_offset_pct is not None else 2
    weight_bear = weight_bear if weight_bear is not None else 0
    weight_base = weight_base if weight_base is not None else 0
    weight_bull = weight_bull if weight_bull is not None else 0

    dcf_blocked_msg = None
    fair_value = None
    bear_fv, bull_fv, weighted_fv = None, None, None
    if inputs["fcf"] < 0:
        dcf_blocked_msg = L(lang, "dcf_negative_fcf", name=name)
    elif discount_pct <= terminal_growth_pct:
        dcf_blocked_msg = L(lang, "dcf_invalid_assumptions")
    else:
        net_debt = inputs["total_debt"] - inputs["total_cash"]
        scenarios = compute_scenario_dcf_fair_values(
            inputs["fcf"], growth_pct, discount_pct, terminal_growth_pct, int(horizon_years),
            net_debt, inputs["shares_outstanding"], growth_offset_pct, discount_offset_pct,
            weight_bear, weight_base, weight_bull,
        )
        result = scenarios["base"]
        if result is None:
            dcf_blocked_msg = L(lang, "dcf_invalid_assumptions")
        else:
            fair_value = result["fair_value_per_share"]
            bear_fv = scenarios["bear"]["fair_value_per_share"] if scenarios["bear"] else None
            bull_fv = scenarios["bull"]["fair_value_per_share"] if scenarios["bull"] else None
            weighted_fv = scenarios["weighted_fair_value"]

    upside_pct = (fair_value / price - 1) * 100 if (fair_value is not None and price) else None

    own_pe = row.get("P/E (trailing)")
    sector = row.get("Secteur")
    # Toujours comparé au sein du même secteur, indépendamment du filtre "Filtrer sur un secteur"
    # de la table ci-dessus (comparer un P/E tech à un P/E utilities n'aurait pas de sens).
    peer_pes = [
        r["P/E (trailing)"] for r in grid_rows
        if r.get("Ticker") != ticker and r.get("Secteur") == sector
        and r.get("P/E (trailing)") and r["P/E (trailing)"] > 0
    ]
    comp_fair_value = None
    comp_hint = L(lang, "comp_insufficient_peers")
    if len(peer_pes) >= 3:
        peer_median_pe = float(np.median(peer_pes))
        comp_fair_value = compute_comparables_fair_value(price, own_pe, peer_median_pe)
        if comp_fair_value is not None:
            comp_hint = L(lang, "comp_hint", n=len(peer_pes), sector=sector, peer_pe=peer_median_pe, own_pe=own_pe)

    own_ev_ebitda = row.get("EV/EBITDA")
    peer_ev_ebitdas = [
        r["EV/EBITDA"] for r in grid_rows
        if r.get("Ticker") != ticker and r.get("Secteur") == sector
        and r.get("EV/EBITDA") and r["EV/EBITDA"] > 0
    ]
    comp_ev_fair_value = None
    comp_ev_hint = L(lang, "comp_ev_insufficient_peers")
    if len(peer_ev_ebitdas) >= 3:
        peer_median_ev_ebitda = float(np.median(peer_ev_ebitdas))
        comp_ev_fair_value = compute_comparables_ev_ebitda_fair_value(
            inputs.get("enterprise_value"), inputs.get("ev_to_ebitda"), peer_median_ev_ebitda,
            inputs["total_debt"], inputs["total_cash"], inputs["shares_outstanding"],
        )
        if comp_ev_fair_value is not None:
            comp_ev_hint = L(lang, "comp_ev_hint", n=len(peer_ev_ebitdas), sector=sector,
                              peer_ev_ebitda=peer_median_ev_ebitda, own_ev_ebitda=own_ev_ebitda)

    # Détail pédagogique du calcul (repliable) : montre le cheminement complet plutôt que le seul
    # résultat, pour que "pourquoi ce chiffre ?" se réponde en dépliant au lieu de devoir redemander.
    detail_children = []
    if fair_value is not None:
        detail_children.append(html.H6("DCF", className="mt-1"))
        if inputs["fcf_history"]:
            detail_children.append(html.P(
                L(lang, "dcf_detail_starting_fcf", fcf=_format_dcf_amount(inputs["fcf"], currency, lang)),
                className="mb-1",
            ))
            history_rows = [
                html.Tr([
                    html.Td(str(rec["year"])),
                    html.Td(_format_dcf_amount(rec["operating_cash_flow"], currency, lang)
                            if rec["operating_cash_flow"] is not None else "N/A"),
                    html.Td(_format_dcf_amount(rec["capex"], currency, lang)
                            if rec["capex"] is not None else "N/A"),
                    html.Td(_format_dcf_amount(rec["fcf"], currency, lang)),
                ])
                for rec in inputs["fcf_history"]
            ]
            detail_children.append(dbc.Table([
                html.Thead(html.Tr([
                    html.Th(L(lang, "dcf_detail_table_year")),
                    html.Th(L(lang, "dcf_detail_table_ocf")),
                    html.Th(L(lang, "dcf_detail_table_capex")),
                    html.Th("FCF"),
                ])),
                html.Tbody(history_rows),
            ], bordered=False, striped=True, size="sm", className="mb-2"))
        else:
            detail_children.append(html.P(
                L(lang, "dcf_detail_starting_fcf_ttm", fcf=_format_dcf_amount(inputs["fcf"], currency, lang)),
                className="mb-2",
            ))
        year_rows = [
            html.Tr([html.Td(str(year)), html.Td(_format_dcf_amount(fcf_y, currency, lang)),
                     html.Td(_format_dcf_amount(pv_y, currency, lang))])
            for year, fcf_y, pv_y in zip(
                range(1, int(horizon_years) + 1), result["projected_fcf"], result["pv_flows"],
            )
        ]
        detail_children.append(dbc.Table([
            html.Thead(html.Tr([
                html.Th(L(lang, "dcf_detail_table_year")),
                html.Th(L(lang, "dcf_detail_table_fcf")),
                html.Th(L(lang, "dcf_detail_table_pv")),
            ])),
            html.Tbody(year_rows),
        ], bordered=False, striped=True, size="sm", className="mb-2"))
        detail_children.append(html.P(
            L(lang, "dcf_detail_terminal", n=int(horizon_years),
              terminal_value=_format_dcf_amount(result["terminal_value"], currency, lang),
              pv_terminal_value=_format_dcf_amount(result["pv_terminal_value"], currency, lang)),
            className="mb-1",
        ))
        detail_children.append(html.P(
            L(lang, "dcf_detail_ev", enterprise_value=_format_dcf_amount(result["enterprise_value"], currency, lang)),
            className="mb-1",
        ))
        detail_children.append(html.P(
            L(lang, "dcf_detail_net_debt", net_debt=_format_dcf_amount(net_debt, currency, lang)),
            className="mb-1",
        ))
        detail_children.append(html.P(
            L(lang, "dcf_detail_equity", equity_value=_format_dcf_amount(result["equity_value"], currency, lang)),
            className="mb-1",
        ))
        detail_children.append(html.P(
            L(lang, "dcf_detail_per_share", shares=_format_abbreviated(inputs["shares_outstanding"], lang),
              fair_value=f"{num(fair_value, ',.2f', lang)} {currency}"),
            className="mb-2",
        ))
    if comp_fair_value is not None:
        detail_children.append(html.H6("Comparables (P/E)", className="mt-2"))
        detail_children.append(html.P(
            L(lang, "comp_detail_formula", n=len(peer_pes),
              price=f"{num(price, ',.2f', lang)} {currency}",
              peer_pe=f"{num(peer_median_pe, '.1f', lang)}x", own_pe=f"{num(own_pe, '.1f', lang)}x",
              comp_fair_value=f"{num(comp_fair_value, ',.2f', lang)} {currency}"),
            className="mb-0",
        ))
    if comp_ev_fair_value is not None:
        detail_children.append(html.H6("Comparables (EV/EBITDA)", className="mt-2"))
        detail_children.append(html.P(
            L(lang, "comp_ev_detail_formula", n=len(peer_ev_ebitdas),
              peer_ev_ebitda=f"{num(peer_median_ev_ebitda, '.1f', lang)}x", own_ev_ebitda=f"{num(own_ev_ebitda, '.1f', lang)}x",
              comp_ev_fair_value=f"{num(comp_ev_fair_value, ',.2f', lang)} {currency}"),
            className="mb-0",
        ))

    stat_cols = []
    if fair_value is not None:
        stat_cols.append(dbc.Col([
            html.Small(L(lang, "dcf_fair_value_label"), className="text-muted d-block"),
            html.H5(f"{num(fair_value, ',.2f', lang)} {currency}"),
        ]))
    if bear_fv is not None:
        stat_cols.append(dbc.Col([
            html.Small(L(lang, "dcf_bear_fair_value_label"), className="text-muted d-block"),
            html.H5(f"{num(bear_fv, ',.2f', lang)} {currency}"),
        ]))
    if bull_fv is not None:
        stat_cols.append(dbc.Col([
            html.Small(L(lang, "dcf_bull_fair_value_label"), className="text-muted d-block"),
            html.H5(f"{num(bull_fv, ',.2f', lang)} {currency}"),
        ]))
    if weighted_fv is not None:
        stat_cols.append(dbc.Col([
            html.Small(L(lang, "dcf_weighted_fair_value_label"), className="text-muted d-block"),
            html.H5(f"{num(weighted_fv, ',.2f', lang)} {currency}"),
        ]))
    if comp_fair_value is not None:
        stat_cols.append(dbc.Col([
            html.Small(L(lang, "comp_fair_value_label"), className="text-muted d-block"),
            html.H5(f"{num(comp_fair_value, ',.2f', lang)} {currency}"),
        ]))
    if comp_ev_fair_value is not None:
        stat_cols.append(dbc.Col([
            html.Small(L(lang, "comp_ev_fair_value_label"), className="text-muted d-block"),
            html.H5(f"{num(comp_ev_fair_value, ',.2f', lang)} {currency}"),
        ]))
    stat_cols.append(
        dbc.Col([html.Small(L(lang, "dcf_current_price_label"), className="text-muted d-block"),
                 html.H5(f"{num(price, ',.2f', lang)} {currency}" if price else "N/A")]),
    )
    if upside_pct is not None:
        stat_cols.append(dbc.Col([
            html.Small(L(lang, "dcf_upside_label"), className="text-muted d-block"),
            html.H5(f"{num(upside_pct, '+.1f', lang)} %", className="text-success" if upside_pct >= 0 else "text-danger"),
        ]))
    card_children = [html.H6(name, className="card-subtitle text-muted mb-2")]
    if dcf_blocked_msg:
        card_children.append(dbc.Alert(dcf_blocked_msg, color="warning", className="py-2 mb-2"))
    card_children.append(dbc.Row(stat_cols))
    card_children.append(html.Small(comp_hint, className="text-muted d-block mt-2"))
    card_children.append(html.Small(comp_ev_hint, className="text-muted d-block"))
    if detail_children:
        card_children.append(html.Details([
            html.Summary(L(lang, "dcf_detail_summary"), className="text-muted mt-2",
                         style={"cursor": "pointer", "fontSize": "0.85rem"}),
            html.Div(detail_children, className="mt-2"),
        ]))
    if fair_value is not None:
        growth_values, discount_values, grid = compute_dcf_sensitivity_grid(
            inputs["fcf"], growth_pct, discount_pct, terminal_growth_pct, int(horizon_years),
            net_debt, inputs["shares_outstanding"],
        )
        half = len(growth_values) // 2
        header = html.Thead(html.Tr(
            [html.Th("")] + [html.Th(f"{num(d, '.1f', lang)}%") for d in discount_values]
        ))
        body_rows = []
        for i, g in enumerate(growth_values):
            cells = [html.Th(f"{num(g, '.1f', lang)}%")]
            for j, val in enumerate(grid[i]):
                text = f"{num(val, ',.2f', lang)} {currency}" if val is not None else "N/A"
                is_center = i == half and j == half
                cells.append(html.Td(text, className="fw-bold table-active" if is_center else None))
            body_rows.append(html.Tr(cells))
        card_children.append(html.Details([
            html.Summary(L(lang, "dcf_sensitivity_summary"), className="text-muted mt-2",
                         style={"cursor": "pointer", "fontSize": "0.85rem"}),
            html.Div(dbc.Table([header, html.Tbody(body_rows)], bordered=True, striped=False, size="sm", className="mt-2")),
        ]))
    card = dbc.Card(dbc.CardBody(card_children))

    # « Football field » : une fourchette par méthode, comparée au cours. Les comparables prennent les
    # multiples du 1er et du 3e quartile des pairs, la médiane en valeur centrale.
    estimates = {}
    if fair_value is not None:
        estimates["dcf_scenarios"] = ([bear_fv, bull_fv], fair_value)
        estimates["dcf_sensitivity"] = ([value for grid_row in grid for value in grid_row], fair_value)
    pe_quartiles = peer_quartile_multiples(peer_pes)
    if pe_quartiles:
        q1, median, q3 = (compute_comparables_fair_value(price, own_pe, m) for m in pe_quartiles)
        estimates["comparables_pe"] = ([q1, q3], median)
    ev_quartiles = peer_quartile_multiples(peer_ev_ebitdas)
    if ev_quartiles:
        q1, median, q3 = (compute_comparables_ev_ebitda_fair_value(
            inputs.get("enterprise_value"), inputs.get("ev_to_ebitda"), m, inputs["total_debt"],
            inputs["total_cash"], inputs["shares_outstanding"]) for m in ev_quartiles)
        estimates["comparables_ev_ebitda"] = ([q1, q3], median)
    ranges = football_field_ranges(estimates)
    if not ranges:
        return card, empty_figure_with_message(L(lang, "football_empty", name=name), dark=dark)
    surface = chart_theme.surface_color(dark)
    colors = {"dcf_scenarios": palette[0], "dcf_sensitivity": chart_theme.blend(palette[0], surface, 0.45),
              "comparables_pe": palette[1 % len(palette)], "comparables_ev_ebitda": palette[2 % len(palette)]}
    fig = make_football_field(
        ranges, {method: L(lang, f"football_{method}") for method in FOOTBALL_FIELD_METHODS}, colors, price,
        L(lang, "dcf_current_price_label"), L(lang, "dcf_chart_title", name=name),
        lambda value: f"{num(value, ',.2f', lang)} {currency}",
        (L(lang, "football_low"), L(lang, "football_mid"), L(lang, "football_high")), dark=dark,
        separators=L(lang, "plotly_separators"),
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
