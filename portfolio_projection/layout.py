"""
Construction de l'interface Dash (sidebar, onglets) et petits helpers d'affichage
conditionnel (visible/caché, libellé de taxe...) réutilisés à la fois ici (pour
l'état initial des composants) et par callbacks/shared.py, qui les enregistre comme
callbacks Dash. Ce module ne dépend jamais du paquet callbacks/ ni de l'instance
`app` (pour éviter tout import circulaire).
"""
import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

import portfolio_db
import portfolio_engine
from constants import (
    BACKTEST_ANCHOR_KEYS, CTO_FLAT_TAX_RATE, N_PORTFOLIOS_MAX, PEA_CONTRIBUTION_CAP, PEA_TAX_RATE,
    TICKER_KEYS, TICKERS, ETF_NAMES,
)
from i18n import L

GRAPH_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "select2d", "lasso2d", "autoScale2d",
        "hoverCompareCartesian", "hoverClosestCartesian", "toggleSpikelines",
    ],
}


def icon_label(icon: str, text: str) -> list:
    """Libellé de bouton précédé d'une icône Bootstrap Icons (feuille chargée dans app.py). L'icône
    accompagne le texte, elle ne le remplace jamais."""
    return [html.I(className=f"bi bi-{icon} me-1", **{"aria-hidden": "true"}), text]

TABLE_BASE_CELL_STYLE = {"fontSize": "0.8rem", "textAlign": "left"}

# Squelette affiché pendant un calcul : la forme du contenu à venir (titre, lignes, bloc) plutôt
# qu'un rond qui tourne. Animation dans assets/theme.css (.skeleton), aux couleurs du mode affiché
# et figée si le système demande moins d'animations. delay_show : rien ne clignote pour un calcul
# instantané.
LOADING_PROPS = {
    "custom_spinner": html.Div([
        html.Div(className="skeleton-bar skeleton-title"),
        html.Div(className="skeleton-bar"),
        html.Div(className="skeleton-bar skeleton-short"),
        html.Div(className="skeleton-block"),
    ], className="skeleton", **{"aria-busy": "true"}),
    "delay_show": 200,
    "parent_className": "loading-area",
}


def table_style_overrides(dark: bool):
    """(style_header, style_cell, style_data) pour un dash_table.DataTable.
    dash_table applique ses propres couleurs par défaut (JS injecté à l'exécution,
    non couvert par le thème Bootstrap) : passer explicitement ces props est le
    seul moyen fiable de le rendre lisible en mode sombre."""
    if not dark:
        return {}, TABLE_BASE_CELL_STYLE, {}
    return (
        {"backgroundColor": "#2b2b2b", "color": "#e9ecef", "border": "1px solid #444"},
        {**TABLE_BASE_CELL_STYLE, "backgroundColor": "#1e1e1e", "color": "#e9ecef", "border": "1px solid #444"},
        {"backgroundColor": "#1e1e1e", "color": "#e9ecef"},
    )

CONFIG_FIELDS = [
    ("source_radio", "source-radio", "value"),
    ("lookback_years", "lookback-slider", "value"),
    ("horizon_years", "horizon-slider", "value"),
    ("enable_decumulation", "decumulation-checkbox", "value"),
    ("decumulation_years", "decumulation-years-slider", "value"),
    ("withdrawal_monthly", "withdrawal-monthly-slider", "value"),
    ("method_radio", "method-radio", "value"),
    ("block_size", "block-size-slider", "value"),
    ("inject_crisis", "crisis-checkbox", "value"),
    ("shock_pct", "shock-pct-slider", "value"),
    ("shock_duration", "shock-duration-slider", "value"),
    ("shock_timing", "shock-timing-radio", "value"),
    ("shock_year", "shock-year-slider", "value"),
    ("view_mode", "view-mode-radio", "value"),
    ("backtest_anchor", "backtest-anchor-radio", "value"),
    ("apport_constant", "apport-constant-slider", "value"),
    ("apport_initial", "apport-initial-slider", "value"),
    ("apport_final", "apport-final-slider", "value"),
    ("annual_fee_pct", "fee-slider", "value"),
    ("inflation_pct", "inflation-slider", "value"),
    ("display_radio", "display-radio", "value"),
    ("apply_tax", "tax-checkbox", "value"),
    ("envelope", "envelope-radio", "value"),
    ("pea_cap", "pea-cap-checkbox", "value"),
    ("pea_overflow", "pea-overflow-checkbox", "value"),
    ("cto_tax_method", "cto-tax-method-radio", "value"),
    ("cto_tmi", "cto-tmi-dropdown", "value"),
    ("compare_envelopes", "compare-envelopes-checkbox", "value"),
    ("band_width", "band-width-slider", "value"),
    ("n_sims", "n-sims-slider", "value"),
    ("seed", "seed-input", "value"),
    ("objective_enabled", "objective-checkbox", "value"),
    ("objective_amount", "objective-amount-input", "value"),
    ("objective_percentile", "objective-percentile-radio", "value"),
] + [
    (f"mu_override_t{i}", f"mu-override-t{i}", "value") for i in range(len(TICKER_KEYS))
]

TAB_STATE_FIELDS = (
    [("indices-checklist", "value"), ("n-portfolios-input", "value")]
    + [(f"name-p{p}", "value") for p in range(N_PORTFOLIOS_MAX)]
    + [(f"weight-p{p}-t{i}", "value") for p in range(N_PORTFOLIOS_MAX) for i in range(len(TICKER_KEYS))]
    + [("shrinkage-slider", "value"), ("risk-free-rate-slider", "value"),
       ("weight-bounds-slider", "value"), ("step-pct-slider", "value")]
)


# ============================================================
# HELPERS D'AFFICHAGE CONDITIONNEL
# ============================================================
# Fonctions pures (pas de décorateur @app.callback ici) : appelées directement
# ci-dessous pour l'état initial des composants, et enregistrées comme
# callbacks Dash dans callbacks/shared.py.

def toggle_etf_info(source):
    return {"display": "block"} if source == "etf" else {"display": "none"}


def compute_cto_tax_rate(method: str, tmi_pct) -> float:
    if method == "bareme":
        return (tmi_pct or 30) / 100 + PEA_TAX_RATE
    return CTO_FLAT_TAX_RATE


def compute_tax_rate(envelope: str, cto_method: str, cto_tmi) -> float:
    if envelope == "cto":
        return compute_cto_tax_rate(cto_method, cto_tmi)
    return PEA_TAX_RATE


def toggle_cto_tax_method(envelope):
    return {"display": "block"} if envelope == "cto" else {"display": "none"}


def toggle_pea_cap_container(envelope):
    return {"display": "block"} if envelope == "pea" else {"display": "none"}


def toggle_pea_overflow_container(pea_cap_val):
    """La case "Continuer sur un CTO" n'a de sens que si le plafond PEA lui-même est actif (sinon
    il n'y a jamais d'excédent à router) : la masquer dès que pea-cap-checkbox est décochée évite
    une case visible et cochable qui ne ferait rien (route_overflow dans callbacks/par_indice.py et portefeuille.py reste False
    tant que pea_cap est None, quoi que vaille cette case)."""
    return {"display": "block"} if (pea_cap_val and "on" in pea_cap_val) else {"display": "none"}


def toggle_cto_tmi(method):
    return {"display": "block"} if method == "bareme" else {"display": "none"}


