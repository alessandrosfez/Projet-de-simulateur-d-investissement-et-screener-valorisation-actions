"""
Construction de l'interface Dash (sidebar, onglets) et petits helpers d'affichage
conditionnel (visible/caché, libellé de taxe...) réutilisés à la fois ici (pour
l'état initial des composants) et par callbacks.py, qui les enregistre comme
callbacks Dash. Ce module ne dépend jamais de callbacks.py ni de l'instance
`app` (pour éviter tout import circulaire).
"""
import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

from constants import CTO_FLAT_TAX_RATE, N_PORTFOLIOS_MAX, PEA_TAX_RATE, TICKER_KEYS, TICKERS, ETF_NAMES, UNIVERSE_CODES
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
    ("apport_constant", "apport-constant-slider", "value"),
    ("apport_initial", "apport-initial-slider", "value"),
    ("apport_final", "apport-final-slider", "value"),
    ("annual_fee_pct", "fee-slider", "value"),
    ("inflation_pct", "inflation-slider", "value"),
    ("display_radio", "display-radio", "value"),
    ("apply_tax", "tax-checkbox", "value"),
    ("envelope", "envelope-radio", "value"),
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
    + [("universe-checklist", "value"), ("sector-filter", "value"), ("shrinkage-slider", "value")]
    + [("dcf-growth-slider", "value"), ("dcf-discount-slider", "value"),
       ("dcf-terminal-growth-slider", "value"), ("dcf-horizon-slider", "value")]
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


def toggle_sidebar(active_tab):
    if active_tab == "tab-actions":
        return {"display": "none"}, 0, 12
    return {"height": "100vh", "overflowY": "auto"}, 3, 9


def toggle_decumulation(v):
    return {"display": "block"} if v and "on" in v else {"display": "none"}


def toggle_objective(v):
    return {"display": "block"} if v and "on" in v else {"display": "none"}


def toggle_block_size(method):
    return {"display": "block"} if method == "bootstrap" else {"display": "none"}


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
    n_portfolios = int(n_portfolios or 1)
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
        slider_block(L(lang, "horizon_label"), "horizon-slider", 5, 40, gv(v, "horizon-slider", 20)),
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
    ]

    withdrawals_crisis_section = [
        html.H6(L(lang, "decumulation_title")),
        dcc.Checklist(id="decumulation-checkbox", options=[{"label": L(lang, "decumulation_checkbox"), "value": "on"}], value=decum_val, className="mb-2"),
        html.Div([
            slider_block(L(lang, "decumulation_years_label"), "decumulation-years-slider", 1, 40, gv(v, "decumulation-years-slider", 20)),
            slider_block(L(lang, "withdrawal_label"), "withdrawal-monthly-slider", 100, 5000, gv(v, "withdrawal-monthly-slider", 1000), step=100),
        ], id="decumulation-options-container", style=toggle_decumulation(decum_val)),

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
    ]

    contrib_section = [
        html.H6(L(lang, "contrib_constant_title")),
        slider_block(L(lang, "contrib_constant_label"), "apport-constant-slider", 100, 1000, gv(v, "apport-constant-slider", 350), step=10),

        html.H6(L(lang, "contrib_progressive_title"), className="mt-3"),
        slider_block(L(lang, "contrib_initial_label"), "apport-initial-slider", 100, 1000, gv(v, "apport-initial-slider", 200), step=10),
        slider_block(L(lang, "contrib_final_label"), "apport-final-slider", 100, 1000, gv(v, "apport-final-slider", 500), step=10),
    ]

    fees_tax_section = [
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
        dcc.Checklist(
            id="compare-envelopes-checkbox",
            options=[{"label": L(lang, "compare_checkbox"), "value": "on"}],
            value=gv(v, "compare-envelopes-checkbox", []), className="mb-2",
        ),
    ]

    display_sim_section = [
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
        dbc.AccordionItem(withdrawals_crisis_section, title=L(lang, "section_withdrawals_crisis"), item_id="item-retraits-crise"),
        dbc.AccordionItem(contrib_section, title=L(lang, "section_contributions"), item_id="item-contrib"),
        dbc.AccordionItem(fees_tax_section, title=L(lang, "section_fees_tax"), item_id="item-fees"),
        dbc.AccordionItem(display_sim_section, title=L(lang, "section_display_sim"), item_id="item-sim"),
        dbc.AccordionItem(config_section, title=L(lang, "section_config"), item_id="item-config"),
    ], always_open=True, active_item=["item-data", "item-contrib", "item-fees"], flush=True)

    return html.Div(accordion, style={"height": "100vh", "overflowY": "auto", "padding": "1rem"})


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
            html.H5(L(lang, "trajectories_title")),
            dbc.Row([
                dbc.Col(dcc.Graph(id="tab1-graph-const", config=GRAPH_CONFIG), width=6),
                dbc.Col(dcc.Graph(id="tab1-graph-prog", config=GRAPH_CONFIG), width=6),
            ]),
            html.Div(id="tab1-metric-cards"),
            html.Div(id="tab1-objective-result", className="mt-2"),
            html.H5(L(lang, "metrics_title"), className="mt-3"),
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
            html.H5(L(lang, "trajectories_title")),
            dbc.Row([
                dbc.Col(dcc.Graph(id="tab2-graph-const", config=GRAPH_CONFIG), width=6),
                dbc.Col(dcc.Graph(id="tab2-graph-prog", config=GRAPH_CONFIG), width=6),
            ]),
            html.Div(id="tab2-metric-cards"),
            html.Div(id="tab2-objective-result", className="mt-2"),
            html.H5(L(lang, "metrics_title_portfolio"), className="mt-3"),
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


