"""
Tests unitaires pour le moteur de calcul pur (engine.py) : fonctions sans réseau
ni dépendance Dash.
Usage : pip install pytest && pytest test_engine.py -v
"""
import numpy as np
import pandas as pd
import pytest

import engine as m


# ---------- frais / fiscalité ----------

def test_apply_fee_zero_is_noop():
    returns = np.array([[0.01, -0.02, 0.03]])
    np.testing.assert_allclose(m.apply_fee(returns, 0.0), returns)


def test_apply_fee_reduces_returns():
    returns = np.full((1, 12), 0.01)
    net = m.apply_fee(returns, annual_fee_pct=2.0)
    assert np.all(net < returns)
    # frein géométrique mensuel équivalent à 2%/an, ordre de grandeur ~0.165%/mois
    assert np.isclose(returns[0, 0] - net[0, 0], 1 - (1 + 0.02) ** (-1 / 12), atol=1e-4)


def test_apply_social_tax_noop_when_disabled():
    value = np.array([[1000.0, 1200.0]])
    invested = np.array([1000.0, 1000.0])
    out = m.apply_social_tax(value, invested, apply_tax=False)
    np.testing.assert_array_equal(out, value)


def test_apply_social_tax_only_taxes_positive_gain():
    value = np.array([[800.0, 1200.0]])  # une perte, un gain
    invested = np.array([1000.0, 1000.0])
    out = m.apply_social_tax(value, invested, apply_tax=True, tax_rate=0.172)
    assert out[0, 0] == 800.0  # perte non taxée
    assert np.isclose(out[0, 1], 1200.0 - 0.172 * 200.0)


# ---------- bootstrap / grille de poids ----------

def test_block_bootstrap_indices_shape_and_bounds():
    rng = np.random.default_rng(0)
    idx = m.block_bootstrap_indices(n_obs=50, n_months=24, n_sims=100, block_size=6, rng=rng)
    assert idx.shape == (100, 24)
    assert idx.min() >= 0 and idx.max() < 50


def test_simplex_grid_sums_to_total():
    combos = list(m.simplex_grid(k=4, total=100, step=25))
    assert len(combos) > 0
    for combo in combos:
        assert len(combo) == 4
        assert sum(combo) == 100
        assert all(c % 25 == 0 for c in combo)


# ---------- choc de marché ----------

def test_inject_shock_random_timing_returns_per_simulation_starts():
    rng = np.random.default_rng(0)
    returns = np.zeros((5, 24))
    shocked, starts = m.inject_shock(returns, shock_pct=-30, shock_duration=6, start_month=None, rng=rng)
    assert starts.shape == (5,)
    assert starts.min() >= 0 and starts.max() <= 24 - 6
    # chaque simulation doit avoir sa fenêtre de choc à l'endroit indiqué par starts[s]
    for s in range(5):
        assert not np.allclose(shocked[s, starts[s]:starts[s] + 6], 0.0)


def test_inject_shock_fixed_timing_returns_none_for_starts():
    rng = np.random.default_rng(0)
    returns = np.zeros((3, 24))
    shocked, starts = m.inject_shock(returns, shock_pct=-30, shock_duration=6, start_month=10, rng=rng)
    assert starts is None
    assert not np.allclose(shocked[:, 10:16], 0.0)
    assert np.allclose(shocked[:, :10], 0.0)


# ---------- accumulation DCA ----------

def test_returns_to_dca_zero_returns_equals_cumulative_contributions():
    monthly_returns = np.zeros((3, 6))
    amounts = np.array([100.0] * 6)
    value, invested = m.returns_to_dca(monthly_returns, amounts)
    np.testing.assert_allclose(value[:, -1], 600.0)
    np.testing.assert_allclose(invested, np.cumsum(amounts))


def test_returns_to_dca_floors_at_zero_on_withdrawal():
    monthly_returns = np.zeros((1, 3))
    amounts = np.array([100.0, -500.0, -10.0])  # retrait dépasse le solde au mois 2
    value, _ = m.returns_to_dca(monthly_returns, amounts)
    assert value[0, 1] == 0.0
    assert value[0, 2] == 0.0  # reste plafonné, pas de solde négatif


