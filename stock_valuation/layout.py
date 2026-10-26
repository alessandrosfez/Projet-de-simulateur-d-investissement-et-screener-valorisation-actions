"""
Construction de l'interface Dash (un seul écran, pas de sidebar : cet outil n'a
qu'un seul mode) et petits helpers réutilisés à la fois ici (pour l'état initial
des composants) et par callbacks.py, qui les enregistre comme callbacks Dash.
Ce module ne dépend jamais de callbacks.py ni de l'instance `app` (pour éviter
tout import circulaire).
"""
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
from dash import dcc, html

from constants import UNIVERSE_CODES
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

# Alignées à droite comme il est d'usage pour des valeurs numériques (les décimales s'alignent
# d'une ligne à l'autre) ; Entreprise, Ticker, Secteur et Devise restent alignés à gauche.
NUMERIC_TABLE_COLUMNS = [
    "Score", "Prix", "P/E (trailing)", "P/E (prévisionnel)", "PEG", "EV/EBITDA", "P/B",
    "Rendement dividende (%)", "P/E moyen 5 ans (approx.)", "Position vs historique 5 ans (percentile)",
]
PE_PERCENTILE_COLUMN = "Position vs historique 5 ans (percentile)"

# Coloration des cellules : classes .cell-good / .cell-warn / .cell-bad de assets/theme.css, qui
# suivent le mode sombre. Chaque règle teste d'abord la présence de la valeur : une donnée manquante
# n'est jamais coloriée (dash_table, faute d'opérateur « non vide », obligeait à remplacer les
# manquants par 50 dans des colonnes techniques ; AG Grid évalue une vraie expression).
# - PEG : < 1 croissance pas chère payée, 1-2 neutre, > 2 chère payée ; un PEG négatif ou nul
#   (croissance estimée négative) n'a pas de sens et reste non colorié.
# - Score composite : >= 70 haut du classement, 40-70 neutre, < 40 bas du classement.
# - P/E (trailing) : coloré selon le percentile du titre dans SA PROPRE histoire, jamais un seuil
#   générique (un P/E bas ou haut dans l'absolu ne veut rien dire, voir « intro3 » dans i18n.py) :
#   < 20 décoté, > 80 tendu, entre les deux volontairement neutre. Voir la section « Validité du
#   signal P/E historique » (engine.pe_signal_forward_returns) avant de le lire comme un conseil.
_PCT = f"params.data['{PE_PERCENTILE_COLUMN}']"
CELL_CLASS_RULES = {
    "PEG": {
        "cell-good": "params.value != null && params.value > 0 && params.value < 1",
        "cell-warn": "params.value != null && params.value >= 1 && params.value <= 2",
        "cell-bad": "params.value != null && params.value > 2",
    },
    "Score": {
        "cell-good": "params.value != null && params.value >= 70",
        "cell-warn": "params.value != null && params.value >= 40 && params.value < 70",
        "cell-bad": "params.value != null && params.value < 40",
    },
    "P/E (trailing)": {
        "cell-good": f"{_PCT} != null && {_PCT} < 20",
        "cell-bad": f"{_PCT} != null && {_PCT} > 80",
    },
}
# Largeurs fixes (px), ajustées au contenu : le dimensionnement automatique d'AG Grid s'exécute
# quand la grille est encore vide (données chargées plus tard par callback) et laisserait toutes
# les colonnes à 200 px. Les en-têtes longs passent sur plusieurs lignes.
COLUMN_WIDTHS = {
    "Entreprise": 180, "Ticker": 100, "Score": 88, "Secteur": 170, "Devise": 84, "Prix": 92,
    "P/E (trailing)": 100, "P/E (prévisionnel)": 132, "PEG": 80, "EV/EBITDA": 104, "P/B": 76,
    "Rendement dividende (%)": 120, "P/E moyen 5 ans (approx.)": 124, PE_PERCENTILE_COLUMN: 136,
    "Capitalisation": 140,
}
# Deux décimales, « N/A » pour une valeur manquante (jamais 0), virgule décimale en français.
NUMBER_FORMATTERS = {
    "fr": {"function": "params.value == null ? 'N/A' : d3.format('.2f')(params.value).replace('.', ',')"},
    "en": {"function": "params.value == null ? 'N/A' : d3.format('.2f')(params.value)"},
}

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

