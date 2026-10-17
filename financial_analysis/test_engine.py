"""
Tests unitaires du moteur de calcul pur (engine.py), sur des DataFrames synthétiques au format
yfinance (index = libellés, colonnes = dates de clôture) : aucun réseau, aucune dépendance Dash.
Usage : pip install -r requirements-dev.txt && pytest -v
"""
import numpy as np
import pandas as pd
import pytest

import engine as m

Y1, Y0 = pd.Timestamp("2024-12-31"), pd.Timestamp("2023-12-31")


def _frame(rows: dict[str, list]) -> pd.DataFrame:
    """État financier synthétique : {libellé: [valeur exercice récent, valeur exercice précédent]}."""
    return pd.DataFrame.from_dict(rows, orient="index", columns=[Y1, Y0], dtype=float)


EMPTY = pd.DataFrame()


# ---------- schéma ----------

def test_schema_keys_are_unique():
    assert len(m.FIELD_KEYS) == len(set(m.FIELD_KEYS))


def test_schema_derivation_operands_are_defined_earlier():
    """Les identités comptables sont évaluées dans l'ordre du schéma : un opérande défini plus bas
    serait encore vide au moment du calcul, et l'identité échouerait sans raison apparente."""
    seen = set()
    for spec in m.FIELD_SCHEMA:
        if spec.derivation is not None:
            assert set(spec.derivation[1]) <= seen, spec.key
        seen.add(spec.key)


def test_schema_statements_are_known():
    assert {spec.statement for spec in m.FIELD_SCHEMA} <= set(m.STATEMENTS)


# ---------- normalisation ----------

def test_published_items_are_mapped_with_provenance():
    income = _frame({"Total Revenue": [1000, 900], "Net Income": [80, 70]})
    result = m.normalize_statements(income, EMPTY, EMPTY)
    assert result.years == [Y1, Y0]
    assert result.get("revenue", Y1) == 1000.0
    assert result.get("net_income", Y0) == 70.0
    assert result.provenance["revenue"][Y1] == {"source": "published", "statement": "income", "label": "Total Revenue"}


def test_missing_item_is_none_never_zero():
    income = _frame({"Total Revenue": [1000, 900]})
    result = m.normalize_statements(income, EMPTY, EMPTY)
    assert result.get("net_income", Y1) is None
    assert result.provenance["net_income"][Y1] == {"source": "missing", "reason": "not_in_yfinance"}


def test_nan_in_yfinance_is_treated_as_missing():
    # Le résultat net garde l'exercice 2023 dans les années retenues (un exercice sans aucune donnée
    # serait écarté, voir test_years_union_across_statements_and_ghost_column_dropped).
    income = _frame({"Total Revenue": [1000, np.nan], "Net Income": [80, 70]})
    result = m.normalize_statements(income, EMPTY, EMPTY)
    assert result.get("revenue", Y0) is None
    assert result.provenance["revenue"][Y0]["source"] == "missing"


def test_published_zero_stays_zero():
    """Un 0 publié est une vraie valeur (ex. stocks nuls d'une société de services), à ne pas
    confondre avec une donnée absente."""
    balance = _frame({"Inventory": [0.0, 0.0], "Total Assets": [500, 450]})
    result = m.normalize_statements(EMPTY, balance, EMPTY)
    assert result.get("inventory", Y1) == 0.0
    assert result.provenance["inventory"][Y1]["source"] == "published"


def test_gross_profit_derived_from_accounting_identity():
    income = _frame({"Total Revenue": [1000, 900], "Cost Of Revenue": [600, 560]})
    result = m.normalize_statements(income, EMPTY, EMPTY)
    assert result.get("gross_profit", Y1) == 400.0
    assert result.provenance["gross_profit"][Y1] == {
        "source": "derived", "operator": "diff", "operands": ("revenue", "cost_of_revenue"),
    }


def test_published_value_wins_over_derivation():
    income = _frame({"Total Revenue": [1000, 900], "Cost Of Revenue": [600, 560], "Gross Profit": [410, 345]})
    result = m.normalize_statements(income, EMPTY, EMPTY)
    assert result.get("gross_profit", Y1) == 410.0
    assert result.provenance["gross_profit"][Y1]["source"] == "published"


def test_derivation_with_missing_operand_reports_which_one():
    income = _frame({"Total Revenue": [1000, 900]})
    result = m.normalize_statements(income, EMPTY, EMPTY)
    assert result.get("gross_profit", Y1) is None
    origin = result.provenance["gross_profit"][Y1]
    assert origin["reason"] == "derivation_inputs_missing"
    assert origin["missing_operands"] == ("cost_of_revenue",)
    assert origin["operator"] == "diff" and origin["operands"] == ("revenue", "cost_of_revenue")