def update_tax_label(envelope, cto_method, cto_tmi, lang="fr"):
    if envelope == "cto":
        rate = compute_cto_tax_rate(cto_method, cto_tmi) * 100
        if cto_method == "bareme":
            return (
                L(lang, "tax_label_cto_bareme", tmi=cto_tmi or 30, rate=rate),
                L(lang, "tax_help_cto_bareme"),
            )
        return (
            L(lang, "tax_label_cto_flat", rate=rate),
            L(lang, "tax_help_cto_flat"),
        )
    return (L(lang, "tax_label_pea"), L(lang, "tax_help_pea"))


def toggle_decumulation(v):
    return {"display": "block"} if v and "on" in v else {"display": "none"}


def toggle_objective(v):
    return {"display": "block"} if v and "on" in v else {"display": "none"}


def toggle_block_size(method):
    return {"display": "block"} if method == "bootstrap" else {"display": "none"}


def toggle_prevision_only(view_mode):
    """Paramètres qui n'ont de sens que pour une simulation (horizon de projection...) : sans
    effet en mode historique, qui rejoue une séquence réellement observée plutôt que de simuler."""
    return {"display": "block"} if (view_mode or "prevision") != "historique" else {"display": "none"}


def toggle_historique_only(view_mode):
    """Paramètres qui n'ont de sens que pour la trajectoire historique (point de départ parmi les
    crises connues...) : sans effet en mode prévision, dont le graphique n'affiche plus cette
    trajectoire réelle depuis qu'elle a sa propre bascule dédiée."""
    return {"display": "block"} if view_mode == "historique" else {"display": "none"}


def toggle_crisis(v):
    return {"display": "block"} if v and "on" in v else {"display": "none"}


def toggle_shock_year(timing):
    return {"display": "block"} if timing == "fixed" else {"display": "none"}


def update_shock_year_bounds(horizon_years, decum_val, decumulation_years, current_value):
    enable = bool(decum_val and "on" in decum_val)
    max_year = horizon_years + (decumulation_years if enable else 0)
    new_value = min(current_value or 5, max_year)
    return max_year, new_value


def toggle_portfolio_blocks(n_portfolios):
    """Le champ "Nombre de portefeuilles" (min=1, max=N_PORTFOLIOS_MAX côté UI) n'empêche pas
    une valeur hors bornes d'arriver ici (saisie clavier au-delà du max, valeur restaurée d'une
    config JSON...) : sans ce clamp, une valeur trop grande retombe sur le "or 1" ci-dessous et
    masque silencieusement tous les portefeuilles sauf le premier, l'inverse de ce que l'utilisateur
    demande."""
    n_portfolios = max(1, min(int(n_portfolios or 1), N_PORTFOLIOS_MAX))
    return [{"display": "block"} if p < n_portfolios else {"display": "none"} for p in range(N_PORTFOLIOS_MAX)]


# ============================================================
# COMPOSANTS DE FORMULAIRE
# ============================================================

def info_tooltip(info_id, tooltip_text):
    """ⓘ cliquable/survolable renvoyant un (Span, Tooltip) à ajouter à côté d'un libellé."""
    return [
        html.Span(" ⓘ", id=info_id, style={"cursor": "help"}),
        dbc.Tooltip(tooltip_text, target=info_id, placement="right"),
    ]


def slider_block(label, slider_id, minv, maxv, value, step=1, marks=None, help_text=None, tooltip_text=None):
    label_row = [dbc.Label(label, html_for=slider_id, className="mb-0")]
    if tooltip_text:
        label_row += info_tooltip(f"{slider_id}-info", tooltip_text)
    children = [html.Div(label_row)]
    if help_text:
        children.append(html.Div(help_text, className="text-muted", style={"fontSize": "0.75rem"}))
    children.append(dcc.Slider(
        id=slider_id, min=minv, max=maxv, step=step, value=value, marks=marks,
        tooltip={"placement": "bottom", "always_visible": False},
        updatemode="mouseup",
    ))
    return html.Div(children, className="mb-3")


def gv(v, cid, default):
    """Valeur courante d'un composant lors d'une reconstruction (changement de langue), ou défaut."""
    if v and v.get(cid) is not None:
        return v[cid]
    return default


