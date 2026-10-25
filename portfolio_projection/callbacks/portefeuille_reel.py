"""
Callbacks de l'onglet « Mon portefeuille réel » : seul endroit de l'appli où des callbacks
écrivent en base (voir le commentaire de section ci-dessous), plus le rendu des totaux, de
la performance réelle, des jalons PEA, des projections et du rééquilibrage.
"""
import base64
import io
import time

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

import layout
import portfolio_db
import portfolio_engine
from app_instance import app
from charts import (
    make_allocation_sunburst, make_contribution_plan_figure, make_correlation_heatmap, make_dividend_calendar_figure,
    make_line_contributions_figure,
    make_target_vs_actual_rings,
)
from constants import PEA_TAX_RATE, STOCK_INDEX_KEY, UNDERLYING_INDICES, UNKNOWN_INDEX_KEY
from engine import (
    simulate_portfolio_asset_returns,
)
import chart_theme
from i18n import L
from market_data import (
    get_aligned_returns_for_tickers, get_current_price, get_dividends_per_share_eur, get_instrument_profile,
    get_daily_price_history, get_daily_total_return_history, get_ticker_name, resolve_isin_to_ticker,
)
from results import (
    build_pea_milestone_cards, build_performance_cards, build_portfolio_totals_cards,
    build_real_portfolio_future_figure,
    build_rebalancing_table_data, build_real_vs_simulated_figure,
)


# ============================================================
# CALLBACKS :onglet 3 (portefeuille réel)
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


OTHER_SLICE_COLOR = "#9AA0A6"
# Au-delà, un anneau devient illisible : les plus petites parts sont regroupées en « Autres ».
MAX_DONUT_SLICES = 6
LEGEND_LABEL_MAX = 42


def _allocation_view(current_values: pd.Series, total: float, unpriced: list, index_of: dict, lang: str,
                     dark: bool):
    """Répartition actuelle : graphique soleil (indices au centre, lignes autour) et, à côté, le
    classement des lignes avec leur part en barre. Couleur par indice attribuée dans l'ordre
    alphabétique des indices affichés, pas selon leur rang : un indice qui grossit ne change pas de
    couleur ; ses lignes en prennent des nuances. Une ligne sans cours est signalée, jamais comptée 0."""
    empty_fig = go.Figure()
    empty_fig.update_layout(template=chart_theme.template(dark))
    notes = []
    if unpriced:
        notes.append(html.Div(L(lang, "allocation_unpriced", tickers=", ".join(unpriced))))
    exposure = portfolio_engine.exposure_by_index(current_values, index_of)
    if exposure.empty:
        return empty_fig, [], notes or L(lang, "allocation_no_data")
    palette = chart_theme.palette_for(None, dark)
    surface = chart_theme.surface_color(dark)
    shown = sorted(k for k in exposure["key"] if k != UNKNOWN_INDEX_KEY)
    index_color = {key: palette[i % len(palette)] for i, key in enumerate(shown)}
    index_color[UNKNOWN_INDEX_KEY] = OTHER_SLICE_COLOR
    total_text = f"{total:,.0f}".replace(",", " ")
    ids, labels, parents, values, colors, hover = (["root"], [L(lang, "allocation_center", total=total_text)], [""],
                                                   [float(exposure["value"].sum())], [surface], [L(lang, "allocation_total")])
    line_color = {}
    for _, group in exposure.iterrows():
        key, base = group["key"], index_color[group["key"]]
        ids.append(f"index:{key}"), labels.append(_index_label(key, lang)), parents.append("root")
        values.append(float(group["value"])), colors.append(base), hover.append(_index_label(key, lang))
        members = sorted(group["tickers"], key=lambda t: -float(current_values[t]))
        for rank, ticker in enumerate(members):
            # Nuances de la teinte de l'indice, de plus en plus proches du fond : lignes distinctes mais
            # visiblement de la même famille.
            shade = chart_theme.blend(base, surface, 0.18 + 0.22 * rank / max(len(members), 1))
            line_color[ticker] = shade
            ids.append(f"line:{ticker}"), labels.append(ticker.split(".")[0]), parents.append(f"index:{key}")
            values.append(float(current_values[ticker])), colors.append(shade), hover.append(_ticker_display_label(ticker))
    fig = make_allocation_sunburst(ids, labels, parents, values, colors, hover, L(lang, "allocation_chart_title"), "€",
                                   dark=dark, separators=L(lang, "plotly_separators"))
    return fig, _allocation_ranking(current_values, total, index_of, line_color, lang), notes


