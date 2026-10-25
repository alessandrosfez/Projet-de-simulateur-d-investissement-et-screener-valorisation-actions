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


def test_cap_schedule_noop_when_cumulative_stays_under_cap():
    amounts = np.array([100.0] * 6)  # cumul max 600
    capped = m.cap_schedule(amounts, cap=1000.0)
    np.testing.assert_allclose(capped, amounts)


def test_cap_schedule_clips_crossing_month_then_zeroes_the_rest():
    amounts = np.array([100.0] * 6)  # cumul : 100, 200, ..., 600
    capped = m.cap_schedule(amounts, cap=250.0)
    np.testing.assert_allclose(capped, [100.0, 100.0, 50.0, 0.0, 0.0, 0.0])
    assert capped.sum() == 250.0


def test_cap_schedule_leaves_withdrawals_untouched():
    amounts = np.array([100.0, 100.0, 100.0, -50.0, -50.0])  # cumul contributions : 300, plafond 150
    capped = m.cap_schedule(amounts, cap=150.0)
    np.testing.assert_allclose(capped, [100.0, 50.0, 0.0, -50.0, -50.0])


def test_overflow_schedule_is_the_complement_of_cap_schedule():
    amounts = np.array([100.0] * 6)  # cumul : 100..600, plafond 250
    overflow = m.overflow_schedule(amounts, cap=250.0)
    np.testing.assert_allclose(overflow, [0.0, 0.0, 50.0, 100.0, 100.0, 100.0])
    # La somme capped + overflow doit reconstituer exactement les versements d'origine.
    np.testing.assert_allclose(m.cap_schedule(amounts, cap=250.0) + overflow, amounts)


def test_overflow_schedule_zero_when_under_cap():
    amounts = np.array([100.0] * 6)  # cumul max 600, plafond 1000 jamais atteint
    overflow = m.overflow_schedule(amounts, cap=1000.0)
    np.testing.assert_allclose(overflow, np.zeros(6))


def test_overflow_schedule_ignores_withdrawals():
    amounts = np.array([100.0, 100.0, 100.0, -50.0, -50.0])  # plafond 150, franchi au mois 2
    overflow = m.overflow_schedule(amounts, cap=150.0)
    np.testing.assert_allclose(overflow, [0.0, 50.0, 100.0, 0.0, 0.0])


def test_withdrawal_schedule_grows_with_inflation():
    sched = m.withdrawal_schedule(n_months_decum=24, monthly_amount=1000.0, inflation_pct=3.0)
    assert sched[0] == 1000.0
    assert sched[-1] > sched[0]  # le retrait suit l'inflation


def test_summarize_historique_zero_returns():
    monthly_returns = np.zeros(24)
    result = m.summarize_historique(monthly_returns)
    assert result["total_return"] == 0.0
    assert result["cagr"] == 0.0
    assert result["volatility"] == 0.0
    assert result["max_drawdown"] == 0.0
    assert result["sharpe"] is None  # volatilité nulle : ratio non défini


def test_summarize_historique_constant_positive_return_matches_cagr():
    # 12 mois à +1%/mois : rendement total = 1.01**12 - 1, et comme la séquence est
    # constante l'annualisé (CAGR sur 1 an) doit coïncider avec le rendement total.
    monthly_returns = np.full(12, 0.01)
    result = m.summarize_historique(monthly_returns)
    expected_total = (1.01 ** 12 - 1) * 100
    assert result["total_return"] == pytest.approx(expected_total, abs=0.05)
    assert result["cagr"] == pytest.approx(expected_total, abs=0.05)
    assert result["max_drawdown"] == 0.0  # jamais de baisse
    assert result["n_years"] == 1.0


def test_summarize_historique_drawdown_detects_the_trough():
    # +10%, -50%, +10% : le point bas (après le krach) doit être détecté comme le max drawdown.
    monthly_returns = np.array([0.10, -0.50, 0.10])
    result = m.summarize_historique(monthly_returns)
    growth = np.cumprod(1 + monthly_returns)
    expected_dd = ((growth[1] - growth[0]) / growth[0]) * 100
    assert result["max_drawdown"] == pytest.approx(expected_dd, abs=0.01)


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