# ---------- Onglet 3 : valorisation d'actions individuelles (P/E) ----------
def build_tab3(lang, v=None):
    v = v or {}
    return html.Div([
        html.P(L(lang, "intro1"), className="text-muted"),
        html.P(L(lang, "intro2"), className="text-muted", style={"fontSize": "0.85rem"}),
        html.P(L(lang, "intro3"), className="text-muted", style={"fontSize": "0.85rem"}),
        html.P(L(lang, "intro4"), className="text-muted", style={"fontSize": "0.85rem"}),

        dbc.Label(L(lang, "markets_label"), className="mb-0"),
        dcc.Checklist(
            id="universe-checklist",
            options=[{"label": f" {L(lang, f'universe_{code}')}", "value": code} for code in UNIVERSE_CODES],
            value=gv(v, "universe-checklist", ["cac40"]), labelStyle={"display": "block"}, className="mb-2",
        ),
        dbc.Button(L(lang, "load_btn"), id="btn-load-stocks", color="primary", className="mb-3"),
        html.Div(id="stocks-warning"),
        dcc.Store(id="stocks-raw-store"),

        dcc.Loading(type="circle", children=[
            html.H5(L(lang, "sector_compare_title")),
            dbc.Row([
                dbc.Col(dcc.Graph(id="stocks-sector-bar", config=GRAPH_CONFIG), width=6),
                dbc.Col(dcc.Graph(id="stocks-sector-box", config=GRAPH_CONFIG), width=6),
            ]),
        ]),

        html.Hr(),
        dbc.Label(L(lang, "sector_filter_label"), className="mb-0"),
        dcc.Dropdown(
            id="sector-filter",
            options=[{"label": L(lang, "sector_all"), "value": "all"}], value=gv(v, "sector-filter", "all"), clearable=False,
            className="mb-3", style={"maxWidth": "420px"},
        ),

        dcc.Loading(type="circle", children=[
            html.Div(id="stocks-top-cards"),
            html.H5(L(lang, "pe_ratio_by_stock_title"), className="mt-3"),
            dcc.Graph(id="stocks-pe-chart", config=GRAPH_CONFIG),
            html.H5(L(lang, "detail_title"), className="mt-3"),
            html.P(L(lang, "detail_hint"), className="text-muted", style={"fontSize": "0.8rem"}),
            dash_table.DataTable(
                id="stocks-table",
                sort_action="native",
                row_selectable="single",
                selected_rows=[],
                style_table={"overflowX": "auto"},
                style_cell={"fontSize": "0.8rem", "textAlign": "left"},
            ),
            html.H5(L(lang, "history_title"), className="mt-3"),
            html.Div(id="stocks-pe-history-title", className="text-muted", style={"fontSize": "0.85rem"}),
            dcc.Graph(id="stocks-pe-history-chart", config=GRAPH_CONFIG),

            html.Hr(),
            html.H5(L(lang, "dcf_title"), className="mt-3"),
            html.P(L(lang, "dcf_intro"), className="text-muted", style={"fontSize": "0.85rem"}),
            dbc.Row([
                dbc.Col(slider_block(L(lang, "dcf_growth_label"), "dcf-growth-slider", -10, 30, gv(v, "dcf-growth-slider", 5), step=1, tooltip_text=L(lang, "dcf_growth_help")), width=3),
                dbc.Col(slider_block(L(lang, "dcf_discount_label"), "dcf-discount-slider", 4, 20, gv(v, "dcf-discount-slider", 8), step=0.5, tooltip_text=L(lang, "dcf_discount_help")), width=3),
                dbc.Col(slider_block(L(lang, "dcf_terminal_growth_label"), "dcf-terminal-growth-slider", 0, 5, gv(v, "dcf-terminal-growth-slider", 2), step=0.25, tooltip_text=L(lang, "dcf_terminal_growth_help")), width=3),
                dbc.Col(slider_block(L(lang, "dcf_horizon_label"), "dcf-horizon-slider", 3, 10, gv(v, "dcf-horizon-slider", 5), step=1, tooltip_text=L(lang, "dcf_horizon_help")), width=3),
            ]),
            html.Div(id="dcf-result", children=L(lang, "dcf_hint_default"), className="text-muted mb-2"),
            dcc.Graph(id="dcf-chart", config=GRAPH_CONFIG),
        ]),
        dbc.Button(L(lang, "download_btn"), id="btn-download-stocks", color="secondary", size="sm", className="mt-2"),
        dcc.Download(id="download-stocks"),
        dcc.Store(id="stocks-csv-store"),
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
        dbc.Tab(build_tab3(lang, v), label=L(lang, "tab_valorisation"), tab_id="tab-actions"),
    ], id="main-tabs", active_tab=active_tab or "tab-par-indice")
