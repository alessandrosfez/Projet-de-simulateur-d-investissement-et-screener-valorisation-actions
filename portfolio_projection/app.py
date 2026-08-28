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
from dash import Input, Output, dcc, html

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


# Construit après l'import de callbacks : build_sidebar()/build_tabs() appellent des helpers
# (update_tax_label(), toggle_etf_info()...) qui doivent déjà être enregistrés comme callbacks.
app.layout = dbc.Container([
    html.Link(id="theme-stylesheet", rel="stylesheet", href=dbc.themes.BOOTSTRAP),
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
                value=False, persistence=True, persistence_type="local",
            ),
        ], width=3),
    ], className="mt-2 align-items-start"),
    dbc.Row([
        dbc.Col(html.Div(layout.build_sidebar("fr", {}), id="sidebar-container"), width=3, id="sidebar-col", className="border-end"),
        dbc.Col(html.Div(layout.build_tabs("fr", {}), id="tabs-container"), width=9, id="main-col"),
    ]),
    html.Hr(className="mt-4"),
    html.Div(layout.build_footer("fr"), id="footer-container", className="text-center mb-2"),
    dcc.Interval(id="resize-kick", interval=300, n_intervals=0, max_intervals=8),
    html.Div(id="resize-kick-dummy", style={"display": "none"}),
], fluid=True)


if __name__ == "__main__":
    # 127.0.0.1 par défaut : le lien affiché dans le terminal est alors cliquable. En conteneur
    # Docker, la variable HOST=0.0.0.0 (voir Dockerfile) est nécessaire pour rester joignable
    # depuis l'extérieur du conteneur.
    # threaded=True : sans ça, le serveur de dev traite une requête à la fois. Plusieurs
    # sections (indices, corrélations) déclenchent des téléchargements yfinance non mis en
    # cache au premier chargement ; sans multi-threading, un changement de paramètre reste
    # bloqué en attente derrière ces requêtes lentes au lieu d'être traité en parallèle.
    app.run(debug=True, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 8050)), threaded=True)