def test_suggest_optimal_weights_max_weight_caps_concentration():
    # Sans contrainte, l'actif le plus rentable (C, override 30%) rafle tout le Sharpe-max ; avec
    # un plafond à 40%, aucune ligne ne doit dépasser cette borne.
    rng = np.random.default_rng(6)
    df = pd.DataFrame(rng.normal(0.005, 0.03, size=(100, 3)), columns=["A", "B", "C"])
    uncapped, _, _ = m.suggest_optimal_weights(df, step_pct=10, shrinkage=1.0, mu_override_pct=[None, None, 30.0])
    assert uncapped["C"] > 40
    capped, _, _ = m.suggest_optimal_weights(
        df, step_pct=10, shrinkage=1.0, mu_override_pct=[None, None, 30.0], max_weight_pct=40.0,
    )
    assert all(w <= 40.0 for w in capped.values())
    assert sum(capped.values()) == pytest.approx(100.0)


def test_suggest_optimal_weights_min_weight_allows_full_exclusion():
    # min_weight_pct=20 avec 3 actifs (20*3=60, faisable) ne doit PAS empêcher un actif d'être
    # totalement exclu (poids 0) -- seuls les actifs INCLUS doivent respecter le plancher.
    rng = np.random.default_rng(6)
    df = pd.DataFrame(rng.normal(0.005, 0.03, size=(100, 3)), columns=["A", "B", "C"])
    sharpe_w, _, _ = m.suggest_optimal_weights(df, step_pct=10, min_weight_pct=20.0)
    assert sharpe_w is not None
    for w in sharpe_w.values():
        assert w == 0 or w >= 20.0


def test_suggest_optimal_weights_infeasible_constraints_return_none():
    # max_weight_pct=10 avec 3 actifs : impossible d'atteindre 100% sans dépasser 10% quelque part.
    rng = np.random.default_rng(6)
    df = pd.DataFrame(rng.normal(0.005, 0.03, size=(100, 3)), columns=["A", "B", "C"])
    sharpe_w, vol_w, rp_w = m.suggest_optimal_weights(df, step_pct=10, max_weight_pct=10.0)
    assert sharpe_w is None and vol_w is None and rp_w is None


def test_suggest_optimal_weights_risk_free_rate_changes_ranking():
    """A : rendement annualisé élevé (~17%) mais volatil. B : rendement modeste (~6%) mais stable.
    Sans taux sans risque, B a le meilleur Sharpe brut (volatilité bien plus faible) ; un taux sans
    risque assez élevé (ici 8%, sous le rendement de A mais au-dessus de celui de B) réduit le
    rendement EXCÉDENTAIRE de B à près de zéro et fait basculer l'allocation Sharpe-max vers A."""
    rng = np.random.default_rng(1)
    a = rng.normal(0.02, 0.08, size=200)
    b = rng.normal(0.006, 0.01, size=200)
    df = pd.DataFrame({"A": a, "B": b})
    sharpe_no_rf, _, _ = m.suggest_optimal_weights(df, step_pct=10, shrinkage=0.0, risk_free_rate_pct=0.0)
    sharpe_high_rf, _, _ = m.suggest_optimal_weights(df, step_pct=10, shrinkage=0.0, risk_free_rate_pct=8.0)
    assert sharpe_no_rf["B"] > sharpe_no_rf["A"]
    assert sharpe_high_rf["A"] > sharpe_high_rf["B"]


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


# ---------- backtest glissant ----------

def test_rolling_backtest_final_values_none_when_history_too_short():
    hist = np.zeros(23)  # 23 mois d'historique, plan sur 24 mois : aucune fenêtre complète
    schedule = np.array([100.0] * 24)
    years_axis = np.arange(24) / 12
    result = m.rolling_backtest_final_values(hist, schedule, years_axis, 0.0, False, 0.0, 0.0, False)
    assert result is None


def test_rolling_backtest_final_values_zero_returns_equals_invested():
    """Rendements nuls sur tout l'historique : chaque fenêtre de départ doit terminer exactement au
    capital investi cumulé, et le nombre de fenêtres doit être n_obs - n_months + 1 (pas de repli
    circulaire, contrairement au bootstrap)."""
    n_obs, n_months = 30, 12
    hist = np.zeros(n_obs)
    schedule = np.array([100.0] * n_months)
    years_axis = np.arange(n_months) / 12
    final_values = m.rolling_backtest_final_values(hist, schedule, years_axis, 0.0, False, 0.0, 0.0, False)
    assert final_values.shape == (n_obs - n_months + 1,)
    np.testing.assert_allclose(final_values, 1200.0)