def test_withdrawal_schedule_grows_with_inflation():
    sched = m.withdrawal_schedule(n_months_decum=24, monthly_amount=1000.0, inflation_pct=3.0)
    assert sched[0] == 1000.0
    assert sched[-1] > sched[0]  # le retrait suit l'inflation


# ---------- simulation Monte Carlo (loi t de Student) ----------

def test_simulate_index_returns_shape_and_target_mean():
    rng_hist = np.random.default_rng(1)
    hist = pd.Series(rng_hist.normal(0.007, 0.04, 240))
    sims = m.simulate_index_returns(hist, n_months=1, n_sims=50000, seed=7, method="normal",
                                     mu_override_pct=12.0)
    assert sims.shape == (50000, 1)
    target_monthly = (1 + 0.12) ** (1 / 12) - 1
    assert abs(sims.mean() - target_monthly) < 0.001
    assert abs(sims.std() - hist.std()) < 0.002  # volatilité historique conservée


def test_simulate_portfolio_asset_returns_preserves_covariance():
    rng_hist = np.random.default_rng(2)
    df = pd.DataFrame({
        "A": rng_hist.normal(0.006, 0.04, 200),
        "B": rng_hist.normal(0.005, 0.035, 200),
    })
    df["A"] = df["A"] + 0.3 * df["B"]  # corrélation induite
    sims = m.simulate_portfolio_asset_returns(df, n_months=1, n_sims=100000, seed=3, method="normal")
    assert sims.shape == (100000, 1, 2)
    sample_cov = np.cov(sims[:, 0, 0], sims[:, 0, 1])
    target_cov = df.cov().values
    np.testing.assert_allclose(sample_cov, target_cov, atol=3e-4)


def test_simulate_index_returns_has_fatter_tails_than_gaussian():
    """La loi t de Student (nu=5) doit produire un excès de kurtosis net positif, contrairement à
    une gaussienne pure : c'est tout l'intérêt du changement de méthode."""
    hist = pd.Series(np.random.default_rng(4).normal(0.007, 0.04, 240))
    sims = m.simulate_index_returns(hist, n_months=1, n_sims=100000, seed=5, method="normal")
    kurtosis = pd.Series(sims.ravel()).kurtosis()
    assert kurtosis > 1.0  # gaussienne ~0, t de Student (nu=5) nettement positive


# ---------- poids suggérés ----------

def test_suggest_optimal_weights_sums_to_100():
    rng = np.random.default_rng(6)
    df = pd.DataFrame(rng.normal(0.005, 0.03, size=(100, 3)), columns=["A", "B", "C"])
    sharpe_w, vol_w, rp_w = m.suggest_optimal_weights(df, step_pct=10)
    for weights in (sharpe_w, vol_w, rp_w):
        assert weights is not None
        assert sum(weights.values()) == pytest.approx(100.0)


def test_suggest_optimal_weights_override_dominates_when_shrinkage_full():
    """Avec shrinkage=100% (toutes les moyennes ramenées à l'identique), un rendement personnalisé
    élevé sur un actif doit faire basculer l'allocation Sharpe dessus."""
    rng = np.random.default_rng(6)
    df = pd.DataFrame(rng.normal(0.005, 0.03, size=(100, 3)), columns=["A", "B", "C"])
    sharpe_w, _, _ = m.suggest_optimal_weights(df, step_pct=10, shrinkage=1.0, mu_override_pct=[None, None, 30.0])
    assert sharpe_w["C"] == max(sharpe_w.values())


# ---------- mode objectif ----------

def test_compute_objective_contribution_linear_scaling():
    schedules = {"constant": np.array([200.0] * 12)}
    all_metrics = {("Actif", "constant"): {"median": 40000.0, "p_low": 20000.0, "p_high": 80000.0}}
    items = [("Actif", None)]

    rows = m.compute_objective_contribution(all_metrics, schedules, items, target_amount=50000.0,
                                              percentile_key="median")
    assert rows == [("Actif", pytest.approx(200.0 * 50000.0 / 40000.0))]


def test_compute_objective_contribution_empty_when_no_constant_schedule():
    assert m.compute_objective_contribution({}, {}, [], 50000.0, "median") == []


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
