"""
Tests de la vision Transaction Services (engine.py) : pont de dette nette, EBITDA ajusté, multiples,
saisies de l'utilisateur. Cas calculés à la main, détail en commentaire.
Usage : pip install -r requirements-dev.txt && pytest -v
"""
import numpy as np
import pandas as pd
import pytest

import engine as m

T, P = pd.Timestamp("2024-12-31"), pd.Timestamp("2023-12-31")


def _balance(**overrides):
    rows = {"Current Debt": [100, 90], "Long Term Debt": [400, 380], "Cash And Cash Equivalents": [150, 120],
            "Capital Lease Obligations": [80, 75], "Non Current Pension And Other Postretirement Benefit Plans": [40, 42],
            "Total Debt": [580, 545], "Cash Cash Equivalents And Short Term Investments": [190, 140]}
    rows.update(overrides)
    frame = pd.DataFrame.from_dict(rows, orient="index", columns=[T, P], dtype=float)
    return m.normalize_statements(pd.DataFrame(), frame, pd.DataFrame())


def _line(bridge, key):
    return next(line for line in bridge["lines"] if line["key"] == key)


# ---------- pont de dette nette ----------

def test_net_debt_bridge_by_hand():
    # Dette brute = 100 + 400 = 500 ; - trésorerie 150 = dette financière nette 350.
    # + dettes locatives 80 + retraites 40 - effet d'impôt 25 % × 40 = 10 -> dette nette (données) 460.
    # + complément de prix 20 - créance assimilable à de la trésorerie 30 -> dette nette ajustée 450.
    user_items = [{"label": "Complément de prix", "amount": 20.0}, {"label": "Créance de cession", "amount": -30.0}]
    bridge = m.net_debt_bridge(_balance(), T, pension_tax_rate=0.25, user_items=user_items)
    assert _line(bridge, "gross_financial_debt")["value"] == 500.0
    assert bridge["net_financial_debt"] == 350.0
    assert _line(bridge, "pension_tax_effect")["value"] == pytest.approx(-10.0)
    assert bridge["net_debt_data"] == pytest.approx(460.0)
    assert bridge["adjusted_net_debt"] == pytest.approx(450.0)
    assert bridge["adjusted_net_debt_excl_ifrs16"] == pytest.approx(370.0)


def test_net_debt_bridge_tags_data_and_assumptions():
    bridge = m.net_debt_bridge(_balance(), T, user_items=[{"label": "Earn-out", "amount": 20.0}])
    sources = {line["key"]: line["source"] for line in bridge["lines"]}
    assert sources["current_debt"] == "data" and sources["cash"] == "data"
    assert sources["pension_tax_effect"] == "assumption" and sources["user_item"] == "assumption"
    assert sources["adjusted_net_debt"] == "subtotal"


def test_short_term_investments_shown_for_memo_not_deducted():
    # Placements court terme = 190 - 150 = 40 : affichés pour mémoire, la dette nette reste 350.
    bridge = m.net_debt_bridge(_balance(), T)
    memo = _line(bridge, "short_term_investments_memo")
    assert memo["source"] == "memo" and memo["value"] == pytest.approx(-40.0)
    assert bridge["net_financial_debt"] == 350.0


def test_gross_debt_falls_back_on_total_debt_minus_leases():
    # Pas de dette court terme : dette brute = dette totale Yahoo 580 - dettes locatives 80 = 500.
    bridge = m.net_debt_bridge(_balance(**{"Current Debt": [np.nan, np.nan]}), T)
    assert _line(bridge, "gross_financial_debt")["value"] == 500.0
    assert bridge["flags"] == ("gross_debt_from_total_debt",)


