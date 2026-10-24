"""
Tests des définitions de colonnes du tableau de criblage (layout.py) : une valeur manquante n'est
jamais coloriée ni affichée comme un nombre, la colonne Entreprise reste figée.
Usage : pip install -r requirements-dev.txt && pytest -v
"""
import layout


def _defs():
    labels = {c: c for c in ["Entreprise", "Ticker", "Score", "PEG", "P/E (trailing)", "Capitalisation"]}
    return {d["field"]: d for d in layout.stocks_column_defs(labels, {"PEG": "aide PEG"})}


def test_every_colour_rule_checks_for_a_missing_value_first():
    for column, rules in layout.CELL_CLASS_RULES.items():
        for css_class, expression in rules.items():
            assert expression.split("&&")[0].strip().endswith("!= null"), (column, css_class)


def test_numeric_columns_show_na_for_missing_values_and_company_is_pinned():
    defs = _defs()
    assert defs["Score"]["valueFormatter"] == layout.NUMBER_FORMATTER
    assert "'N/A'" in layout.NUMBER_FORMATTER["function"]
    assert defs["PEG"]["headerTooltip"] == "aide PEG" and "headerTooltip" not in defs["Score"]
    assert defs["Entreprise"]["pinned"] == "left"
    assert "valueFormatter" not in defs["Capitalisation"] and defs["Capitalisation"]["type"] == "rightAligned"
