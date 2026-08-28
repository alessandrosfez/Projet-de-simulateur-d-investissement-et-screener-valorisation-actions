"""
Constructeurs de graphiques Plotly, indépendants de Dash (pas de callback ici).
"""
import plotly.graph_objects as go


def empty_figure_with_message(message: str, dark: bool = False) -> go.Figure:
    """Graphique vide avec un message centré, pour un état 'pas encore de données' propre
    plutôt qu'une grille vide qui ressemble à une erreur."""
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark" if dark else "plotly",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        annotations=[dict(
            text=message, xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=13, color="gray"),
        )],
        margin=dict(t=20, b=20, l=20, r=20),
    )
    return fig