def build_sidebar(lang, v=None):
    v = v or {}
    source = gv(v, "source-radio", "etf")
    decum_val = gv(v, "decumulation-checkbox", [])
    method = gv(v, "method-radio", "normal")
    crisis_val = gv(v, "crisis-checkbox", [])
    shock_timing = gv(v, "shock-timing-radio", "random")
    envelope = gv(v, "envelope-radio", "pea")
    cto_method = gv(v, "cto-tax-method-radio", "flat")
    cto_tmi = gv(v, "cto-tmi-dropdown", 30)
    tax_label, tax_help = update_tax_label(envelope, cto_method, cto_tmi, lang)
    objective_val = gv(v, "objective-checkbox", [])
    view_mode = gv(v, "view-mode-radio", "prevision")

    view_mode_section = html.Div([
        html.Div([dbc.Label(L(lang, "view_mode_label"), className="mb-0 fw-bold")] + info_tooltip("view-mode-info", L(lang, "view_mode_help"))),
        dcc.RadioItems(
            id="view-mode-radio",
            options=[
                {"label": L(lang, "view_mode_prevision"), "value": "prevision"},
                {"label": L(lang, "view_mode_historique"), "value": "historique"},
            ],
            value=view_mode, labelStyle={"display": "block"}, className="mb-2",
        ),
    ], className="mb-3 pb-3 border-bottom")

    data_section = [
        dbc.Label(L(lang, "source_label"), className="mb-0"),
        dcc.RadioItems(
            id="source-radio",
            options=[
                {"label": L(lang, "source_indice"), "value": "indice"},
                {"label": L(lang, "source_etf"), "value": "etf"},
            ],
            value=source, labelStyle={"display": "block"}, className="mb-2",
        ),
        html.Div(
            html.Ul([
                html.Li([html.B(name), f" → {TICKERS[name]['etf']} : {ETF_NAMES[TICKERS[name]['etf']]}"])
                for name in TICKERS
            ], style={"fontSize": "0.75rem"}),
            id="etf-info", style=toggle_etf_info(source), className="mb-2",
        ),
        slider_block(L(lang, "lookback_label"), "lookback-slider", 5, 30, gv(v, "lookback-slider", 20)),
        html.Div(
            slider_block(L(lang, "horizon_label"), "horizon-slider", 5, 40, gv(v, "horizon-slider", 20)),
            id="horizon-slider-container", style=toggle_prevision_only(view_mode),
        ),
        html.Div([
            html.Div([dbc.Label(L(lang, "backtest_anchor_label"), className="mb-0")] + info_tooltip("backtest-anchor-info", L(lang, "backtest_anchor_help"))),
            dcc.RadioItems(
                id="backtest-anchor-radio",
                options=[{"label": L(lang, f"backtest_anchor_{k}"), "value": k} for k in BACKTEST_ANCHOR_KEYS],
                value=gv(v, "backtest-anchor-radio", "recent"), labelStyle={"display": "block"}, className="mb-2",
            ),
        ], id="backtest-anchor-container", style=toggle_historique_only(view_mode)),
        html.Div([
            html.Div([dbc.Label(L(lang, "method_label"), className="mb-0")] + info_tooltip("method-radio-info", L(lang, "method_help"))),
            dcc.RadioItems(
                id="method-radio",
                options=[{"label": L(lang, "method_normal"), "value": "normal"}, {"label": L(lang, "method_bootstrap"), "value": "bootstrap"}],
                value=method, labelStyle={"display": "block"}, className="mb-2",
            ),
            html.Div(
                slider_block(
                    L(lang, "block_size_label"), "block-size-slider", 1, 36, gv(v, "block-size-slider", 12),
                    help_text=L(lang, "block_size_help"),
                ),
                id="block-size-container", style=toggle_block_size(method),
            ),
        ], id="method-section-container", style=toggle_prevision_only(view_mode)),
        html.Div([
            dbc.Button(L(lang, "mu_override_toggle"), id="btn-toggle-mu-override",
                       color="link", size="sm", className="p-0 mb-2"),
            dbc.Collapse([
                html.Div(L(lang, "mu_override_note"), className="text-muted mb-2",
                          style={"fontSize": "0.75rem", "whiteSpace": "pre-line"}),
                html.Div([
                    dbc.Row([
                        dbc.Col(dbc.Label(name, className="mb-0", style={"fontSize": "0.8rem"}), width=7),
                        dbc.Col(dcc.Input(
                            id=f"mu-override-t{i}", type="number", step=0.1,
                            placeholder=L(lang, "mu_override_placeholder"),
                            value=gv(v, f"mu-override-t{i}", None),
                            className="form-control form-control-sm",
                        ), width=5),
                    ], className="mb-1 align-items-center")
                    for i, name in enumerate(TICKER_KEYS)
                ]),
            ], id="mu-override-collapse", is_open=False, className="mb-2"),
        ], id="mu-override-container", style=toggle_prevision_only(view_mode)),
    ]

    withdrawals_crisis_section = [
        html.Div([
            html.H6(L(lang, "decumulation_title")),
            dcc.Checklist(id="decumulation-checkbox", options=[{"label": L(lang, "decumulation_checkbox"), "value": "on"}], value=decum_val, className="mb-2"),
            html.Div([
                slider_block(L(lang, "decumulation_years_label"), "decumulation-years-slider", 1, 40, gv(v, "decumulation-years-slider", 20)),
                slider_block(L(lang, "withdrawal_label"), "withdrawal-monthly-slider", 100, 5000, gv(v, "withdrawal-monthly-slider", 1000), step=100),
            ], id="decumulation-options-container", style=toggle_decumulation(decum_val)),

            html.Div([
                html.H6(L(lang, "crisis_title"), className="mt-3"),
                dcc.Checklist(id="crisis-checkbox", options=[{"label": L(lang, "crisis_checkbox"), "value": "on"}], value=crisis_val, className="mb-2"),
                html.Div([
                    slider_block(L(lang, "shock_pct_label"), "shock-pct-slider", -80, -5, gv(v, "shock-pct-slider", -30), step=5),
                    slider_block(L(lang, "shock_duration_label"), "shock-duration-slider", 1, 24, gv(v, "shock-duration-slider", 6)),
                    dbc.Label(L(lang, "shock_timing_label"), className="mb-0"),
                    dcc.RadioItems(
                        id="shock-timing-radio",
                        options=[{"label": L(lang, "shock_random"), "value": "random"}, {"label": L(lang, "shock_fixed"), "value": "fixed"}],
                        value=shock_timing, labelStyle={"display": "block"}, className="mb-2",
                    ),
                    html.Div(
                        slider_block(L(lang, "shock_year_label"), "shock-year-slider", 1, 20, gv(v, "shock-year-slider", 5)),
                        id="shock-year-container", style=toggle_shock_year(shock_timing),
                    ),
                ], id="crisis-options-container", style=toggle_crisis(crisis_val)),
            ], id="crisis-section-container", style=toggle_prevision_only(view_mode)),
        ], id="withdrawals-section-container", style=toggle_prevision_only(view_mode)),
    ]

    contrib_section = [
        html.Div([
            html.H6(L(lang, "contrib_constant_title")),
            slider_block(L(lang, "contrib_constant_label"), "apport-constant-slider", 100, 1000, gv(v, "apport-constant-slider", 350), step=10),

            html.H6(L(lang, "contrib_progressive_title"), className="mt-3"),
            slider_block(L(lang, "contrib_initial_label"), "apport-initial-slider", 100, 1000, gv(v, "apport-initial-slider", 200), step=10),
            slider_block(L(lang, "contrib_final_label"), "apport-final-slider", 100, 1000, gv(v, "apport-final-slider", 500), step=10),
        ], id="contrib-section-container", style=toggle_prevision_only(view_mode)),
    ]

    fees_tax_section = [
        html.Div([
            slider_block(
                L(lang, "fee_label"), "fee-slider", 0.0, 2.0, gv(v, "fee-slider", 0.2), step=0.1,
                help_text=L(lang, "fee_help"),
            ),
            slider_block(L(lang, "inflation_label"), "inflation-slider", 0.0, 5.0, gv(v, "inflation-slider", 2.0), step=0.1),
            html.Div([dbc.Label(L(lang, "display_label"), className="mb-0")] + info_tooltip("display-radio-info", L(lang, "display_help"))),
            dcc.RadioItems(
                id="display-radio",
                options=[{"label": L(lang, "display_nominal"), "value": "nominal"}, {"label": L(lang, "display_real"), "value": "real"}],
                value=gv(v, "display-radio", "nominal"), labelStyle={"display": "block"}, className="mb-2",
            ),
            dbc.Label(L(lang, "envelope_label"), className="mb-0"),
            dcc.RadioItems(
                id="envelope-radio",
                options=[
                    {"label": L(lang, "envelope_pea"), "value": "pea"},
                    {"label": L(lang, "envelope_cto"), "value": "cto"},
                ],
                value=envelope, labelStyle={"display": "block"}, className="mb-1",
            ),
            html.Div([
                dcc.Checklist(
                    id="pea-cap-checkbox",
                    options=[{"label": L(lang, "pea_cap_checkbox", cap=f"{PEA_CONTRIBUTION_CAP:,.0f} €".replace(",", " ")), "value": "on"}],
                    value=gv(v, "pea-cap-checkbox", ["on"]), className="mb-0",
                ),
                html.Div(L(lang, "pea_cap_help"), className="text-muted mb-2", style={"fontSize": "0.75rem"}),
                html.Div([
                    dcc.Checklist(
                        id="pea-overflow-checkbox",
                        options=[{"label": L(lang, "pea_overflow_checkbox"), "value": "on"}],
                        value=gv(v, "pea-overflow-checkbox", []), className="mb-0",
                    ),
                    html.Div(L(lang, "pea_overflow_help"), className="text-muted mb-2", style={"fontSize": "0.75rem"}),
                ], id="pea-overflow-container", style=toggle_pea_overflow_container(gv(v, "pea-cap-checkbox", ["on"]))),
            ], id="pea-cap-container", style=toggle_pea_cap_container(envelope)),
            html.Div([
                dbc.Label(L(lang, "cto_method_label"), className="mb-0", style={"fontSize": "0.85rem"}),
                dcc.RadioItems(
                    id="cto-tax-method-radio",
                    options=[
                        {"label": L(lang, "cto_flat"), "value": "flat"},
                        {"label": L(lang, "cto_bareme"), "value": "bareme"},
                    ],
                    value=cto_method, labelStyle={"display": "block"}, className="mb-1",
                ),
                html.Div([
                    dbc.Label(L(lang, "cto_tmi_label"), className="mb-0", style={"fontSize": "0.85rem"}),
                    dcc.Dropdown(
                        id="cto-tmi-dropdown",
                        options=[{"label": f"{t} %", "value": t} for t in [0, 11, 30, 41, 45]],
                        value=cto_tmi, clearable=False, style={"maxWidth": "200px"}, className="mb-1",
                    ),
                ], id="cto-tmi-container", style=toggle_cto_tmi(cto_method)),
            ], id="cto-tax-method-container", style=toggle_cto_tax_method(envelope), className="mb-2"),
            dcc.Checklist(id="tax-checkbox", options=[{"label": "", "value": "on"}], value=gv(v, "tax-checkbox", []), style={"display": "inline-block"}),
            html.Span(tax_label, id="tax-checkbox-label", style={"fontSize": "0.9rem"}),
            html.Div(tax_help, id="tax-checkbox-help", className="text-muted mb-2", style={"fontSize": "0.75rem"}),
            html.Div(
                dcc.Checklist(
                    id="compare-envelopes-checkbox",
                    options=[{"label": L(lang, "compare_checkbox"), "value": "on"}],
                    value=gv(v, "compare-envelopes-checkbox", []), className="mb-2",
                ),
                id="compare-envelopes-option-container", style=toggle_prevision_only(view_mode),
            ),
        ], id="fees-tax-section-container", style=toggle_prevision_only(view_mode)),
    ]

    display_sim_section = [
        html.Div([
            slider_block(
                L(lang, "band_width_label"), "band-width-slider", 50, 95, gv(v, "band-width-slider", 80), step=None,
                marks={50: "50", 80: "80", 90: "90", 95: "95"},
            ),
            slider_block(L(lang, "n_sims_label"), "n-sims-slider", 100, 3000, gv(v, "n-sims-slider", 500), step=100),
            dbc.Label(L(lang, "seed_label"), className="mb-0"),
            dbc.Row([
                dbc.Col(dcc.Input(id="seed-input", type="number", value=gv(v, "seed-input", 42), step=1, className="form-control"), width=8),
                dbc.Col(dbc.Button("🎲", id="btn-reroll", color="secondary", size="sm"), width=4),
            ], className="mb-3 g-1"),
        ], id="sim-settings-container", style=toggle_prevision_only(view_mode)),

        html.Div([
            html.H6(L(lang, "objective_title"), className="mt-3"),
            dcc.Checklist(
                id="objective-checkbox",
                options=[{"label": L(lang, "objective_checkbox"), "value": "on"}],
                value=objective_val, className="mb-2",
            ),
            html.Div([
                dbc.Label(L(lang, "objective_amount_label"), className="mb-0"),
                dcc.Input(
                    id="objective-amount-input", type="number", min=1000, step=1000,
                    value=gv(v, "objective-amount-input", 50000), className="form-control mb-2",
                ),
                dbc.Label(L(lang, "objective_percentile_label"), className="mb-0"),
                dcc.RadioItems(
                    id="objective-percentile-radio",
                    options=[
                        {"label": L(lang, "objective_p_low"), "value": "p_low"},
                        {"label": L(lang, "objective_median"), "value": "median"},
                        {"label": L(lang, "objective_p_high"), "value": "p_high"},
                    ],
                    value=gv(v, "objective-percentile-radio", "median"), labelStyle={"display": "block"},
                    className="mb-2",
                ),
            ], id="objective-options-container", style=toggle_objective(objective_val)),
        ], id="objective-section-container", style=toggle_prevision_only(view_mode)),
    ]

    config_section = [
        dbc.Button(icon_label("download", L(lang, "config_export_btn")), id="btn-download-config", color="primary", size="sm", className="mb-2 w-100"),
        dcc.Download(id="download-config"),
        dcc.Upload(
            id="upload-config",
            children=html.Div(L(lang, "config_upload_placeholder")),
            style={
                "width": "100%", "padding": "10px", "borderWidth": "1px", "borderStyle": "dashed",
                "borderRadius": "5px", "textAlign": "center", "fontSize": "0.75rem",
            },
        ),
    ]

    accordion = dbc.Accordion([
        dbc.AccordionItem(data_section, title=L(lang, "section_data"), item_id="item-data"),
        dbc.AccordionItem(
            withdrawals_crisis_section, title=L(lang, "section_withdrawals_crisis"), item_id="item-retraits-crise",
            id="accordion-item-retraits-crise", style=toggle_prevision_only(view_mode),
        ),
        dbc.AccordionItem(
            contrib_section, title=L(lang, "section_contributions"), item_id="item-contrib",
            id="accordion-item-contrib", style=toggle_prevision_only(view_mode),
        ),
        dbc.AccordionItem(
            fees_tax_section, title=L(lang, "section_fees_tax"), item_id="item-fees",
            id="accordion-item-fees", style=toggle_prevision_only(view_mode),
        ),
        dbc.AccordionItem(
            display_sim_section, title=L(lang, "section_display_sim"), item_id="item-sim",
            id="accordion-item-sim", style=toggle_prevision_only(view_mode),
        ),
        dbc.AccordionItem(config_section, title=L(lang, "section_config"), item_id="item-config"),
    ], always_open=True, active_item=["item-data", "item-contrib", "item-fees"], flush=True)

    return html.Div([view_mode_section, accordion], style={"height": "100vh", "overflowY": "auto", "padding": "1rem"})


