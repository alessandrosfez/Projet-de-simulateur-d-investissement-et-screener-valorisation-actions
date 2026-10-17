"""
Tests du module loi de Benford (engine.py) : un échantillon conforme généré synthétiquement passe,
un échantillon uniforme échoue, le seuil de taille déclenche bien l'avertissement, et la lecture des
montants et des CSV gère les formats européens.
Usage : pip install -r requirements-dev.txt && pytest -v
"""
import math

import numpy as np
import pandas as pd
import pytest

import engine as m


def _benford_sample(n: int, seed: int = 0) -> list[float]:
    """Montants dont la mantisse est uniforme en échelle logarithmique sur 6 décades : le premier chiffre
    suit alors exactement la loi de Benford (propriété d'invariance d'échelle)."""
    rng = np.random.default_rng(seed)
    return list(10 ** rng.uniform(1, 7, size=n))


# ---------- échantillons de référence ----------

def test_synthetic_benford_sample_conforms():
    result = m.benford_first_digit_test(_benford_sample(5000))
    assert result["n"] == 5000
    assert result["conformity"] == "close"
    assert result["mad"] < 0.006
    assert result["p_value"] > 0.01
    assert result["sample_warning"] is None


def test_uniform_first_digits_fail():
    # Entiers de 100 à 999 : chaque premier chiffre a 1 chance sur 9, loin de 30 % pour le 1.
    rng = np.random.default_rng(1)
    result = m.benford_first_digit_test(list(rng.integers(100, 1000, size=5000).astype(float)))
    assert result["conformity"] == "nonconformity"
    assert result["mad"] > 0.015
    assert result["p_value"] < 1e-6


def test_observed_frequencies_and_mad_by_hand():
    # 10 montants : six commencent par 1, quatre par 2.
    amounts = [10, 11, 12, 150, 1900, 17, 20, 25, 230, 2999]
    result = m.benford_first_digit_test(amounts)
    assert result["counts"][1] == 6 and result["counts"][2] == 4
    expected_mad = (abs(0.6 - math.log10(2)) + abs(0.4 - math.log10(1.5))
                    + sum(math.log10(1 + 1 / d) for d in range(3, 10))) / 9
    assert result["mad"] == pytest.approx(expected_mad)


def test_empty_sample():
    result = m.benford_first_digit_test([])
    assert result["n"] == 0 and result["mad"] is None and result["sample_warning"] == "empty"


# ---------- taille minimale ----------

@pytest.mark.parametrize("n,warning", [(399, "not_interpretable"), (400, "caution"), (1499, "caution"), (1500, None)])
def test_sample_size_warning_levels(n, warning):
    assert m.benford_first_digit_test(_benford_sample(n))["sample_warning"] == warning


def test_thresholds_follow_expected_mad_under_conformity():
    """Les seuils de taille découlent des bornes de Nigrini : le MAD attendu sous conformité parfaite
    (bruit d'échantillonnage seul) croise 0,012 vers N = 380 et 0,006 vers N = 1 530."""
    assert m.expected_mad_under_conformity(380) == pytest.approx(0.012, abs=1e-4)
    assert m.expected_mad_under_conformity(1530) == pytest.approx(0.006, abs=1e-4)
    # Les seuils retenus sont les arrondis de ces croisements (400 pour ~380, 1 500 pour ~1 530) : au
    # seuil, le MAD attendu est à la borne de Nigrini à quelques % près.
    assert m.expected_mad_under_conformity(m.BENFORD_MIN_INTERPRETABLE) <= 0.012
    assert m.expected_mad_under_conformity(m.BENFORD_MIN_FULL_RESOLUTION) == pytest.approx(0.006, rel=0.02)


def test_small_conforming_sample_looks_nonconforming_by_chance():
    """Justification du seuil : avec 100 montants pourtant tirés selon Benford, le MAD dépasse en
    moyenne la borne de non-conformité."""
    mads = [m.benford_first_digit_test(_benford_sample(100, seed))["mad"] for seed in range(50)]
    assert np.mean(mads) > 0.015


