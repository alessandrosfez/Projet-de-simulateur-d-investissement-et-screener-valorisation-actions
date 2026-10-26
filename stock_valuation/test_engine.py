"""
Tests unitaires pour le moteur de calcul pur (engine.py) : fonctions sans réseau
ni dépendance Dash.
Usage : pip install pytest && pytest test_engine.py -v
"""
import numpy as np
import pandas as pd
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


# ---------- Comparables EV/EBITDA ----------

def test_compute_comparables_ev_ebitda_fair_value_same_multiple_returns_current_price():
    # Si le multiple des pairs == le sien, le résultat doit redonner exactement market_cap/shares,
    # c'est-à-dire le prix courant : enterprise_value = market_cap + debt - cash par construction
    # (voir market_data.get_dcf_inputs), donc ebitda * meme_multiple revient à enterprise_value.
    market_cap, total_debt, total_cash, shares = 8_000.0, 500.0, 200.0, 100.0
    enterprise_value = market_cap + total_debt - total_cash
    ev_to_ebitda = 12.0
    result = m.compute_comparables_ev_ebitda_fair_value(
        enterprise_value, ev_to_ebitda, peer_median_ev_ebitda=ev_to_ebitda,
        total_debt=total_debt, total_cash=total_cash, shares_outstanding=shares,
    )
    assert result == pytest.approx(market_cap / shares)


def test_compute_comparables_ev_ebitda_fair_value_higher_peer_multiple_increases_value():
    base = m.compute_comparables_ev_ebitda_fair_value(
        enterprise_value=8300.0, ev_to_ebitda=10.0, peer_median_ev_ebitda=10.0,
        total_debt=500.0, total_cash=200.0, shares_outstanding=100.0,
    )
    higher = m.compute_comparables_ev_ebitda_fair_value(
        enterprise_value=8300.0, ev_to_ebitda=10.0, peer_median_ev_ebitda=15.0,
        total_debt=500.0, total_cash=200.0, shares_outstanding=100.0,
    )
    assert higher > base


def test_compute_comparables_ev_ebitda_fair_value_none_when_own_multiple_missing_or_zero():
    assert m.compute_comparables_ev_ebitda_fair_value(
        8300.0, None, 10.0, 500.0, 200.0, 100.0) is None
    assert m.compute_comparables_ev_ebitda_fair_value(
        8300.0, 0.0, 10.0, 500.0, 200.0, 100.0) is None


def test_compute_comparables_ev_ebitda_fair_value_none_when_peer_median_missing():
    assert m.compute_comparables_ev_ebitda_fair_value(
        8300.0, 10.0, None, 500.0, 200.0, 100.0) is None


def test_compute_comparables_ev_ebitda_fair_value_none_when_shares_missing_or_zero():
    assert m.compute_comparables_ev_ebitda_fair_value(
        8300.0, 10.0, 10.0, 500.0, 200.0, None) is None
    assert m.compute_comparables_ev_ebitda_fair_value(
        8300.0, 10.0, 10.0, 500.0, 200.0, 0.0) is None


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


# ---------- Track record (rendement/risque réalisés) ----------

def test_annualized_return_constant_monthly_return_matches_closed_form():
    # +1%/mois pendant 12 mois : CAGR = 1.01**12 - 1, pas 12*1% (intérêts composés).
    returns = np.full(12, 0.01)
    assert m.annualized_return(returns) == pytest.approx(1.01 ** 12 - 1)


def test_annualized_return_empty_series_is_none():
    assert m.annualized_return(np.array([])) is None


def test_annualized_volatility_single_point_is_none():
    assert m.annualized_volatility(np.array([0.05])) is None


def test_annualized_volatility_scales_by_sqrt_periods():
    returns = np.array([0.01, -0.01, 0.02, -0.02, 0.01, -0.01])
    expected = np.std(returns, ddof=1) * np.sqrt(12)
    assert m.annualized_volatility(returns, periods_per_year=12) == pytest.approx(expected)