def _allocation_ranking(current_values: pd.Series, total: float, index_of: dict, line_color: dict, lang: str):
    """Classement des lignes, de la plus grosse à la plus petite : pastille de couleur (celle du
    graphique soleil), nom du fonds, indice suivi, part en barre et en %, montant. Remplace la légende,
    illisible dès que les noms de fonds sont longs."""
    values = current_values.dropna()
    values = values[values > 0].sort_values(ascending=False)
    largest = float(values.iloc[0]) if not values.empty else 1.0
    rows = []
    for ticker, value in values.items():
        share = float(value) / total if total else 0.0
        rows.append(html.Div([
            html.Div([
                html.Span(className="alloc-dot", style={"backgroundColor": line_color.get(ticker, OTHER_SLICE_COLOR)}),
                html.Span(_ticker_display_label(ticker), className="alloc-name"),
                html.Span(f"{share * 100:.1f} %".replace(".", "," if lang == "fr" else "."), className="alloc-share"),
            ], className="alloc-head"),
            html.Div(html.Div(className="alloc-bar-fill", style={"width": f"{float(value) / largest * 100:.1f}%",
                                                                  "backgroundColor": line_color.get(ticker, OTHER_SLICE_COLOR)}),
                     className="alloc-bar"),
            html.Small(f"{_index_label(index_of.get(ticker, UNKNOWN_INDEX_KEY), lang)} · "
                       f"{float(value):,.0f} €".replace(",", " "), className="alloc-sub"),
        ], className="alloc-row"))
    return html.Div(rows, className="alloc-ranking")


def _target_vs_actual_view(current_values: pd.Series, target_weights: pd.DataFrame, lang: str, dark: bool):
    """Anneaux cible (intérieur) / actuel (extérieur), seulement s'il y a des pondérations cibles et des
    lignes valorisées : sinon rien, le tableau de rééquilibrage affiche déjà la consigne."""
    shares = portfolio_engine.target_vs_actual_shares(current_values, target_weights, max_slices=MAX_DONUT_SLICES)
    if shares.empty:
        return None
    shown = sorted(k for k in shares["key"] if k != portfolio_engine.OTHER_ALLOCATION_KEY)
    color_of = {ticker: chart_theme.palette_for(None, dark)[i] for i, ticker in enumerate(shown)}
    labels, hover_names, colors = [], [], []
    for key in shares["key"]:
        if key == portfolio_engine.OTHER_ALLOCATION_KEY:
            labels.append(L(lang, "allocation_other"))
            hover_names.append(L(lang, "allocation_other"))
            colors.append(OTHER_SLICE_COLOR)
        else:
            full_name = _ticker_display_label(key)
            labels.append(full_name if len(full_name) <= LEGEND_LABEL_MAX else full_name[:LEGEND_LABEL_MAX - 1] + "…")
            hover_names.append(full_name)
            colors.append(color_of[key])
    fig = make_target_vs_actual_rings(
        labels, list(shares["actual"]), list(shares["target"]), hover_names, colors, L(lang, "target_chart_title"),
        L(lang, "target_ring_actual"), L(lang, "target_ring_target"), L(lang, "target_center"), dark=dark,
        separators=L(lang, "plotly_separators"),
    )
    return dcc.Graph(figure=fig, config=layout.GRAPH_CONFIG, className="mb-2")


def _index_label(key: str, lang: str) -> str:
    if key == STOCK_INDEX_KEY:
        return L(lang, "index_stock")
    if key == UNKNOWN_INDEX_KEY:
        return L(lang, "index_unknown")
    if key == portfolio_engine.OTHER_ALLOCATION_KEY:
        return L(lang, "allocation_other")
    return key