def test_rolling_backtest_final_values_no_circular_wrap():
    """Un pic de rendement placé au tout dernier mois de l'historique ne doit affecter QUE la
    dernière fenêtre (celle qui l'inclut réellement) : avec un repli circulaire (comme
    block_bootstrap_indices), il pourrait aussi se retrouver combiné à des fenêtres démarrant
    ailleurs dans l'historique. (Un pic au tout premier mois n'est pas utilisable ici : le premier
    rendement d'une fenêtre n'a par construction aucun effet, le solde de départ étant nul.)"""
    n_obs, n_months = 30, 12
    hist = np.zeros(n_obs)
    hist[-1] = 10.0  # pic isolé au tout dernier mois : n'appartient qu'à la dernière fenêtre valide
    schedule = np.array([100.0] * n_months)
    years_axis = np.arange(n_months) / 12
    final_values = m.rolling_backtest_final_values(hist, schedule, years_axis, 0.0, False, 0.0, 0.0, False)
    assert final_values[-1] > 1200.0  # la dernière fenêtre a capté le pic
    np.testing.assert_allclose(final_values[:-1], 1200.0)  # aucune autre fenêtre ne l'a capté


# ---------- walk_forward_calibration / summarize_calibration ----------

def _synthetic_iid_returns(n, mu=0.006, sigma=0.04, seed=123):
    """Rendements mensuels i.i.d. générés selon EXACTEMENT la même famille (loi t de Student, même
    degré de liberté) que le mode paramétrique de simulate_index_returns -- un modèle bien spécifié
    sur ces données doit donc produire une couverture proche du nominal ; une série i.i.d. n'a par
    ailleurs aucune autocorrélation à casser, donc le bootstrap par blocs doit aussi bien se
    calibrer dessus (seul le mode historique/bootstrap a besoin de préserver une structure
    temporelle, absente ici par construction)."""
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n)
    scale = m._student_t_scale(rng, m.STUDENT_T_DOF, size=n)
    values = mu + sigma * z * scale
    dates = pd.date_range("2000-01-01", periods=n, freq="MS")
    return pd.Series(values, index=dates)


@pytest.mark.parametrize("method", ["normal", "bootstrap"])
def test_walk_forward_calibration_coverage_close_to_nominal_on_iid_synthetic_data(method):
    returns_hist = _synthetic_iid_returns(n=700)
    result = m.walk_forward_calibration(
        returns_hist, horizon_months=60, n_sims=300, seed=42, method=method,
        step_months=3, min_calibration_months=120, block_size=12,
    )
    assert result["n_origins"] >= 30
    summary = m.summarize_calibration(result["pit"], bands=((5, 95), (25, 75)))
    for row in summary:
        nominal = row["upper_pct"] - row["lower_pct"]
        # Tolérance large : peu d'origines "effectives" indépendantes (voir n_effective) + bruit
        # Monte Carlo propre à n_sims -- on vérifie "pas d'écart grossier", pas une égalité précise.
        assert abs(row["observed_pct"] - nominal) <= 25


def test_walk_forward_calibration_empty_when_no_valid_origin():
    returns_hist = _synthetic_iid_returns(n=20)
    result = m.walk_forward_calibration(
        returns_hist, horizon_months=60, n_sims=50, seed=1, method="normal", min_calibration_months=24,
    )
    assert result == {"origin_dates": [], "pit": pytest.approx(np.array([])), "n_origins": 0, "n_effective": 0}


