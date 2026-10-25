"""
Construction de l'interface Dash (un seul écran, pas de sidebar, comme stock_valuation) et helpers
d'affichage réutilisés par callbacks.py (mise en forme des montants, texte de provenance, tableaux
d'états financiers). Ce module ne dépend jamais de callbacks.py ni de l'instance `app` (pour éviter
tout import circulaire), et ne fait aucun calcul financier : tout chiffre affiché vient d'engine.py.
"""
import dash_bootstrap_components as dbc
import pandas as pd
from dash import dash_table, dcc, html

from charts import make_benford_chart
from constants import CAC40_TICKERS
from engine import (
    ALTMAN_MODELS, BENEISH_COEFFICIENTS, BENEISH_INDICES, BENEISH_REFERENCE_MEANS, BENEISH_THRESHOLD, FIELD_SCHEMA,
    PEER_METRICS, PIOTROSKI_CRITERIA, NormalizedStatements, beneish_verdict, beneish_m_score_from_indices,
)
from i18n import TRANSLATIONS, L

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

TABLE_BASE_CELL_STYLE = {"fontSize": "0.82rem", "textAlign": "right", "padding": "0.45rem 0.8rem", "minWidth": "95px"}

# Champs dont la valeur doit survivre à un changement de langue (voir gv() et
# callbacks.rebuild_on_language_change).
TAB_STATE_FIELDS = [
    ("ticker-input", "value"), ("benford-source-radio", "value"), ("benford-column-dropdown", "value"),
    ("benford-sign-radio", "value"), ("benford-min-amount-input", "value"),
]

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


def table_style_overrides(dark: bool):
    """(style_header, style_cell, style_data) pour un dash_table.DataTable, recopié de
    stock_valuation : dash_table applique ses propres couleurs par défaut, non couvertes par le
    thème Bootstrap, et passer ces props est le seul moyen fiable de le rendre lisible en mode
    sombre. Couleurs alignées sur assets/theme.css (à garder synchronisées)."""
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


def info_tooltip(info_id, tooltip_text):
    """ⓘ cliquable/survolable renvoyant un (Span, Tooltip) à ajouter à côté d'un libellé."""
    return [
        html.Span(" ⓘ", id=info_id, style={"cursor": "help"}),
        dbc.Tooltip(tooltip_text, target=info_id, placement="right"),
    ]


def gv(v, cid, default):
    """Valeur courante d'un composant lors d'une reconstruction (changement de langue), ou défaut."""
    if v and v.get(cid) is not None:
        return v[cid]
    return default


# ============================================================
# Mise en forme
# ============================================================

def format_number(value: float, spec: str, lang: str) -> str:
    """Nombre mis en forme selon spec (« .2f », « +.3f », « ,.0f »...) avec les conventions de la
    langue : virgule décimale en français, point en anglais, espace comme séparateur de milliers dans
    les deux (convention déjà employée partout dans l'outil). Seul point de passage des nombres
    affichés, pour qu'aucun « 2.87 » ne subsiste dans un texte français."""
    text = format(value, spec).replace(",", " ")
    return text.replace(".", ",") if lang == "fr" else text


def format_amount(value: float | None, lang: str) -> str:
    """Montant abrégé (Md/M en français, bn/m en anglais), signe conservé ; « n.d. » si None.
    Les états financiers se comptent en milliards : les afficher en entier les rendrait illisibles."""
    if value is None:
        return L(lang, "na")
    sign = "-" if value < 0 else ""
    abs_value = abs(value)
    for threshold, unit_key in ((1e9, "unit_billion"), (1e6, "unit_million")):
        if abs_value >= threshold:
            return f"{sign}{format_number(abs_value / threshold, ',.2f', lang)} {L(lang, unit_key)}"
    return f"{sign}{format_number(abs_value, ',.0f', lang)}"


def format_year(year: pd.Timestamp, lang: str) -> str:
    return year.strftime(L(lang, "date_format"))


def _formula_text(operator: str, operands: tuple[str, ...], lang: str) -> str:
    symbol = " + " if operator == "sum" else " − "
    return symbol.join(L(lang, f"field_{key}") for key in operands)


def provenance_text(origin: dict, lang: str) -> str:
    """Phrase qui explique d'où vient une valeur normalisée (ou pourquoi elle manque), à partir de
    la provenance produite par engine.normalize_statements."""
    source = origin.get("source")
    if source in ("published", "equivalent"):
        statement = L(lang, f"statement_{origin['statement']}")
        return L(lang, f"prov_{source}", label=origin["label"], statement=statement)
    if source == "imported":
        return L(lang, "prov_imported")
    if source == "derived":
        return L(lang, "prov_derived", formula=_formula_text(origin["operator"], origin["operands"], lang))
    if origin.get("reason") == "derivation_inputs_missing":
        return L(
            lang, "prov_missing_derivation",
            formula=_formula_text(origin["operator"], origin["operands"], lang),
            missing=", ".join(L(lang, f"field_{key}") for key in origin["missing_operands"]),
        )
    if origin.get("reason") == "not_in_import":
        return L(lang, "prov_missing_not_in_import")
    return L(lang, "prov_missing_not_in_yfinance")


def statement_table(normalized: NormalizedStatements, statement: str, lang: str, dark: bool, table_id: str):
    """DataTable d'un état financier : une ligne par poste interne, une colonne par exercice.

    Chaque cellule porte sa provenance en infobulle (tooltip_data), et une colonne technique cachée
    par exercice (_prov_yN) sert au style conditionnel : dash_table ne sait pas styler une cellule
    selon une donnée qui n'est pas dans la ligne, d'où ces colonnes présentes dans `data` mais
    absentes de `columns`, même technique que stock_valuation pour ses couleurs de signal."""
    year_ids = [f"y{i}" for i in range(len(normalized.years))]
    columns = [{"name": L(lang, "col_item"), "id": "item"}] + [
        {"name": format_year(year, lang), "id": year_id} for year, year_id in zip(normalized.years, year_ids)
    ]
    rows, tooltips = [], []
    for spec in FIELD_SCHEMA:
        if spec.statement != statement:
            continue
        row = {"item": L(lang, f"field_{spec.key}")}
        tooltip = {"item": {"value": L(lang, f"field_{spec.key}_help"), "type": "text"}}
        for year, year_id in zip(normalized.years, year_ids):
            origin = normalized.provenance[spec.key][year]
            row[year_id] = format_amount(normalized.get(spec.key, year), lang)
            row[f"_prov_{year_id}"] = origin["source"]
            tooltip[year_id] = {"value": provenance_text(origin, lang), "type": "text"}
        rows.append(row)
        tooltips.append(tooltip)

    style_header, style_cell, style_data = table_style_overrides(dark)
    muted = "#8b93a7" if dark else "#8a8f99"
    conditional = []
    for year_id in year_ids:
        for source in ("derived", "equivalent"):
            conditional.append({
                "if": {"column_id": year_id, "filter_query": f"{{_prov_{year_id}}} = {source}"},
                "fontStyle": "italic",
            })
        conditional.append({
            "if": {"column_id": year_id, "filter_query": f"{{_prov_{year_id}}} = missing"},
            "color": muted,
        })
    return dash_table.DataTable(
        id=table_id, columns=columns, data=rows, tooltip_data=tooltips,
        tooltip_delay=0, tooltip_duration=None,
        style_header=style_header, style_cell=style_cell, style_data=style_data,
        style_cell_conditional=[{"if": {"column_id": "item"}, "textAlign": "left", "minWidth": "260px"}],
        style_data_conditional=conditional,
        style_table={"overflowX": "auto"},
    )


