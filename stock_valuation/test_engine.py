"""
Tests unitaires pour le moteur de calcul pur (engine.py) : fonctions sans réseau
ni dépendance Dash.
Usage : pip install pytest && pytest test_engine.py -v
"""
import numpy as np
import pytest

import engine as m


# ---------- DCF ----------

def test_project_fcf_grows_geometrically():
    projected = m.project_fcf(100.0, growth_rate_pct=10.0, n_years=3)
    np.testing.assert_allclose(projected, [110.0, 121.0, 133.1])


def test_terminal_value_gordon_formula():
    tv = m.terminal_value_gordon(final_fcf=100.0, terminal_growth_pct=2.0, discount_rate_pct=8.0)
    assert tv == pytest.approx(100.0 * 1.02 / 0.06)


def test_discount_to_present_first_year_uses_one_year_of_discounting():
    pv = m.discount_to_present(np.array([100.0, 100.0]), discount_rate_pct=10.0)
    np.testing.assert_allclose(pv, [100.0 / 1.1, 100.0 / 1.1**2])


def test_compute_dcf_fair_value_basic():
    result = m.compute_dcf_fair_value(
        last_fcf=100.0, growth_rate_pct=5.0, discount_rate_pct=8.0, terminal_growth_pct=2.0,
        n_years=5, net_debt=200.0, shares_outstanding=100.0,
    )
    assert result is not None
    assert result["enterprise_value"] > 0
    assert result["equity_value"] == pytest.approx(result["enterprise_value"] - 200.0)
    assert result["fair_value_per_share"] == pytest.approx(result["equity_value"] / 100.0)


def test_compute_dcf_fair_value_none_when_terminal_growth_exceeds_discount_rate():
    assert m.compute_dcf_fair_value(100.0, 5.0, 2.0, 3.0, 5, 0.0, 100.0) is None


def test_compute_dcf_fair_value_none_when_no_shares_outstanding():
    assert m.compute_dcf_fair_value(100.0, 5.0, 8.0, 2.0, 5, 0.0, 0) is None


def test_compute_dcf_fair_value_net_cash_increases_equity_value():
    """Une dette nette négative (plus de cash que de dette) doit augmenter la valeur des
    capitaux propres par rapport à la valeur d'entreprise, pas la diminuer."""
    result = m.compute_dcf_fair_value(100.0, 5.0, 8.0, 2.0, 5, net_debt=-50.0, shares_outstanding=100.0)
    assert result["equity_value"] > result["enterprise_value"]


# ---------- Comparables ----------

def test_compute_comparables_fair_value_scales_price_by_multiple_ratio():
    result = m.compute_comparables_fair_value(price=100.0, own_pe=10.0, peer_median_pe=15.0)
    assert result == pytest.approx(150.0)


def test_compute_comparables_fair_value_none_when_own_pe_missing_or_zero():
    assert m.compute_comparables_fair_value(price=100.0, own_pe=None, peer_median_pe=15.0) is None
    assert m.compute_comparables_fair_value(price=100.0, own_pe=0.0, peer_median_pe=15.0) is None


def test_compute_comparables_fair_value_none_when_peer_median_missing():
    assert m.compute_comparables_fair_value(price=100.0, own_pe=10.0, peer_median_pe=None) is None