def test_walk_forward_calibration_no_future_leakage(monkeypatch):
    """Construit une série avec une discontinuité connue (zéros puis une valeur sentinelle) et
    espionne les appels à simulate_index_returns pour vérifier que la fenêtre de calibration de
    CHAQUE origine correspond exactement au préfixe attendu (ni plus court ni plus long d'un mois)
    -- la seule façon de garantir qu'aucune donnée à partir de t n'est jamais utilisée, plutôt que
    de se fier à la relecture du code."""
    n = 60
    values = np.zeros(n)
    values[30:] = 999.0  # discontinuité connue, repérable si elle apparaît trop tôt
    dates = pd.date_range("2000-01-01", periods=n, freq="MS")
    returns_hist = pd.Series(values, index=dates)

    seen_calibration_windows = []
    original = m.simulate_index_returns

    def spy(calibration_series, *args, **kwargs):
        seen_calibration_windows.append(np.asarray(calibration_series.values))
        return original(calibration_series, *args, **kwargs)

    monkeypatch.setattr(m, "simulate_index_returns", spy)

    min_calibration_months, step_months, horizon_months = 10, 5, 6
    m.walk_forward_calibration(
        returns_hist, horizon_months=horizon_months, n_sims=10, seed=1, method="normal",
        step_months=step_months, min_calibration_months=min_calibration_months,
    )

    expected_origins = list(range(min_calibration_months, n - horizon_months + 1, step_months))
    assert len(seen_calibration_windows) == len(expected_origins)
    for captured, t in zip(seen_calibration_windows, expected_origins):
        assert len(captured) == t
        np.testing.assert_array_equal(captured, values[:t])


def test_summarize_calibration_perfectly_uniform_pit_matches_nominal_exactly():
    # PIT exactement uniforme sur 100 points -> couverture observée = nominale au point près.
    pit_values = np.linspace(0.005, 0.995, 100)
    summary = m.summarize_calibration(pit_values, bands=((5, 95), (25, 75)))
    by_band = {(row["lower_pct"], row["upper_pct"]): row["observed_pct"] for row in summary}
    assert by_band[(5, 95)] == pytest.approx(90.0, abs=1.0)
    assert by_band[(25, 75)] == pytest.approx(50.0, abs=1.0)


def test_summarize_calibration_empty_pit_returns_none_observed():
    summary = m.summarize_calibration(np.array([]), bands=((5, 95),))
    assert summary == [{"lower_pct": 5, "upper_pct": 95, "nominal_pct": 90, "observed_pct": None}]


# ---------- verdict de calibration (test binomial, intervalle de Wilson) ----------

def test_wilson_interval_matches_reference_value():
    # Valeur de référence (Wilson 1927, formule standard) : 8 succès sur 10 -> [0,490 ; 0,943].
    low, high = m.wilson_interval(0.8, 10)
    assert low == pytest.approx(0.4902, abs=1e-3) and high == pytest.approx(0.9433, abs=1e-3)


def test_calibration_verdict_flags_understated_risk_only_when_the_interval_excludes_nominal():
    # 60 % observés sur 100 observations indépendantes : [50,2 ; 69,1], loin sous 90 % -> trop étroites.
    assert m.calibration_verdict(60.0, 90, 100)["verdict"] == "too_narrow"
    # Mêmes 60 % sur 4 observations : intervalle [20,5 ; 89,7] -> 90 % reste au-dessus, de justesse.
    assert m.calibration_verdict(60.0, 90, 4)["verdict"] == "too_narrow"
    # 75 % sur 4 observations : [30 ; 95] contient 90 %, mais trop large pour conclure.
    assert m.calibration_verdict(75.0, 90, 4)["verdict"] == "inconclusive"
    # 88 % sur 400 observations : étroit et compatible -> calibré.
    assert m.calibration_verdict(88.0, 90, 400)["verdict"] == "calibrated"
    # 80 % observés pour une bande nominale de 50 % sur 100 observations -> trop prudentes.
    assert m.calibration_verdict(80.0, 50, 100)["verdict"] == "too_wide"
    assert m.calibration_verdict(None, 50, 10)["verdict"] is None


def test_combined_verdict_puts_understated_risk_first():
    assert m.combine_calibration_verdicts(["calibrated", "too_narrow"]) == "too_narrow"
    assert m.combine_calibration_verdicts(["too_wide", "inconclusive"]) == "too_wide"
    assert m.combine_calibration_verdicts(["calibrated", "inconclusive"]) == "inconclusive"
    assert m.combine_calibration_verdicts(["calibrated", "calibrated"]) == "calibrated"
    assert m.combine_calibration_verdicts([None]) is None