# ============================================================
# Ratios : affichage et détail du calcul
# ============================================================
# Unité d'affichage de chaque ratio : multiple (1,52x), pourcentage (-5,0 %) ou jours (44 j).
RATIO_KINDS = {
    "cfo_to_net_income": "multiple", "fcf_to_net_income": "multiple", "sloan_accruals": "percent",
    "dso": "days", "dio": "days", "dpo": "days", "ccc": "days",
}
# Sens favorable d'une évolution, pour colorer la colonne Évolution : +1 = une hausse est bonne
# (plus de cash par euro de résultat), -1 = une baisse est bonne (moins d'accruals, clients payés
# plus vite, stocks qui tournent plus vite, cycle plus court), 0 = pas de lecture univoque. Le DPO est
# neutre : payer ses fournisseurs plus tard améliore la trésorerie mais peut aussi signaler des
# tensions, la couleur ne trancherait pas honnêtement.
TREND_FAVORABLE = {
    "cfo_to_net_income": 1, "fcf_to_net_income": 1, "sloan_accruals": -1,
    "dso": -1, "dio": -1, "dpo": 0, "ccc": -1,
}
SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


def spark_text(values: list) -> str:
    """Mini-courbe en caractères (▁▃▅▇), de l'exercice le plus ancien au plus récent : la forme de
    l'évolution dans une cellule de tableau. Un exercice n.d. est un point médian, jamais un 0."""
    present = [v for v in values if v is not None]
    if len(present) < 2:
        return ""
    low, high = min(present), max(present)
    span = (high - low) or 1.0
    return "".join("·" if v is None else SPARK_BLOCKS[round((v - low) / span * (len(SPARK_BLOCKS) - 1))]
                   for v in values)


def trend_state(metric: str, delta: float | None) -> str:
    """« good », « bad » ou « neutral » selon TREND_FAVORABLE et le signe de l'évolution."""
    direction = TREND_FAVORABLE.get(metric, 0)
    if delta is None or direction == 0 or delta == 0:
        return "neutral"
    return "good" if delta * direction > 0 else "bad"


def format_ratio(value: float | None, kind: str, lang: str, signed: bool = False) -> str:
    if value is None:
        return L(lang, "na")
    sign = "+" if signed else ""
    if kind == "percent":
        return f"{format_number(value * 100, '+.1f' if signed or value < 0 else '.1f', lang)} %"
    if kind == "days":
        return f"{format_number(value, sign + '.0f', lang)} {L(lang, 'unit_days')}"
    return f"{format_number(value, sign + '.2f', lang)}x"


def _component_label(key: str, lang: str) -> str:
    """Nom lisible d'une composante : poste des états financiers (éventuellement suffixé _t / _p pour
    l'exercice t ou t-1 des scores), ou ratio (le cycle de conversion se compose de DSO, DIO et DPO)."""
    suffix = ""
    for marker, suffix_key in (("_t", "suffix_t"), ("_p", "suffix_p")):
        if key.endswith(marker) and L(lang, f"field_{key[:-2]}") != f"field_{key[:-2]}":
            key, suffix = key[:-2], " " + L(lang, suffix_key)
            break
    field_label = L(lang, f"field_{key}")
    label = field_label if field_label != f"field_{key}" else L(lang, f"ratio_{key}")
    return label + suffix


def ratio_tooltip(result: dict, lang: str) -> str:
    """Détail du calcul d'un ratio : formule remplie avec les montants réels, puis mentions (repli sur
    un poste voisin...) et, si la valeur manque, la raison. De quoi refaire le calcul à la main."""
    components = result["components"]
    formatted = {
        key: (format_ratio(value, RATIO_KINDS[key], lang) if key in RATIO_KINDS else format_amount(value, lang))
        for key, value in components.items()
    }
    lines = [L(lang, f"formula_{result['formula']}", **formatted)]
    if result["value"] is not None:
        lines[0] += f" = {format_ratio(result['value'], RATIO_KINDS[result['formula']], lang)}"
    elif result["reason"] == "missing_inputs":
        lines.append(L(lang, "reason_missing_inputs",
                       missing=", ".join(_component_label(key, lang) for key in result["missing"])))
    elif result["reason"] == "non_positive_denominator":
        lines.append(L(lang, "reason_non_positive_denominator",
                       denominator=L(lang, f"denominator_{result['denominator']}")))
    elif result["reason"] == "no_prior_year":
        lines.append(L(lang, "reason_no_prior_year"))
    lines += [L(lang, f"flag_{flag}") for flag in result["flags"]]
    # Un paragraphe par ligne : les infobulles dash_table sont rendues en markdown (voir ratio_table),
    # où un simple retour à la ligne serait fusionné avec la ligne précédente.
    return "\n\n".join(lines)


def ratio_table(results_by_year: dict, metrics: tuple[str, ...], years: list, lang: str, dark: bool,
                table_id: str, trends: dict | None = None):
    """Tableau d'indicateurs : une ligne par ratio, une colonne par exercice (du plus récent au plus
    ancien, comme les états financiers), et une colonne d'évolution si trends est fourni. L'en-tête de
    ligne porte la définition du ratio (ce qu'il mesure, formule, seuil), chaque cellule le détail de
    son calcul. Cellules avec une mention (repli) en italique, n.d. en gris."""
    year_ids = [f"y{i}" for i in range(len(years))]
    columns = [{"name": L(lang, "col_metric"), "id": "metric"}] + [
        {"name": format_year(year, lang), "id": year_id} for year, year_id in zip(years, year_ids)
    ]
    if trends is not None:
        columns.append({"name": L(lang, "col_trend"), "id": "trend"})
    rows, tooltips = [], []
    for metric in metrics:
        kind = RATIO_KINDS[metric]
        row = {"metric": L(lang, f"ratio_{metric}")}
        tooltip = {"metric": {"value": L(lang, f"ratio_{metric}_help"), "type": "text"}}
        for year, year_id in zip(years, year_ids):
            result = results_by_year[year][metric]
            row[year_id] = format_ratio(result["value"], kind, lang)
            row[f"_state_{year_id}"] = "na" if result["value"] is None else ("flagged" if result["flags"] else "ok")
            tooltip[year_id] = {"value": ratio_tooltip(result, lang), "type": "markdown"}
        if trends is not None:
            trend = trends.get(metric)
            if trend is None:
                row["trend"], row["_trend_state"] = L(lang, "trend_na"), "neutral"
            else:
                # Mini-courbe chronologique, flèche, écart : la tendance se lit sans comparer les colonnes.
                chronological = [results_by_year[year][metric]["value"] for year in sorted(years)]
                arrow = "▲" if trend["delta"] > 0 else ("▼" if trend["delta"] < 0 else "▶")
                row["trend"] = f"{spark_text(chronological)}  {arrow} " + L(
                    lang, "trend_text", delta=format_ratio(trend["delta"], kind, lang, signed=True),
                    first=trend["first_year"].year, last=trend["last_year"].year,
                )
                row["_trend_state"] = trend_state(metric, trend["delta"])
        rows.append(row)
        tooltips.append(tooltip)

    style_header, style_cell, style_data = table_style_overrides(dark)
    muted = "#8b93a7" if dark else "#8a8f99"
    conditional = []
    for year_id in year_ids:
        conditional.append({"if": {"column_id": year_id, "filter_query": f"{{_state_{year_id}}} = flagged"},
                            "fontStyle": "italic"})
        conditional.append({"if": {"column_id": year_id, "filter_query": f"{{_state_{year_id}}} = na"}, "color": muted})
    # Évolution favorable / défavorable (TREND_FAVORABLE) : la flèche et l'écart portent le sens, la
    # couleur le rappelle.
    good, bad = ("#3fd13f", "#ff7a7a") if dark else ("#0b7a0b", "#c23434")
    conditional += [
        {"if": {"column_id": "trend", "filter_query": "{_trend_state} = good"}, "color": good, "fontWeight": "600"},
        {"if": {"column_id": "trend", "filter_query": "{_trend_state} = bad"}, "color": bad, "fontWeight": "600"},
    ]
    return dash_table.DataTable(
        id=table_id, columns=columns, data=rows, tooltip_data=tooltips, tooltip_delay=0, tooltip_duration=None,
        style_header=style_header, style_cell=style_cell, style_data=style_data,
        style_cell_conditional=[
            {"if": {"column_id": "metric"}, "textAlign": "left", "minWidth": "260px"},
            {"if": {"column_id": "trend"}, "minWidth": "170px"},
        ],
        style_data_conditional=conditional, style_table={"overflowX": "auto"},
    )


