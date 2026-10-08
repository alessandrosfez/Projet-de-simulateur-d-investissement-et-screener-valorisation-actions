"""
Enregistrement de tous les callbacks Dash. Importer ce module (voir app.py)
suffit à les enregistrer sur l'instance `app` partagée (app_instance.py) : les
fonctions ci-dessous ne sont pas appelées directement ailleurs, sauf les
helpers réutilisés par layout.py lui-même.
"""
import concurrent.futures
import threading

import dash
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

import layout
from app_instance import app
from charts import empty_figure_with_message
from constants import UNIVERSE_TICKERS
from engine import (
    compute_comparables_fair_value, compute_dcf_sensitivity_grid, compute_scenario_dcf_fair_values,
    pe_signal_forward_returns, summarize_pe_signal_backtest,
)
from i18n import L, PALETTE, PALETTE_CODES, PALETTE_NAMES, PALETTES
from market_data import get_dcf_inputs, get_stock_pe_history, get_stock_quality_metrics, get_stock_valuation

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

def _format_market_cap(value):
    """Formate une capitalisation dans la devise locale de cotation (EUR, GBP ou USD selon le marché)."""
    if not value or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    for threshold, suffix in [(1e12, "T"), (1e9, "Md"), (1e6, "M")]:
        if value >= threshold:
            return f"{value / threshold:.1f} {suffix}"
    return f"{value:,.0f}".replace(",", " ")


def _format_abbreviated(value):
    """Nombre abrégé (M/Md), signe conservé, sans unité (à ajouter par l'appelant si besoin) :
    utilisé pour le détail du calcul DCF, où les montants (FCF, dette, valeur d'entreprise...)
    sont trop grands pour s'afficher lisiblement en entier."""
    sign = "-" if value < 0 else ""
    abs_value = abs(value)
    for threshold, suffix in [(1e9, "Md"), (1e6, "M")]:
        if abs_value >= threshold:
            return f"{sign}{abs_value / threshold:.2f} {suffix}"
    return f"{sign}{abs_value:,.0f}".replace(",", " ")


def _format_dcf_amount(value, currency):
    return f"{_format_abbreviated(value)} {currency}"


