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


# ---------- Scénarios Bear/Base/Bull ----------

_SCENARIO_BASE_ARGS = dict(
    last_fcf=100.0, base_growth_pct=5.0, base_discount_pct=8.0, terminal_growth_pct=2.0,
    n_years=5, net_debt=200.0, shares_outstanding=100.0,
)


def test_compute_scenario_dcf_fair_values_weighted_average_arithmetic():
    scenarios = m.compute_scenario_dcf_fair_values(
        **_SCENARIO_BASE_ARGS, growth_offset_pct=2.0, discount_offset_pct=1.0,
        weight_bear=25, weight_base=50, weight_bull=25,
    )
    assert scenarios["bear"] is not None and scenarios["base"] is not None and scenarios["bull"] is not None
    expected = (
        scenarios["bear"]["fair_value_per_share"] * 25
        + scenarios["base"]["fair_value_per_share"] * 50
        + scenarios["bull"]["fair_value_per_share"] * 25
    ) / 100
    assert scenarios["weighted_fair_value"] == pytest.approx(expected)
    # Bear (croissance réduite, taux augmenté) doit valoriser moins que Bull (l'inverse).
    assert scenarios["bear"]["fair_value_per_share"] < scenarios["base"]["fair_value_per_share"]
    assert scenarios["bull"]["fair_value_per_share"] > scenarios["base"]["fair_value_per_share"]


def test_compute_scenario_dcf_fair_values_renormalization_invariance():
    """Le résultat pondéré ne doit dépendre que du RATIO des poids, pas de leur échelle absolue."""
    a = m.compute_scenario_dcf_fair_values(
        **_SCENARIO_BASE_ARGS, growth_offset_pct=2.0, discount_offset_pct=1.0,
        weight_bear=25, weight_base=50, weight_bull=25,
    )
    b = m.compute_scenario_dcf_fair_values(
        **_SCENARIO_BASE_ARGS, growth_offset_pct=2.0, discount_offset_pct=1.0,
        weight_bear=10, weight_base=20, weight_bull=10,
    )
    assert a["weighted_fair_value"] == pytest.approx(b["weighted_fair_value"])


def test_compute_scenario_dcf_fair_values_invalid_scenario_excluded_from_average():
    """Un écart de taux d'actualisation assez agressif pour faire tomber le scénario Bull sous la
    croissance terminale doit le rendre None sans casser les autres, la moyenne pondérée se
    renormalisant sur les scénarios restants."""
    scenarios = m.compute_scenario_dcf_fair_values(
        **_SCENARIO_BASE_ARGS, growth_offset_pct=2.0, discount_offset_pct=6.5,  # 8 - 6.5 = 1.5 < terminal_growth 2.0
        weight_bear=25, weight_base=50, weight_bull=25,
    )
    assert scenarios["bull"] is None
    assert scenarios["bear"] is not None and scenarios["base"] is not None
    expected = (
        scenarios["bear"]["fair_value_per_share"] * 25 + scenarios["base"]["fair_value_per_share"] * 50
    ) / 75
    assert scenarios["weighted_fair_value"] == pytest.approx(expected)


def test_compute_scenario_dcf_fair_values_none_when_all_weights_zero():
    scenarios = m.compute_scenario_dcf_fair_values(
        **_SCENARIO_BASE_ARGS, growth_offset_pct=2.0, discount_offset_pct=1.0,
        weight_bear=0, weight_base=0, weight_bull=0,
    )
    assert scenarios["weighted_fair_value"] is None


# ---------- Grille de sensibilité DCF ----------

def test_compute_dcf_sensitivity_grid_shape_and_center_cell():
    growth_values, discount_values, grid = m.compute_dcf_sensitivity_grid(
        last_fcf=100.0, base_growth_pct=5.0, base_discount_pct=8.0, terminal_growth_pct=2.0,
        n_years=5, net_debt=200.0, shares_outstanding=100.0, growth_step_pct=5, discount_step_pct=1,
        grid_size=5,
    )
    assert len(growth_values) == 5 and len(discount_values) == 5
    assert len(grid) == 5 and all(len(row) == 5 for row in grid)
    half = 5 // 2
    assert growth_values[half] == pytest.approx(5.0)
    assert discount_values[half] == pytest.approx(8.0)
    base_result = m.compute_dcf_fair_value(100.0, 5.0, 8.0, 2.0, 5, 200.0, 100.0)
    assert grid[half][half] == pytest.approx(base_result["fair_value_per_share"])