def bridge_controls(years: list, lang: str):
    """Sélecteur d'exercice du pont résultat net -> CFO (exercice le plus récent par défaut) et
    emplacements du graphique et de ses notes, remplis par callbacks.update_bridge."""
    return html.Div([
        html.Div([dbc.Label(L(lang, "bridge_year_label"), className="mb-0")] + info_tooltip(
            "bridge-help-info", L(lang, "bridge_help"),
        )),
        dcc.Dropdown(
            id="bridge-year-dropdown",
            options=[{"label": format_year(year, lang), "value": year.isoformat()} for year in years],
            value=years[0].isoformat(), clearable=False, style={"width": "200px"},
        ),
        dcc.Graph(id="bridge-graph", config=GRAPH_CONFIG),
        html.Div(id="bridge-notes", className="text-muted", style={"fontSize": "0.8rem"}),
    ])


# ============================================================
# Scores d'alerte : tableaux détaillés
# ============================================================

def detail_table(table_id: str, first_column: str, column_names: list[str], rows: list[dict], dark: bool):
    """Tableau générique des scores : rows = [{"label", "help", "cells": [{"text", "tooltip", "state"}]}].
    state colore la cellule : "good" (vert), "warn" (ambre), "bad" (rouge), "na" (gris), "flagged"
    (italique, repli sur un poste voisin), "ok" (neutre). Même technique de colonnes cachées que
    statement_table pour le style conditionnel."""
    column_ids = [f"c{i}" for i in range(len(column_names))]
    columns = [{"name": first_column, "id": "label"}] + [
        {"name": name, "id": column_id} for name, column_id in zip(column_names, column_ids)
    ]
    data, tooltips = [], []
    for row in rows:
        record = {"label": row["label"]}
        tooltip = {"label": {"value": row.get("help", ""), "type": "markdown"}}
        for column_id, cell in zip(column_ids, row["cells"]):
            record[column_id] = cell["text"]
            record[f"_state_{column_id}"] = cell.get("state", "ok")
            if cell.get("tooltip"):
                tooltip[column_id] = {"value": cell["tooltip"], "type": "markdown"}
        data.append(record)
        tooltips.append(tooltip)

    style_header, style_cell, style_data = table_style_overrides(dark)
    if dark:
        colors = {"good": ("#173a24", "#8fd19e"), "warn": ("#3a2f12", "#e0c46c"), "bad": ("#3a1616", "#e88a8a")}
        muted = "#8b93a7"
    else:
        colors = {"good": ("#d4edda", "#155724"), "warn": ("#fff3cd", "#856404"), "bad": ("#f8d7da", "#721c24")}
        muted = "#8a8f99"
    conditional = []
    for column_id in column_ids:
        for state, (background, foreground) in colors.items():
            conditional.append({"if": {"column_id": column_id, "filter_query": f"{{_state_{column_id}}} = {state}"},
                                "backgroundColor": background, "color": foreground})
        conditional.append({"if": {"column_id": column_id, "filter_query": f"{{_state_{column_id}}} = na"}, "color": muted})
        conditional.append({"if": {"column_id": column_id, "filter_query": f"{{_state_{column_id}}} = flagged"},
                            "fontStyle": "italic"})
        conditional.append({"if": {"column_id": column_id, "filter_query": f"{{_state_{column_id}}} = subtotal"},
                            "fontWeight": "600"})
        conditional.append({"if": {"column_id": column_id, "filter_query": f"{{_state_{column_id}}} = memo"},
                            "fontStyle": "italic", "color": muted})
    return dash_table.DataTable(
        id=table_id, columns=columns, data=data, tooltip_data=tooltips, tooltip_delay=0, tooltip_duration=None,
        style_header=style_header, style_cell=style_cell, style_data=style_data,
        style_cell_conditional=[{"if": {"column_id": "label"}, "textAlign": "left", "minWidth": "260px"}],
        style_data_conditional=conditional, style_table={"overflowX": "auto"},
    )


def _na_cell(tooltip: str, lang: str) -> dict:
    return {"text": L(lang, "na"), "tooltip": tooltip, "state": "na"}


def _reason_text(result: dict, lang: str) -> str:
    if result.get("reason") == "missing_inputs":
        return L(lang, "reason_missing_inputs", missing=", ".join(_component_label(k, lang) for k in result["missing"]))
    if result.get("reason") == "non_positive_base":
        return L(lang, "reason_non_positive_base")
    return ""


def pair_label(pair: tuple, lang: str) -> str:
    return L(lang, "col_pair", t=format_year(pair[0], lang), p=format_year(pair[1], lang))