def test_ebit_prefers_identity_over_neighbouring_operating_income():
    """L'identité de Yahoo (résultat avant impôt + intérêts) est exacte, le résultat opérationnel
    publié n'est qu'un voisin : il ne doit servir que si l'identité est impossible."""
    income = _frame({"Pretax Income": [100, 90], "Interest Expense": [20, 25], "Operating Income": [130, 120]})
    result = m.normalize_statements(income, EMPTY, EMPTY)
    assert result.get("ebit", Y1) == 120.0
    assert result.provenance["ebit"][Y1]["source"] == "derived"


def test_neighbouring_item_used_as_last_resort_and_flagged():
    income = _frame({"Operating Income": [130, 120]})
    result = m.normalize_statements(income, EMPTY, EMPTY)
    assert result.get("ebit", Y1) == 130.0
    assert result.provenance["ebit"][Y1] == {"source": "equivalent", "statement": "income", "label": "Operating Income"}


def test_broader_receivables_only_as_fallback():
    balance = _frame({"Accounts Receivable": [200, 180], "Receivables": [260, 240]})
    result = m.normalize_statements(EMPTY, balance, EMPTY)
    assert result.get("receivables", Y1) == 200.0
    balance_without_trade = _frame({"Receivables": [260, 240]})
    fallback = m.normalize_statements(EMPTY, balance_without_trade, EMPTY)
    assert fallback.get("receivables", Y1) == 260.0
    assert fallback.provenance["receivables"][Y1]["source"] == "equivalent"


def test_cross_statement_published_item():
    """Les dotations aux amortissements absentes du compte de résultat sont reprises du tableau de
    flux (même grandeur), avec l'état d'origine dans la provenance."""
    cashflow = _frame({"Depreciation And Amortization": [50, 45]})
    result = m.normalize_statements(EMPTY, EMPTY, cashflow)
    assert result.get("d_and_a", Y1) == 50.0
    assert result.provenance["d_and_a"][Y1]["statement"] == "cashflow"


def test_chained_derivations_ebitda_from_derived_ebit():
    income = _frame({"Pretax Income": [100, 90], "Interest Expense": [20, 25], "Reconciled Depreciation": [30, 28]})
    result = m.normalize_statements(income, EMPTY, EMPTY)
    assert result.get("ebitda", Y1) == 150.0
    assert result.provenance["ebitda"][Y1]["operands"] == ("ebit", "d_and_a")


def test_fcf_derived_with_negative_capex_sign():
    cashflow = _frame({"Operating Cash Flow": [300, 280], "Capital Expenditure": [-120, -100]})
    result = m.normalize_statements(EMPTY, EMPTY, cashflow)
    assert result.get("fcf", Y1) == 180.0


def test_lease_liabilities_sum_of_short_and_long_term():
    balance = _frame({"Current Capital Lease Obligation": [10, 9], "Long Term Capital Lease Obligation": [40, 38]})
    result = m.normalize_statements(EMPTY, balance, EMPTY)
    assert result.get("lease_liabilities", Y1) == 50.0


def test_years_union_across_statements_and_ghost_column_dropped():
    """yfinance ajoute souvent un exercice ancien vide (ici 2022 dans le tableau de flux) : il ne doit
    pas produire une colonne entière de n.d."""
    income = _frame({"Total Revenue": [1000, 900]})
    ghost = pd.Timestamp("2022-12-31")
    cashflow = pd.DataFrame({Y1: [300.0], Y0: [280.0], ghost: [np.nan]}, index=["Operating Cash Flow"])
    result = m.normalize_statements(income, EMPTY, cashflow)
    assert result.years == [Y1, Y0]


def test_columns_with_time_component_are_aligned_on_dates():
    income = pd.DataFrame({pd.Timestamp("2024-12-31 00:00:00"): [1000.0]}, index=["Total Revenue"])
    balance = pd.DataFrame({pd.Timestamp("2024-12-31"): [500.0]}, index=["Total Assets"])
    result = m.normalize_statements(income, balance, EMPTY)
    assert result.years == [Y1]
    assert result.get("revenue", Y1) == 1000.0 and result.get("total_assets", Y1) == 500.0


def test_all_empty_statements_give_no_years():
    result = m.normalize_statements(EMPTY, None, EMPTY)
    assert result.years == []


def test_available_count():
    income = _frame({"Total Revenue": [1000, 900], "Cost Of Revenue": [600, 560]})
    result = m.normalize_statements(income, EMPTY, EMPTY)
    assert result.available_count(Y1) == 3  # CA, coût des ventes, marge brute dérivée


