"""
Construction de l'interface Dash (un seul écran, pas de sidebar : cet outil n'a
qu'un seul mode) et petits helpers réutilisés à la fois ici (pour l'état initial
des composants) et par callbacks.py, qui les enregistre comme callbacks Dash.
Ce module ne dépend jamais de callbacks.py ni de l'instance `app` (pour éviter
tout import circulaire).
"""
import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

from constants import UNIVERSE_CODES
from i18n import L

GRAPH_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "select2d", "lasso2d", "autoScale2d",
        "hoverCompareCartesian", "hoverClosestCartesian", "toggleSpikelines",
    ],
}

TABLE_BASE_CELL_STYLE = {"fontSize": "0.8rem", "textAlign": "left"}

# Nav d'ancres sticky en tête de la zone résultats (voir build_tab3) : utilise les variables
# CSS Bootstrap (--bs-body-bg, --bs-border-color) plutôt qu'un CSS dédié dans assets/, pour
# suivre automatiquement le mode sombre (posé via data-bs-theme, voir app.py).
QUICK_NAV_STYLE = {
    "position": "sticky", "top": "0", "zIndex": 1020,
    "backgroundColor": "var(--bs-body-bg)", "borderBottom": "1px solid var(--bs-border-color)",
    "padding": "0.5rem 0", "marginBottom": "1rem",
}
QUICK_NAV_LINK_STYLE = {"marginRight": "1.25rem", "fontSize": "0.85rem"}


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


def peg_conditional_style(dark: bool):
    """style_data_conditional pour la colonne PEG du tableau : vert (<1, croissance pas chère
    payée), orange (1-2), rouge (>2, croissance chère payée) — lecture usuelle du PEG. PEG
    négatif ou nul (croissance négative estimée) volontairement non coloré : le signal n'a pas
    de sens dans ce cas."""
    if dark:
        green, amber, red = "#173a24", "#3a2f12", "#3a1616"
        green_fg, amber_fg, red_fg = "#8fd19e", "#e0c46c", "#e88a8a"
    else:
        green, amber, red = "#d4edda", "#fff3cd", "#f8d7da"
        green_fg, amber_fg, red_fg = "#155724", "#856404", "#721c24"
    return [
        {"if": {"column_id": "PEG", "filter_query": "{PEG} > 0 && {PEG} < 1"},
         "backgroundColor": green, "color": green_fg},
        {"if": {"column_id": "PEG", "filter_query": "{PEG} >= 1 && {PEG} <= 2"},
         "backgroundColor": amber, "color": amber_fg},
        {"if": {"column_id": "PEG", "filter_query": "{PEG} > 2"},
         "backgroundColor": red, "color": red_fg},
    ]


# Champs dont la valeur doit survivre à un changement de langue (voir gv() et
# callbacks.rebuild_on_language_change) : pas d'export/import JSON dans ce
# projet (contrairement à portfolio_projection), juste la persistance de
# session normale. La watchlist (watchlist-dropdown) n'a PAS de persistance navigateur — testé et
# abandonné, voir le commentaire sur sa définition plus bas — mais reste ici pour survivre au
# moins à un changement de langue en cours de session, comme le reste de ces champs.
TAB_STATE_FIELDS = [
    ("universe-checklist", "value"), ("sector-filter", "value"),
    ("filter-pe-max", "value"), ("filter-peg-max", "value"), ("filter-div-min", "value"),
    ("watchlist-dropdown", "value"), ("watchlist-only-switch", "value"),
    ("dcf-growth-slider", "value"), ("dcf-discount-slider", "value"),
    ("dcf-terminal-growth-slider", "value"), ("dcf-horizon-slider", "value"),
    ("dcf-growth-offset-slider", "value"), ("dcf-discount-offset-slider", "value"),
    ("dcf-weight-bear-input", "value"), ("dcf-weight-base-input", "value"), ("dcf-weight-bull-input", "value"),
]


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