# ---------- Onglet 1 : par indice ----------
def build_tab1(lang, v=None):
    v = v or {}
    return html.Div([
        dcc.Checklist(
            id="indices-checklist",
            options=[{"label": f" {name}", "value": name} for name in TICKERS],
            value=gv(v, "indices-checklist", list(TICKERS.keys())), inline=True, className="mb-3",
        ),
        html.Div(id="tab1-warning"),
        dcc.Loading(**LOADING_PROPS, children=[
            html.H5(L(lang, "trajectories_title"), id="tab1-trajectories-title", className="section-title"),
            html.Div([
                html.Div(dcc.Graph(id="tab1-graph-const", config=GRAPH_CONFIG),
                         id="tab1-graph-const-container", style={"flex": "1", "minWidth": "0"}),
                html.Div(dcc.Graph(id="tab1-graph-prog", config=GRAPH_CONFIG),
                         id="tab1-graph-prog-container", style={"flex": "1", "minWidth": "0"}),
            ], style={"display": "flex", "gap": "1rem", "flexWrap": "wrap"}),
            html.Div(id="tab1-metric-cards"),
            html.Div(id="tab1-objective-result", className="mt-2"),
            html.Div(id="tab1-rolling-backtest-result", className="mt-2"),
            html.H5(L(lang, "metrics_title"), id="tab1-metrics-title", className="section-title"),
            dash_table.DataTable(id="tab1-metrics-table", style_table={"overflowX": "auto"}, style_cell={"fontSize": "0.8rem", "textAlign": "left"}, tooltip_delay=0, tooltip_duration=None),
            html.Div([
                html.H5(L(lang, "compare_pea_cto_title"), className="section-title"),
                dcc.Graph(id="tab1-envelope-compare-chart", config=GRAPH_CONFIG),
            ], id="tab1-envelope-compare-container", style={"display": "none"}),
            html.Div([
                html.H5(L(lang, "sequence_risk_title"), className="section-title"),
                html.P(L(lang, "sequence_risk_intro"), className="text-muted", style={"fontSize": "0.8rem"}),
                dcc.Graph(id="tab1-sequence-risk-chart", config=GRAPH_CONFIG),
            ], id="tab1-sequence-risk-container", style={"display": "none"}),
        ]),
        dbc.Button(icon_label("filetype-csv", L(lang, "download_metrics_btn")), id="btn-download-tab1", color="secondary", size="sm", className="mt-2"),
        dcc.Download(id="download-tab1"),
        dcc.Store(id="tab1-csv-store"),
    ], className="p-3")


