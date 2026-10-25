"""
Callbacks de l'onglet « Validation du modèle » : backtest walk-forward lancé par bouton
(voir engine.walk_forward_calibration).
"""

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, html

from app_instance import app
from charts import make_pit_histogram
from constants import TICKERS
from engine import (
    calibration_verdict, combine_calibration_verdicts, summarize_calibration, walk_forward_calibration,
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

# Icône et état visuel de chaque verdict (classes .verdict-tile de assets/theme.css) : l'icône et
# le libellé portent le sens, la couleur ne fait que le rappeler.
VERDICT_STYLES = {
    "calibrated": ("check-circle", "good"), "too_narrow": ("exclamation-triangle", "bad"),
    "too_wide": ("info-circle", "warn"), "inconclusive": ("hourglass-split", "neutral"),
}


def _verdict_tile(method: str, summary: dict, n_effective: int, bands, lang: str):
    """Tuile de verdict d'une méthode : conclusion en clair, puis une ligne par bande (couverture
    observée, annoncée, intervalle de confiance)."""
    details, verdicts = [], []
    for lo, hi in bands:
        row = summary[lo]
        result = calibration_verdict(row["observed_pct"], row["nominal_pct"], n_effective)
        verdicts.append(result["verdict"])
        if result["verdict"] is not None:
            details.append(html.Li(L(lang, "verdict_band_line", band=f"{lo}-{hi}", observed=row["observed_pct"],
                                     nominal=row["nominal_pct"], low=result["low_pct"], high=result["high_pct"])))
    verdict = combine_calibration_verdicts(verdicts)
    if verdict is None:
        return None
    icon, state = VERDICT_STYLES[verdict]
    return dbc.Col(html.Div([
        html.Div(L(lang, f"verdict_method_{method}"), className="kpi-label"),
        html.Div([html.I(className=f"bi bi-{icon} me-2", **{"aria-hidden": "true"}), L(lang, f"verdict_{verdict}")],
                 className="verdict-title"),
        html.Div(L(lang, f"verdict_{verdict}_sub", n=n_effective), className="kpi-sub mb-1"),
        html.Ul(details, className="verdict-details"),
    ], className=f"verdict-tile {state} h-100"), xs=12, lg=6, className="mb-3")


def _verdict_info(lang: str) -> list:
    return [html.Span(" ⓘ", id="verdict-help-info", style={"cursor": "help"}),
            dbc.Tooltip(L(lang, "verdict_help"), target="verdict-help-info", placement="right")]


@app.callback(
    Output("validation-verdict", "children"),
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
        return "", empty_fig, empty_fig, [], [], "", L(lang, "validation_insufficient_history")

    results_by_method = {}
    for method in ("normal", "bootstrap"):
        results_by_method[method] = walk_forward_calibration(
            returns_hist, horizon_months, VALIDATION_N_SIMS, VALIDATION_SEED, method,
            step_months=step_months or 12, min_calibration_months=VALIDATION_MIN_CALIBRATION_MONTHS,
        )

    n_origins = results_by_method["normal"]["n_origins"]
    if n_origins == 0:
        return "", empty_fig, empty_fig, [], [], "", L(lang, "validation_insufficient_history")

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
    tiles = [tile for tile in (
        _verdict_tile("normal", summary_normal, n_effective, bands, lang),
        _verdict_tile("bootstrap", summary_bootstrap, n_effective, bands, lang),
    ) if tile is not None]
    verdict = html.Div([
        html.Div([L(lang, "verdict_heading")] + _verdict_info(lang), className="perf-group-title"),
        dbc.Row(tiles, className="g-3"),
    ], className="mb-2") if tiles else ""
    info_caption = html.Div([
        html.Div(L(lang, "validation_n_origins_label", n=n_origins)),
        html.Div(L(lang, "validation_n_effective_label", n=n_effective)),
        html.Div(L(lang, "validation_overlap_warning"), className="fst-italic mt-1"),
    ])

    return verdict, fig_normal, fig_bootstrap, table_data, table_columns, info_caption, ""