def build_tab3(lang, v=None):
    v = v or {}
    return html.Div([
        html.P(L(lang, "intro1"), className="text-muted"),
        dbc.Button(L(lang, "intro_more_toggle"), id="btn-toggle-intro-details",
                   color="link", size="sm", className="p-0 mb-2 d-block"),
        dbc.Collapse([
            html.P(L(lang, "intro2"), className="text-muted", style={"fontSize": "0.85rem"}),
            html.P(L(lang, "intro3"), className="text-muted", style={"fontSize": "0.85rem"}),
            html.P(L(lang, "intro4"), className="text-muted", style={"fontSize": "0.85rem"}),
        ], id="intro-details-collapse", is_open=False, className="mb-2"),

        dbc.Label(L(lang, "markets_label"), className="mb-0"),
        dcc.Checklist(
            id="universe-checklist",
            options=[{"label": f" {L(lang, f'universe_{code}')}", "value": code} for code in UNIVERSE_CODES],
            value=gv(v, "universe-checklist", ["cac40"]), labelStyle={"display": "block"}, className="mb-2",
        ),
        dbc.Button(L(lang, "load_btn"), id="btn-load-stocks", color="primary", className="mb-3"),
        html.Div(id="stocks-warning"),
        dcc.Store(id="stocks-raw-store"),

        # Masqué (style posé par render_stock_views) tant qu'aucune donnée n'est chargée : évite
        # d'empiler cinq gros placeholders vides à l'écran initial.
        html.Div(id="stocks-results-container", style={"display": "none"}, children=[
            html.Div([
                html.A(L(lang, "sector_compare_title"), href="#anchor-sector", style=QUICK_NAV_LINK_STYLE),
                html.A(L(lang, "detail_title"), href="#anchor-table", style=QUICK_NAV_LINK_STYLE),
                html.A(L(lang, "history_title"), href="#anchor-history", style=QUICK_NAV_LINK_STYLE),
                html.A(L(lang, "quality_title"), href="#anchor-quality", style=QUICK_NAV_LINK_STYLE),
                html.A(L(lang, "dcf_title"), href="#anchor-dcf", style=QUICK_NAV_LINK_STYLE),
            ], style=QUICK_NAV_STYLE),

            dcc.Loading(type="circle", children=[
                html.H5(L(lang, "sector_compare_title"), id="anchor-sector"),
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

            dbc.Label(L(lang, "screening_filters_label"), className="mb-1"),
            dbc.Row([
                dbc.Col([
                    dbc.Label(L(lang, "filter_pe_max_label"), className="mb-0", style={"fontSize": "0.8rem"}),
                    dcc.Input(id="filter-pe-max", type="number", min=0, step=1, value=gv(v, "filter-pe-max", None),
                               placeholder="—", className="form-control form-control-sm"),
                ], width="auto"),
                dbc.Col([
                    dbc.Label(L(lang, "filter_peg_max_label"), className="mb-0", style={"fontSize": "0.8rem"}),
                    dcc.Input(id="filter-peg-max", type="number", min=0, step=0.1, value=gv(v, "filter-peg-max", None),
                               placeholder="—", className="form-control form-control-sm"),
                ], width="auto"),
                dbc.Col([
                    dbc.Label(L(lang, "filter_div_min_label"), className="mb-0", style={"fontSize": "0.8rem"}),
                    dcc.Input(id="filter-div-min", type="number", min=0, step=0.5, value=gv(v, "filter-div-min", None),
                               placeholder="—", className="form-control form-control-sm"),
                ], width="auto"),
            ], className="mb-3 gx-4"),

            dbc.Label(L(lang, "watchlist_label"), className="mb-1"),
            dbc.Row([
                dbc.Col(
                    # Volontairement sans persistence navigateur : la watchlist ne survit qu'à la
                    # session en cours (retour à vide au rechargement de la page). Testé avec
                    # persistence=True (natif) et avec un dcc.Store dédié storage_type="local" :
                    # les deux se sont heurtés au même comportement erratique au rechargement
                    # (le storage repassait à [] avant que la restauration n'ait pu s'appliquer,
                    # course entre l'hydratation cliente du storage et le premier aller-retour de
                    # callback) sans qu'une cause précise n'ait pu être isolée. Pas bloquant pour
                    # l'usage (choisir des valeurs, filtrer dessus pendant qu'on explore le
                    # tableau), donc pas retenté pour l'instant plutôt que de perdre plus de temps
                    # dessus.
                    dcc.Dropdown(
                        id="watchlist-dropdown", options=[], value=gv(v, "watchlist-dropdown", []), multi=True,
                        placeholder=L(lang, "watchlist_placeholder"),
                    ), width=8,
                ),
                dbc.Col(
                    dbc.Checklist(
                        id="watchlist-only-switch",
                        options=[{"label": L(lang, "watchlist_only_label"), "value": "only"}],
                        value=gv(v, "watchlist-only-switch", []), switch=True,
                    ), width=4, className="d-flex align-items-center",
                ),
            ], className="mb-3"),

            dcc.Loading(type="circle", children=[
                html.Div(id="stocks-top-cards"),
                html.H5(L(lang, "pe_ratio_by_stock_title"), className="mt-3"),
                dcc.Graph(id="stocks-pe-chart", config=GRAPH_CONFIG),
                html.H5(L(lang, "detail_title"), className="mt-3", id="anchor-table"),
                html.P(L(lang, "detail_hint"), className="text-muted", style={"fontSize": "0.8rem"}),
                dash_table.DataTable(
                    id="stocks-table",
                    sort_action="native",
                    row_selectable="single",
                    selected_rows=[],
                    style_table={"overflowX": "auto"},
                    style_cell={"fontSize": "0.8rem", "textAlign": "left"},
                ),
                html.H5(L(lang, "history_title"), className="mt-3", id="anchor-history"),
                html.Div(id="stocks-pe-history-title", className="text-muted", style={"fontSize": "0.85rem"}),
                dcc.Graph(id="stocks-pe-history-chart", config=GRAPH_CONFIG),

                html.H5(L(lang, "quality_title"), className="mt-3", id="anchor-quality"),
                html.Div(id="quality-metrics-card"),

                html.Hr(),
                html.H5(L(lang, "dcf_title"), className="mt-3", id="anchor-dcf"),
                html.P(L(lang, "dcf_intro"), className="text-muted", style={"fontSize": "0.85rem"}),
                dbc.Row([
                    dbc.Col(slider_block(L(lang, "dcf_growth_label"), "dcf-growth-slider", -10, 30, gv(v, "dcf-growth-slider", 5), step=1, tooltip_text=L(lang, "dcf_growth_help")), width=3),
                    dbc.Col(slider_block(L(lang, "dcf_discount_label"), "dcf-discount-slider", 4, 20, gv(v, "dcf-discount-slider", 8), step=0.5, tooltip_text=L(lang, "dcf_discount_help")), width=3),
                    dbc.Col(slider_block(L(lang, "dcf_terminal_growth_label"), "dcf-terminal-growth-slider", 0, 5, gv(v, "dcf-terminal-growth-slider", 2), step=0.25, tooltip_text=L(lang, "dcf_terminal_growth_help")), width=3),
                    dbc.Col(slider_block(L(lang, "dcf_horizon_label"), "dcf-horizon-slider", 3, 10, gv(v, "dcf-horizon-slider", 5), step=1, tooltip_text=L(lang, "dcf_horizon_help")), width=3),
                ]),
                dbc.Button(L(lang, "dcf_scenario_toggle"), id="btn-toggle-dcf-scenarios",
                           color="link", size="sm", className="p-0 mb-2"),
                dbc.Collapse([
                    dbc.Row([
                        dbc.Col(slider_block(L(lang, "dcf_growth_offset_label"), "dcf-growth-offset-slider", 0, 15, gv(v, "dcf-growth-offset-slider", 5), step=1), width=3),
                        dbc.Col(slider_block(L(lang, "dcf_discount_offset_label"), "dcf-discount-offset-slider", 0, 5, gv(v, "dcf-discount-offset-slider", 2), step=0.5), width=3),
                        dbc.Col([
                            dbc.Label(L(lang, "dcf_weight_bear_label"), className="mb-0"),
                            dcc.Input(id="dcf-weight-bear-input", type="number", min=0, step=5, value=gv(v, "dcf-weight-bear-input", 25), className="form-control form-control-sm"),
                        ], width=2),
                        dbc.Col([
                            dbc.Label(L(lang, "dcf_weight_base_label"), className="mb-0"),
                            dcc.Input(id="dcf-weight-base-input", type="number", min=0, step=5, value=gv(v, "dcf-weight-base-input", 50), className="form-control form-control-sm"),
                        ], width=2),
                        dbc.Col([
                            dbc.Label(L(lang, "dcf_weight_bull_label"), className="mb-0"),
                            dcc.Input(id="dcf-weight-bull-input", type="number", min=0, step=5, value=gv(v, "dcf-weight-bull-input", 25), className="form-control form-control-sm"),
                        ], width=2),
                    ], className="align-items-end"),
                    html.Div(id="dcf-scenario-weights-caption", className="text-muted mb-2", style={"fontSize": "0.75rem"}),
                ], id="dcf-scenario-collapse", is_open=False, className="mb-2"),
                html.Div(id="dcf-result", children=L(lang, "dcf_hint_default"), className="text-muted mb-2"),
                dcc.Graph(id="dcf-chart", config=GRAPH_CONFIG),
            ]),
            dbc.Button(L(lang, "download_btn"), id="btn-download-stocks", color="secondary", size="sm", className="mt-2"),
        ]),
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