def _index_view(current_values: pd.Series, held_tickers: list, lang: str):
    """Indice suivi par chaque ligne (détecté automatiquement ou corrigé à la main), alertes pour chaque
    indice suivi par plusieurs lignes (doublon sans diversification) et tableau de correction.
    Renvoie aussi index_of, qui regroupe les lignes du graphique soleil."""
    dropdown = {"index_key": {"options": [{"label": _index_label(key, lang), "value": key}
                                          for key in (*UNDERLYING_INDICES, STOCK_INDEX_KEY, UNKNOWN_INDEX_KEY)]}}
    if not held_tickers:
        return [], [], dropdown, {}
    detected = {t: portfolio_engine.detect_underlying_index(t, **get_instrument_profile(t)) for t in held_tickers}
    overrides = portfolio_db.get_index_overrides()
    index_of = portfolio_engine.resolve_underlying_indices(detected, overrides)
    rows = [{"ticker": t, "label": _ticker_display_label(t), "index_key": index_of[t], "detected": detected[t],
             "source": L(lang, "index_source_override" if t in overrides else "index_source_auto")}
            for t in held_tickers]
    exposure = portfolio_engine.exposure_by_index(current_values, index_of)
    alerts = []
    for _, dup in portfolio_engine.duplicate_index_exposures(exposure).iterrows():
        share = f"{dup['share'] * 100:.0f}"
        names = list(dup["tickers"])
        tickers_text = f"{', '.join(names[:-1])} {L(lang, 'and_word')} {names[-1]}"
        alerts.append(dbc.Alert(L(lang, "index_duplicate_alert", tickers=tickers_text,
                                  index=_index_label(dup["key"], lang), share=share),
                                color="warning", className="py-2 mb-2"))
    if any(index_of[t] == UNKNOWN_INDEX_KEY for t in held_tickers):
        alerts.append(html.Small(L(lang, "index_unknown_hint"), className="text-muted d-block mb-2"))
    return alerts, rows, dropdown, index_of