# ---------- Onglet 2 : portefeuille pondéré ----------
def build_portfolio_block(p, lang, v=None):
    v = v or {}
    n_portfolios = gv(v, "n-portfolios-input", 1)
    return html.Div([
        dbc.Input(id=f"name-p{p}", type="text", value=gv(v, f"name-p{p}", L(lang, "portfolio_default_name", n=p + 1)), className="mb-2"),
        html.Div([
            html.Div([
                dbc.Label(L(lang, "weight_label", name=name), className="mb-0"),
                dcc.Slider(
                    id=f"weight-p{p}-t{i}", min=0, max=100, step=1,
                    value=gv(v, f"weight-p{p}-t{i}", round(100 / len(TICKER_KEYS))),
                    tooltip={"placement": "bottom", "always_visible": False},
                    updatemode="mouseup",
                ),
            ], className="mb-2")
            for i, name in enumerate(TICKER_KEYS)
        ]),
        html.Div(id=f"caption-p{p}", className="text-muted", style={"fontSize": "0.75rem"}),
    ], id=f"portfolio-block-{p}", style=toggle_portfolio_blocks(n_portfolios)[p],
       className="border rounded p-2 mb-3")


def build_tab2(lang, v=None):
    v = v or {}
    return html.Div([
        dbc.Label(L(lang, "n_portfolios_label"), className="mb-0"),
        dcc.Input(id="n-portfolios-input", type="number", min=1, max=N_PORTFOLIOS_MAX, step=1, value=gv(v, "n-portfolios-input", 1), className="form-control mb-3", style={"width": "100px"}),

        html.Div([build_portfolio_block(p, lang, v) for p in range(N_PORTFOLIOS_MAX)]),

        html.Div(id="tab2-warning"),

        dcc.Loading(**LOADING_PROPS, children=[
            html.H5(L(lang, "corr_title"), className="section-title"),
            dcc.Graph(id="tab2-corr-heatmap", config=GRAPH_CONFIG),

            html.H5(L(lang, "suggested_weights_title"), className="section-title"),
            dbc.Button(L(lang, "weights_explain_toggle"), id="btn-toggle-weights-explain",
                       color="link", size="sm", className="p-0 mb-2"),
            dbc.Collapse([
                html.Div(L(lang, "weights_explain_text"), className="text-muted mb-2",
                          style={"fontSize": "0.8rem", "whiteSpace": "pre-line"}),
                slider_block(
                    L(lang, "shrinkage_label"), "shrinkage-slider", 0, 100,
                    gv(v, "shrinkage-slider", 50), step=5, help_text=L(lang, "shrinkage_help"),
                ),
                slider_block(
                    L(lang, "risk_free_rate_label"), "risk-free-rate-slider", 0, 10,
                    gv(v, "risk-free-rate-slider", 0), step=0.5, help_text=L(lang, "risk_free_rate_help"),
                ),
                html.Div([
                    dbc.Label(L(lang, "weight_bounds_label"), className="mb-0"),
                    html.Div(L(lang, "weight_bounds_help"), className="text-muted", style={"fontSize": "0.75rem"}),
                    dcc.RangeSlider(
                        id="weight-bounds-slider", min=0, max=100, step=5,
                        value=gv(v, "weight-bounds-slider", [0, 100]),
                        marks={0: "0%", 50: "50%", 100: "100%"},
                        tooltip={"placement": "bottom", "always_visible": False}, updatemode="mouseup",
                    ),
                ], className="mb-3"),
                slider_block(
                    L(lang, "step_pct_label"), "step-pct-slider", 5, 25,
                    gv(v, "step-pct-slider", 10), step=None, marks={5: "5%", 10: "10%", 15: "15%", 20: "20%", 25: "25%"},
                    help_text=L(lang, "step_pct_help"),
                ),
            ], id="weights-explain-collapse", is_open=False, className="mb-2"),
            dbc.Row([
                dbc.Col([
                    html.B(L(lang, "sharpe_title")),
                    html.Div(id="tab2-sharpe-weights-display"),
                    dbc.Button(L(lang, "apply_btn"), id="btn-apply-sharpe", color="secondary", size="sm", className="mt-1"),
                ], width=4),
                dbc.Col([
                    html.B(L(lang, "vol_title")),
                    html.Div(id="tab2-vol-weights-display"),
                    dbc.Button(L(lang, "apply_btn"), id="btn-apply-vol", color="secondary", size="sm", className="mt-1"),
                ], width=4),
                dbc.Col([
                    html.B(L(lang, "rp_title")),
                    html.Div(id="tab2-rp-weights-display"),
                    dbc.Button(L(lang, "apply_btn"), id="btn-apply-rp", color="secondary", size="sm", className="mt-1"),
                ], width=4),
            ], className="mb-3"),
        ]),
        dcc.Store(id="sharpe-weights-store"),
        dcc.Store(id="vol-weights-store"),
        dcc.Store(id="rp-weights-store"),

        dcc.Loading(**LOADING_PROPS, children=[
            html.H5(L(lang, "trajectories_title"), id="tab2-trajectories-title", className="section-title"),
            html.Div([
                html.Div(dcc.Graph(id="tab2-graph-const", config=GRAPH_CONFIG),
                         id="tab2-graph-const-container", style={"flex": "1", "minWidth": "0"}),
                html.Div(dcc.Graph(id="tab2-graph-prog", config=GRAPH_CONFIG),
                         id="tab2-graph-prog-container", style={"flex": "1", "minWidth": "0"}),
            ], style={"display": "flex", "gap": "1rem", "flexWrap": "wrap"}),
            html.Div(id="tab2-metric-cards"),
            html.Div(id="tab2-objective-result", className="mt-2"),
            html.Div(id="tab2-rolling-backtest-result", className="mt-2"),
            html.H5(L(lang, "metrics_title_portfolio"), id="tab2-metrics-title", className="section-title"),
            dash_table.DataTable(id="tab2-metrics-table", style_table={"overflowX": "auto"}, style_cell={"fontSize": "0.8rem", "textAlign": "left"}, tooltip_delay=0, tooltip_duration=None),
            html.Div([
                html.H5(L(lang, "compare_pea_cto_title"), className="section-title"),
                dcc.Graph(id="tab2-envelope-compare-chart", config=GRAPH_CONFIG),
            ], id="tab2-envelope-compare-container", style={"display": "none"}),
            html.Div([
                html.H5(L(lang, "sequence_risk_title"), className="section-title"),
                html.P(L(lang, "sequence_risk_intro"), className="text-muted", style={"fontSize": "0.8rem"}),
                dcc.Graph(id="tab2-sequence-risk-chart", config=GRAPH_CONFIG),
            ], id="tab2-sequence-risk-container", style={"display": "none"}),
        ]),
        dbc.Button(icon_label("filetype-csv", L(lang, "download_metrics_btn")), id="btn-download-tab2", color="secondary", size="sm", className="mt-2"),
        dcc.Download(id="download-tab2"),
        dcc.Store(id="tab2-csv-store"),
    ], className="p-3")


# Navigation entre les outils du dépôt (en-tête) : la page d'accueil est servie par run_all.py ; un
# outil lancé seul (Docker, app.py) garde ces liens, qui ne répondent alors que si les autres tournent.
HOME_URL = "http://localhost:8049"
TOOL_URLS = {"projection": "http://localhost:8050", "valuation": "http://localhost:8051",
             "analysis": "http://localhost:8052"}
CURRENT_TOOL = "projection"


