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
    assert regime["applicable"] == {"beneish": False, "altman": False, "piotroski": False, "working_capital": False, "earnings_quality": False}


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
        "applicable": {"beneish": True, "altman": True, "piotroski": True, "working_capital": True, "earnings_quality": True},
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


# ---------- qualité des résultats (cas calculés à la main) ----------

def _quality_case(**overrides):
    """Société synthétique sur deux exercices, chiffres ronds pour un calcul à la main."""
    income = {"Net Income Including Noncontrolling Interests": [100, 80], "Net Income": [90, 72],
              "Total Revenue": [1000, 900], "Cost Of Revenue": [600, 540], "Reconciled Depreciation": [30, 28]}
    balance = {"Total Assets": [1100, 900], "Accounts Receivable": [120, 100], "Inventory": [80, 75],
               "Accounts Payable": [90, 70]}
    cashflow = {"Operating Cash Flow": [150, 70], "Capital Expenditure": [-50, -40], "Change In Working Capital": [-20, -15]}
    for group in (income, balance, cashflow):
        for label, values in overrides.items():
            if label in group:
                group[label] = values
    extra = {k: v for k, v in overrides.items() if not any(k in g for g in (income, balance, cashflow))}
    for label, (statement, values) in extra.items():
        {"income": income, "balance": balance, "cashflow": cashflow}[statement][label] = values
    return m.normalize_statements(_frame(income), _frame(balance), _frame(cashflow))


def test_cash_conversion_uses_net_income_including_minorities():
    # CFO 150 / RN y compris minoritaires 100 = 1,5 (pas 150 / 90, la part du groupe).
    # FCF = CFO 150 + capex -50 = 100 -> FCF / RN = 100 / 100 = 1,0.
    result = m.cash_conversion(_quality_case())[Y1]
    assert result["cfo_to_net_income"]["value"] == pytest.approx(1.5)
    assert result["fcf_to_net_income"]["value"] == pytest.approx(1.0)
    assert result["cfo_to_net_income"]["components"] == {"cfo": 150.0, "net_income": 100.0}
    assert result["cfo_to_net_income"]["flags"] == ()


def test_cash_conversion_falls_back_to_group_share_and_flags_it():
    ns = _quality_case(**{"Net Income Including Noncontrolling Interests": [np.nan, np.nan]})
    result = m.cash_conversion(ns)[Y1]["cfo_to_net_income"]
    assert result["value"] == pytest.approx(150 / 90)
    assert result["flags"] == ("group_share_fallback",)


def test_cash_conversion_not_meaningful_on_a_loss():
    ns = _quality_case(**{"Net Income Including Noncontrolling Interests": [-40, 80]})
    result = m.cash_conversion(ns)[Y1]["cfo_to_net_income"]
    assert result["value"] is None
    assert result["reason"] == "non_positive_denominator"
    assert result["denominator"] == "net_income"


def test_cash_conversion_missing_cfo_is_reported():
    ns = _quality_case(**{"Operating Cash Flow": [np.nan, 70]})
    result = m.cash_conversion(ns)[Y1]
    assert result["cfo_to_net_income"]["reason"] == "missing_inputs"
    assert result["cfo_to_net_income"]["missing"] == ("cfo",)
    # Le FCF n'est pas publié ici et sa dérivation (CFO + capex) échoue aussi.
    assert result["fcf_to_net_income"]["missing"] == ("fcf",)


def test_sloan_accruals_on_average_total_assets():
    # (RN 100 - CFO 150) / ((1 100 + 900) / 2) = -50 / 1 000 = -5 % : CFO supérieur au résultat.
    result = m.sloan_accruals(_quality_case())
    assert result[Y1]["value"] == pytest.approx(-0.05)
    assert result[Y1]["components"] == {"net_income": 100.0, "cfo": 150.0, "total_assets": 1100.0,
                                        "total_assets_prior": 900.0}


def test_sloan_accruals_oldest_year_has_no_opening_balance():
    result = m.sloan_accruals(_quality_case())
    assert result[Y0]["value"] is None
    assert result[Y0]["reason"] == "no_prior_year"


