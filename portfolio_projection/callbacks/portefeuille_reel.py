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
from charts import make_allocation_donut, make_correlation_heatmap
from constants import PEA_TAX_RATE
from engine import (
    simulate_portfolio_asset_returns,
)
from i18n import L, PALETTE
from market_data import (
    get_aligned_returns_for_tickers, get_current_price,
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
LEGEND_LABEL_MAX = 42


def _allocation_view(current_values: pd.Series, total: float, unpriced: list, lang: str, dark: bool):
    """Anneau de la répartition actuelle (valeurs de marché en euros). Couleur attribuée dans l'ordre
    alphabétique des tickers affichés, pas selon leur rang : une ligne qui grossit ou maigrit ne
    change pas de couleur. Six couleurs dans la palette : au-delà de six lignes, les plus petites
    sont regroupées en « Autres » (gris)."""
    empty_fig = go.Figure()
    empty_fig.update_layout(template="plotly_dark" if dark else "plotly")
    notes = []
    if unpriced:
        notes.append(html.Div(L(lang, "allocation_unpriced", tickers=", ".join(unpriced))))
    slices = portfolio_engine.allocation_slices(current_values, max_slices=len(PALETTE))
    if slices.empty:
        return empty_fig, notes or L(lang, "allocation_no_data")
    # Ordre alphabétique des seules parts affichées : jamais deux parts visibles de même couleur.
    shown = sorted(k for k in slices["key"] if k != portfolio_engine.OTHER_ALLOCATION_KEY)
    color_of = {ticker: PALETTE[i] for i, ticker in enumerate(shown)}
    labels, hover_names, colors = [], [], []
    for key in slices["key"]:
        if key == portfolio_engine.OTHER_ALLOCATION_KEY:
            labels.append(L(lang, "allocation_other"))
            hover_names.append(L(lang, "allocation_other"))
            colors.append(OTHER_SLICE_COLOR)
        else:
            # Nom du fonds dans la légende : un ticker seul (« PAASI.PA ») ne dit pas ce qu'est la ligne.
            full_name = _ticker_display_label(key)
            labels.append(full_name if len(full_name) <= LEGEND_LABEL_MAX else full_name[:LEGEND_LABEL_MAX - 1] + "…")
            hover_names.append(full_name)
            colors.append(color_of[key])
    total_text = f"{total:,.0f}".replace(",", " ")
    fig = make_allocation_donut(
        labels, list(slices["value"]), hover_names, colors, L(lang, "allocation_chart_title"),
        L(lang, "allocation_center", total=total_text), "€", dark=dark, separators=L(lang, "plotly_separators"),
    )
    return fig, notes


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
    unpriced = [t for t in holdings["ticker"] if t not in current_values.index] if not holdings.empty else []
    allocation_fig, allocation_note = _allocation_view(current_values, current_value_total, unpriced, lang, dark)

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
        totals_cards, allocation_fig, allocation_note, real_pace_display, real_vs_sim_fig, projection_fig, corr_fig,
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