def build_header_text(lang):
    """En-tête de l'outil : barre de navigation vers l'accueil et les deux autres outils, vignette
    illustrée (version claire ou sombre selon le thème, voir assets/theme.css), titre et sous-titre.
    Reconstruit à chaque changement de langue (callback de reconstruction)."""
    nav = [html.A([html.I(className="bi bi-house-door me-1", **{"aria-hidden": "true"}), L(lang, "nav_home")],
                  href=HOME_URL, className="app-nav-link")]
    for key, url in TOOL_URLS.items():
        current = key == CURRENT_TOOL
        nav.append(html.A(L(lang, f"nav_{key}"), href=url, className="app-nav-link" + (" active" if current else ""),
                          **({"aria-current": "page"} if current else {})))
    return [
        html.Nav(nav, className="app-nav", **{"aria-label": L(lang, "nav_label")}),
        html.Div([
            html.Div([
                html.Img(src="/assets/header_art_light.svg", alt="", className="header-art header-art-light"),
                html.Img(src="/assets/header_art_dark.svg", alt="", className="header-art header-art-dark"),
            ], className="header-art-box"),
            html.Div([
                html.H1(L(lang, "app_title"), className="app-title"),
                html.P(L(lang, "app_subtitle"), className="app-subtitle"),
            ]),
        ], className="header-main"),
    ]


def build_footer(lang):
    return html.Small(L(lang, "footer_disclaimer"), className="text-muted")


def build_tabs(lang, v=None, active_tab="tab-par-indice"):
    v = v or {}
    return dbc.Tabs([
        dbc.Tab(build_tab1(lang, v), label=L(lang, "tab_par_indice"), tab_id="tab-par-indice"),
        dbc.Tab(build_tab2(lang, v), label=L(lang, "tab_portefeuille"), tab_id="tab-portefeuille"),
        dbc.Tab(build_tab3(lang), label=L(lang, "tab_portefeuille_reel"), tab_id="tab-portefeuille-reel"),
        dbc.Tab(build_tab4(lang), label=L(lang, "tab_validation"), tab_id="tab-validation"),
    ], id="main-tabs", active_tab=active_tab or "tab-par-indice")


# ---------- Onglet 3 : portefeuille réel ----------
# État entièrement en base (portfolio_db.py), pas dans TAB_STATE_FIELDS/CONFIG_FIELDS : un
# changement de langue ou un import/export JSON de config ne restaure donc rien ici (il n'y a
# rien à restaurer), le re-rendu se fait en re-interrogeant la base (voir callbacks/portefeuille_reel.py).
def _default_next_contribution(transactions_df):
    """Montant prérempli du prochain versement : le rythme mensuel réel moyen, arrondi à 10 €.
    Vide sans historique, plutôt qu'un montant inventé."""
    schedule = portfolio_engine.monthly_contribution_schedule(transactions_df)
    if schedule.empty or schedule.mean() <= 0:
        return None
    return int(round(float(schedule.mean()) / 10) * 10)


