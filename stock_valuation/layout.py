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


# Champs dont la valeur doit survivre à un changement de langue (voir gv() et
# callbacks.rebuild_on_language_change) : pas d'export/import JSON dans ce
# projet (contrairement à portfolio_projection), juste la persistance de
# session normale.
TAB_STATE_FIELDS = [
    ("universe-checklist", "value"), ("sector-filter", "value"),
    ("dcf-growth-slider", "value"), ("dcf-discount-slider", "value"),
    ("dcf-terminal-growth-slider", "value"), ("dcf-horizon-slider", "value"),
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