def beneish_table(results: list[dict], lang: str, dark: bool):
    """Une colonne par couple (t, t-1), du plus récent au plus ancien, puis les moyennes de référence de
    Beneish (1999, tableau 2). Infobulle de chaque indice : formule remplie avec les montants des deux
    exercices, valeur, contribution au score (coefficient x indice) et mentions."""
    columns = [pair_label(r["pair"], lang) for r in results] + [
        L(lang, "col_reference_manipulators"), L(lang, "col_reference_non_manipulators"),
    ]
    rows = []
    for index in BENEISH_INDICES:
        cells = []
        for result in results:
            item = result["indices"][index]
            formula = L(lang, f"formula_beneish_{index}", **{k: format_amount(v, lang) for k, v in item["components"].items()})
            if item["value"] is None:
                cells.append(_na_cell(f"{formula}\n\n{_reason_text(item, lang)}", lang))
                continue
            lines = [f"{formula} = {format_number(item['value'], '.3f', lang)}", L(
                lang, "contribution_text", coefficient=f"{format_number(BENEISH_COEFFICIENTS[index], '+.3f', lang)}", value=f"{format_number(item['value'], '.3f', lang)}",
                contribution=f"{format_number(result['contributions'][index], '+.3f', lang)}",
            )]
            lines += [L(lang, f"flag_{flag}") for flag in item["flags"]]
            cells.append({"text": f"{format_number(item['value'], '.3f', lang)}", "tooltip": "\n\n".join(lines),
                          "state": "flagged" if item["flags"] else "ok"})
        cells += [{"text": f"{format_number(BENEISH_REFERENCE_MEANS[group][index], '.3f', lang)}", "state": "ok"}
                  for group in ("manipulators", "non_manipulators")]
        rows.append({"label": L(lang, f"beneish_{index}"), "help": L(lang, f"beneish_{index}_help"), "cells": cells})

    m_cells = []
    for result in results:
        score = result["m_score"]
        if score["value"] is None:
            missing = ", ".join(L(lang, f"beneish_{i}") for i in score["missing"])
            m_cells.append(_na_cell(L(lang, "beneish_official_na", pair=pair_label(result["pair"], lang), missing=missing), lang))
        else:
            m_cells.append({"text": f"{format_number(score['value'], '.2f', lang)}", "state": "bad" if score["value"] > BENEISH_THRESHOLD else "good",
                            "tooltip": L(lang, f"beneish_verdict_{score['verdict']}", pair=pair_label(result["pair"], lang),
                                         value=f"{format_number(score['value'], '.2f', lang)}")})
    reference_scores = []
    for group in ("manipulators", "non_manipulators"):
        value = beneish_m_score_from_indices(BENEISH_REFERENCE_MEANS[group])
        reference_scores.append({"text": f"{format_number(value, '.2f', lang)}", "state": "bad" if value > BENEISH_THRESHOLD else "good"})
    rows.append({"label": L(lang, "beneish_m_score"), "help": L(lang, "beneish_help"), "cells": m_cells + reference_scores})

    if any(r["m_score_indicative"] for r in results):
        indicative_cells = []
        for result in results:
            indicative = result["m_score_indicative"]
            if indicative is None:
                indicative_cells.append({"text": "—", "state": "ok"})
                continue
            neutralized = ", ".join(L(lang, f"beneish_{i}") for i in indicative["neutralized"])
            indicative_cells.append({
                "text": f"{format_number(indicative['value'], '.2f', lang)}", "state": "warn",
                "tooltip": L(lang, "beneish_indicative_note", neutralized=neutralized),
            })
        indicative_cells += [{"text": "—", "state": "ok"}, {"text": "—", "state": "ok"}]
        rows.append({"label": L(lang, "beneish_m_score_indicative"), "help": L(lang, "beneish_indicative_note",
                                                                              neutralized="…"), "cells": indicative_cells})
    return detail_table("table-beneish", L(lang, "col_metric"), columns, rows, dark)


def beneish_summary(result: dict, lang: str):
    """Phrase de conclusion sur le couple le plus récent : verdict du M-score officiel, ou pourquoi il est
    n.d. et ce que donne la variante indicative."""
    pair = pair_label(result["pair"], lang)
    score = result["m_score"]
    if score["value"] is not None:
        color = "warning" if score["verdict"] == "manipulation_risk" else "success"
        return dbc.Alert(L(lang, f"beneish_verdict_{score['verdict']}", pair=pair, value=f"{format_number(score['value'], '.2f', lang)}"),
                         color=color, className="py-2 mt-2")
    missing = ", ".join(L(lang, f"beneish_{i}") for i in score["missing"])
    children = [html.Div(L(lang, "beneish_official_na", pair=pair, missing=missing))]
    indicative = result["m_score_indicative"]
    if indicative is not None:
        neutralized = ", ".join(L(lang, f"beneish_{i}") for i in indicative["neutralized"])
        verdict = L(lang, f"beneish_verdict_{beneish_verdict(indicative['value'])}", pair=pair,
                    value=f"{format_number(indicative['value'], '.2f', lang)}")
        children += [html.Div(L(lang, "beneish_indicative_note", neutralized=neutralized)), html.Div(verdict)]
    return dbc.Alert(children, color="secondary", className="py-2 mt-2")


ZONE_STATES = {"safe": "good", "grey": "warn", "distress": "bad"}


def altman_ratio_label_key(model: str, x: str) -> str:
    """Libellé d'un ratio d'Altman : X4 n'a pas le même numérateur selon le modèle (capitalisation
    boursière pour le Z d'origine, capitaux propres comptables pour Z''), d'où deux libellés."""
    return "altman_x4_market" if model == "original" and x == "x4" else f"altman_{x}"


def altman_table(results: list[dict], lang: str, dark: bool, imported: bool = False):
    """Une colonne par exercice (du plus récent au plus ancien) : X1 à X5, Z, zone. Infobulle de chaque
    ratio : numérateur ÷ dénominateur = valeur, puis contribution (coefficient x ratio). imported : la
    capitalisation vient de la ligne market_cap du fichier, pas des cours, d'où un autre message."""
    model = results[0]["model"]
    coefficients = ALTMAN_MODELS[model]["coefficients"]
    columns = [format_year(r["year"], lang) for r in results]
    rows = []
    for x, coefficient in coefficients.items():
        cells = []
        for result in results:
            component = result["components"][x]
            formula = L(
                lang, "altman_ratio_formula",
                numerator_label=_component_label(component["numerator_key"], lang),
                numerator=format_amount(component["numerator"], lang),
                denominator_label=_component_label(component["denominator_key"], lang),
                denominator=format_amount(component["denominator"], lang),
                value=f"{format_number(component['value'], '.3f', lang)}" if component["value"] is not None else L(lang, "na"),
            )
            if component["value"] is None:
                text = formula
                if component["numerator_key"] == "market_value_of_equity" and component["numerator"] is None:
                    text += "\n\n" + L(lang, "altman_mve_unavailable_import" if imported else "altman_mve_unavailable")
                cells.append(_na_cell(text, lang))
                continue
            contribution = L(lang, "contribution_text", coefficient=f"{format_number(coefficient, 'g', lang)}", value=f"{format_number(component['value'], '.3f', lang)}",
                             contribution=f"{format_number(result['contributions'][x], '+.3f', lang)}")
            cells.append({"text": f"{format_number(component['value'], '.3f', lang)}", "tooltip": f"{formula}\n\n{contribution}", "state": "ok"})
        rows.append({"label": L(lang, altman_ratio_label_key(model, x)), "help": L(lang, f"altman_{x}_help"),
                     "cells": cells})
    z_cells, zone_cells = [], []
    for result in results:
        if result["value"] is None:
            missing = ", ".join(_component_label(k, lang) for k in result["missing"])
            z_cells.append(_na_cell(L(lang, "reason_missing_inputs", missing=missing), lang))
            zone_cells.append(_na_cell("", lang))
        else:
            state = ZONE_STATES[result["zone"]]
            flags = "\n\n".join(L(lang, f"flag_{flag}") for flag in result["flags"])
            z_cells.append({"text": f"{format_number(result['value'], '.2f', lang)}", "state": state, "tooltip": flags or None})
            zone_cells.append({"text": L(lang, f"zone_{result['zone']}"), "state": state})
    rows.append({"label": L(lang, "altman_z"), "help": L(lang, "altman_help"), "cells": z_cells})
    rows.append({"label": L(lang, "altman_zone"), "help": L(lang, "altman_help"), "cells": zone_cells})
    return detail_table("table-altman", L(lang, "col_metric"), columns, rows, dark)