def test_sloan_accruals_positive_when_earnings_exceed_cash():
    # (100 - 60) / 1 000 = +4 % : 40 de résultat non encore encaissé.
    ns = _quality_case(**{"Operating Cash Flow": [60, 70]})
    assert m.sloan_accruals(ns)[Y1]["value"] == pytest.approx(0.04)


def test_bridge_reconciles_exactly_to_cfo():
    # RN 100 + dotations 30 + variation BFR -20 = 110 ; autres éléments = 150 - 110 = 40.
    bridge = m.net_income_to_cfo_bridge(_quality_case(), Y1)
    assert bridge["available"] is True
    assert [(s["key"], s["value"]) for s in bridge["steps"]] == [
        ("net_income", 100.0), ("d_and_a", 30.0), ("change_in_working_capital", -20.0), ("other_items", 40.0),
    ]
    assert sum(s["value"] for s in bridge["steps"]) == pytest.approx(bridge["cfo"])


def test_bridge_missing_item_goes_into_residual_and_is_reported_not_zeroed():
    ns = _quality_case(**{"Change In Working Capital": [np.nan, -15]})
    bridge = m.net_income_to_cfo_bridge(ns, Y1)
    assert bridge["missing_items"] == ("change_in_working_capital",)
    assert [s["key"] for s in bridge["steps"]] == ["net_income", "d_and_a", "other_items"]
    assert bridge["steps"][-1]["value"] == pytest.approx(150 - 100 - 30)


def test_bridge_unavailable_without_cfo():
    ns = _quality_case(**{"Operating Cash Flow": [np.nan, 70]})
    bridge = m.net_income_to_cfo_bridge(ns, Y1)
    assert bridge["available"] is False
    assert bridge["missing"] == ("cfo",)


# ---------- BFR en jours (cas calculés à la main) ----------

def test_working_capital_days_on_closing_balances():
    # DSO = 120 / 1 000 × 365 = 43,8 j ; DIO = 80 / 600 × 365 = 48,67 j ; DPO = 90 / 600 × 365 = 54,75 j.
    # Cycle = 43,8 + 48,67 - 54,75 = 37,72 j.
    days = m.working_capital_days(_quality_case())[Y1]
    assert days["dso"]["value"] == pytest.approx(43.8)
    assert days["dio"]["value"] == pytest.approx(80 / 600 * 365)
    assert days["dpo"]["value"] == pytest.approx(54.75)
    assert days["ccc"]["value"] == pytest.approx(43.8 + 80 / 600 * 365 - 54.75)


def test_dio_and_dpo_not_computed_on_revenue_when_cost_of_revenue_missing():
    ns = _quality_case(**{"Cost Of Revenue": [np.nan, np.nan]})
    days = m.working_capital_days(ns)[Y1]
    assert days["dso"]["value"] == pytest.approx(43.8)
    assert days["dio"]["value"] is None and days["dio"]["missing"] == ("cost_of_revenue",)
    assert days["dpo"]["value"] is None
    assert days["ccc"]["value"] is None and days["ccc"]["missing"] == ("dio", "dpo")


def test_broad_receivables_used_but_flagged():
    ns = _quality_case(**{"Accounts Receivable": [np.nan, np.nan], "Receivables": ("balance", [150, 130])})
    days = m.working_capital_days(ns)[Y1]
    assert days["dso"]["value"] == pytest.approx(150 / 1000 * 365)
    assert days["dso"]["flags"] == ("broad_receivables",)
    assert "broad_receivables" in days["ccc"]["flags"]


def test_metric_trend_first_to_last_available_year():
    # DSO 2023 = 100 / 900 × 365 = 40,56 j -> 2024 = 43,8 j.
    trend = m.metric_trend(m.working_capital_days(_quality_case()), "dso")
    assert trend["first_year"] == Y0 and trend["last_year"] == Y1
    assert trend["delta"] == pytest.approx(43.8 - 100 / 900 * 365)


def test_metric_trend_needs_two_points():
    days = m.working_capital_days(_quality_case(**{"Accounts Receivable": [120, np.nan]}))
    assert m.metric_trend(days, "dso") is None
