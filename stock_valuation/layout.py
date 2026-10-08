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

TABLE_BASE_CELL_STYLE = {"fontSize": "0.82rem", "textAlign": "left", "padding": "0.55rem 0.8rem", "minWidth": "95px"}

# Alignées à droite comme il est d'usage pour des valeurs numériques (les décimales s'alignent
# visuellement d'une ligne à l'autre) ; le reste (Entreprise, Ticker, Secteur, Devise) garde
# l'alignement à gauche par défaut de TABLE_BASE_CELL_STYLE. Statique (ne dépend pas du thème
# clair/sombre) : posé directement sur le DataTable dans build_tab3, pas besoin de passer par un
# callback.
NUMERIC_TABLE_COLUMNS = [
    "Prix", "P/E (trailing)", "P/E (prévisionnel)", "PEG", "EV/EBITDA", "P/B",
    "Rendement dividende (%)", "P/E moyen 5 ans (approx.)", "Position vs historique 5 ans (percentile)",
    "Capitalisation",
]
TABLE_CELL_ALIGNMENT = [{"if": {"column_id": c}, "textAlign": "right"} for c in NUMERIC_TABLE_COLUMNS]

# Nav d'ancres sticky en tête de la zone résultats (voir build_tab3) : styles dans
# assets/theme.css (.quick-nav / .quick-nav-link), qui suivent le mode sombre via l'attribut
# data-bs-theme (posé par le clientside_callback du switch, voir app.py).


def table_style_overrides(dark: bool):
    """(style_header, style_cell, style_data) pour un dash_table.DataTable.
    dash_table applique ses propres couleurs par défaut (JS injecté à l'exécution,
    non couvert par le thème Bootstrap) : passer explicitement ces props est le
    seul moyen fiable de le rendre lisible en mode sombre.

    En-tête distinct (fond + bordure basse à l'accent) et bordures horizontales fines plutôt
    qu'un quadrillage complet sur chaque cellule : un vrai tableau de données plutôt que la
    grille brute de dash_table par défaut. Couleurs alignées sur assets/theme.css (--surface,
    --surface-2, --border-soft, --accent) : dupliquées ici en dur faute de pouvoir lire des
    variables CSS depuis Python, à garder synchronisées si la palette du thème change."""
    if dark:
        header_bg, header_fg, accent = "#1f2330", "#e9ecef", "#7b84ff"
        cell_bg, cell_fg, row_border = "#171a23", "#e9ecef", "#2a2f3d"
    else:
        header_bg, header_fg, accent = "#f1f3f9", "#1f2430", "#636efa"
        cell_bg, cell_fg, row_border = "#ffffff", "#1f2430", "#e4e7ef"
    style_header = {
        "backgroundColor": header_bg, "color": header_fg, "fontWeight": "600",
        "borderBottom": f"2px solid {accent}", "borderTop": "none", "borderLeft": "none", "borderRight": "none",
    }
    style_cell = {
        **TABLE_BASE_CELL_STYLE, "backgroundColor": cell_bg, "color": cell_fg,
        "borderBottom": f"1px solid {row_border}", "borderTop": "none", "borderLeft": "none", "borderRight": "none",
    }
    style_data = {"backgroundColor": cell_bg, "color": cell_fg}
    return style_header, style_cell, style_data