# Unité d'affichage des détails des critères de Piotroski.
PIOTROSKI_DETAIL_KINDS = {
    "roa_t": "percent", "roa_p": "percent", "leverage_t": "percent", "leverage_p": "percent",
    "gross_margin_t": "percent", "gross_margin_p": "percent", "current_ratio_t": "multiple",
    "current_ratio_p": "multiple", "turnover_t": "multiple", "turnover_p": "multiple",
    "cfo_t": "amount", "net_income_t": "amount", "shares_t": "amount", "shares_p": "amount",
    "equity_issuance_t": "amount",
}


def _format_detail(key: str, value: float | None, lang: str) -> str:
    kind = PIOTROSKI_DETAIL_KINDS[key]
    if kind == "amount":
        return format_amount(value, lang)
    return format_ratio(value, kind, lang)


def piotroski_table(results: list[dict], lang: str, dark: bool):
    """Une colonne par exercice comparé à son précédent : 1 / 0 / n.d. par critère, puis le F-score
    (« 6 / 8 » quand un critère n'est pas calculable). Infobulle : valeurs comparées."""
    columns = [pair_label((r["year"], r["prior_year"]), lang) for r in results]
    rows = []
    for criterion in PIOTROSKI_CRITERIA:
        cells = []
        for result in results:
            item = result["criteria"][criterion]
            details = " · ".join(f"{L(lang, f'piotroski_detail_{k}')} {_format_detail(k, v, lang)}"
                                 for k, v in item["details"].items())
            details = "\n\n".join([details] + [L(lang, f"flag_{flag}") for flag in item["flags"]])
            if item["value"] is None:
                cells.append(_na_cell(details, lang))
            else:
                cells.append({"text": str(item["value"]), "tooltip": details, "state": "good" if item["value"] else "bad"})
        rows.append({"label": L(lang, f"piotroski_{criterion}"), "help": L(lang, f"piotroski_{criterion}_help"),
                     "cells": cells})
    score_cells = []
    for result in results:
        if result["score"] is None:
            score_cells.append(_na_cell("", lang))
            continue
        partial = result["n_available"] < result["n_criteria"]
        score_cells.append({
            "text": L(lang, "piotroski_score_text", score=result["score"], n=result["n_available"]),
            "tooltip": L(lang, "piotroski_partial", n=result["n_available"]) if partial else None,
            "state": "flagged" if partial else ("good" if result["score"] >= 8 else "bad" if result["score"] <= 2 else "ok"),
        })
    rows.append({"label": L(lang, "piotroski_score"), "help": L(lang, "piotroski_help"), "cells": score_cells})
    return detail_table("table-piotroski", L(lang, "col_metric"), columns, rows, dark)


def altman_controls(lang: str):
    """Bascule de modèle Altman (automatique par défaut) et emplacement du tableau, rempli par
    callbacks.update_altman. persistence : le choix survit au changement de langue, qui recrée ce
    composant."""
    return html.Div([
        dbc.Label(L(lang, "altman_model_label"), className="mb-0"),
        dcc.RadioItems(
            id="altman-model-radio",
            options=[{"label": f" {L(lang, f'altman_model_{code}')}", "value": code}
                     for code in ("auto", "original", "z_double_prime")],
            value="auto", inline=True, persistence=True, persistence_type="session", className="mb-2",
            inputStyle={"marginLeft": "0.8rem"},
        ),
        html.Div(id="altman-container"),
    ])


# ============================================================
# Vision Transaction Services
# ============================================================

EFFECT_ROWS = ("ebitda", "net_debt", "enterprise_value", "ev_to_ebitda", "net_debt_to_ebitda")
EMPTY_USER_ROWS = [{"label": "", "amount": ""}, {"label": "", "amount": ""}]


def user_items_table(table_id: str, rows: list[dict] | None, lang: str, currency: str, dark: bool):
    """Tableau éditable de saisies (libellé, montant en millions). Montant en texte plutôt qu'en nombre :
    accepte la virgule décimale française, la conversion et la validation se font dans
    engine.parse_user_items, qui signale une saisie invalide au lieu de l'ignorer en silence."""
    style_header, style_cell, style_data = table_style_overrides(dark)
    return dash_table.DataTable(
        id=table_id,
        columns=[{"name": L(lang, "col_label"), "id": "label", "type": "text"},
                 {"name": L(lang, "col_amount_millions", currency=currency), "id": "amount", "type": "text"}],
        data=rows if rows else [dict(r) for r in EMPTY_USER_ROWS],
        editable=True, row_deletable=True,
        style_header=style_header, style_cell=style_cell, style_data=style_data,
        style_cell_conditional=[{"if": {"column_id": "label"}, "textAlign": "left", "minWidth": "300px"}],
        style_table={"overflowX": "auto", "maxWidth": "620px"},
    )


def transaction_controls(year: pd.Timestamp, saved: dict, currency: str, lang: str, dark: bool):
    """Section Transaction Services : taux d'impôt sur les retraites, pont de dette nette, saisies de
    l'utilisateur et effets sur les multiples. Les tableaux de saisie sont pré-remplis avec les saisies
    déjà faites pour cette société (voir callbacks.update_transaction_view, qui les conserve) : ils sont
    recréés à chaque changement de langue, un défaut vide effacerait le travail de l'utilisateur."""
    return html.Div([
        html.Small(L(lang, "transaction_intro", year=format_year(year, lang)), className="text-muted d-block mb-2"),
        html.Div([dbc.Label(L(lang, "pension_tax_rate_label"), className="mb-0")]
                 + info_tooltip("pension-tax-info", L(lang, "pension_tax_rate_help"))),
        dcc.Input(id="ts-pension-tax-input", type="number", min=0, max=100, step=0.5,
                  value=saved.get("pension_tax_rate_pct", 25), className="form-control form-control-sm mb-3",
                  style={"width": "100px"}),
        html.H6(L(lang, "net_debt_bridge_title"), className="mt-2"),
        html.Div(id="ts-bridge-container"),
        html.H6(L(lang, "net_debt_items_title"), className="mt-3"),
        html.Small(L(lang, "net_debt_items_help", currency=currency), className="text-muted d-block mb-1"),
        user_items_table("ts-net-debt-items", saved.get("net_debt_items"), lang, currency, dark),
        dbc.Button(L(lang, "add_row_btn"), id="ts-add-net-debt-item", color="link", size="sm", className="p-0 mb-2"),
        html.H6(L(lang, "ebitda_adjustments_title"), className="mt-3"),
        html.Small(L(lang, "ebitda_adjustments_help", currency=currency), className="text-muted d-block mb-1"),
        user_items_table("ts-ebitda-adjustments", saved.get("ebitda_adjustments"), lang, currency, dark),
        dbc.Button(L(lang, "add_row_btn"), id="ts-add-ebitda-adjustment", color="link", size="sm", className="p-0 mb-2"),
        html.Div(id="ts-input-warnings"),
        html.H6(L(lang, "effects_title"), className="mt-3"),
        html.Div(id="ts-effects-container"),
    ])


