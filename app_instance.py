"""
Instance Dash partagée. Isolée dans son propre module pour que layout.py et
callbacks.py puissent tous les deux s'appuyer dessus sans import circulaire.

Le thème Bootstrap n'est pas passé en `external_stylesheets` ici : il est injecté
via un <link> dans app.py dont le `href` bascule entre clair/sombre (voir
dark-mode-switch), pour permettre le changement de thème sans rechargement.
"""
from dash import Dash

app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "Outils PEA & CTO"