def empty_state(kind: str, title: str, text: str, action_label: str | None = None, action_href: str | None = None):
    """État vide illustré (assets/empty_<kind>_light|dark.svg, selon le thème) : ce qui manque et
    l'action qui le remplit, au lieu d'une phrase grise isolée. Recopié à l'identique dans les trois
    outils (pas d'import croisé)."""
    children = [
        html.Img(src=f"/assets/empty_{kind}_light.svg", alt="", className="empty-art art-light"),
        html.Img(src=f"/assets/empty_{kind}_dark.svg", alt="", className="empty-art art-dark"),
        html.Div(title, className="empty-title"),
        html.Div(text, className="empty-text"),
    ]
    if action_label and action_href:
        children.append(html.A([html.I(className="bi bi-arrow-down-circle me-1", **{"aria-hidden": "true"}),
                                action_label], href=action_href, className="btn btn-primary btn-sm mt-2"))
    return html.Div(children, className="empty-state")


def stocks_column_defs(labels: dict[str, str], help_texts: dict[str, str], lang: str = "fr") -> list[dict]:
    """Colonnes du tableau de criblage : libellé traduit, définition en infobulle d'en-tête,
    format numérique et coloration. La première colonne (Entreprise) reste figée au défilement
    horizontal."""
    defs = []
    for column, label in labels.items():
        col = {"field": column, "headerName": label, "width": COLUMN_WIDTHS.get(column, 110)}
        if column in help_texts:
            col["headerTooltip"] = help_texts[column]
        if column in NUMERIC_TABLE_COLUMNS:
            col.update(type="rightAligned", valueFormatter=NUMBER_FORMATTERS.get(lang, NUMBER_FORMATTERS["fr"]))
        elif column == "Capitalisation":
            col["type"] = "rightAligned"
        if column in CELL_CLASS_RULES:
            col["cellClassRules"] = CELL_CLASS_RULES[column]
        if column == "Entreprise":
            col["pinned"] = "left"
        defs.append(col)
    return defs


# Nav d'ancres sticky en tête de la zone résultats (voir build_tab3) : styles dans
# assets/theme.css (.quick-nav / .quick-nav-link), qui suivent le mode sombre via l'attribut
# data-bs-theme (posé par le clientside_callback du switch, voir app.py).