def net_debt_bridge_table(bridge: dict, currency: str, lang: str, dark: bool):
    """Une ligne par étape du pont, avec son montant et sa source (donnée, hypothèse, sous-total, pour
    mémoire). Ligne de donnée absente : n.d., avec en infobulle la mention qu'elle est exclue du total."""
    rows = []
    for line in bridge["lines"]:
        label = L(lang, f"bridge_line_{line['key']}", label=line.get("label", ""),
                  rate=f"{format_number(line.get('rate', 0) * 100, 'g', lang)}")
        source = line["source"]
        if line["value"] is None:
            amount_cell = _na_cell(L(lang, "bridge_excluded") if line.get("excluded") else "", lang)
        else:
            state = {"subtotal": "subtotal", "memo": "memo"}.get(source, "ok")
            tooltip = L(lang, "bridge_memo_help") if source == "memo" else None
            amount_cell = {"text": format_amount(line["value"], lang), "state": state, "tooltip": tooltip}
        source_cell = {"text": L(lang, f"source_{source}"), "state": "memo" if source == "memo" else
                       ("subtotal" if source == "subtotal" else "ok")}
        rows.append({"label": label, "help": "", "cells": [amount_cell, source_cell]})
    return detail_table("table-net-debt-bridge", L(lang, "col_item"),
                        [L(lang, "col_amount", currency=currency), L(lang, "col_source")], rows, dark)


def effects_table(published: dict, adjusted: dict, lang: str, dark: bool):
    """Publié, ajusté et écart pour l'EBITDA, la dette nette, la valeur d'entreprise et les deux
    multiples. published / adjusted : {"ebitda", "net_debt", "enterprise_value", "ev_to_ebitda",
    "net_debt_to_ebitda"} (montants en unités, multiples en x)."""
    rows = []
    for key in EFFECT_ROWS:
        is_multiple = key in ("ev_to_ebitda", "net_debt_to_ebitda")
        before, after = published.get(key), adjusted.get(key)

        def fmt(value, signed=False):
            if value is None:
                return L(lang, "na")
            return format_ratio(value, "multiple", lang, signed=signed) if is_multiple else (
                ("+" if signed and value > 0 else "") + format_amount(value, lang))

        change = after - before if before is not None and after is not None else None
        cells = [
            {"text": fmt(before), "state": "na" if before is None else "ok"},
            {"text": fmt(after), "state": "na" if after is None else "subtotal"},
            {"text": fmt(change, signed=True), "state": "na" if change is None else "ok"},
        ]
        rows.append({"label": L(lang, f"effects_{key}"), "help": L(lang, f"effects_{key}_help"), "cells": cells})
    return detail_table("table-effects", L(lang, "col_metric"),
                        [L(lang, "col_published"), L(lang, "col_adjusted"), L(lang, "col_change")], rows, dark)


# ============================================================
# Loi de Benford
# ============================================================

def benford_file_info(file_store: dict | None, lang: str):
    if not file_store:
        return ""
    return html.Small(L(lang, "benford_file_loaded", filename=file_store["filename"], rows=file_store["n_rows"],
                        cols=len(file_store["columns"])), className="text-muted")


def build_benford(lang: str, v: dict | None, file_store: dict | None):
    """Section Benford, indépendante de la société analysée en mode CSV. Reconstruite à chaque changement
    de langue : le fichier importé n'y vit pas (il est dans benford-file-store, hors de la zone
    reconstruite), seules les options de colonne en sont recalculées ici."""
    v = v or {}
    columns = list((file_store or {}).get("columns", {}))
    column_value = gv(v, "benford-column-dropdown", (file_store or {}).get("guessed_column"))
    if column_value not in columns:
        column_value = (file_store or {}).get("guessed_column")
    return html.Div([
        html.H5(L(lang, "section_benford"), className="section-title"),
        html.P(L(lang, "benford_intro"), className="text-muted", style={"fontSize": "0.85rem"}),
        dbc.Label(L(lang, "benford_source_label"), className="mb-0"),
        dcc.RadioItems(
            id="benford-source-radio",
            options=[{"label": f" {L(lang, 'benford_source_csv')}", "value": "csv"},
                     {"label": f" {L(lang, 'benford_source_statements')}", "value": "statements"}],
            value=gv(v, "benford-source-radio", "csv"), labelStyle={"display": "block"}, className="mb-2",
        ),
        dcc.Upload(
            id="benford-upload", children=html.Div(L(lang, "benford_upload")), multiple=False,
            style={"borderWidth": "1px", "borderStyle": "dashed", "borderRadius": "10px", "padding": "1rem",
                   "textAlign": "center", "cursor": "pointer", "maxWidth": "620px"},
            className="mb-1",
        ),
        html.Div(benford_file_info(file_store, lang), id="benford-file-info", className="mb-2"),
        dbc.Row([
            dbc.Col([
                dbc.Label(L(lang, "benford_column_label"), className="mb-0"),
                dcc.Dropdown(id="benford-column-dropdown", options=[{"label": c, "value": c} for c in columns],
                             value=column_value, clearable=False, style={"width": "240px"}),
            ], width="auto"),
            dbc.Col([
                html.Div([dbc.Label(L(lang, "benford_sign_label"), className="mb-0")]
                         + info_tooltip("benford-sign-info", L(lang, "benford_sign_help"))),
                dcc.RadioItems(
                    id="benford-sign-radio",
                    options=[{"label": f" {L(lang, 'benford_sign_positive')}", "value": "positive"},
                             {"label": f" {L(lang, 'benford_sign_negative')}", "value": "negative"}],
                    value=gv(v, "benford-sign-radio", "positive"), labelStyle={"display": "block"},
                ),
            ], width="auto"),
            dbc.Col([
                html.Div([dbc.Label(L(lang, "benford_min_amount_label"), className="mb-0")]
                         + info_tooltip("benford-min-info", L(lang, "benford_min_amount_help"))),
                dcc.Input(id="benford-min-amount-input", type="number", min=0, step=1,
                          value=gv(v, "benford-min-amount-input", 10), className="form-control form-control-sm",
                          style={"width": "110px"}),
            ], width="auto"),
        ], className="mb-3 gx-4"),
    ], className="px-3")


def benford_result_view(result: dict, counts: dict | None, demo: bool, lang: str, dark: bool, palette) -> list:
    """Résultat du test : avertissements d'abord (démonstration, taille d'échantillon), puis MAD et zone de
    Nigrini, χ² et p-value, histogramme observé contre attendu et tableau par chiffre."""
    children = []
    if demo:
        children.append(dbc.Alert(L(lang, "benford_demo_warning"), color="warning", className="py-2"))
    if counts is not None:
        children.append(html.Small(L(lang, "benford_counts", **counts), className="text-muted d-block mb-2"))
    if result["n"] == 0:
        return children + [dbc.Alert(L(lang, "benford_empty"), color="secondary", className="py-2")]
    expected_mad = f"{format_number(result['expected_mad'], '.4f', lang)}"
    if result["sample_warning"] in ("not_interpretable", "caution"):
        color = "danger" if result["sample_warning"] == "not_interpretable" else "warning"
        children.append(dbc.Alert(L(lang, f"benford_warning_{result['sample_warning']}", n=result["n"],
                                    expected_mad=expected_mad), color=color, className="py-2"))

    zone_state = {"close": "success", "acceptable": "success", "marginal": "warning", "nonconformity": "danger"}

    def stat(label_key, value_text, help_key=None, color=None):
        label = [L(lang, label_key)] + (info_tooltip(f"{label_key}-info", L(lang, help_key)) if help_key else [])
        return dbc.Col([html.Small(label, className="text-muted d-block"),
                        html.H6(value_text, className=f"mb-0 text-{color}" if color else "mb-0")], width=3, className="mb-2")

    children.append(dbc.Card(dbc.CardBody([
        dbc.Row([
            stat("col_count", f"{result['n']:,}".replace(",", " ")),
            stat("benford_mad_label", f"{format_number(result['mad'], '.4f', lang)}", "benford_mad_help"),
            stat("benford_conformity_label", L(lang, f"conformity_{result['conformity']}"), "benford_mad_help",
                 color=zone_state[result["conformity"]]),
            stat("benford_chi2_label", f"{format_number(result['chi2'], '.1f', lang)} (p = {format_number(result['p_value'], '.3g', lang)})", "benford_chi2_help"),
        ]),
        html.Small(L(lang, "benford_expected_mad", n=result["n"], value=expected_mad), className="text-muted"),
    ]), className="mb-2"))
    labels = {k: L(lang, f"benford_{k}") for k in ("observed", "expected", "digit", "frequency")}
    children.append(dcc.Graph(figure=make_benford_chart(result["observed"], result["expected"], labels,
                                                        L(lang, "benford_chart_title"), dark=dark, palette=palette,
                                                        separators=L(lang, "plotly_separators")),
                              config=GRAPH_CONFIG))
    style_header, style_cell, style_data = table_style_overrides(dark)
    rows = [{
        "digit": d, "count": result["counts"][d], "observed": f"{format_number(result['observed'][d] * 100, '.1f', lang)}",
        "expected": f"{format_number(result['expected'][d] * 100, '.1f', lang)}",
        "deviation": f"{format_number((result['observed'][d] - result['expected'][d]) * 100, '+.1f', lang)}",
    } for d in sorted(result["expected"])]
    children.append(dash_table.DataTable(
        id="table-benford", data=rows,
        columns=[{"name": L(lang, key), "id": col} for key, col in (
            ("col_digit", "digit"), ("col_count", "count"), ("col_observed_pct", "observed"),
            ("col_expected_pct", "expected"), ("col_deviation_pct", "deviation"))],
        style_header=style_header, style_cell=style_cell, style_data=style_data, style_table={"maxWidth": "620px"},
    ))
    return children