def pe_history_conditional_style(dark: bool):
    """style_data_conditional pour la colonne P/E (trailing), basé sur le percentile du titre vs
    SA PROPRE histoire 5 ans, jamais un seuil générique : l'intro de l'app dit explicitement
    qu'un P/E bas ou haut dans l'absolu ne veut rien dire, ça dépend du secteur et des
    perspectives de croissance (voir "intro3" dans i18n.py). Vert = décoté vs sa propre histoire
    (percentile < 20), rouge = tendu vs sa propre histoire (percentile > 80). Zone intermédiaire
    (20-80) volontairement non colorée : voir la section "Validité du signal P/E historique"
    (engine.pe_signal_forward_returns) pour une vérification empirique de ce signal avant de le
    lire comme un conseil.

    Référence la colonne technique "_pe_pct_for_style" (voir callbacks.render_stock_views), pas
    directement "Position vs historique 5 ans (percentile)" : dash_table (bundle v7.4.1) n'a pas
    d'opérateur "is not blank" utilisable ici (syntaxe rejetée côté client, qui casse le rendu
    entier du tableau — vérifié en pratique) pour exclure les valeurs manquantes d'un filter_query
    numérique ; sans cette exclusion, un percentile manquant (None, titre sans assez d'historique,
    ex. Michelin) se comparait comme < 20 et se coloriait vert à tort. La colonne technique
    substitue un None par 50 (ni < 20 ni > 80), qui retombe donc naturellement en zone neutre."""
    style_col = "_pe_pct_for_style"
    if dark:
        green, red = "#173a24", "#3a1616"
        green_fg, red_fg = "#8fd19e", "#e88a8a"
    else:
        green, red = "#d4edda", "#f8d7da"
        green_fg, red_fg = "#155724", "#721c24"
    return [
        {"if": {"column_id": "P/E (trailing)", "filter_query": f"{{{style_col}}} < 20"},
         "backgroundColor": green, "color": green_fg},
        {"if": {"column_id": "P/E (trailing)", "filter_query": f"{{{style_col}}} > 80"},
         "backgroundColor": red, "color": red_fg},
    ]


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
        dbc.Button(L(lang, "load_btn"), id="btn-load-stocks", color="primary", className="mb-2"),
        # Avance par petits pas pendant que load_stock_valuations tourne (voir callbacks.py) :
        # un chargement à froid de tout un gros panier (plusieurs centaines de titres jamais mis
        # en cache) prend par nature une bonne minute (latence Yahoo Finance, hors de notre
        # contrôle — testé : plus de threads en parallèle n'accélère rien, le palier vient d'eux,
        # pas de nous). Ce texte ne rend pas le chargement plus rapide, juste visiblement vivant
        # au lieu d'un spinner figé qui donne l'impression d'un plantage.
        html.Div(id="stocks-load-progress", className="text-muted mb-1", style={"fontSize": "0.8rem"}),
        dcc.Interval(id="load-progress-interval", interval=500, n_intervals=0),
        html.Div(id="stocks-warning"),
        dcc.Store(id="stocks-raw-store"),

        # Masqué (style posé par render_stock_views) tant qu'aucune donnée n'est chargée : évite
        # d'empiler cinq gros placeholders vides à l'écran initial.
        html.Div(id="stocks-results-container", style={"display": "none"}, children=[
            html.Div([
                html.A(L(lang, "sector_compare_title"), href="#anchor-sector", className="quick-nav-link"),
                html.A(L(lang, "pe_backtest_title"), href="#anchor-pe-backtest", className="quick-nav-link"),
                html.A(L(lang, "detail_title"), href="#anchor-table", className="quick-nav-link"),
                html.A(L(lang, "history_title"), href="#anchor-history", className="quick-nav-link"),
                html.A(L(lang, "quality_title"), href="#anchor-quality", className="quick-nav-link"),
                html.A(L(lang, "dcf_title"), href="#anchor-dcf", className="quick-nav-link"),
            ], className="quick-nav"),

            dcc.Loading(type="circle", color="#636efa", children=[
                html.H5(L(lang, "sector_compare_title"), id="anchor-sector", className="section-title"),
                dbc.Row([
                    dbc.Col(dcc.Graph(id="stocks-sector-bar", config=GRAPH_CONFIG), width=6),
                    dbc.Col(dcc.Graph(id="stocks-sector-box", config=GRAPH_CONFIG), width=6),
                ]),
                html.P(L(lang, "sector_box_caption"), className="text-muted", style={"fontSize": "0.8rem"}),
            ]),

            html.Hr(),
            html.H5(L(lang, "pe_backtest_title"), className="section-title", id="anchor-pe-backtest"),
            html.P(L(lang, "pe_backtest_intro"), className="text-muted", style={"fontSize": "0.85rem"}),
            dcc.Loading(type="circle", color="#636efa", children=[
                html.Div(id="pe-backtest-result", children=L(lang, "pe_backtest_hint_default")),
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

            dcc.Loading(type="circle", color="#636efa", children=[
                html.Div(id="stocks-top-cards"),
                html.H5(L(lang, "pe_ratio_by_stock_title"), className="section-title"),
                dcc.Graph(id="stocks-pe-chart", config=GRAPH_CONFIG),
                html.H5(L(lang, "detail_title"), className="section-title", id="anchor-table"),
                html.P(L(lang, "detail_hint"), className="text-muted", style={"fontSize": "0.8rem"}),
                dash_table.DataTable(
                    id="stocks-table",
                    sort_action="native",
                    row_selectable="single",
                    selected_rows=[],
                    # Hauteur bornée + scroll interne : condition pour que fixed_rows/fixed_columns
                    # ci-dessous aient un sens (sans plafond, le tableau grandit avec ses lignes et
                    # c'est la page entière qui défile — rien ne "fige" dans ce cas, dash_table n'a
                    # de quoi figer que par rapport à SON PROPRE scroll interne).
                    style_table={"overflowX": "auto", "overflowY": "auto", "maxHeight": "70vh", "minWidth": "100%"},
                    style_cell=TABLE_BASE_CELL_STYLE,
                    style_cell_conditional=TABLE_CELL_ALIGNMENT,
                    style_header_conditional=TABLE_CELL_ALIGNMENT,
                    fixed_rows={"headers": True},
                    fixed_columns={"headers": True, "data": 1},
                    tooltip_delay=0, tooltip_duration=None,
                ),
                html.H5(L(lang, "history_title"), className="section-title", id="anchor-history"),
                html.Div(id="stocks-pe-history-title", className="text-muted", style={"fontSize": "0.85rem"}),
                dcc.Graph(id="stocks-pe-history-chart", config=GRAPH_CONFIG),

                html.H5(L(lang, "quality_title"), className="section-title", id="anchor-quality"),
                html.Div(id="quality-metrics-card"),

                html.Hr(),
                html.H5(L(lang, "dcf_title"), className="section-title", id="anchor-dcf"),
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