# État de progression du chargement en cours, partagé entre load_stock_valuations (qui l'écrit,
# sur le thread du serveur de dev qui traite la requête "Charger" — threaded=True dans app.py,
# voir ce fichier) et update_load_progress ci-dessous (qui le lit, sur un thread différent à
# chaque tic de dcc.Interval). total=0 veut dire "rien en cours" : c'est ce que lit l'intervalle
# la plupart du temps, pas de round-trip Dash coûteux pour autant (juste une lecture de dict sous
# verrou). Alternative à un vrai callback "background" de Dash (qui aurait demandé une nouvelle
# dépendance, diskcache, pour un gain purement cosmétique ici).
_load_progress_lock = threading.Lock()
_load_progress = {"done": 0, "total": 0}


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
            future_to_stock = {executor.submit(get_stock_valuation, ticker): (name, ticker) for name, ticker in tickers.items()}
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
                html.H5(f"{stats['mean']:+.1%}", className=f"text-{color} mb-1"),
                html.Small(
                    L(lang, "pe_backtest_stats_caption", median=f"{stats['median']:+.1%}", n=stats["n"]),
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
    Output("stocks-table", "style_data_conditional"),
    Output("stocks-table", "tooltip_header"),
    Output("stocks-csv-store", "data"),
    Output("stocks-results-container", "style"),
    Input("stocks-raw-store", "data"),
    Input("sector-filter", "value"),
    Input("filter-pe-max", "value"),
    Input("filter-peg-max", "value"),
    Input("filter-div-min", "value"),
    Input("watchlist-dropdown", "value"),
    Input("watchlist-only-switch", "value"),
    Input("lang-radio", "value"),
    Input("palette-dropdown", "value"),
    Input("dark-mode-switch", "value"),
)
def render_stock_views(rows, sector_value, pe_max, peg_max, div_min, watchlist_tickers, watchlist_only,
                        lang, palette_code, dark_mode):
    lang = lang or "fr"
    palette = PALETTES.get(palette_code, PALETTE)
    dark = bool(dark_mode)
    style_header, style_cell, style_data = layout.table_style_overrides(dark)
    conditional_style = layout.peg_conditional_style(dark) + layout.pe_history_conditional_style(dark)
    column_label_keys = {
        "Entreprise": "col_company", "Ticker": "col_ticker", "Secteur": "col_sector", "Devise": "col_currency",
        "Prix": "col_price", "P/E (trailing)": "col_pe_trailing", "P/E (prévisionnel)": "col_pe_forward",
        "PEG": "col_peg", "EV/EBITDA": "col_ev_ebitda", "P/B": "col_pb", "Rendement dividende (%)": "col_div_yield",
        "P/E moyen 5 ans (approx.)": "col_pe_5y_mean", "Position vs historique 5 ans (percentile)": "col_pe_5y_pct",
        "Capitalisation": "col_market_cap",
    }
    # tooltip_header est indexé par id de colonne (le nom technique interne, pas le libellé
    # affiché) : survol d'un en-tête -> définition/formule. Seules les colonnes avec une clé
    # "..._help" dans i18n.py en ont un (L() retombe sur la clé elle-même si absente, d'où le
    # test d'égalité pour ne garder que les traductions qui existent vraiment). Construit ici
    # (dépend seulement de lang, pas des données chargées) pour être disponible même dans la
    # branche "rien à afficher" juste en dessous.
    tooltip_header = {}
    for c, label_key in column_label_keys.items():
        help_key = f"{label_key}_help"
        help_text = L(lang, help_key)
        if help_text != help_key:
            tooltip_header[c] = {"type": "text", "value": help_text}
    if not rows:
        placeholder = empty_figure_with_message(L(lang, "load_hint_placeholder"), dark=dark)
        return (placeholder, placeholder, "", placeholder, [], [], style_header, style_cell, style_data, conditional_style,
                tooltip_header, "", {"display": "none"})

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
            sector_rows = priced_all.loc[priced_all["Secteur"] == sector]
            # hoveron="points" (pas "boxes"/"boxes+points") : le survol de la boîte elle-même
            # déclenche sinon un groupe de 7 bulles Plotly natives (une par statistique : min, q1,
            # médiane, q3, max, "lower/upper fence"), DONT LE TEXTE N'EST PAS personnalisable via
            # hovertemplate (vérifié en pratique : le hovertemplate ci-dessous est ignoré tant que
            # "boxes" fait partie de hoveron, Plotly réaffiche son propre jargon statistique quoi
            # qu'il arrive). En ne laissant réagir que les points individuels (une entreprise par
            # point, boxpoints="all" pour tous les afficher, pas seulement les valeurs aberrantes),
            # chaque survol redevient une seule bulle "Entreprise : P/E X" — la boîte reste visible
            # comme repère visuel (quartiles), juste plus interactive pour son propre résumé.
            sector_box.add_trace(go.Box(
                y=sector_rows["P/E (trailing)"], name=sector, marker_color=palette[i % len(palette)],
                boxpoints="all", pointpos=0, jitter=0.4,
                hoveron="points",
                text=sector_rows["Entreprise"],
                hovertemplate="<b>%{text}</b><br>P/E : %{y:.1f}<extra></extra>",
            ))
        sector_box.update_layout(
            template="plotly_dark" if dark else "plotly",
            title=L(lang, "sector_dist_pe_title"), showlegend=False, yaxis_title="P/E",
            # Échelle log : un seul P/E extrême (voir ci-dessus) écrase sinon visuellement toutes
            # les autres boîtes près de zéro, rendant leur survol imprécis (cible de quelques
            # pixels). Toutes les valeurs comparées ici sont > 0 (filtré dans priced_all),
            # condition nécessaire pour un axe log.
            yaxis_type="log",
            margin=dict(t=60, b=100), xaxis=dict(tickangle=-45),
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

    # reindex plutôt qu'un simple df[[...]] : tolère une colonne absente (ex. cache disque écrit
    # par une version antérieure du code, avant l'ajout d'un champ) en la remplissant de NaN plutôt
    # que de lever une KeyError.
    table_df = detail_df.reindex(columns=[
        "Entreprise", "Ticker", "Secteur", "Devise", "Prix", "P/E (trailing)", "P/E (prévisionnel)",
        "PEG", "EV/EBITDA", "P/B", "Rendement dividende (%)",
        "P/E moyen 5 ans (approx.)", "Position vs historique 5 ans (percentile)", "Capitalisation",
    ]).copy()
    table_df["Capitalisation"] = table_df["Capitalisation"].map(_format_market_cap)
    for col in ["Prix", "P/E (trailing)", "P/E (prévisionnel)", "PEG", "EV/EBITDA", "P/B", "Rendement dividende (%)",
                "P/E moyen 5 ans (approx.)", "Position vs historique 5 ans (percentile)"]:
        table_df[col] = table_df[col].round(2)
    table_df = table_df.sort_values("P/E (trailing)")

    columns = [{"name": L(lang, column_label_keys.get(c, c)), "id": c} for c in table_df.columns]
    csv_data = table_df.to_csv(index=False)
    # Colonne technique, absente de `columns` donc jamais affichée, mais présente dans `data` :
    # dash_table l'utilise quand même pour évaluer le filter_query de pe_history_conditional_style.
    # Nécessaire parce que ce filter_query ne peut pas tester directement "valeur manquante" (voir
    # layout.pe_history_conditional_style) : un NaN substitué par 50 (ni < 20 ni > 80) retombe
    # naturellement dans la zone neutre non coloriée, sans fausse coloration verte/rouge.
    table_df["_pe_pct_for_style"] = table_df["Position vs historique 5 ans (percentile)"].fillna(50)
    # NaN -> None : sinon un JSON NaN (invalide) part vers le DataTable et s'affiche mal.
    table_df = table_df.astype(object).where(pd.notnull(table_df), None)

    return (sector_bar, sector_box, cards_row, fig, table_df.to_dict("records"), columns,
            style_header, style_cell, style_data, conditional_style, tooltip_header, csv_data,
            {"display": "block"})


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
    Input("stocks-table", "derived_virtual_selected_rows"),
    Input("lang-radio", "value"),
    State("stocks-table", "derived_virtual_data"),
)
def update_quality_metrics(selected_rows, lang, virtual_data):
    lang = lang or "fr"
    if not selected_rows or not virtual_data:
        return html.Div(L(lang, "quality_hint_default"), className="text-muted")

    row = virtual_data[selected_rows[0]]
    ticker = row["Ticker"]
    m = get_stock_quality_metrics(ticker)

    def stat(label_key, value, suffix=""):
        text = f"{value:.1f}{suffix}" if value is not None else "N/A"
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
    Output("dcf-result", "children"),
    Output("dcf-chart", "figure"),
    Input("stocks-table", "derived_virtual_selected_rows"),
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
    State("stocks-table", "derived_virtual_data"),
)
def update_dcf(selected_rows, growth_pct, discount_pct, terminal_growth_pct, horizon_years,
                growth_offset_pct, discount_offset_pct, weight_bear, weight_base, weight_bull,
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
        r["P/E (trailing)"] for r in virtual_data
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

    # Détail pédagogique du calcul (repliable) : montre le cheminement complet plutôt que le seul
    # résultat, pour que "pourquoi ce chiffre ?" se réponde en dépliant au lieu de devoir redemander.
    detail_children = []
    if fair_value is not None:
        detail_children.append(html.H6("DCF", className="mt-1"))
        if inputs["fcf_history"]:
            detail_children.append(html.P(
                L(lang, "dcf_detail_starting_fcf", fcf=_format_dcf_amount(inputs["fcf"], currency)),
                className="mb-1",
            ))
            history_rows = [
                html.Tr([
                    html.Td(str(rec["year"])),
                    html.Td(_format_dcf_amount(rec["operating_cash_flow"], currency)
                            if rec["operating_cash_flow"] is not None else "N/A"),
                    html.Td(_format_dcf_amount(rec["capex"], currency)
                            if rec["capex"] is not None else "N/A"),
                    html.Td(_format_dcf_amount(rec["fcf"], currency)),
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
                L(lang, "dcf_detail_starting_fcf_ttm", fcf=_format_dcf_amount(inputs["fcf"], currency)),
                className="mb-2",
            ))
        year_rows = [
            html.Tr([html.Td(str(year)), html.Td(_format_dcf_amount(fcf_y, currency)),
                     html.Td(_format_dcf_amount(pv_y, currency))])
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
              terminal_value=_format_dcf_amount(result["terminal_value"], currency),
              pv_terminal_value=_format_dcf_amount(result["pv_terminal_value"], currency)),
            className="mb-1",
        ))
        detail_children.append(html.P(
            L(lang, "dcf_detail_ev", enterprise_value=_format_dcf_amount(result["enterprise_value"], currency)),
            className="mb-1",
        ))
        detail_children.append(html.P(
            L(lang, "dcf_detail_net_debt", net_debt=_format_dcf_amount(net_debt, currency)),
            className="mb-1",
        ))
        detail_children.append(html.P(
            L(lang, "dcf_detail_equity", equity_value=_format_dcf_amount(result["equity_value"], currency)),
            className="mb-1",
        ))
        detail_children.append(html.P(
            L(lang, "dcf_detail_per_share", shares=_format_abbreviated(inputs["shares_outstanding"]),
              fair_value=f"{fair_value:,.2f} {currency}".replace(",", " ")),
            className="mb-2",
        ))
    if comp_fair_value is not None:
        detail_children.append(html.H6("Comparables", className="mt-2"))
        detail_children.append(html.P(
            L(lang, "comp_detail_formula", n=len(peer_pes),
              price=f"{price:,.2f} {currency}".replace(",", " "),
              peer_pe=f"{peer_median_pe:.1f}x", own_pe=f"{own_pe:.1f}x",
              comp_fair_value=f"{comp_fair_value:,.2f} {currency}".replace(",", " ")),
            className="mb-0",
        ))

    stat_cols = []
    if fair_value is not None:
        stat_cols.append(dbc.Col([
            html.Small(L(lang, "dcf_fair_value_label"), className="text-muted d-block"),
            html.H5(f"{fair_value:,.2f} {currency}".replace(",", " ")),
        ]))
    if bear_fv is not None:
        stat_cols.append(dbc.Col([
            html.Small(L(lang, "dcf_bear_fair_value_label"), className="text-muted d-block"),
            html.H5(f"{bear_fv:,.2f} {currency}".replace(",", " ")),
        ]))
    if bull_fv is not None:
        stat_cols.append(dbc.Col([
            html.Small(L(lang, "dcf_bull_fair_value_label"), className="text-muted d-block"),
            html.H5(f"{bull_fv:,.2f} {currency}".replace(",", " ")),
        ]))
    if weighted_fv is not None:
        stat_cols.append(dbc.Col([
            html.Small(L(lang, "dcf_weighted_fair_value_label"), className="text-muted d-block"),
            html.H5(f"{weighted_fv:,.2f} {currency}".replace(",", " ")),
        ]))
    if comp_fair_value is not None:
        stat_cols.append(dbc.Col([
            html.Small(L(lang, "comp_fair_value_label"), className="text-muted d-block"),
            html.H5(f"{comp_fair_value:,.2f} {currency}".replace(",", " ")),
        ]))
    stat_cols.append(
        dbc.Col([html.Small(L(lang, "dcf_current_price_label"), className="text-muted d-block"),
                 html.H5(f"{price:,.2f} {currency}".replace(",", " ") if price else "N/A")]),
    )
    if upside_pct is not None:
        stat_cols.append(dbc.Col([
            html.Small(L(lang, "dcf_upside_label"), className="text-muted d-block"),
            html.H5(f"{upside_pct:+.1f} %", className="text-success" if upside_pct >= 0 else "text-danger"),
        ]))
    card_children = [html.H6(name, className="card-subtitle text-muted mb-2")]
    if dcf_blocked_msg:
        card_children.append(dbc.Alert(dcf_blocked_msg, color="warning", className="py-2 mb-2"))
    card_children.append(dbc.Row(stat_cols))
    card_children.append(html.Small(comp_hint, className="text-muted d-block mt-2"))
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
            [html.Th("")] + [html.Th(f"{d:.1f}%") for d in discount_values]
        ))
        body_rows = []
        for i, g in enumerate(growth_values):
            cells = [html.Th(f"{g:.1f}%")]
            for j, val in enumerate(grid[i]):
                text = f"{val:,.2f} {currency}".replace(",", " ") if val is not None else "N/A"
                is_center = i == half and j == half
                cells.append(html.Td(text, className="fw-bold table-active" if is_center else None))
            body_rows.append(html.Tr(cells))
        card_children.append(html.Details([
            html.Summary(L(lang, "dcf_sensitivity_summary"), className="text-muted mt-2",
                         style={"cursor": "pointer", "fontSize": "0.85rem"}),
            html.Div(dbc.Table([header, html.Tbody(body_rows)], bordered=True, striped=False, size="sm", className="mt-2")),
        ]))
    card = dbc.Card(dbc.CardBody(card_children))

    bar_labels, bar_values, bar_colors = [], [], []
    if fair_value is not None:
        bar_labels.append(L(lang, "dcf_fair_value_label"))
        bar_values.append(fair_value)
        bar_colors.append(palette[0])
    if bear_fv is not None:
        bar_labels.append(L(lang, "dcf_bear_fair_value_label"))
        bar_values.append(bear_fv)
        bar_colors.append(palette[3 % len(palette)])
    if bull_fv is not None:
        bar_labels.append(L(lang, "dcf_bull_fair_value_label"))
        bar_values.append(bull_fv)
        bar_colors.append(palette[4 % len(palette)])
    if weighted_fv is not None:
        bar_labels.append(L(lang, "dcf_weighted_fair_value_label"))
        bar_values.append(weighted_fv)
        bar_colors.append(palette[5 % len(palette)])
    if comp_fair_value is not None:
        bar_labels.append(L(lang, "comp_fair_value_label"))
        bar_values.append(comp_fair_value)
        bar_colors.append(palette[2 % len(palette)])
    bar_labels.append(L(lang, "dcf_current_price_label"))
    bar_values.append(price or 0)
    bar_colors.append(palette[1 % len(palette)])

    fig = go.Figure()
    fig.add_trace(go.Bar(x=bar_labels, y=bar_values, marker_color=bar_colors))
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
