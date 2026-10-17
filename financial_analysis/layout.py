"""
Construction de l'interface Dash (un seul écran, pas de sidebar, comme stock_valuation) et helpers
d'affichage réutilisés par callbacks.py (mise en forme des montants, texte de provenance, tableaux
d'états financiers). Ce module ne dépend jamais de callbacks.py ni de l'instance `app` (pour éviter
tout import circulaire), et ne fait aucun calcul financier : tout chiffre affiché vient d'engine.py.
"""
import dash_bootstrap_components as dbc
import pandas as pd
from dash import dash_table, dcc, html

from constants import CAC40_TICKERS
from engine import FIELD_SCHEMA, NormalizedStatements
from i18n import L

GRAPH_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "select2d", "lasso2d", "autoScale2d",
        "hoverCompareCartesian", "hoverClosestCartesian", "toggleSpikelines",
    ],
}

TABLE_BASE_CELL_STYLE = {"fontSize": "0.82rem", "textAlign": "right", "padding": "0.45rem 0.8rem", "minWidth": "95px"}

# Champs dont la valeur doit survivre à un changement de langue (voir gv() et
# callbacks.rebuild_on_language_change).
TAB_STATE_FIELDS = [("ticker-input", "value")]


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

def format_amount(value: float | None, lang: str) -> str:
    """Montant abrégé (Md/M en français, bn/m en anglais), signe conservé ; « n.d. » si None.
    Les états financiers se comptent en milliards : les afficher en entier les rendrait illisibles."""
    if value is None:
        return L(lang, "na")
    sign = "-" if value < 0 else ""
    abs_value = abs(value)
    for threshold, unit_key in ((1e9, "unit_billion"), (1e6, "unit_million")):
        if abs_value >= threshold:
            return f"{sign}{abs_value / threshold:,.2f} {L(lang, unit_key)}".replace(",", " ")
    return f"{sign}{abs_value:,.0f}".replace(",", " ")


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
    if source == "derived":
        return L(lang, "prov_derived", formula=_formula_text(origin["operator"], origin["operands"], lang))
    if origin.get("reason") == "derivation_inputs_missing":
        return L(
            lang, "prov_missing_derivation",
            formula=_formula_text(origin["operator"], origin["operands"], lang),
            missing=", ".join(L(lang, f"field_{key}") for key in origin["missing_operands"]),
        )
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


def format_ratio(value: float | None, kind: str, lang: str, signed: bool = False) -> str:
    if value is None:
        return L(lang, "na")
    if kind == "percent":
        return f"{value * 100:+.1f} %" if signed or value < 0 else f"{value * 100:.1f} %"
    if kind == "days":
        return f"{value:+.0f} {L(lang, 'unit_days')}" if signed else f"{value:.0f} {L(lang, 'unit_days')}"
    return f"{value:+.2f}x" if signed else f"{value:.2f}x"


def _component_label(key: str, lang: str) -> str:
    """Nom lisible d'une composante : poste des états financiers, ou ratio (le cycle de conversion se
    compose de DSO, DIO et DPO)."""
    field_label = L(lang, f"field_{key}")
    return field_label if field_label != f"field_{key}" else L(lang, f"ratio_{key}")


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
            row["trend"] = L(lang, "trend_na") if trend is None else L(
                lang, "trend_text", delta=format_ratio(trend["delta"], kind, lang, signed=True),
                first=trend["first_year"].year, last=trend["last_year"].year,
            )
        rows.append(row)
        tooltips.append(tooltip)

    style_header, style_cell, style_data = table_style_overrides(dark)
    muted = "#8b93a7" if dark else "#8a8f99"
    conditional = []
    for year_id in year_ids:
        conditional.append({"if": {"column_id": year_id, "filter_query": f"{{_state_{year_id}}} = flagged"},
                            "fontStyle": "italic"})
        conditional.append({"if": {"column_id": year_id, "filter_query": f"{{_state_{year_id}}} = na"}, "color": muted})
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
        fx_text = L(lang, "fx_detail", quote=market["quote_major_currency"], rate=market["fx_rate"],
                    reporting=market["reporting_currency"])
    minor_unit_note = None
    if market["divisor"] != 1.0:
        minor_unit_note = html.Small(
            L(lang, "minor_unit_detail", quote_raw=profile["quote_currency"], divisor=market["divisor"]),
            className="text-muted",
        )
    price_text = f"{market['price']:,.2f} {reporting}".replace(",", " ") if market["price"] is not None else L(lang, "na")
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
        alerts.append(dbc.Alert(L(lang, "warn_minor_unit_inconsistent", ratio=consistency["empirical_ratio"],
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
                dbc.Button(L(lang, "analyze_btn"), id="analyze-btn", color="primary"),
                width="auto", className="d-flex align-items-end",
            ),
        ], className="mb-3 gx-3"),
    ], className="pt-3 px-3")


def build_header_text(lang):
    return [
        html.H2(L(lang, "app_title")),
        html.P(L(lang, "app_subtitle"), className="text-muted"),
    ]


def build_footer(lang):
    return html.Small(L(lang, "footer_disclaimer"), className="text-muted")
