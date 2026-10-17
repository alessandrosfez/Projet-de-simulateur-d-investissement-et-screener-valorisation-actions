"""
Tests de l'import d'états financiers en CSV (engine.py) : lecture du format du modèle, validation
stricte (chaque erreur listée avec sa ligne, aucun import partiel), cellules vides jamais lues comme 0,
normalisation avec les mêmes identités comptables que pour Yahoo, et équivalence avec le chemin Yahoo.
Usage : pip install -r requirements-dev.txt && pytest -v
"""
import pandas as pd
import pytest

import engine as m

T, P = pd.Timestamp("2018-12-31"), pd.Timestamp("2017-12-31")

VALID = """# Exemple de société
# societe = Exemple SA
# devise = EUR
# unite = millions
# regime = general
poste;libelle;2018-12-31;2017-12-31
revenue;Chiffre d'affaires;2 016,2;1 489,6
cost_of_revenue;Coût des ventes;1 100,0;800,0
net_income;Résultat net;347,4;256,1
total_assets;Total actif;5 854,9;4 534,0
receivables;Créances clients;;
market_cap;Capitalisation;18 600;14 200
"""


def _parse(text: str) -> dict:
    return m.parse_statements_csv(text)


def _codes(result: dict) -> list[str]:
    return [e["code"] for e in result["errors"]]


def test_parses_metadata_european_amounts_and_unit():
    result = _parse(VALID)
    assert result["errors"] == []
    dataset = result["dataset"]
    assert dataset["meta"]["company"] == "Exemple SA" and dataset["meta"]["currency"] == "EUR"
    assert dataset["meta"]["unit"] == 1e6 and dataset["meta"]["regime"] == "general"
    assert dataset["years"] == ["2018-12-31", "2017-12-31"]
    assert dataset["values"]["revenue"]["2018-12-31"] == pytest.approx(2016.2e6)
    assert dataset["market_cap"]["2017-12-31"] == pytest.approx(14200e6)


def test_empty_cell_stays_missing_never_zero():
    dataset = _parse(VALID)["dataset"]
    assert dataset["values"]["receivables"]["2018-12-31"] is None
    assert dataset["values"]["inventory"]["2018-12-31"] is None  # ligne absente du fichier
    explicit_zero = _parse(VALID.replace("receivables;Créances clients;;", "receivables;Créances clients;0;n.d."))
    assert explicit_zero["dataset"]["values"]["receivables"] == {"2018-12-31": 0.0, "2017-12-31": None}


def test_comma_separated_file_with_iso_dates_is_read():
    text = "poste,2018-12-31\nrevenue,1234.5\n"
    assert _parse(text)["dataset"]["values"]["revenue"]["2018-12-31"] == pytest.approx(1234.5)


def test_french_dates_in_header():
    dataset = _parse("poste;31/12/2018;31/12/2017\nrevenue;10;9\n")["dataset"]
    assert dataset["years"] == ["2018-12-31", "2017-12-31"]


@pytest.mark.parametrize("bad_line,code", [
    ("revenu;CA;1;2", "unknown_key"),
    ("revenue;CA;1;2", "duplicate_key"),
    ("ebit;EBIT;abc;2", "unreadable_amount"),
    ("ebit;EBIT;-;2", "ambiguous_dash"),
    (";;5;6", "missing_key"),
])
def test_invalid_rows_reject_the_whole_import_with_their_line(bad_line, code):
    text = "poste;libelle;2018-12-31;2017-12-31\nrevenue;CA;10;9\n" + bad_line + "\n"
    result = _parse(text)
    assert result["dataset"] is None
    assert result["errors"][0]["code"] == code
    assert result["errors"][0]["line"] == 3


def test_all_errors_are_listed_not_only_the_first():
    text = "# unite = douzaines\nposte;2018-12-31\nrevenu;1\nebit;x\n"
    assert _codes(_parse(text)) == ["bad_unit", "unknown_key", "unreadable_amount"]


@pytest.mark.parametrize("header,code", [
    ("poste;libelle", "no_year_columns"),
    ("poste;2018;2017", "bare_year"),
    ("poste;2018-12-31;31/12/2018", "duplicate_year"),
])
def test_header_errors(header, code):
    assert code in _codes(_parse(f"{header}\nrevenue;1;2\n"))