def build_tab3(lang):
    # Les 3 tableaux éditables (tx/dividendes/pondérations) sont pré-remplis avec le contenu RÉEL
    # de la base dès la construction du layout, plutôt que de laisser data vide par défaut : ce
    # composant est reconstruit à chaque changement de langue (voir rebuild_on_language_change dans
    # callbacks/shared.py, qui remplace tabs-container en entier), et les callbacks de suppression
    # (delete_removed_*) interprètent un data vide comme "toutes les lignes ont été supprimées" --
    # sans ce pré-remplissage, un simple changement de langue viderait la base.
    transactions_df = portfolio_db.get_transactions()
    dividends_df = portfolio_db.get_dividends()
    weights_df = portfolio_db.get_target_weights()
    tx_data = transactions_df.to_dict("records")
    div_data = dividends_df.to_dict("records")
    weights_data = weights_df.to_dict("records")
    ticker_options = [
        {"label": portfolio_engine.ticker_display_label(t), "value": t}
        for t in portfolio_engine.known_tickers(transactions_df, dividends_df, weights_df)
    ]
    benchmark_options = [
        {"label": portfolio_engine.ticker_display_label(tks["etf"]), "value": tks["etf"]} for tks in TICKERS.values()
    ]

    def ticker_dropdown(dropdown_id, placeholder):
        # dcc.Dropdown plutôt qu'un simple texte libre : reproposer un ticker déjà utilisé en un
        # clic. Reste "creatable" côté client (voir le clientside_callback dans app.py qui ajoute
        # le texte tapé aux options à la volée) : un ticker encore jamais vu reste saisissable,
        # cette app accepte n'importe quel ticker, pas seulement ceux déjà connus.
        return dcc.Dropdown(
            id=dropdown_id, options=ticker_options, placeholder=placeholder,
            clearable=True, searchable=True, style={"width": "160px", "fontSize": "0.85rem"},
        )

    # style={"width": "...px"} explicite sur chaque input : .form-control (width:100%) dans une
    # Col width="auto" sans largeur propre se réduit sinon à quasi rien (l'input n'a aucun contenu
    # intrinsèque pour calculer la largeur de sa colonne "auto" -- bug constaté en pratique, le
    # placeholder devenait illisible, tronqué à son seul premier caractère).
    tx_form = dbc.Row([
        dbc.Col(ticker_dropdown("tab3-tx-ticker-input", L(lang, "tx_ticker_label")), width="auto"),
        dbc.Col(dcc.DatePickerSingle(id="tab3-tx-date-input", display_format="YYYY-MM-DD",
                                      placeholder=L(lang, "tx_date_label")), width="auto"),
        dbc.Col(dcc.Input(id="tab3-tx-amount-input", type="number", placeholder=L(lang, "tx_amount_label"),
                           className="form-control form-control-sm", style={"width": "110px"}), width="auto"),
        dbc.Col(dcc.Input(id="tab3-tx-price-input", type="number", placeholder=L(lang, "tx_price_label"),
                           className="form-control form-control-sm", style={"width": "110px"}), width="auto"),
        dbc.Col(dcc.Input(id="tab3-tx-fee-input", type="number", placeholder=L(lang, "tx_fee_label"),
                           className="form-control form-control-sm", style={"width": "90px"}), width="auto"),
        dbc.Col(dbc.Button(icon_label("plus-lg", L(lang, "btn_add_transaction")), id="tab3-btn-add-tx", color="primary", size="sm"),
                width="auto"),
    ], className="mb-2 gx-2 align-items-center")

    div_form = dbc.Row([
        dbc.Col(ticker_dropdown("tab3-div-ticker-input", L(lang, "div_ticker_label")), width="auto"),
        dbc.Col(dcc.DatePickerSingle(id="tab3-div-date-input", display_format="YYYY-MM-DD",
                                      placeholder=L(lang, "div_date_label")), width="auto"),
        dbc.Col(dcc.Input(id="tab3-div-amount-input", type="number", placeholder=L(lang, "div_amount_label"),
                           className="form-control form-control-sm", style={"width": "110px"}), width="auto"),
        dbc.Col(dbc.Button(icon_label("plus-lg", L(lang, "btn_add_dividend")), id="tab3-btn-add-div", color="primary", size="sm"),
                width="auto"),
    ], className="mb-2 gx-2 align-items-center")

    weight_form = dbc.Row([
        dbc.Col(ticker_dropdown("tab3-weight-ticker-input", L(lang, "weight_ticker_label")), width="auto"),
        dbc.Col(dcc.Input(id="tab3-weight-pct-input", type="number", placeholder=L(lang, "weight_pct_label"),
                           className="form-control form-control-sm", style={"width": "150px"}), width="auto"),
        dbc.Col(dbc.Button(icon_label("plus-lg", L(lang, "btn_add_weight")), id="tab3-btn-add-weight", color="secondary", size="sm"),
                width="auto"),
    ], className="mb-2 gx-2 align-items-center")

    # Format maison uniquement (ticker,date,amount_eur,price,fee_eur / ticker,date,amount_eur) :
    # un format d'export Trade Republic a été envisagé mais aucune spec fiable de ses en-têtes n'a
    # pu être trouvée (fonctionnalité récente, avril 2026) -- plutôt que deviner et risquer un
    # mauvais import de vraies données financières, il est reporté à quand un vrai export pourra
    # être montré. detect_csv_kind (portfolio_engine.py) distingue les deux schémas maison par
    # leurs colonnes, un seul bouton d'import suffit donc pour les deux.
    csv_import_block = html.Div([
        dcc.Upload(
            id="tab3-upload-csv",
            children=html.Div(L(lang, "csv_upload_placeholder")),
            style={
                "width": "100%", "padding": "10px", "borderWidth": "1px", "borderStyle": "dashed",
                "borderRadius": "5px", "textAlign": "center", "fontSize": "0.8rem",
            },
        ),
        html.Div(id="tab3-csv-import-result", className="mt-1", style={"fontSize": "0.8rem"}),
        dbc.Row([
            dbc.Col(dbc.Button(icon_label("file-earmark-arrow-down", L(lang, "btn_download_tx_template")), id="tab3-btn-download-tx-template",
                                color="link", size="sm", className="p-0"), width="auto"),
            dbc.Col(dbc.Button(icon_label("file-earmark-arrow-down", L(lang, "btn_download_div_template")), id="tab3-btn-download-div-template",
                                color="link", size="sm", className="p-0"), width="auto"),
        ], className="mt-1 gx-3"),
        dcc.Download(id="tab3-download-tx-template"),
        dcc.Download(id="tab3-download-div-template"),
    ], className="mb-3")

    # Chaque section est un dbc.Card (ombre/coins arrondis déjà définis dans .card, assets/
    # theme.css) : titre en dehors (section-title), formulaire/tableau dans la carte -- même
    # découpage que les cartes qualité/track-record de stock_valuation, pour que cet onglet se
    # lise comme le reste de l'appli plutôt qu'une simple liste de champs à plat.
    return html.Div([
        html.Div(id="tab3-totals-cards"),
        html.Div([
            html.Span(id="tab3-real-pace-display", className="text-muted d-block mb-1", style={"fontSize": "0.85rem"}),
            dbc.Button(L(lang, "btn_use_real_pace"), id="tab3-btn-use-real-pace", color="link", size="sm",
                       className="p-0"),
        ], className="mb-3"),

        html.H5(L(lang, "section_allocation"), className="section-title", id="anchor-tab3-allocation"),
        dbc.Card(dbc.CardBody([
            dcc.Loading(**LOADING_PROPS, children=[dbc.Row([
                dbc.Col(dcc.Graph(id="tab3-allocation-graph", config=GRAPH_CONFIG), lg=7),
                dbc.Col(html.Div(id="tab3-allocation-list"), lg=5, className="d-flex align-items-center"),
            ], className="g-3")]),
            html.Div(id="tab3-index-alerts"),
            html.Div(id="tab3-allocation-note", className="text-muted", style={"fontSize": "0.8rem"}),
            html.Details([
                html.Summary(L(lang, "index_table_summary"), style={"cursor": "pointer", "fontSize": "0.85rem"}),
                html.Small(L(lang, "index_table_hint"), className="text-muted d-block my-2"),
                dash_table.DataTable(
                    id="tab3-index-table", editable=True, style_cell=TABLE_BASE_CELL_STYLE,
                    columns=[
                        {"name": L(lang, "index_col_line"), "id": "label", "editable": False},
                        {"name": L(lang, "index_col_index"), "id": "index_key", "presentation": "dropdown"},
                        {"name": L(lang, "index_col_source"), "id": "source", "editable": False},
                    ],
                    css=[{"selector": ".Select-menu-outer", "rule": "display: block !important"}],
                ),
            ], className="mt-2"),
        ]), className="mb-4"),

        html.H5(L(lang, "section_pea_milestones"), className="section-title", id="anchor-tab3-milestones"),
        dbc.Card(dbc.CardBody([
            html.Div([
                html.Div([dbc.Label(L(lang, "pea_opening_date_label"), className="mb-0")] + info_tooltip(
                    "pea-opening-date-info", L(lang, "pea_opening_date_help"),
                )),
                # Pré-rempli depuis la base, comme les tableaux ci-dessous : ce composant est
                # reconstruit à chaque changement de langue, et le callback qui l'écoute enregistre
                # sa valeur -- un défaut vide effacerait la date enregistrée.
                dcc.DatePickerSingle(
                    id="tab3-pea-opening-date", date=portfolio_db.get_pea_opening_date(),
                    display_format="DD/MM/YYYY" if lang == "fr" else "YYYY-MM-DD", clearable=True,
                ),
            ], className="mb-3"),
            html.Div(id="tab3-pea-milestones"),
        ]), className="mb-4"),

        html.H5(L(lang, "section_performance"), className="section-title", id="anchor-tab3-performance"),
        dbc.Card(dbc.CardBody([
            html.Div([
                html.Div([dbc.Label(L(lang, "benchmark_label"), className="mb-0")] + info_tooltip(
                    "benchmark-ticker-info", L(lang, "benchmark_help"),
                )),
                # Creatable comme les autres menus ticker de l'onglet (voir app.py) : n'importe quel
                # ticker Yahoo peut servir de référence, pas seulement les ETF de l'univers simulé.
                # persistence : le choix survit au rechargement et au changement de langue.
                dcc.Dropdown(
                    id="tab3-benchmark-ticker-input", options=benchmark_options,
                    value=TICKERS["MSCI World"]["etf"], clearable=False, searchable=True,
                    persistence=True, persistence_type="local",
                    style={"width": "320px", "fontSize": "0.85rem"},
                ),
            ], className="mb-3"),
            dcc.Loading(**LOADING_PROPS, children=[html.Div(id="tab3-performance-cards")]),
            html.Small(L(lang, "performance_conventions_note"), className="text-muted d-block mt-1"),
        ]), className="mb-4"),

        html.H5(L(lang, "section_real_vs_simulated"), className="section-title", id="anchor-tab3-chart"),
        dbc.Card(dbc.CardBody(
            dcc.Loading(**LOADING_PROPS, children=[dcc.Graph(id="tab3-real-vs-sim-graph", config=GRAPH_CONFIG)]),
        ), className="mb-4"),

        html.H5(L(lang, "section_real_portfolio_projection"), className="section-title", id="anchor-tab3-projection"),
        dbc.Card(dbc.CardBody([
            html.Small(L(lang, "real_portfolio_projection_hint"), className="text-muted d-block mb-2"),
            dcc.Loading(**LOADING_PROPS, children=[dcc.Graph(id="tab3-projection-graph", config=GRAPH_CONFIG)]),
        ]), className="mb-4"),

        html.H5(L(lang, "section_real_portfolio_corr"), className="section-title", id="anchor-tab3-corr"),
        dbc.Card(dbc.CardBody([
            html.Small(L(lang, "real_portfolio_corr_hint"), className="text-muted d-block mb-2"),
            dcc.Loading(**LOADING_PROPS, children=[dcc.Graph(id="tab3-corr-heatmap", config=GRAPH_CONFIG)]),
        ]), className="mb-4"),

        html.H5(L(lang, "section_rebalancing"), className="section-title", id="anchor-tab3-rebalancing"),
        dbc.Card(dbc.CardBody([
            # Rééquilibrage par les flux (portfolio_engine.allocate_contribution) : où placer le
            # prochain versement, sans rien vendre. Montant prérempli avec le rythme mensuel réel.
            html.Div([
                html.Div([dbc.Label(L(lang, "next_contribution_label"), className="mb-0",
                                    html_for="tab3-next-contribution-amount")]
                         + info_tooltip("next-contribution-info", L(lang, "next_contribution_help"))),
                dcc.Input(
                    id="tab3-next-contribution-amount", type="number", min=0, step=10,
                    value=_default_next_contribution(transactions_df), debounce=True,
                    className="form-control form-control-sm", style={"maxWidth": "180px"},
                ),
            ], className="mb-2"),
            dcc.Loading(**LOADING_PROPS, children=[
                html.Div(id="tab3-next-contribution-summary"),
                dcc.Graph(id="tab3-next-contribution-graph", config=GRAPH_CONFIG),
            ]),
            html.Hr(className="my-3"),
            html.Small(L(lang, "rebalancing_hint"), className="text-muted d-block mb-2"),
            html.Div(id="tab3-rebalancing-warning"),
            html.Div(id="tab3-target-container"),
            dash_table.DataTable(id="tab3-rebalancing-table", style_cell=TABLE_BASE_CELL_STYLE),
        ]), className="mb-4"),

        html.H5(L(lang, "section_target_weights"), className="section-title", id="anchor-tab3-weights"),
        dbc.Card(dbc.CardBody([
            weight_form,
            html.Div(id="tab3-weight-form-error", className="text-danger mb-2", style={"fontSize": "0.8rem"}),
            dash_table.DataTable(
                id="tab3-weights-table", row_deletable=True, style_cell=TABLE_BASE_CELL_STYLE,
                data=weights_data,
                columns=[
                    {"name": L(lang, "weight_ticker_label"), "id": "ticker"},
                    {"name": L(lang, "weight_pct_label"), "id": "weight_pct"},
                ],
            ),
        ]), className="mb-4"),

        html.H5(L(lang, "section_log_transaction"), className="section-title", id="anchor-tab3-tx"),
        dbc.Card(dbc.CardBody([
            csv_import_block,
            tx_form,
            html.Div(id="tab3-tx-form-error", className="text-danger mb-2", style={"fontSize": "0.8rem"}),
            dash_table.DataTable(
                id="tab3-tx-table", row_deletable=True, style_cell=TABLE_BASE_CELL_STYLE,
                data=tx_data,
                columns=[
                    {"name": L(lang, "tx_col_ticker"), "id": "ticker"},
                    {"name": L(lang, "tx_col_date"), "id": "date"},
                    {"name": L(lang, "tx_col_amount"), "id": "amount_eur"},
                    {"name": L(lang, "tx_col_price"), "id": "price"},
                    {"name": L(lang, "tx_col_fee"), "id": "fee_eur"},
                ],
            ),
        ]), className="mb-4"),

        html.H5(L(lang, "section_log_dividend"), className="section-title", id="anchor-tab3-div"),
        dbc.Card(dbc.CardBody([
            div_form,
            html.Div(id="tab3-div-form-error", className="text-danger mb-2", style={"fontSize": "0.8rem"}),
            dash_table.DataTable(
                id="tab3-div-table", row_deletable=True, style_cell=TABLE_BASE_CELL_STYLE,
                data=div_data,
                columns=[
                    {"name": L(lang, "div_col_ticker"), "id": "ticker"},
                    {"name": L(lang, "div_col_date"), "id": "date"},
                    {"name": L(lang, "div_col_amount"), "id": "amount_eur"},
                ],
            ),
        ]), className="mb-4"),

        dcc.Store(id="tab3-refresh-trigger", data=0),
    ], className="p-3")