def test_max_drawdown_v_shaped_series():
    # +10% (nouveau plus haut) puis -50% : le drawdown se mesure par rapport à CE plus haut.
    # Une chute dès le tout premier point ne compterait pas (rien dans la série avant lui ne sert
    # de référence) -- cohérent avec l'absence de point de départ "base 1.0" explicite.
    returns = np.array([0.10, -0.5, 0.0])
    assert m.max_drawdown(returns) == pytest.approx(0.55 / 1.1 - 1)


def test_max_drawdown_empty_series_is_none():
    assert m.max_drawdown(np.array([])) is None


def test_sharpe_ratio_none_when_volatility_zero():
    assert m.sharpe_ratio(0.08, 0.0) is None


def test_sharpe_ratio_none_when_return_missing():
    assert m.sharpe_ratio(None, 0.1) is None


def test_sharpe_ratio_basic_computation():
    assert m.sharpe_ratio(0.10, 0.2, risk_free_rate=0.02) == pytest.approx((0.10 - 0.02) / 0.2)


# ---------- P/E historique sur BPA annuels ----------

def test_pe_from_annual_eps_uses_the_last_published_eps_with_a_lag():
    """BPA 2022 = 4, BPA 2023 = 5, chacun connu 91 jours après la clôture du 31/12 : le 15/03/2024, le
    BPA 2023 n'est pas encore publié (31/03/2024), le P/E utilise donc le BPA 2022."""
    closes = pd.Series([40.0, 50.0, 60.0], index=pd.to_datetime(["2023-02-01", "2024-03-15", "2024-04-15"]))
    eps = pd.Series([4.0, 5.0], index=pd.to_datetime(["2022-12-31", "2023-12-31"]))
    pe = m.pe_from_annual_eps(closes, eps)
    # 01/02/2023 : BPA 2022 publié le 01/04/2023 seulement -> aucun BPA connu, point écarté.
    assert list(pe.index) == list(pd.to_datetime(["2024-03-15", "2024-04-15"]))
    assert list(pe) == pytest.approx([50.0 / 4.0, 60.0 / 5.0])


def test_pe_from_annual_eps_drops_loss_years_and_handles_timezones():
    closes = pd.Series([30.0, 30.0], index=pd.to_datetime(["2023-06-01", "2024-06-03"]).tz_localize("Europe/Paris"))
    eps = pd.Series([-2.0, 3.0], index=pd.to_datetime(["2022-12-31", "2023-12-31"]))
    pe = m.pe_from_annual_eps(closes, eps)
    assert len(pe) == 1 and pe.iloc[0] == pytest.approx(10.0)  # 2023 : perte 2022, P/E sans signification


def test_pe_from_annual_eps_matches_the_old_method_with_constant_eps():
    """Invariant : à BPA identique chaque année, on retrouve l'ancien calcul (cours / BPA actuel)."""
    closes = pd.Series([90.0, 100.0, 110.0], index=pd.to_datetime(["2024-05-01", "2024-09-02", "2025-05-02"]))
    eps = pd.Series([5.0, 5.0, 5.0], index=pd.to_datetime(["2022-12-31", "2023-12-31", "2024-12-31"]))
    assert list(m.pe_from_annual_eps(closes, eps)) == pytest.approx(list(closes / 5.0))


def test_pe_from_annual_eps_empty_without_eps():
    assert m.pe_from_annual_eps(pd.Series([1.0], index=pd.to_datetime(["2024-01-02"])), pd.Series(dtype=float)).empty


# ---------- Football field ----------

def test_peer_quartile_multiples_needs_three_peers():
    assert m.peer_quartile_multiples([10.0, 20.0]) is None
    assert m.peer_quartile_multiples([10.0, 12.0, 14.0, 16.0, 30.0]) == pytest.approx((12.0, 14.0, 16.0))


