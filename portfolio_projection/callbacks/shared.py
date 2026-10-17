"""
Callbacks communs à toute l'appli : affichage conditionnel de la sidebar, reconstruction
de l'interface au changement de langue, export/import de configuration JSON et badge de
fraîcheur des données de l'en-tête. Rien ici n'appartient à un onglet en particulier.
"""
import base64
import json
import time

import dash
import dash_bootstrap_components as dbc
import numpy as np
from dash import Input, Output, State, dcc

import layout
from app_instance import app
from constants import N_PORTFOLIOS_MAX, TICKER_KEYS
from i18n import L, PALETTE_CODES, PALETTE_NAMES
from market_data import (
    data_freshness, get_served_download_times,
)


# ============================================================
# CALLBACKS :affichage conditionnel
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
# CALLBACKS :configuration (export / import JSON)
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
# CALLBACKS : fraîcheur des données de marché (badge de l'en-tête)
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
