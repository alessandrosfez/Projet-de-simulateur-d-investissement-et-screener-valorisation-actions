"""
Enregistrement de tous les callbacks Dash. Importer ce module (voir app.py)
suffit à les enregistrer sur l'instance `app` partagée (app_instance.py) : les
fonctions ci-dessous ne sont pas appelées directement ailleurs, sauf les
helpers réutilisés par layout.py lui-même.
"""
import concurrent.futures

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
from engine import compute_comparables_fair_value, compute_dcf_sensitivity_grid, compute_scenario_dcf_fair_values
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

    rows, failures = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        future_to_stock = {executor.submit(get_stock_valuation, ticker): (name, ticker) for name, ticker in tickers.items()}
        for future in concurrent.futures.as_completed(future_to_stock):
            name, ticker = future_to_stock[future]
            try:
                data = future.result()
            except Exception:
                failures.append(name)
                continue
            data["Entreprise"] = name
            data["Ticker"] = ticker
            rows.append(data)

    warning = ""
    if failures:
        warning = dbc.Alert(L(lang, "unavailable_tickers", names=", ".join(sorted(failures))), color="warning")
    if not rows:
        warning = dbc.Alert(L(lang, "no_data_fetched"), color="danger")
    return rows, warning


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
    Output("stocks-sector-bar", "figure"),
    Output("stocks-sector-box", "figure"),
    Output("stocks-top-cards", "children"),
    Output("stocks-pe-chart", "figure"),
    Output("stocks-table", "data"),
    Output("stocks-table", "columns"),
    Output("stocks-table", "style_header"),
    Output("stocks-table", "style_cell"),
    Output("stocks-table", "style_data"),
    Output("stocks-csv-store", "data"),
    Input("stocks-raw-store", "data"),
    Input("sector-filter", "value"),
    Input("lang-radio", "value"),
    Input("palette-dropdown", "value"),
    Input("dark-mode-switch", "value"),
)
def render_stock_views(rows, sector_value, lang, palette_code, dark_mode):
    lang = lang or "fr"
    palette = PALETTES.get(palette_code, PALETTE)
    dark = bool(dark_mode)
    style_header, style_cell, style_data = layout.table_style_overrides(dark)
    if not rows:
        placeholder = empty_figure_with_message(L(lang, "load_hint_placeholder"), dark=dark)
        return placeholder, placeholder, "", placeholder, [], [], style_header, style_cell, style_data, ""

    # Noms de colonnes internes gardés stables (français) : ce sont des clés de travail, pas du
    # texte affiché : seul le libellé de colonne du tableau final ("name") est traduit plus bas.
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "sector": "Secteur", "currency": "Devise", "price": "Prix",
        "trailing_pe": "P/E (trailing)", "forward_pe": "P/E (prévisionnel)",
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
            values = priced_all.loc[priced_all["Secteur"] == sector, "P/E (trailing)"]
            sector_box.add_trace(go.Box(y=values, name=sector, marker_color=palette[i % len(palette)]))
        sector_box.update_layout(
            template="plotly_dark" if dark else "plotly",
            title=L(lang, "sector_dist_pe_title"), showlegend=False, yaxis_title="P/E",
            margin=dict(t=60, b=100), xaxis=dict(tickangle=-45),
        )

    # --- Détail (cartes, graphique, tableau) : filtré sur le secteur choisi ---
    detail_df = df if sector_value == "all" else df[df["Secteur"] == sector_value]
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

    table_df = detail_df[[
        "Entreprise", "Ticker", "Secteur", "Devise", "Prix", "P/E (trailing)", "P/E (prévisionnel)",
        "P/B", "Rendement dividende (%)",
        "P/E moyen 5 ans (approx.)", "Position vs historique 5 ans (percentile)", "Capitalisation",
    ]].copy()
    table_df["Capitalisation"] = table_df["Capitalisation"].map(_format_market_cap)
    for col in ["Prix", "P/E (trailing)", "P/E (prévisionnel)", "P/B", "Rendement dividende (%)",
                "P/E moyen 5 ans (approx.)", "Position vs historique 5 ans (percentile)"]:
        table_df[col] = table_df[col].round(2)
    table_df = table_df.sort_values("P/E (trailing)")

    column_label_keys = {
        "Entreprise": "col_company", "Ticker": "col_ticker", "Secteur": "col_sector", "Devise": "col_currency",
        "Prix": "col_price", "P/E (trailing)": "col_pe_trailing", "P/E (prévisionnel)": "col_pe_forward",
        "P/B": "col_pb", "Rendement dividende (%)": "col_div_yield",
        "P/E moyen 5 ans (approx.)": "col_pe_5y_mean", "Position vs historique 5 ans (percentile)": "col_pe_5y_pct",
        "Capitalisation": "col_market_cap",
    }
    columns = [{"name": L(lang, column_label_keys.get(c, c)), "id": c} for c in table_df.columns]
    csv_data = table_df.to_csv(index=False)
    # NaN -> None : sinon un JSON NaN (invalide) part vers le DataTable et s'affiche mal.
    table_df = table_df.astype(object).where(pd.notnull(table_df), None)

    return (sector_bar, sector_box, cards_row, fig, table_df.to_dict("records"), columns,
            style_header, style_cell, style_data, csv_data)


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