def test_metadata_errors():
    assert _codes(_parse("# devis = EUR\nposte;2018-12-31\nrevenue;1\n")) == ["unknown_meta"]
    assert _codes(_parse("# regime = hedge_fund\nposte;2018-12-31\nrevenue;1\n")) == ["bad_regime"]


def test_free_comments_are_ignored():
    text = "# Chiffres tirés du rapport annuel, page 112\n# (montants en millions)\nposte;2018-12-31\nrevenue;1\n"
    assert _parse(text)["errors"] == []


def test_file_without_any_value_is_rejected():
    assert _codes(_parse("poste;2018-12-31\nrevenue;\n")) == ["no_values"]


def test_normalize_imported_marks_provenance_and_applies_identities():
    ns = m.normalize_imported(_parse(VALID)["dataset"])
    assert ns.years == [T, P]
    assert ns.provenance["revenue"][T] == {"source": "imported"}
    assert ns.get("gross_profit", T) == pytest.approx((2016.2 - 1100.0) * 1e6)
    assert ns.provenance["gross_profit"][T]["source"] == "derived"
    assert ns.get("inventory", T) is None
    assert ns.provenance["inventory"][T] == {"source": "missing", "reason": "not_in_import"}


def test_import_and_yahoo_paths_give_the_same_normalized_values():
    """Mêmes montants publiés, lus par le chemin Yahoo (libellés yfinance) ou importés (clés internes) :
    tous les postes normalisés, dérivés compris, doivent coïncider."""
    published = {"Total Revenue": ("revenue", [100.0, 90.0]), "Cost Of Revenue": ("cost_of_revenue", [60.0, 50.0]),
                 "Pretax Income": ("pretax_income", [20.0, 15.0]), "Interest Expense": ("interest_expense", [5.0, 4.0]),
                 "Net Income": ("net_income", [14.0, 11.0])}
    balance = {"Total Assets": ("total_assets", [300.0, 280.0]), "Current Assets": ("current_assets", [120.0, 100.0]),
               "Current Liabilities": ("current_liabilities", [80.0, 70.0])}
    cashflow = {"Operating Cash Flow": ("cfo", [25.0, 18.0]), "Capital Expenditure": ("capex", [-10.0, -8.0])}

    def frame(rows):
        return pd.DataFrame({label: vals for label, (_key, vals) in rows.items()}, index=[T, P]).T

    yahoo = m.normalize_statements(frame(published), frame(balance), frame(cashflow))
    lines = ["poste;2018-12-31;2017-12-31"] + [
        f"{key};{vals[0]};{vals[1]}" for rows in (published, balance, cashflow) for key, vals in rows.values()
    ]
    imported = m.normalize_imported(_parse("\n".join(lines))["dataset"])
    assert imported.years == yahoo.years
    for key in m.FIELD_KEYS:
        for year in yahoo.years:
            assert imported.get(key, year) == yahoo.get(key, year), key


def test_regime_from_import_explicit_or_detected():
    assert m.regime_from_import({"regime": "bank"})["applicable"]["beneish"] is False
    assert m.regime_from_import({"regime": "general"})["caution"] is None
    assert m.regime_from_import({"regime": None, "industry": None})["caution"] == "unknown_industry"


def test_imported_market_caps_and_benford_amounts():
    dataset = _parse(VALID)["dataset"]
    assert m.imported_market_caps(dataset)[T] == pytest.approx(18600e6)
    amounts = m.imported_statement_amounts(dataset)
    assert 18600e6 not in amounts  # capitalisation exclue
    assert len(amounts) == 8


def test_template_lists_every_key_and_parses_back():
    labels = {"_key": "poste", "_label": "libelle", **{key: f"libellé {key}" for key in m.IMPORT_KEYS}}
    text = m.statements_csv_template(labels, ["Modèle"], [("devise", "EUR"), ("unite", "millions")],
                                     ["2024-12-31", "2023-12-31"])
    keys = [line.split(";")[0] for line in text.splitlines()[4:]]
    assert keys == list(m.IMPORT_KEYS)
    assert _codes(_parse(text)) == ["no_values"]  # modèle vierge : rien d'autre à redire
