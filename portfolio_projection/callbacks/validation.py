"""
Callbacks de l'onglet « Validation du modèle » : backtest walk-forward lancé par bouton
(voir engine.walk_forward_calibration).
"""

import plotly.graph_objects as go
from dash import Input, Output, State, html

from app_instance import app
from charts import make_pit_histogram
from constants import TICKERS
from engine import (
    summarize_calibration, walk_forward_calibration,
)
import chart_theme
from i18n import L, PALETTE
from market_data import (
    get_monthly_returns,
)


# ============================================================
# CALLBACKS : onglet 4 (validation du modèle, backtest walk-forward)
# ============================================================
# Un seul n_sims par origine, modeste (300) et non réglable par l'utilisateur : situer un point
# réel dans une distribution simulée n'a pas besoin de la précision fine utilisée ailleurs pour
# afficher des bandes de percentiles, et ce nombre est multiplié par chaque date d'origine testée
# (des dizaines à des centaines) -- un curseur exposé inviterait à le monter sans que ça change le
# diagnostic, au prix d'un calcul bien plus lent.
VALIDATION_N_SIMS = 300
VALIDATION_SEED = 42
VALIDATION_MIN_CALIBRATION_MONTHS = 24
# Historique propre au test, indépendant du curseur lookback-slider (plafonné à 30 ans) : le nombre
# de dates d'origine testables, donc la valeur du diagnostic, croît directement avec la longueur
# de l'historique -- yfinance renvoie simplement tout ce qui existe s'il y en a moins.
VALIDATION_LOOKBACK_YEARS = 50


@app.callback(
    Output("validation-pit-graph-normal", "figure"),
    Output("validation-pit-graph-bootstrap", "figure"),
    Output("validation-coverage-table", "data"),
    Output("validation-coverage-table", "columns"),
    Output("validation-info-caption", "children"),
    Output("validation-error", "children"),
    Input("validation-run-btn", "n_clicks"),
    State("validation-ticker-dropdown", "value"),
    State("validation-source-radio", "value"),
    State("validation-horizon-radio", "value"),
    State("validation-step-radio", "value"),
    State("lang-radio", "value"),
    State("dark-mode-switch", "value"),
    prevent_initial_call=True,
)
def run_model_validation(n_clicks, index_name, source, horizon_months, step_months, lang, dark_mode):
    lang = lang or "fr"
    dark = bool(dark_mode)
    empty_fig = go.Figure()
    empty_fig.update_layout(template=chart_theme.template(dark))

    ticker = TICKERS[index_name][source or "indice"]
    try:
        returns_hist = get_monthly_returns(ticker, VALIDATION_LOOKBACK_YEARS)
    except Exception:
        return empty_fig, empty_fig, [], [], "", L(lang, "validation_insufficient_history")

    results_by_method = {}
    for method in ("normal", "bootstrap"):
        results_by_method[method] = walk_forward_calibration(
            returns_hist, horizon_months, VALIDATION_N_SIMS, VALIDATION_SEED, method,
            step_months=step_months or 12, min_calibration_months=VALIDATION_MIN_CALIBRATION_MONTHS,
        )

    n_origins = results_by_method["normal"]["n_origins"]
    if n_origins == 0:
        return empty_fig, empty_fig, [], [], "", L(lang, "validation_insufficient_history")

    pit_normal = results_by_method["normal"]["pit"]
    pit_bootstrap = results_by_method["bootstrap"]["pit"]
    fig_normal = make_pit_histogram(
        pit_normal, L(lang, "pit_histogram_title_normal"), lang=lang, palette=PALETTE, dark=dark,
    )
    fig_bootstrap = make_pit_histogram(
        pit_bootstrap, L(lang, "pit_histogram_title_bootstrap"), lang=lang, palette=PALETTE, dark=dark,
    )

    bands = ((5, 95), (25, 75))
    summary_normal = {row["lower_pct"]: row for row in summarize_calibration(pit_normal, bands=bands)}
    summary_bootstrap = {row["lower_pct"]: row for row in summarize_calibration(pit_bootstrap, bands=bands)}
    col_band = L(lang, "validation_col_band")
    col_nominal = L(lang, "validation_col_nominal")
    col_normal = L(lang, "validation_col_observed_normal")
    col_bootstrap = L(lang, "validation_col_observed_bootstrap")
    table_data = [
        {
            col_band: f"{lo}-{hi} %",
            col_nominal: summary_normal[lo]["nominal_pct"],
            col_normal: summary_normal[lo]["observed_pct"],
            col_bootstrap: summary_bootstrap[lo]["observed_pct"],
        }
        for lo, hi in bands
    ]
    table_columns = [{"name": c, "id": c} for c in [col_band, col_nominal, col_normal, col_bootstrap]]

    n_effective = results_by_method["normal"]["n_effective"]
    info_caption = html.Div([
        html.Div(L(lang, "validation_n_origins_label", n=n_origins)),
        html.Div(L(lang, "validation_n_effective_label", n=n_effective)),
        html.Div(L(lang, "validation_overlap_warning"), className="fst-italic mt-1"),
    ])

    return fig_normal, fig_bootstrap, table_data, table_columns, info_caption, ""
