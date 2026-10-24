"""
Thème visuel commun des graphiques Plotly (recopié à l'identique dans les trois outils du dépôt,
sans import croisé, voir le README racine).

Deux modèles Plotly, "pea_light" et "pea_dark", enregistrés à l'import de ce module :
- fonds transparents : le graphique prend la couleur de la carte qui le contient (assets/theme.css),
  au lieu du rectangle noir #111 de plotly_dark posé sur des cartes #171a23 ;
- police Inter et encres du thème de la page, grilles et axes en retrait, infobulles aux couleurs
  des cartes ;
- palette catégorielle validée (contraste, daltonisme) pour chaque mode.

Palette « Défaut » : palette de référence du skill dataviz, mêmes 8 teintes en clair et en sombre,
chaque mode avec ses propres pas. Validée sur les fonds réels de l'application (#ffffff et
#171a23) : bande de luminance, saturation, séparation entre couleurs voisines sous les trois formes
de daltonisme (ΔE ≥ 8,4) et en vision normale (ΔE ≥ 19,3). En clair, trois teintes (aqua, jaune,
magenta) restent sous 3:1 de contraste : admis parce que chaque série a une légende ou un libellé.
L'ancienne palette (celle de Plotly) échouait à la bande de luminance dans les deux modes.
"""
import plotly.graph_objects as go
import plotly.io as pio

from i18n import PALETTES

SERIES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SERIES_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]

# Encres et traits, alignés sur les variables de assets/theme.css (--surface, --border-soft).
CHROME = {
    "light": {"ink": "#1f2433", "muted": "#5b6275", "grid": "#e9ecf3", "axis": "#c9cedb",
              "hover_bg": "#ffffff", "hover_border": "#e4e7ef", "surface": "#ffffff"},
    "dark": {"ink": "#e6e8ef", "muted": "#9aa1b2", "grid": "#262b38", "axis": "#3a4052",
             "hover_bg": "#1f2330", "hover_border": "#2a2f3d", "surface": "#171a23"},
}
FONT_FAMILY = "Inter, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"


def palette_for(code: str | None, dark: bool) -> list[str]:
    """Palette choisie par l'utilisateur ; « Défaut » prend la variante du mode affiché."""
    if code in (None, "default") or code not in PALETTES:
        return SERIES_DARK if dark else SERIES_LIGHT
    return PALETTES[code]


def surface_color(dark: bool) -> str:
    """Couleur des cartes, pour les liserés qui séparent deux parts d'un anneau ou deux barres."""
    return CHROME["dark" if dark else "light"]["surface"]


def blend(color: str, other: str, weight: float) -> str:
    """Mélange de deux couleurs hexadécimales : weight = part de other (0 = color inchangée). Sert aux
    nuances d'une même teinte, par exemple les lignes d'un même indice dans le graphique soleil."""
    a = [int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(other.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * weight):02x}" for x, y in zip(a, b))


def _build(mode: str) -> go.layout.Template:
    c = CHROME[mode]
    base = pio.templates["plotly_dark" if mode == "dark" else "plotly_white"]
    template = go.layout.Template(base)
    axis = dict(gridcolor=c["grid"], linecolor=c["axis"], zerolinecolor=c["axis"], zeroline=False,
                tickfont=dict(color=c["muted"], size=11), title=dict(font=dict(color=c["muted"], size=12)),
                showline=True, ticks="")
    template.layout.update(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_FAMILY, color=c["ink"], size=12),
        title=dict(font=dict(size=15, color=c["ink"]), x=0.01, xanchor="left"),
        colorway=SERIES_DARK if mode == "dark" else SERIES_LIGHT,
        xaxis=axis, yaxis=axis,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=c["muted"], size=11)),
        hoverlabel=dict(bgcolor=c["hover_bg"], bordercolor=c["hover_border"],
                        font=dict(family=FONT_FAMILY, color=c["ink"], size=12)),
        margin=dict(t=56, r=16, b=40, l=16),
    )
    return template


pio.templates["pea_light"] = _build("light")
pio.templates["pea_dark"] = _build("dark")


def template(dark: bool) -> str:
    return "pea_dark" if dark else "pea_light"