def _stat(label: str, value_text: str, extra=None):
    children = [html.Small(label, className="text-muted d-block"), html.H6(value_text, className="mb-0")]
    if extra is not None:
        children.append(extra)
    return dbc.Col(children, width=3, className="mb-2")


def company_card(ticker: str, profile: dict, regime: dict, market: dict, lang: str):
    """Identité de la société, devises et données de marché ramenées dans la devise des comptes,
    avec le détail de la conversion (diviseur de sous-unité, taux de change) pour que le calcul se
    refasse à la main. market : voir engine.market_values_in_reporting_currency."""
    reporting = market["reporting_currency"] or L(lang, "na")
    if market["fx_rate"] is None:
        fx_text = L(lang, "na")
    elif market["fx_rate"] == 1.0 and market["quote_major_currency"] == market["reporting_currency"]:
        fx_text = L(lang, "fx_same_currency")
    else:
        fx_text = L(lang, "fx_detail", quote=market["quote_major_currency"],
                    rate=format_number(market["fx_rate"], ".4f", lang), reporting=market["reporting_currency"])
    minor_unit_note = None
    if market["divisor"] != 1.0:
        minor_unit_note = html.Small(
            L(lang, "minor_unit_detail", quote_raw=profile["quote_currency"], divisor=market["divisor"]),
            className="text-muted",
        )
    price_text = (f"{format_number(market['price'], ',.2f', lang)} {reporting}" if market["price"] is not None
                  else L(lang, "na"))
    cap_text = f"{format_amount(market['market_cap'], lang)} {reporting}" if market["market_cap"] is not None else L(lang, "na")
    header = html.Div([
        html.H5(f"{profile['name']} ({ticker})", className="mb-1 d-inline"),
        dbc.Badge(L(lang, f"regime_{regime['regime']}"), color="secondary" if regime["regime"] == "general" else "warning",
                  className="ms-2 align-text-bottom"),
    ], className="mb-2")
    return dbc.Card(dbc.CardBody([
        header,
        dbc.Row([
            _stat(L(lang, "label_sector"), profile.get("sector") or L(lang, "na")),
            _stat(L(lang, "label_industry"), profile.get("industry") or L(lang, "na")),
            _stat(L(lang, "label_reporting_currency"), reporting),
            _stat(L(lang, "label_quote_currency"), profile.get("quote_currency") or L(lang, "na")),
            _stat(L(lang, "label_price"), price_text, minor_unit_note),
            _stat(L(lang, "label_market_cap"), cap_text),
            dbc.Col([
                html.Small([L(lang, "label_fx_rate")] + info_tooltip("currency-info", L(lang, "currency_help")),
                           className="text-muted d-block"),
                html.H6(fx_text, className="mb-0"),
            ], width=6, className="mb-2"),
        ]),
    ]), className="mb-3")


PEER_METRIC_LABELS = {"beneish_m_score": "beneish_m_score", "altman_z_double_prime": "altman_model_z_double_prime",
                      "piotroski_f_score": "piotroski_score"}


def _peer_value_text(metric: str, value: float | None, lang: str) -> str:
    if value is None:
        return L(lang, "na")
    if metric in RATIO_KINDS:
        return format_ratio(value, RATIO_KINDS[metric], lang)
    return format_number(value, ".0f" if metric == "piotroski_f_score" else ".2f", lang)


def peers_table(target: dict, stats: dict, ranks: dict, indicative_peers: list[str], lang: str, dark: bool):
    """Une ligne par indicateur : valeur de la société, médiane et intervalle interquartile des pairs,
    rang centile de la société parmi eux, nombre de pairs disposant de la donnée."""
    rows = []
    for metric in PEER_METRICS:
        label_key = PEER_METRIC_LABELS.get(metric, f"ratio_{metric}")
        stat = stats[metric]
        iqr = (f"{_peer_value_text(metric, stat['q1'], lang)} – {_peer_value_text(metric, stat['q3'], lang)}"
               if stat["n"] else L(lang, "na"))
        rank = ranks[metric]
        help_text = L(lang, f"{label_key}_help") if f"{label_key}_help" in TRANSLATIONS[lang] else ""
        if metric == "beneish_m_score":
            help_text = L(lang, "peers_beneish_note", n=len(indicative_peers))
        rows.append({"label": L(lang, label_key), "help": help_text, "cells": [
            {"text": _peer_value_text(metric, target["values"][metric], lang),
             "state": "na" if target["values"][metric] is None else "subtotal"},
            {"text": _peer_value_text(metric, stat["median"], lang), "state": "na" if stat["median"] is None else "ok"},
            {"text": iqr, "state": "na" if not stat["n"] else "ok"},
            {"text": L(lang, "peers_rank_text", rank=format_number(rank, ".0f", lang)) if rank is not None else L(lang, "na"),
             "state": "na" if rank is None else "ok"},
            {"text": str(stat["n"]), "state": "ok"},
        ]})
    columns = [L(lang, "col_company"), L(lang, "col_peer_median"), L(lang, "col_peer_iqr"), L(lang, "col_peer_rank"),
               L(lang, "col_peer_n")]
    return detail_table("table-peers", L(lang, "col_metric"), columns, rows, dark)


IMPORT_UNIT_NAMES = {1.0: "import_unit_units", 1e3: "import_unit_thousands", 1e6: "import_unit_millions",
                     1e9: "import_unit_billions"}


def _unit_text(unit: float, lang: str) -> str:
    """Unité de saisie du fichier en toutes lettres (« millions »), ou le multiplicateur s'il est inhabituel."""
    key = IMPORT_UNIT_NAMES.get(float(unit))
    return L(lang, key) if key else f"× {format_number(unit, 'g', lang)}"


