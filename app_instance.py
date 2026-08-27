"""
Instance Dash partagée. Isolée dans son propre module pour que layout.py et
callbacks.py puissent tous les deux s'appuyer dessus sans import circulaire.
"""
import dash_bootstrap_components as dbc
from dash import Dash

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
app.title = "Outils PEA & CTO"
