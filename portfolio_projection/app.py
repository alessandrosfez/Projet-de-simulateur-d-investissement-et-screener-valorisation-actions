"""
Projection PEA/CTO : simulation Monte Carlo interactive (version Dash)
====================================================================
Projet autonome (aucune dépendance vers ../stock_valuation) : combien épargner
et selon quel scénario, pas quoi acheter (voir le projet frère pour ça).

Point d'entrée : assemble l'instance Dash (app_instance.py), le layout
(layout.py) et les callbacks (callbacks.py, importé pour son effet de bord :
l'enregistrement des callbacks sur `app`).

Auteur : Alessandro
Usage  : python app.py
Prérequis : pip install -r requirements.txt
"""
import os

import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html

import callbacks  # noqa: F401 (l'import enregistre les callbacks sur `app`)
import layout
from app_instance import app
from i18n import L, PALETTE_CODES, PALETTE_NAMES

app.clientside_callback(
    """
    function(n_intervals) {
        window.dispatchEvent(new Event('resize'));
        return '';
    }
    """,
    Output("resize-kick-dummy", "children"),
    Input("resize-kick", "n_intervals"),
)

app.clientside_callback(
    f"""
    function(isDark) {{
        document.body.classList.toggle('dark-mode', !!isDark);
        // Bootstrap 5.3+ garde certaines variables (dont la couleur du texte) derrière cet
        // attribut : sans lui, la feuille de style sombre change les fonds mais pas le texte.
        document.documentElement.setAttribute('data-bs-theme', isDark ? 'dark' : 'light');
        return isDark ? "{dbc.themes.DARKLY}" : "{dbc.themes.BOOTSTRAP}";
    }}
    """,
    Output("theme-stylesheet", "href"),
    Input("dark-mode-switch", "value"),
)

app.clientside_callback(
    """
    function(active_tab) {
        [50, 200, 500].forEach(function(delay) {
            setTimeout(function(){ window.dispatchEvent(new Event('resize')); }, delay);
        });
        return window.dash_clientside.no_update;
    }
    """,
    Output("resize-kick-dummy", "children", allow_duplicate=True),
    Input("main-tabs", "active_tab"),
    prevent_initial_call=True,
)

# Rend les 3 menus déroulants ticker de l'onglet "portefeuille réel" "creatable" : un dcc.Dropdown
# n'accepte normalement que les valeurs présentes dans `options`, hors cette app accepte n'importe
# quel ticker, pas seulement ceux déjà vus (voir layout.build_tab3) -- ce callback ajoute le texte
# tapé à la volée aux options dès qu'il ne s'y trouve pas déjà, pour qu'il devienne sélectionnable.
# Entièrement côté client (pas d'aller-retour serveur à chaque frappe) ; coexiste avec
# callbacks.refresh_tab3, qui réécrit les mêmes `options` depuis la base à chaque rafraîchissement
# (allow_duplicate=True des deux côtés, aucune dépendance circulaire : les deux ont des Inputs
# différents).
_CREATABLE_TICKER_DROPDOWN_JS = """
function(search_value, current_options) {
    if (!search_value) { return window.dash_clientside.no_update; }
    const ticker = search_value.trim().toUpperCase();
    if (!ticker) { return window.dash_clientside.no_update; }
    const options = current_options || [];
    if (options.some(function(opt) { return opt.value === ticker; })) {
        return window.dash_clientside.no_update;
    }
    return options.concat([{label: ticker, value: ticker}]);
}
"""
for _dropdown_id in ("tab3-tx-ticker-input", "tab3-div-ticker-input", "tab3-weight-ticker-input",
                     "tab3-benchmark-ticker-input"):
    app.clientside_callback(
        _CREATABLE_TICKER_DROPDOWN_JS,
        Output(_dropdown_id, "options", allow_duplicate=True),
        Input(_dropdown_id, "search_value"),
        State(_dropdown_id, "options"),
        prevent_initial_call=True,
    )


# Construit après l'import de callbacks : build_sidebar()/build_tabs() appellent des helpers
# (update_tax_label(), toggle_etf_info()...) qui doivent déjà être enregistrés comme callbacks.
app.layout = dbc.Container([
    html.Link(id="theme-stylesheet", rel="stylesheet", href=dbc.themes.DARKLY),
    dbc.Row([
        dbc.Col(html.Div(layout.build_header_text("fr"), id="header-text-container"), width=9),
        dbc.Col([
            dbc.Label(L("fr", "lang_label"), id="lang-label", className="mb-0", style={"fontSize": "0.8rem"}),
            dcc.RadioItems(
                id="lang-radio",
                options=[{"label": " FR", "value": "fr"}, {"label": " EN", "value": "en"}],
                value="fr", inline=True, persistence=True, persistence_type="local",
                className="mb-2",
            ),
            dbc.Label(L("fr", "palette_label"), id="palette-label", className="mb-0", style={"fontSize": "0.8rem"}),
            dcc.Dropdown(
                id="palette-dropdown",
                options=[{"label": PALETTE_NAMES["fr"][code], "value": code} for code in PALETTE_CODES],
                value="default", clearable=False, persistence=True, persistence_type="local",
                className="mb-2",
            ),
            dbc.Switch(
                id="dark-mode-switch", label=L("fr", "dark_mode_label"),
                value=True, persistence=True, persistence_type="local",
            ),
        ], width=3),
    ], className="mt-2 align-items-start app-header"),
    dbc.Row([
        dbc.Col(html.Div(layout.build_sidebar("fr", {}), id="sidebar-container"), width=3, id="sidebar-col", className="sidebar-panel"),
        dbc.Col(html.Div(layout.build_tabs("fr", {}), id="tabs-container"), width=9, id="main-col"),
    ]),
    html.Hr(className="mt-4"),
    html.Div(layout.build_footer("fr"), id="footer-container", className="text-center mb-2"),
    dcc.Interval(id="resize-kick", interval=300, n_intervals=0, max_intervals=8),
    html.Div(id="resize-kick-dummy", style={"display": "none"}),
], fluid=True, className="px-3 px-lg-5")


if __name__ == "__main__":
    # 127.0.0.1 par défaut : le lien affiché dans le terminal est alors cliquable. En conteneur
    # Docker, la variable HOST=0.0.0.0 (voir Dockerfile) est nécessaire pour rester joignable
    # depuis l'extérieur du conteneur.
    # threaded=True : sans ça, le serveur de dev traite une requête à la fois. Plusieurs
    # sections (indices, corrélations) déclenchent des téléchargements yfinance non mis en
    # cache au premier chargement ; sans multi-threading, un changement de paramètre reste
    # bloqué en attente derrière ces requêtes lentes au lieu d'être traité en parallèle.
    # debug=False par défaut (sécurité/perf) : DASH_DEBUG=1 réactive le rechargement à chaud en
    # développement local. Comparaison de chaîne explicite plutôt que bool(os.environ.get(...)) :
    # bool("0") vaut True en Python, un simple DASH_DEBUG=0 activerait sinon le mode debug.
    debug = os.environ.get("DASH_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
    app.run(debug=debug, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 8050)), threaded=True)