# ---------- Onglet 4 : validation du modèle (backtest walk-forward) ----------
def build_tab4(lang):
    """Backtest walk-forward (voir engine.walk_forward_calibration) : onglet indépendant des 3
    autres, sans State partagé avec eux (indice/horizon/pas propres à ce test) -- seul le
    lancement est explicite (bouton), pas réactif aux curseurs, vu le coût d'une simulation Monte
    Carlo complète par date d'origine testée (voir callbacks/validation.py)."""
    return html.Div([
        html.P(L(lang, "validation_intro"), className="text-muted"),
        html.Div([
            html.Div([
                html.Div([dbc.Label(L(lang, "validation_ticker_label"), className="mb-0")] + info_tooltip(
                    "validation-help-info", L(lang, "validation_help"),
                )),
                dcc.Dropdown(
                    id="validation-ticker-dropdown",
                    options=[{"label": name, "value": name} for name in TICKER_KEYS],
                    value=TICKER_KEYS[0], clearable=False, style={"width": "280px"},
                ),
            ], className="mb-2"),
            html.Div([
                dbc.Label(L(lang, "source_label"), className="mb-0"),
                dcc.RadioItems(
                    id="validation-source-radio",
                    options=[
                        {"label": L(lang, "source_indice"), "value": "indice"},
                        {"label": L(lang, "source_etf"), "value": "etf"},
                    ],
                    # Indice brut par défaut, contrairement au reste de l'appli : les ETF PEA ont
                    # souvent moins de 15 ans d'historique, trop peu pour plus d'une poignée de
                    # dates d'origine une fois retirés la calibration minimale et l'horizon H.
                    value="indice", inline=True,
                ),
                html.Small(L(lang, "validation_source_hint"), className="text-muted d-block"),
            ], className="mb-2"),
            html.Div([
                dbc.Label(L(lang, "validation_horizon_label"), className="mb-0"),
                dcc.RadioItems(
                    id="validation-horizon-radio",
                    options=[
                        {"label": L(lang, "validation_horizon_5y"), "value": 60},
                        {"label": L(lang, "validation_horizon_10y"), "value": 120},
                    ],
                    value=60, inline=True,
                ),
            ], className="mb-2"),
            html.Div([
                dbc.Label(L(lang, "validation_step_label"), className="mb-0"),
                dcc.RadioItems(
                    id="validation-step-radio",
                    options=[
                        {"label": L(lang, "validation_step_monthly"), "value": 1},
                        {"label": L(lang, "validation_step_annual"), "value": 12},
                    ],
                    value=12, inline=True,
                ),
            ], className="mb-2"),
            dbc.Button(
                L(lang, "validation_run_btn"), id="validation-run-btn", color="primary", size="sm",
                className="mt-1",
            ),
        ], className="mb-3"),
        dcc.Loading(**LOADING_PROPS, children=[
            html.Div(id="validation-error", className="text-danger"),
            # Verdict en clair (engine.calibration_verdict) avant les histogrammes, plus techniques.
            html.Div(id="validation-verdict"),
            html.Div(id="validation-info-caption", className="text-muted mb-2", style={"fontSize": "0.85rem"}),
            html.Div([
                html.Div(dcc.Graph(id="validation-pit-graph-normal", config=GRAPH_CONFIG),
                         style={"flex": "1", "minWidth": "0"}),
                html.Div(dcc.Graph(id="validation-pit-graph-bootstrap", config=GRAPH_CONFIG),
                         style={"flex": "1", "minWidth": "0"}),
            ], style={"display": "flex", "gap": "1rem", "flexWrap": "wrap"}),
            html.H5(L(lang, "validation_coverage_table_title"), className="section-title mt-2"),
            dash_table.DataTable(id="validation-coverage-table", style_cell=TABLE_BASE_CELL_STYLE),
        ]),
    ], className="p-3")