# Champs dont la valeur doit survivre à un changement de langue (voir gv() et
# callbacks.rebuild_on_language_change) : pas d'export/import JSON dans ce
# projet (contrairement à portfolio_projection), juste la persistance de
# session normale. La watchlist (watchlist-dropdown) n'a PAS de persistance navigateur — testé et
# abandonné, voir le commentaire sur sa définition plus bas — mais reste ici pour survivre au
# moins à un changement de langue en cours de session, comme le reste de ces champs.
TAB_STATE_FIELDS = [
    ("universe-checklist", "value"), ("sector-filter", "value"),
    ("filter-pe-max", "value"), ("filter-peg-max", "value"), ("filter-div-min", "value"), ("filter-score-min", "value"),
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


def build_journal_panel(lang):
    """Journal d'investissement (journal_db.py) : formulaire d'une entrée par titre, rappel des revues
    dues et fiches des entrées (callbacks.render_journal). Volontairement hors de TAB_STATE_FIELDS :
    le contenu vient de la base, relue à chaque reconstruction ; seul un brouillon non enregistré
    serait perdu à un changement de langue."""
    return html.Div([
        html.Div([html.I(className="bi bi-journal-text me-2", **{"aria-hidden": "true"}), L(lang, "journal_title")]
                 + info_tooltip("journal-info", L(lang, "journal_help")), className="watch-title"),
        html.Div(id="journal-reviews-due"),
        dbc.Row([
            dbc.Col([
                dbc.Label(L(lang, "journal_ticker_label"), html_for="journal-ticker", className="journal-label"),
                dcc.Dropdown(id="journal-ticker", options=[], placeholder=L(lang, "journal_ticker_placeholder")),
            ], xs=12, md=5),
            dbc.Col([
                dbc.Label(L(lang, "journal_target_label"), html_for="journal-target", className="journal-label"),
                dcc.Input(id="journal-target", type="number", min=0, step="any", placeholder="—",
                          className="form-control form-control-sm"),
            ], xs=6, md=3),
            dbc.Col([
                dbc.Label(L(lang, "journal_review_label"), html_for="journal-review-date", className="journal-label"),
                dcc.Input(id="journal-review-date", type="date", className="form-control form-control-sm"),
            ], xs=6, md=4),
        ], className="gx-3 gy-2 mb-2"),
        dbc.Label(L(lang, "journal_thesis_label"), html_for="journal-thesis", className="journal-label"),
        dcc.Textarea(id="journal-thesis", placeholder=L(lang, "journal_thesis_placeholder"),
                     className="form-control form-control-sm journal-thesis-input"),
        html.Div([
            dbc.Button(icon_label("save", L(lang, "journal_save_btn")), id="btn-journal-save",
                       color="primary", size="sm"),
            html.Span(id="journal-save-feedback", className="journal-feedback"),
        ], className="d-flex align-items-center gap-2 mt-2"),
        html.Div(id="journal-entries", className="mt-2"),
        dcc.Store(id="journal-refresh-trigger", data=0),
    ], className="watch-panel journal-panel mb-3", id="anchor-journal")


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
        dbc.Button(icon_label("cloud-arrow-down", L(lang, "load_btn")), id="btn-load-stocks", color="primary", className="mb-2"),
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

        # État vide illustré tant qu'aucune donnée n'est chargée (masqué ensuite par render_stock_views).
        html.Div(empty_state("stocks", L(lang, "empty_stocks_title"), L(lang, "empty_stocks_text")),
                 id="stocks-empty-state", className="mb-3"),
        # Masqué (style posé par render_stock_views) tant qu'aucune donnée n'est chargée : évite
        # d'empiler cinq gros placeholders vides à l'écran initial.
        html.Div(id="stocks-results-container", style={"display": "none"}, children=[
            html.Div([
                html.A(L(lang, "sector_compare_title"), href="#anchor-sector", className="quick-nav-link"),
                html.A(L(lang, "pe_backtest_title"), href="#anchor-pe-backtest", className="quick-nav-link"),
                html.A(L(lang, "detail_title"), href="#anchor-table", className="quick-nav-link"),
                html.A(L(lang, "history_title"), href="#anchor-history", className="quick-nav-link"),
                html.A(L(lang, "quality_title"), href="#anchor-quality", className="quick-nav-link"),
                html.A(L(lang, "track_record_title"), href="#anchor-track-record", className="quick-nav-link"),
                html.A(L(lang, "dcf_title"), href="#anchor-dcf", className="quick-nav-link"),
            ], className="quick-nav"),

            dcc.Loading(**LOADING_PROPS, children=[
                html.H5(L(lang, "sector_compare_title"), id="anchor-sector", className="section-title"),
                dcc.Graph(id="stocks-sector-strip", config=GRAPH_CONFIG),
                html.P(L(lang, "sector_box_caption"), className="text-muted", style={"fontSize": "0.8rem"}),
            ]),

            html.Hr(),
            html.H5(L(lang, "pe_backtest_title"), className="section-title", id="anchor-pe-backtest"),
            html.P(L(lang, "pe_backtest_intro"), className="text-muted", style={"fontSize": "0.85rem"}),
            dcc.Loading(**LOADING_PROPS, children=[
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
                               placeholder="—", className="form-control form-control-sm", style={"width": "80px"},
                               persistence=True, persistence_type="local"),
                ], width="auto"),
                dbc.Col([
                    dbc.Label(L(lang, "filter_peg_max_label"), className="mb-0", style={"fontSize": "0.8rem"}),
                    dcc.Input(id="filter-peg-max", type="number", min=0, step=0.1, value=gv(v, "filter-peg-max", None),
                               placeholder="—", className="form-control form-control-sm", style={"width": "80px"},
                               persistence=True, persistence_type="local"),
                ], width="auto"),
                dbc.Col([
                    dbc.Label(L(lang, "filter_div_min_label"), className="mb-0", style={"fontSize": "0.8rem"}),
                    dcc.Input(id="filter-div-min", type="number", min=0, step=0.5, value=gv(v, "filter-div-min", None),
                               placeholder="—", className="form-control form-control-sm", style={"width": "90px"},
                               persistence=True, persistence_type="local"),
                ], width="auto"),
                dbc.Col([
                    dbc.Label(L(lang, "filter_score_min_label"), className="mb-0", style={"fontSize": "0.8rem"}),
                    dcc.Input(id="filter-score-min", type="number", min=0, max=100, step=1,
                               value=gv(v, "filter-score-min", None),
                               placeholder="—", className="form-control form-control-sm", style={"width": "80px"},
                               persistence=True, persistence_type="local"),
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
            ], className="mb-2"),
            # Alertes des titres suivis (engine.watchlist_alerts), indépendantes des filtres du tableau.
            dcc.Loading(**LOADING_PROPS, children=[html.Div(id="watchlist-alerts", className="mb-3")]),
            build_journal_panel(lang),

            dcc.Loading(**LOADING_PROPS, children=[
                html.Div(id="stocks-top-cards"),
                html.H5(L(lang, "pe_ratio_by_stock_title"), className="section-title"),
                dcc.Graph(id="stocks-pe-chart", config=GRAPH_CONFIG),
                html.H5(L(lang, "detail_title"), className="section-title", id="anchor-table"),
                html.P(L(lang, "detail_hint"), className="text-muted", style={"fontSize": "0.8rem"}),
                # AG Grid : tri, redimensionnement et colonne figée natifs, sélection d'une ligne
                # (case ou clic) ; getRowId garde la sélection quand les données se rechargent
                # (changement de langue, de thème ou de filtre qui la laisse visible).
                dag.AgGrid(
                    id="stocks-table",
                    rowData=[], columnDefs=[],
                    getRowId="params.data.Ticker",
                    defaultColDef={"sortable": True, "resizable": True, "minWidth": 72,
                                   "wrapHeaderText": True, "autoHeaderHeight": True},
                    dashGridOptions={
                        "rowSelection": {"mode": "singleRow", "checkboxes": True, "enableClickSelection": True},
                        "selectionColumnDef": {"pinned": "left"},
                        "tooltipShowDelay": 0, "tooltipHideDelay": 60000,
                        "suppressDragLeaveHidesColumns": True,
                    },
                    className="pea-grid", style={"height": "70vh"},
                ),
                html.H5(L(lang, "history_title"), className="section-title", id="anchor-history"),
                html.Div(id="stocks-pe-history-title", className="text-muted", style={"fontSize": "0.85rem"}),
                dcc.Graph(id="stocks-pe-history-chart", config=GRAPH_CONFIG),

                html.H5(L(lang, "quality_title"), className="section-title", id="anchor-quality"),
                html.Div(id="quality-metrics-card"),

                html.H5(L(lang, "track_record_title"), className="section-title", id="anchor-track-record"),
                html.Div(id="track-record-card"),

                html.Hr(),
                html.H5(L(lang, "dcf_title"), className="section-title", id="anchor-dcf"),
                html.P(L(lang, "dcf_intro"), className="text-muted", style={"fontSize": "0.85rem"}),
                dbc.Row([
                    dbc.Col(slider_block(L(lang, "dcf_growth_label"), "dcf-growth-slider", -10, 30, gv(v, "dcf-growth-slider", DCF_DEFAULTS["growth_pct"]), step=1, tooltip_text=L(lang, "dcf_growth_help")), width=3),
                    dbc.Col(slider_block(L(lang, "dcf_discount_label"), "dcf-discount-slider", 4, 20, gv(v, "dcf-discount-slider", DCF_DEFAULTS["discount_pct"]), step=0.5, tooltip_text=L(lang, "dcf_discount_help")), width=3),
                    dbc.Col(slider_block(L(lang, "dcf_terminal_growth_label"), "dcf-terminal-growth-slider", 0, 5, gv(v, "dcf-terminal-growth-slider", DCF_DEFAULTS["terminal_growth_pct"]), step=0.25, tooltip_text=L(lang, "dcf_terminal_growth_help")), width=3),
                    dbc.Col(slider_block(L(lang, "dcf_horizon_label"), "dcf-horizon-slider", 3, 10, gv(v, "dcf-horizon-slider", DCF_DEFAULTS["horizon_years"]), step=1, tooltip_text=L(lang, "dcf_horizon_help")), width=3),
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
            dbc.Button(icon_label("filetype-csv", L(lang, "download_btn")), id="btn-download-stocks", color="secondary", size="sm", className="mt-2"),
        ]),
        dcc.Download(id="download-stocks"),
        dcc.Store(id="stocks-csv-store"),
    ], className="p-3")


# Hypothèses DCF par défaut : position initiale des curseurs ET hypothèses de l'alerte « cours sous
# le DCF » de la liste de suivi (callbacks.update_watchlist_alerts), pour qu'elles ne divergent pas.
DCF_DEFAULTS = {"growth_pct": 5, "discount_pct": 8, "terminal_growth_pct": 2, "horizon_years": 5}


# Navigation entre les outils du dépôt (en-tête) : la page d'accueil est servie par run_all.py ; un
# outil lancé seul (Docker, app.py) garde ces liens, qui ne répondent alors que si les autres tournent.
HOME_URL = "http://localhost:8049"
TOOL_URLS = {"projection": "http://localhost:8050", "valuation": "http://localhost:8051",
             "analysis": "http://localhost:8052"}
CURRENT_TOOL = "valuation"


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
