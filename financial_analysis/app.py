"""
Analyse financière : qualité et solidité des comptes d'une société (version Dash)
================================================================================
Projet autonome (aucune dépendance vers ../portfolio_projection ni ../stock_valuation) : les comptes
sont-ils fiables et solides ? Pas combien épargner, ni quoi acheter (voir les projets frères).

Point d'entrée : assemble l'instance Dash (app_instance.py), le layout (layout.py) et les callbacks
(callbacks.py, importé pour son effet de bord : l'enregistrement des callbacks sur `app`).

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


# Pas de sidebar (comme stock_valuation) : un seul outil, tous ses contrôles dans le corps de la
# page. La zone de résultats et le Store du ticker analysé sont HORS de main-content-container
# (reconstruit à chaque changement de langue) : ils survivent ainsi à la reconstruction, et les
# résultats sont régénérés dans la nouvelle langue par leur propre callback, sans dépendre de
# l'ordre d'exécution entre reconstruction et rendu.
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
    html.Div(layout.build_main("fr", {}), id="main-content-container"),
    dcc.Store(id="analysis-ticker-store"),
    # Saisies de la vision Transaction Services ({ticker: {...}}), conservées pour la session du
    # navigateur : survivent au changement de langue et au passage d'une société à l'autre.
    dcc.Store(id="adjustments-store", storage_type="session"),
    # Hors de results-container : le bouton d'export y est recréé à chaque rendu, le téléchargement non.
    dcc.Download(id="databook-download"),
    dcc.Loading(type="circle", color="#636efa", children=[html.Div(id="results-container", className="px-3")]),
    # Module Benford : ses contrôles sont reconstruits au changement de langue, mais le fichier importé
    # (benford-file-store) et le résultat (benford-result) restent hors de cette zone, pour ne jamais
    # perdre l'import ni dépendre de l'ordre d'exécution entre reconstruction et calcul.
    dcc.Store(id="benford-file-store"),
    html.Div(layout.build_benford("fr", {}, None), id="benford-container"),
    dcc.Loading(type="circle", color="#636efa", children=[html.Div(id="benford-result", className="px-3")]),
    html.Hr(className="mt-4"),
    html.Div(layout.build_footer("fr"), id="footer-container", className="text-center mb-2"),
    dcc.Interval(id="resize-kick", interval=300, n_intervals=0, max_intervals=8),
    html.Div(id="resize-kick-dummy", style={"display": "none"}),
], fluid=True, className="px-3 px-lg-5")


if __name__ == "__main__":
    # 127.0.0.1 par défaut : le lien affiché dans le terminal est alors cliquable. En conteneur
    # Docker, la variable HOST=0.0.0.0 (voir Dockerfile) est nécessaire pour rester joignable
    # depuis l'extérieur du conteneur.
    # threaded=True : sans ça, le serveur de dev traite une requête à la fois, et un premier
    # téléchargement yfinance lent bloquerait toute l'interface.
    # debug=False par défaut (sécurité/perf) : DASH_DEBUG=1 réactive le rechargement à chaud en
    # développement local. Comparaison de chaîne explicite plutôt que bool(os.environ.get(...)) :
    # bool("0") vaut True en Python, un simple DASH_DEBUG=0 activerait sinon le mode debug.
    debug = os.environ.get("DASH_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
    app.run(debug=debug, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 8052)), threaded=True)