def test_compute_dcf_sensitivity_grid_monotonic():
    growth_values, discount_values, grid = m.compute_dcf_sensitivity_grid(
        last_fcf=100.0, base_growth_pct=5.0, base_discount_pct=8.0, terminal_growth_pct=2.0,
        n_years=5, net_debt=200.0, shares_outstanding=100.0, growth_step_pct=5, discount_step_pct=1,
        grid_size=5,
    )
    # Ligne fixe : plus le taux d'actualisation (colonnes) augmente, plus la valeur baisse.
    row = grid[2]
    assert all(row[j] > row[j + 1] for j in range(len(row) - 1))
    # Colonne fixe : plus la croissance (lignes) augmente, plus la valeur augmente.
    col = [grid[i][2] for i in range(len(grid))]
    assert all(col[i] < col[i + 1] for i in range(len(col) - 1))


def test_compute_dcf_sensitivity_grid_none_at_invalid_edge():
    """Une cellule où le taux d'actualisation descend à/sous la croissance terminale doit valoir
    None, pas planter ni renvoyer un chiffre trompeur."""
    growth_values, discount_values, grid = m.compute_dcf_sensitivity_grid(
        last_fcf=100.0, base_growth_pct=5.0, base_discount_pct=3.0, terminal_growth_pct=2.0,
        n_years=5, net_debt=200.0, shares_outstanding=100.0, growth_step_pct=5, discount_step_pct=1,
        grid_size=5,
    )
    # base_discount=3, discount_step=1, grid_size=5 -> colonnes [1,2,3,4,5] : 1 et 2 <= terminal_growth (2.0)
    assert grid[0][0] is None
    assert grid[0][1] is None


# ---------- Comparables ----------

def test_compute_comparables_fair_value_scales_price_by_multiple_ratio():
    result = m.compute_comparables_fair_value(price=100.0, own_pe=10.0, peer_median_pe=15.0)
    assert result == pytest.approx(150.0)


def test_compute_comparables_fair_value_none_when_own_pe_missing_or_zero():
    assert m.compute_comparables_fair_value(price=100.0, own_pe=None, peer_median_pe=15.0) is None
    assert m.compute_comparables_fair_value(price=100.0, own_pe=0.0, peer_median_pe=15.0) is None


def test_compute_comparables_fair_value_none_when_peer_median_missing():
    assert m.compute_comparables_fair_value(price=100.0, own_pe=10.0, peer_median_pe=None) is None


# ---------- Backtest du signal P/E historique ----------

def test_compute_pe_percentile_series_nan_before_min_history():
    series = np.arange(1.0, 11.0)  # longueur 10
    percentiles = m.compute_pe_percentile_series(series, min_history=5)
    assert np.all(np.isnan(percentiles[:5]))
    assert not np.any(np.isnan(percentiles[5:]))


def test_compute_pe_percentile_series_strictly_increasing_series_approaches_100th_percentile():
    series = np.arange(1.0, 11.0)
    percentiles = m.compute_pe_percentile_series(series, min_history=5)
    # Chaque nouveau point est un nouveau maximum de sa fenêtre (les t éléments précédents, sur
    # une fenêtre de longueur t+1, sont tous strictement inférieurs) : percentile = 100*t/(t+1),
    # jamais exactement 100 pour une fenêtre finie.
    t = np.arange(5, 10)
    np.testing.assert_allclose(percentiles[5:], 100.0 * t / (t + 1))


def test_pe_signal_forward_returns_classifies_and_computes_forward_return():
    series = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 1.0, 10.0, 2.0, 3.0, 4.0])
    low, mid, high = m.pe_signal_forward_returns(series, forward_periods=3, min_history=5)
    # t=5 (valeur 1.0, minimum de la fenêtre -> percentile 0, "bas") : rendement vers t=8 (3.0).
    assert low == pytest.approx([3.0 / 1.0 - 1])
    # t=6 (valeur 10.0, maximum de la fenêtre -> percentile ~85.7, "haut") : rendement vers t=9 (4.0).
    assert high == pytest.approx([4.0 / 10.0 - 1])
    assert mid == []


def test_pe_signal_forward_returns_empty_when_series_too_short():
    series = np.arange(1.0, 6.0)  # longueur 5
    low, mid, high = m.pe_signal_forward_returns(series, forward_periods=3, min_history=5)
    assert low == mid == high == []


def test_summarize_pe_signal_backtest_pools_across_stocks():
    per_stock = [
        ([0.1, 0.3], [], [-0.1]),
        ([0.2], [0.0], []),
    ]
    summary = m.summarize_pe_signal_backtest(per_stock)
    assert summary["low"]["n"] == 3
    assert summary["low"]["mean"] == pytest.approx((0.1 + 0.3 + 0.2) / 3)
    assert summary["mid"]["n"] == 1
    assert summary["high"]["n"] == 1


def test_summarize_pe_signal_backtest_empty_bucket_has_none_mean():
    summary = m.summarize_pe_signal_backtest([([], [], [])])
    assert summary["low"] == {"n": 0, "mean": None, "median": None}