def test_football_field_ranges_ignore_missing_values_and_keep_method_order():
    rows = m.football_field_ranges({
        "comparables_pe": ([90.0, 130.0], 110.0),
        "dcf_scenarios": ([80.0, None, 140.0], 100.0),  # valeur manquante : écartée, pas prise pour 0
        "dcf_sensitivity": ([None, None], None),         # rien à tracer : méthode absente
        "comparables_ev_ebitda": ([120.0, 95.0], None),   # bornes dans le désordre, centre absent
    })
    assert [r["method"] for r in rows] == ["dcf_scenarios", "comparables_pe", "comparables_ev_ebitda"]
    assert rows[0] == {"method": "dcf_scenarios", "low": 80.0, "mid": 100.0, "high": 140.0}
    assert rows[2] == {"method": "comparables_ev_ebitda", "low": 95.0, "mid": pytest.approx(107.5), "high": 120.0}


def test_football_field_central_value_widens_a_too_narrow_range():
    rows = m.football_field_ranges({"dcf_scenarios": ([100.0, 110.0], 130.0)})
    assert rows[0]["low"] == 100.0 and rows[0]["high"] == 130.0 and rows[0]["mid"] == 130.0


# ---------- alertes de la liste de suivi ----------

def test_watchlist_alerts_all_five_triggers_with_their_values():
    # Cours 50, P/E 10 contre une médiane de pairs à 15 -> valeur implicite 75, soit +50 %.
    alerts = m.watchlist_alerts(price=50.0, own_pe=10.0, pe_percentile=12.0, score=78.0,
                                peer_pes=[14.0, 15.0, 16.0], dcf_fair_value=60.0, target_price=55.0)
    assert set(alerts) == set(m.WATCHLIST_ALERTS)
    assert alerts["below_target"] == pytest.approx(10.0)
    assert alerts["pe_history_low"] == pytest.approx(12.0)
    assert alerts["below_comparables"] == pytest.approx(50.0)
    assert alerts["below_dcf"] == pytest.approx(20.0)
    assert alerts["high_score"] == pytest.approx(78.0)


def test_watchlist_alerts_stay_silent_on_missing_or_unfavourable_data():
    # Trop peu de pairs, DCF sous le cours, percentile et score dans la zone neutre, données manquantes.
    assert m.watchlist_alerts(50.0, 10.0, 45.0, 55.0, [15.0, 16.0], 40.0) == {}
    assert m.watchlist_alerts(50.0, None, None, None, [14.0, 15.0, 16.0], None) == {}
    assert m.watchlist_alerts(None, 10.0, np.nan, np.nan, [14.0, 15.0, 16.0], 60.0) == {}
    # P/E au-dessus de la médiane des pairs : pas de décote par comparables.
    assert "below_comparables" not in m.watchlist_alerts(50.0, 20.0, None, None, [14.0, 15.0, 16.0], None)


def test_below_target_alert_fires_at_or_under_the_target_only():
    assert m.watchlist_alerts(40.0, None, None, None, [], None, target_price=40.0) == {"below_target": 0.0}
    assert "below_target" not in m.watchlist_alerts(41.0, None, None, None, [], None, target_price=40.0)
    # Cible absente ou cours absent : aucun signal, jamais une cible prise pour 0.
    assert m.watchlist_alerts(30.0, None, None, None, [], None, target_price=None) == {}
    assert m.watchlist_alerts(None, None, None, None, [], None, target_price=40.0) == {}


def test_reviews_due_keeps_past_and_today_oldest_first():
    entries = [{"ticker": "AAA.PA", "review_date": "2026-11-02"}, {"ticker": "BBB.PA", "review_date": "2026-10-26"},
               {"ticker": "CCC.PA", "review_date": None}, {"ticker": "DDD.PA", "review_date": "2026-09-30"}]
    due = m.reviews_due(entries, "2026-10-26")
    assert [e["ticker"] for e in due] == ["DDD.PA", "BBB.PA"]


def test_gap_to_target_pct_signs_and_missing_values():
    assert m.gap_to_target_pct(45.0, 50.0) == pytest.approx(-10.0)
    assert m.gap_to_target_pct(60.0, 50.0) == pytest.approx(20.0)
    assert m.gap_to_target_pct(None, 50.0) is None
    assert m.gap_to_target_pct(45.0, None) is None
    assert m.gap_to_target_pct(float("nan"), 50.0) is None