@app.callback(
    Output("tab3-refresh-trigger", "data", allow_duplicate=True),
    Input("tab3-index-table", "data_timestamp"),
    State("tab3-index-table", "data"),
    prevent_initial_call=True,
)
def save_index_overrides(_timestamp, rows):
    """Correction de l'indice d'une ligne : stockée seulement si elle diffère de la détection
    automatique ; revenir à l'indice détecté supprime la correction."""
    overrides = portfolio_db.get_index_overrides()
    changed = False
    for row in rows or []:
        ticker, chosen, detected = row.get("ticker"), row.get("index_key"), row.get("detected")
        if not ticker or not chosen:
            continue
        wanted = None if chosen == detected else chosen
        if overrides.get(ticker) != wanted:
            portfolio_db.set_index_override(ticker, wanted)
            changed = True
    if not changed:
        raise dash.exceptions.PreventUpdate
    return time.time()


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
    Output("tab3-allocation-graph", "figure"),
    Output("tab3-allocation-note", "children"),
    Output("tab3-allocation-list", "children"),
    Output("tab3-index-alerts", "children"),
    Output("tab3-index-table", "data"),
    Output("tab3-index-table", "dropdown"),
    Output("tab3-index-table", "style_header"),
    Output("tab3-index-table", "style_cell"),
    Output("tab3-index-table", "style_data"),
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
    Output("tab3-target-container", "children"),
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
    real_series = portfolio_engine.reconstruct_equity_curve(transactions, price_histories)
    totals_cards = build_portfolio_totals_cards(totals, lang, real_series=real_series, dark=dark,
                                               palette=chart_theme.palette_for(None, dark))
    unpriced = [t for t in holdings["ticker"] if t not in current_values.index] if not holdings.empty else []
    if unpriced:
        # Sans cours, une ligne manque à la valeur actuelle mais pas au capital investi : la plus-value
        # affichée serait une fausse perte. Avertissement AU-DESSUS des totaux, pas en note de bas de graphique.
        totals_cards = html.Div([
            dbc.Alert(L(lang, "totals_partial_warning", tickers=", ".join(unpriced)), color="warning",
                      className="py-2 mb-2"),
            totals_cards,
        ])
    held_tickers = sorted(holdings["ticker"]) if not holdings.empty else []
    index_alerts, index_rows, index_dropdown, index_of = _index_view(current_values, held_tickers, lang)
    allocation_fig, allocation_list, allocation_note = _allocation_view(
        current_values, current_value_total, unpriced, index_of, lang, dark)


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
    empty_fig.update_layout(template=chart_theme.template(dark))
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
                    lower_pct=10, upper_pct=90, lang=lang, palette=chart_theme.palette_for(None, dark), dark=dark,
                )

                if not monthly_amounts.empty:
                    n_months = len(monthly_amounts)
                    asset_returns = simulate_portfolio_asset_returns(
                        aligned, n_months, n_sims or 500, seed or 42, method or "bootstrap",
                    )
                    portfolio_returns = asset_returns @ weights_vec
                    real_vs_sim_fig = build_real_vs_simulated_figure(
                        portfolio_returns, monthly_amounts.values, monthly_amounts.index, real_series,
                        annual_fee_pct=0.0, lower_pct=10, upper_pct=90, lang=lang, palette=chart_theme.palette_for(None, dark), dark=dark,
                        purchases=portfolio_engine.purchase_points(transactions, real_series),
                    )
        elif not real_series.empty:
            # Historique insuffisant pour aligner tous les tickers détenus (voir
            # get_aligned_returns_for_tickers) : on affiche quand même la courbe réelle seule,
            # plutôt que rien, la comparaison simulée n'étant qu'un complément.
            real_vs_sim_fig.add_trace(go.Scatter(
                x=real_series.index, y=real_series.values, mode="lines",
                name=L(lang, "real_equity_trace"), line=dict(color=chart_theme.palette_for(None, dark)[0], width=2),
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
        totals_cards, allocation_fig, allocation_note,
        allocation_list, index_alerts, index_rows, index_dropdown, *table_styles,
        real_pace_display, real_vs_sim_fig, projection_fig, corr_fig,
        rebalancing_data, rebalancing_columns, *table_styles, rebalancing_warning,
        _target_vs_actual_view(current_values, target_weights, lang, dark),
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
    Output("tab3-next-contribution-summary", "children"),
    Output("tab3-next-contribution-graph", "figure"),
    Input("tab3-refresh-trigger", "data"),
    Input("tab3-next-contribution-amount", "value"),
    Input("lang-radio", "value"),
    Input("dark-mode-switch", "value"),
    Input("palette-dropdown", "value"),
)
def plan_next_contribution(_trigger, amount, lang, dark_mode, palette_code):
    """Où placer le prochain versement pour se rapprocher des poids cibles sans vendre (voir
    portfolio_engine.allocate_contribution). Une ligne sans cours rend le plan indisponible : la
    compter pour 0 pousserait le versement vers elle à tort."""
    lang = lang or "fr"
    dark = bool(dark_mode)
    target_weights = portfolio_db.get_target_weights()
    # Figure réduite à rien quand il n'y a pas de plan : seul le message au-dessus compte, pas un
    # grand cadre vide.
    empty = go.Figure()
    empty.update_layout(template=chart_theme.template(dark), height=10, margin=dict(t=0, b=0, l=0, r=0),
                        xaxis=dict(visible=False), yaxis=dict(visible=False))
    if target_weights.empty:
        return html.Div(L(lang, "rebalancing_no_weights_hint"), className="text-muted"), empty
    if not amount or float(amount) <= 0:
        return html.Div(L(lang, "next_contribution_no_amount"), className="text-muted"), empty

    holdings = portfolio_engine.reconstruct_holdings(portfolio_db.get_transactions())
    current_values, unpriced = pd.Series(dtype=float), []
    for _, row in holdings.iterrows():
        price = get_current_price(row["ticker"])
        if price is None:
            unpriced.append(row["ticker"])
        else:
            current_values[row["ticker"]] = row["quantity"] * price
    if unpriced:
        return dbc.Alert(L(lang, "next_contribution_unpriced", tickers=", ".join(unpriced)), color="warning",
                         className="py-2"), empty

    amount = float(amount)
    lines, summary = portfolio_engine.allocate_contribution(target_weights, current_values, amount)
    lines = lines[(lines["target_pct"] > 0) | (lines["contribution_eur"] > 0)]
    def money(value):
        return f"{value:,.0f} €".replace(",", " ")

    summary_text = L(lang, "next_contribution_summary", amount=money(amount),
                     before=summary["deviation_before_pt"], after=summary["deviation_after_pt"])
    fig = make_contribution_plan_figure(
        [_ticker_display_label(t) for t in lines["ticker"]],
        lines["current_pct"].tolist(), lines["after_pct"].tolist(), lines["target_pct"].tolist(),
        [f"+{money(v)}" if v >= 0.5 else "" for v in lines["contribution_eur"]],
        (L(lang, "next_contribution_current"), L(lang, "next_contribution_after"), L(lang, "next_contribution_target")),
        L(lang, "next_contribution_title", amount=money(amount)),
        chart_theme.palette_for(palette_code, dark)[0], dark=dark, separators=L(lang, "plotly_separators"),
    )
    return html.Div(summary_text, className="kpi-sub mb-1"), fig


@app.callback(
    Output("tab3-line-contributions-graph", "figure"),
    Output("tab3-line-contributions-note", "children"),
    Input("tab3-refresh-trigger", "data"),
    Input("lang-radio", "value"),
    Input("dark-mode-switch", "value"),
)
def refresh_line_contributions(_trigger, lang, dark_mode):
    """Gain ou perte en euros de chaque ligne depuis son achat (portfolio_engine.line_contributions).
    Une ligne sans cours n'est pas tracée, elle est nommée dans la note, jamais comptée pour 0."""
    lang = lang or "fr"
    dark = bool(dark_mode)
    transactions = portfolio_db.get_transactions()
    if transactions.empty:
        empty = go.Figure()
        empty.update_layout(template=chart_theme.template(dark), height=10, margin=dict(t=0, b=0, l=0, r=0),
                            xaxis=dict(visible=False), yaxis=dict(visible=False))
        return empty, L(lang, "performance_no_data")
    holdings = portfolio_engine.reconstruct_holdings(transactions)
    current_values = pd.Series(dtype=float)
    for _, row in holdings.iterrows():
        price = get_current_price(row["ticker"])
        if price is not None:
            current_values[row["ticker"]] = row["quantity"] * price
    lines = portfolio_engine.line_contributions(transactions, portfolio_db.get_dividends(), current_values)
    priced = lines.dropna(subset=["gain_eur"])
    unpriced = lines.loc[lines["gain_eur"].isna(), "ticker"].tolist()

    def money(value):
        return f"{value:,.0f} €".replace(",", " ")

    labels = [_ticker_display_label(t) for t in priced["ticker"]]
    texts = [L(lang, "line_contribution_text", gain=g, pct=p * 100) for g, p in zip(priced["gain_eur"], priced["gain_pct"])]
    hovers = [
        L(lang, "line_contribution_hover", label=label, cost=money(r.cost_eur), value=money(r.value_eur),
          dividends=money(r.dividends_eur))
        for label, r in zip(labels, priced.itertuples())
    ]
    total = float(priced["gain_eur"].sum())
    fig = make_line_contributions_figure(
        labels, priced["gain_eur"].tolist(), texts, hovers,
        L(lang, "line_contributions_title", total=total), dark=dark, separators=L(lang, "plotly_separators"),
    )
    note = L(lang, "allocation_unpriced", tickers=", ".join(unpriced)) if unpriced else ""
    return fig, note


def _collapsed_figure(dark: bool):
    """Figure réduite à rien : quand il n'y a rien à tracer, seul le message au-dessus compte."""
    fig = go.Figure()
    fig.update_layout(template=chart_theme.template(dark), height=10, margin=dict(t=0, b=0, l=0, r=0),
                      xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


@app.callback(
    Output("tab3-dividend-summary", "children"),
    Output("tab3-dividend-calendar-graph", "figure"),
    Output("tab3-dividend-notes", "children"),
    Input("tab3-refresh-trigger", "data"),
    Input("lang-radio", "value"),
    Input("dark-mode-switch", "value"),
    Input("palette-dropdown", "value"),
)
def refresh_dividend_calendar(_trigger, lang, dark_mode, palette_code):
    """Dividendes perçus sur 12 mois et estimés sur les 12 prochains (portfolio_engine.dividend_calendar).
    Les lignes de capitalisation et celles dont Yahoo n'a pas répondu sont nommées à part : les
    premières ne versent rien par construction, les secondes ne sont pas estimées (jamais 0 €)."""
    lang = lang or "fr"
    dark = bool(dark_mode)
    transactions = portfolio_db.get_transactions()
    dividends = portfolio_db.get_dividends()
    holdings = portfolio_engine.reconstruct_holdings(transactions)
    per_share, unknown, accumulating = {}, [], []
    for ticker in holdings["ticker"] if not holdings.empty else []:
        series = get_dividends_per_share_eur(ticker)
        if series is None:
            unknown.append(ticker)
        else:
            per_share[ticker] = series
            if series.empty:
                accumulating.append(ticker)
    today = pd.Timestamp.today().normalize()
    calendar = portfolio_engine.dividend_calendar(dividends, per_share, holdings, today)

    notes = []
    if accumulating:
        notes.append(html.Div(L(lang, "dividends_accumulating", tickers=", ".join(accumulating))))
    if unknown:
        notes.append(html.Div(L(lang, "dividends_unknown", tickers=", ".join(unknown))))
    if calendar.empty:
        return html.Div(L(lang, "dividends_none"), className="text-muted mb-1"), _collapsed_figure(dark), notes

    received = float(calendar.loc[calendar["kind"] == "received", "amount_eur"].sum())
    estimated = float(calendar.loc[calendar["kind"] == "estimated", "amount_eur"].sum())
    summary = html.Div(L(lang, "dividends_summary", received=received, estimated=estimated), className="kpi-sub mb-1")
    tickers = sorted(set(holdings["ticker"]) | set(calendar["ticker"]))
    palette = chart_theme.palette_for(palette_code, dark)
    colors = {t: palette[i % len(palette)] for i, t in enumerate(tickers)}
    this_month = today.replace(day=1)
    fig = make_dividend_calendar_figure(
        calendar, this_month - pd.DateOffset(months=11), this_month, this_month + pd.DateOffset(months=12),
        {t: _ticker_display_label(t) for t in tickers}, colors,
        (L(lang, "dividends_received"), L(lang, "dividends_estimated")), L(lang, "dividends_chart_title"),
        L(lang, "dividends_today"), dark=dark, separators=L(lang, "plotly_separators"),
    )
    return summary, fig, notes


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
    cost = portfolio_engine.invested_cost(transactions)
    dividends_total = float(dividends["amount_eur"].sum()) if not dividends.empty else 0.0
    years = portfolio_engine.history_years(transactions, today)
    perf = {
        "xirr": portfolio_engine.xirr(
            portfolio_engine.portfolio_cash_flows(transactions, dividends, current_value_total, today)
        ),
        "twr": portfolio_engine.time_weighted_return(
            portfolio_engine.reconstruct_equity_curve(transactions, price_histories), transactions, dividends,
        ),
        "real_value": current_value_total,
        # Moins d'un an d'historique : gain de la période en valeur principale (voir
        # portfolio_engine.SHORT_HISTORY_YEARS), les taux annualisés passent en mention secondaire.
        "short_history": years is not None and years < portfolio_engine.SHORT_HISTORY_YEARS,
        "gain": portfolio_engine.period_gain(current_value_total, dividends_total, cost),
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
            perf["benchmark_gain"] = portfolio_engine.period_gain(benchmark_value, 0.0, cost)

    return html.Div([warning, build_performance_cards(perf, lang)] if warning else [build_performance_cards(perf, lang)])