# ---------- χ² ----------

@pytest.mark.parametrize("critical,alpha", [(15.507, 0.05), (20.090, 0.01), (26.124, 0.001)])
def test_chi2_closed_form_matches_tabulated_critical_values(critical, alpha):
    assert m.chi2_survival_even_df(critical, 8) == pytest.approx(alpha, abs=5e-4)


def test_chi2_closed_form_rejects_odd_degrees_of_freedom():
    with pytest.raises(ValueError):
        m.chi2_survival_even_df(3.0, 3)


# ---------- lecture des montants ----------

@pytest.mark.parametrize("raw,value", [
    ("1 234,56", 1234.56), ("1.234,56", 1234.56), ("1,234.56", 1234.56), ("1234.5", 1234.5),
    ("-45,2", -45.2), ("(123,45)", -123.45), ("€ 1 000", 1000.0), ("12,500", 12500.0), ("1.234.567", 1234567.0),
    (42, 42.0), ("", None), ("abc", None), (None, None), (float("nan"), None),
])
def test_parse_amount_formats(raw, value):
    assert m.parse_amount(raw) == (pytest.approx(value) if value is not None else None)


@pytest.mark.parametrize("value,digit", [(1000, 1), (0.0042, 4), (9.99, 9), (-350, 3), (0, None), (float("inf"), None)])
def test_first_significant_digit(value, digit):
    assert m.first_significant_digit(value) == digit


def test_select_amounts_separates_signs_and_excludes_small_amounts():
    raw = ["120", "-80", "5", "0", "abc", "1 500,00", "-12"]
    kept, counts = m.select_benford_amounts(raw, sign="positive", min_amount=10)
    assert kept == [120.0, 1500.0]
    assert counts == {"total": 7, "unreadable": 1, "zero": 1, "other_sign": 2, "below_min": 1, "kept": 2}
    negatives, _ = m.select_benford_amounts(raw, sign="negative", min_amount=10)
    assert negatives == [80.0, 12.0]


# ---------- CSV ----------

def test_read_ledger_csv_semicolon_european_format():
    text = "date;libellé;montant\n2024-01-02;Facture A;1 234,56\n2024-01-03;Avoir B;-45,20\n"
    frame = m.read_ledger_csv(text)
    assert list(frame.columns) == ["date", "libellé", "montant"]
    assert frame["montant"].tolist() == ["1 234,56", "-45,20"]  # brut : la conversion est faite à part


def test_read_ledger_csv_comma():
    frame = m.read_ledger_csv("id,amount\n1,100.5\n2,200\n")
    assert frame["amount"].tolist() == ["100.5", "200"]


def test_guess_amount_column_picks_the_numeric_one():
    columns = {"date": ["2024-01-02", "2024-01-03"], "label": ["A", "B"], "amount": ["1 234,56", "-45,20"]}
    assert m.guess_amount_column(columns) == "amount"
    assert m.guess_amount_column({"label": ["A", "B"]}) is None


# ---------- démonstration sur les états financiers ----------

def test_financial_statement_amounts_dedupes_within_each_year():
    y1, y0 = pd.Timestamp("2024-12-31"), pd.Timestamp("2023-12-31")
    income = pd.DataFrame({y1: [1000.0, 80.0], y0: [900.0, 70.0]}, index=["Total Revenue", "Net Income"])
    cashflow = pd.DataFrame({y1: [80.0, 150.0], y0: [70.0, np.nan]}, index=["Net Income From Continuing Operations",
                                                                          "Operating Cash Flow"])
    amounts = m.financial_statement_amounts({"income": income, "cashflow": cashflow})
    # Le résultat net (80 / 70) figure dans les deux états : compté une seule fois par exercice.
    assert sorted(amounts) == sorted([900.0, 70.0, 1000.0, 80.0, 150.0])