# ---------- classement sectoriel ----------

@pytest.mark.parametrize("industry", ["Banks - Regional", "Banks - Diversified"])
def test_banks_are_detected_and_analyses_disabled(industry):
    regime = m.detect_sector_regime("Financial Services", industry)
    assert regime["regime"] == "bank"
    assert regime["applicable"] == {"beneish": False, "altman": False, "working_capital": False}


@pytest.mark.parametrize("industry", ["Insurance - Diversified", "Insurance - Life", "Insurance - Reinsurance"])
def test_insurers_are_detected(industry):
    assert m.detect_sector_regime("Financial Services", industry)["regime"] == "insurer"


def test_insurance_brokers_are_analyzed_with_caution():
    regime = m.detect_sector_regime("Financial Services", "Insurance Brokers")
    assert regime["regime"] == "general"
    assert regime["caution"] == "third_party_funds"
    assert all(regime["applicable"].values())


def test_exchange_is_analyzed_with_caution_not_excluded():
    regime = m.detect_sector_regime("Financial Services", "Financial Data & Stock Exchanges")
    assert regime["regime"] == "general"
    assert regime["caution"] == "third_party_funds"


def test_industrial_company_has_everything_applicable():
    regime = m.detect_sector_regime("Basic Materials", "Specialty Chemicals")
    assert regime == {
        "regime": "general", "caution": None,
        "applicable": {"beneish": True, "altman": True, "working_capital": True},
        "sector": "Basic Materials", "industry": "Specialty Chemicals",
    }


@pytest.mark.parametrize("industry", [None, "", "   "])
def test_unknown_industry_is_flagged(industry):
    regime = m.detect_sector_regime(None, industry)
    assert regime["regime"] == "general"
    assert regime["caution"] == "unknown_industry"


# ---------- devises ----------

def test_split_currency_unit():
    assert m.split_currency_unit("GBp") == ("GBP", 100.0)
    assert m.split_currency_unit("EUR") == ("EUR", 1.0)
    assert m.split_currency_unit(None) == (None, 1.0)


def test_same_currency_no_conversion():
    result = m.market_values_in_reporting_currency(173.16, 110e9, "EUR", "EUR", None)
    assert result["price"] == pytest.approx(173.16)
    assert result["market_cap"] == pytest.approx(110e9)
    assert result["fx_rate"] == 1.0 and result["reason"] is None


def test_pence_quote_with_usd_accounts_like_shell():
    """Cas de Shell : cours 3 938 GBp, capitalisation 224 Md£ (déjà en livres), comptes en USD."""
    result = m.market_values_in_reporting_currency(3938.0, 224e9, "GBp", "USD", 1.333)
    assert result["divisor"] == 100.0
    assert result["price"] == pytest.approx(39.38 * 1.333)
    assert result["market_cap"] == pytest.approx(224e9 * 1.333)
    assert result["quote_major_currency"] == "GBP"


def test_pence_quote_with_gbp_accounts_only_divides_price():
    result = m.market_values_in_reporting_currency(535.0, 11.8e9, "GBp", "GBP", None)
    assert result["price"] == pytest.approx(5.35)
    assert result["market_cap"] == pytest.approx(11.8e9)


def test_missing_fx_rate_gives_none_not_unconverted_values():
    result = m.market_values_in_reporting_currency(3938.0, 224e9, "GBp", "USD", None)
    assert result["price"] is None and result["market_cap"] is None
    assert result["reason"] == "fx_unavailable"


def test_unknown_reporting_currency():
    result = m.market_values_in_reporting_currency(100.0, 1e9, "EUR", None, None)
    assert result["reason"] == "currency_unknown"
    assert result["price"] is None


def test_minor_unit_consistency_matches_pence_divisor():
    # Shell : 3 938 GBp / (11,65 × 3,38 £) = 100, alors que les comptes sont en USD.
    check = m.minor_unit_consistency(3938.0, 11.6508875, 3.38, 100.0)
    assert check["consistent"] is True
    assert check["empirical_ratio"] == pytest.approx(100.0, rel=1e-3)


def test_minor_unit_consistency_flags_mismatch():
    check = m.minor_unit_consistency(39.38, 11.65, 3.38, 100.0)
    assert check["consistent"] is False


def test_minor_unit_consistency_not_computable_without_positive_pe():
    assert m.minor_unit_consistency(100.0, None, 2.0, 1.0)["consistent"] is None
    assert m.minor_unit_consistency(100.0, -5.0, -2.0, 1.0)["consistent"] is None
