"""
Construction de l'interface Dash (sidebar, onglets) et petits helpers d'affichage
conditionnel (visible/caché, libellé de taxe...) réutilisés à la fois ici (pour
l'état initial des composants) et par callbacks.py, qui les enregistre comme
callbacks Dash. Ce module ne dépend jamais de callbacks.py ni de l'instance
`app` (pour éviter tout import circulaire).
"""
import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

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

TABLE_BASE_CELL_STYLE = {"fontSize": "0.8rem", "textAlign": "left"}


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
    + [("shrinkage-slider", "value")]
)


# ============================================================
# HELPERS D'AFFICHAGE CONDITIONNEL
# ============================================================
# Fonctions pures (pas de décorateur @app.callback ici) : appelées directement
# ci-dessous pour l'état initial des composants, et enregistrées comme
# callbacks Dash dans callbacks.py.

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
    une case visible et cochable qui ne ferait rien (route_overflow dans callbacks.py reste False
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
    source = gv(v, "source-radio", "indice")
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
        dbc.Button(L(lang, "config_export_btn"), id="btn-download-config", color="primary", size="sm", className="mb-2 w-100"),
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
        dcc.Loading(type="circle", children=[
            html.H5(L(lang, "trajectories_title"), id="tab1-trajectories-title"),
            html.Div([
                html.Div(dcc.Graph(id="tab1-graph-const", config=GRAPH_CONFIG),
                         id="tab1-graph-const-container", style={"flex": "1", "minWidth": "0"}),
                html.Div(dcc.Graph(id="tab1-graph-prog", config=GRAPH_CONFIG),
                         id="tab1-graph-prog-container", style={"flex": "1", "minWidth": "0"}),
            ], style={"display": "flex", "gap": "1rem", "flexWrap": "wrap"}),
            html.Div(id="tab1-metric-cards"),
            html.Div(id="tab1-objective-result", className="mt-2"),
            html.Div(id="tab1-rolling-backtest-result", className="mt-2"),
            html.H5(L(lang, "metrics_title"), id="tab1-metrics-title", className="mt-3"),
            dash_table.DataTable(id="tab1-metrics-table", style_table={"overflowX": "auto"}, style_cell={"fontSize": "0.8rem", "textAlign": "left"}, tooltip_delay=0, tooltip_duration=None),
            html.Div([
                html.H5(L(lang, "compare_pea_cto_title"), className="mt-3"),
                dcc.Graph(id="tab1-envelope-compare-chart", config=GRAPH_CONFIG),
            ], id="tab1-envelope-compare-container", style={"display": "none"}),
            html.Div([
                html.H5(L(lang, "sequence_risk_title"), className="mt-3"),
                html.P(L(lang, "sequence_risk_intro"), className="text-muted", style={"fontSize": "0.8rem"}),
                dcc.Graph(id="tab1-sequence-risk-chart", config=GRAPH_CONFIG),
            ], id="tab1-sequence-risk-container", style={"display": "none"}),
        ]),
        dbc.Button(L(lang, "download_metrics_btn"), id="btn-download-tab1", color="secondary", size="sm", className="mt-2"),
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

        dcc.Loading(type="circle", children=[
            html.H5(L(lang, "corr_title")),
            dcc.Graph(id="tab2-corr-heatmap", config=GRAPH_CONFIG),

            html.H5(L(lang, "suggested_weights_title")),
            dbc.Button(L(lang, "weights_explain_toggle"), id="btn-toggle-weights-explain",
                       color="link", size="sm", className="p-0 mb-2"),
            dbc.Collapse([
                html.Div(L(lang, "weights_explain_text"), className="text-muted mb-2",
                          style={"fontSize": "0.8rem", "whiteSpace": "pre-line"}),
                slider_block(
                    L(lang, "shrinkage_label"), "shrinkage-slider", 0, 100,
                    gv(v, "shrinkage-slider", 50), step=5, help_text=L(lang, "shrinkage_help"),
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

        dcc.Loading(type="circle", children=[
            html.H5(L(lang, "trajectories_title"), id="tab2-trajectories-title"),
            html.Div([
                html.Div(dcc.Graph(id="tab2-graph-const", config=GRAPH_CONFIG),
                         id="tab2-graph-const-container", style={"flex": "1", "minWidth": "0"}),
                html.Div(dcc.Graph(id="tab2-graph-prog", config=GRAPH_CONFIG),
                         id="tab2-graph-prog-container", style={"flex": "1", "minWidth": "0"}),
            ], style={"display": "flex", "gap": "1rem", "flexWrap": "wrap"}),
            html.Div(id="tab2-metric-cards"),
            html.Div(id="tab2-objective-result", className="mt-2"),
            html.Div(id="tab2-rolling-backtest-result", className="mt-2"),
            html.H5(L(lang, "metrics_title_portfolio"), id="tab2-metrics-title", className="mt-3"),
            dash_table.DataTable(id="tab2-metrics-table", style_table={"overflowX": "auto"}, style_cell={"fontSize": "0.8rem", "textAlign": "left"}, tooltip_delay=0, tooltip_duration=None),
            html.Div([
                html.H5(L(lang, "compare_pea_cto_title"), className="mt-3"),
                dcc.Graph(id="tab2-envelope-compare-chart", config=GRAPH_CONFIG),
            ], id="tab2-envelope-compare-container", style={"display": "none"}),
            html.Div([
                html.H5(L(lang, "sequence_risk_title"), className="mt-3"),
                html.P(L(lang, "sequence_risk_intro"), className="text-muted", style={"fontSize": "0.8rem"}),
                dcc.Graph(id="tab2-sequence-risk-chart", config=GRAPH_CONFIG),
            ], id="tab2-sequence-risk-container", style={"display": "none"}),
        ]),
        dbc.Button(L(lang, "download_metrics_btn"), id="btn-download-tab2", color="secondary", size="sm", className="mt-2"),
        dcc.Download(id="download-tab2"),
        dcc.Store(id="tab2-csv-store"),
    ], className="p-3")


def build_header_text(lang):
    return [
        html.H2(L(lang, "app_title")),
        html.P(L(lang, "app_subtitle"), className="text-muted"),
    ]


def build_footer(lang):
    return html.Small(L(lang, "footer_disclaimer"), className="text-muted")


def build_tabs(lang, v=None, active_tab="tab-par-indice"):
    v = v or {}
    return dbc.Tabs([
        dbc.Tab(build_tab1(lang, v), label=L(lang, "tab_par_indice"), tab_id="tab-par-indice"),
        dbc.Tab(build_tab2(lang, v), label=L(lang, "tab_portefeuille"), tab_id="tab-portefeuille"),
    ], id="main-tabs", active_tab=active_tab or "tab-par-indice")