def import_card(filename: str, meta: dict, regime: dict, latest_market_cap: float | None,
                latest_year: pd.Timestamp | None, lang: str):
    """Carte d'une société importée : pas de cours ni de change, seulement ce que déclare le fichier, et
    la capitalisation de la dernière clôture qui sert aux multiples."""
    currency = meta.get("currency") or L(lang, "na")
    if latest_market_cap is not None and latest_year is not None:
        cap_text = f"{format_amount(latest_market_cap, lang)} {currency}"
        cap_label = L(lang, "label_market_cap_at", year=format_year(latest_year, lang))
    else:
        cap_text, cap_label = L(lang, "na"), L(lang, "label_market_cap")
    header = html.Div([
        html.H5(meta.get("company") or filename, className="mb-1 d-inline"),
        dbc.Badge(L(lang, "badge_imported"), color="info", className="ms-2 align-text-bottom"),
        dbc.Badge(L(lang, f"regime_{regime['regime']}"), color="secondary" if regime["regime"] == "general" else "warning",
                  className="ms-2 align-text-bottom"),
    ], className="mb-2")
    return dbc.Card(dbc.CardBody([
        header,
        dbc.Row([
            _stat(L(lang, "label_source_file"), filename),
            _stat(L(lang, "label_sector"), meta.get("sector") or L(lang, "na")),
            _stat(L(lang, "label_industry"), meta.get("industry") or L(lang, "na")),
            _stat(L(lang, "label_reporting_currency"), currency),
            _stat(L(lang, "label_import_unit"), _unit_text(meta.get("unit") or 1.0, lang)),
            _stat(cap_label, cap_text),
        ]),
    ]), className="mb-3")


def import_feedback(result: dict | None, filename: str, lang: str):
    """Résultat d'un import : nombre d'exercices lus, ou la liste complète des erreurs (ligne, détail)."""
    if result is None:
        return dbc.Alert(L(lang, "import_error_unreadable_file"), color="danger", className="py-1 px-2 mb-0")
    if result["errors"]:
        items = []
        for error in result["errors"]:
            text = L(lang, f"import_error_{error['code']}", detail=error["detail"] or "")
            if error["line"] is not None:
                text = L(lang, "import_error_at_line", line=error["line"], text=text)
            items.append(html.Li(text))
        return dbc.Alert([html.Div(L(lang, "import_rejected", filename=filename)), html.Ul(items, className="mb-0")],
                         color="danger", className="py-1 px-2 mb-0")
    dataset = result["dataset"]
    return dbc.Alert(L(lang, "import_success", filename=filename, n=len(dataset["years"])), color="success",
                     className="py-1 px-2 mb-0")


def analysis_alerts(profile: dict, regime: dict, market: dict, consistency: dict, lang: str) -> list:
    """Bandeaux d'avertissement : analyses non applicables (banque/assureur), prudence sectorielle,
    conversion de devise impossible ou incohérente. Toujours affichés AVANT les chiffres, pour que
    l'utilisateur sache dans quelle mesure s'y fier."""
    alerts = []
    not_applicable = [analysis for analysis, ok in regime["applicable"].items() if not ok]
    if not_applicable:
        alerts.append(dbc.Alert(L(
            lang, "regime_not_applicable", regime=L(lang, f"regime_{regime['regime']}"),
            analyses=", ".join(L(lang, f"analysis_{a}") for a in not_applicable),
        ), color="warning"))
    if regime["caution"] == "third_party_funds":
        alerts.append(dbc.Alert(L(lang, "caution_third_party_funds", industry=regime["industry"]), color="info"))
    elif regime["caution"] == "unknown_industry":
        alerts.append(dbc.Alert(L(lang, "caution_unknown_industry"), color="info"))
    if market["reason"] == "fx_unavailable":
        alerts.append(dbc.Alert(L(lang, "warn_fx_unavailable", quote=market["quote_major_currency"],
                                  reporting=market["reporting_currency"]), color="warning"))
    elif market["reason"] == "currency_unknown":
        alerts.append(dbc.Alert(L(lang, "warn_currency_unknown"), color="warning"))
    if consistency["consistent"] is False:
        alerts.append(dbc.Alert(L(lang, "warn_minor_unit_inconsistent",
                                  ratio=format_number(consistency["empirical_ratio"], ".1f", lang),
                                  divisor=consistency["expected_divisor"]), color="warning"))
    return alerts


# ============================================================
# Écran
# ============================================================

def build_main(lang, v=None):
    v = v or {}
    return html.Div([
        html.P(L(lang, "intro"), className="text-muted"),
        dbc.Row([
            dbc.Col([
                dbc.Label(L(lang, "ticker_label"), html_for="ticker-input", className="mb-0"),
                # Largeur explicite : un .form-control dans une colonne "auto" sans contenu propre se
                # réduit sinon à presque rien (bug constaté dans les deux autres outils du dépôt).
                dcc.Input(
                    id="ticker-input", type="text", value=gv(v, "ticker-input", ""), debounce=False,
                    placeholder=L(lang, "ticker_placeholder"), className="form-control", style={"width": "160px"},
                ),
            ], width="auto"),
            dbc.Col([
                dbc.Label(L(lang, "quick_pick_label"), className="mb-0"),
                dcc.Dropdown(
                    id="quick-pick-dropdown",
                    options=[{"label": name, "value": ticker} for name, ticker in CAC40_TICKERS.items()],
                    placeholder=L(lang, "quick_pick_placeholder"), clearable=True, style={"width": "280px"},
                ),
            ], width="auto"),
            dbc.Col(
                dbc.Button(icon_label("search", L(lang, "analyze_btn")), id="analyze-btn", color="primary"),
                width="auto", className="d-flex align-items-end",
            ),
        ], className="mb-2 gx-3"),
        # Import d'états financiers : remplace Yahoo pour l'analyse (société radiée, plus d'historique).
        dbc.Row([
            dbc.Col([
                html.Div([dbc.Label(L(lang, "import_label"), className="mb-0")]
                         + info_tooltip("import-info", L(lang, "import_help"))),
                dcc.Upload(
                    id="statements-upload", children=html.Div(L(lang, "import_upload")), multiple=False,
                    style={"borderWidth": "1px", "borderStyle": "dashed", "borderRadius": "10px", "padding": "0.5rem 1rem",
                           "textAlign": "center", "cursor": "pointer", "width": "420px", "maxWidth": "100%"},
                ),
            ], width="auto"),
            dbc.Col([
                dbc.Button(icon_label("file-earmark-arrow-down", L(lang, "import_template_btn")), id="statements-template-btn", color="secondary",
                           outline=True, size="sm"),
                dcc.Download(id="statements-template-download"),
            ], width="auto", className="d-flex align-items-end"),
        ], className="mb-2 gx-3"),
        html.Div(id="statements-import-feedback", className="mb-3", style={"maxWidth": "760px"}),
    ], className="pt-3 px-3")


# Navigation entre les outils du dépôt (en-tête) : la page d'accueil est servie par run_all.py ; un
# outil lancé seul (Docker, app.py) garde ces liens, qui ne répondent alors que si les autres tournent.
HOME_URL = "http://localhost:8049"
TOOL_URLS = {"projection": "http://localhost:8050", "valuation": "http://localhost:8051",
             "analysis": "http://localhost:8052"}
CURRENT_TOOL = "analysis"


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