def test_missing_leases_are_excluded_and_flagged_not_zeroed_silently():
    ns = _balance(**{"Capital Lease Obligations": [np.nan, np.nan], "Total Debt": [np.nan, np.nan]})
    bridge = m.net_debt_bridge(ns, T)
    assert _line(bridge, "lease_liabilities")["value"] is None
    assert _line(bridge, "lease_liabilities")["excluded"] is True
    assert bridge["excluded"] == ("lease_liabilities",)
    assert bridge["net_debt_data"] == pytest.approx(350 + 40 - 10)
    assert bridge["adjusted_net_debt_excl_ifrs16"] is None


def test_missing_cash_makes_net_debt_unavailable():
    bridge = m.net_debt_bridge(_balance(**{"Cash And Cash Equivalents": [np.nan, np.nan]}), T)
    assert bridge["net_financial_debt"] is None
    assert bridge["adjusted_net_debt"] is None


def test_pension_tax_rate_is_adjustable():
    bridge = m.net_debt_bridge(_balance(), T, pension_tax_rate=0.0)
    assert bridge["net_debt_data"] == pytest.approx(350 + 80 + 40)


# ---------- saisies de l'utilisateur ----------

def test_parse_user_items_in_millions():
    rows = [
        {"label": "Litige", "amount": "1,5"},       # virgule décimale -> 1,5 M
        {"label": "", "amount": 2},                 # libellé manquant -> numéro de ligne
        {"label": None, "amount": None},            # ligne vide : ignorée
        {"label": "Affacturage", "amount": "abc"},  # montant invalide : signalé
        {"label": "Sans montant", "amount": ""},    # libellé sans montant : signalé
    ]
    items, invalid = m.parse_user_items(rows)
    assert items == [{"label": "Litige", "amount": 1.5e6}, {"label": "#2", "amount": 2e6}]
    assert invalid == [4, 5]


def test_parse_user_items_empty():
    assert m.parse_user_items(None) == ([], [])


# ---------- EBITDA ajusté et multiples ----------

def test_adjusted_ebitda_by_hand():
    # 1 000 + 50 (coûts de restructuration réintégrés) - 20 (plus-value de cession retirée) = 1 030.
    result = m.adjusted_ebitda(1000.0, [{"label": "Restructuration", "amount": 50.0},
                                        {"label": "Plus-value", "amount": -20.0}])
    assert result["total_adjustments"] == 30.0
    assert result["adjusted"] == 1030.0


def test_adjusted_ebitda_unavailable_without_published_ebitda():
    assert m.adjusted_ebitda(None, [{"label": "x", "amount": 50.0}])["adjusted"] is None


def test_transaction_multiples_by_hand():
    # VE = capitalisation 2 000 + dette nette 460 + minoritaires 50 = 2 510 ; VE / EBITDA 1 000 = 2,51x ;
    # dette nette / EBITDA = 0,46x.
    result = m.transaction_multiples(2000.0, 50.0, 460.0, 1000.0)
    assert result["enterprise_value"] == 2510.0
    assert result["ev_to_ebitda"] == pytest.approx(2.51)
    assert result["net_debt_to_ebitda"] == pytest.approx(0.46)
    assert result["flags"] == ()


def test_multiples_adjusted_vs_published_move_as_expected():
    published = m.transaction_multiples(2000.0, 50.0, 460.0, 1000.0)
    adjusted = m.transaction_multiples(2000.0, 50.0, 450.0, 1030.0)
    assert adjusted["ev_to_ebitda"] == pytest.approx(2500 / 1030)
    assert adjusted["ev_to_ebitda"] < published["ev_to_ebitda"]


def test_missing_minorities_excluded_and_flagged():
    result = m.transaction_multiples(2000.0, None, 460.0, 1000.0)
    assert result["enterprise_value"] == 2460.0
    assert result["flags"] == ("minority_interest_missing",)


def test_multiples_not_meaningful_on_negative_ebitda():
    result = m.transaction_multiples(2000.0, 50.0, 460.0, -100.0)
    assert result["ev_to_ebitda"] is None and result["net_debt_to_ebitda"] is None
    assert result["reason"] == "non_positive_denominator"
    assert result["enterprise_value"] == 2510.0
