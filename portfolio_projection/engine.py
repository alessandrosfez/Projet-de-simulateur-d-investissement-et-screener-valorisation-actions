"""
Moteur de calcul pur : simulation Monte Carlo (paramétrique ou bootstrap), DCA,
frais, fiscalité, et optimisation de poids de portefeuille. Aucune dépendance
sur Dash/Plotly/yfinance : c'est ce que couvre test_engine.py.
"""
from collections.abc import Iterator, Sequence

import numpy as np
import pandas as pd

# ============================================================
# SIMULATION MONTE CARLO (paramétrique ou bootstrap)
# ============================================================

def block_bootstrap_indices(n_obs: int, n_months: int, n_sims: int, block_size: int,
                            rng: np.random.Generator) -> np.ndarray:
    """Indices (n_sims, n_months) pour un bootstrap par blocs circulaire dans l'historique."""
    n_blocks = int(np.ceil(n_months / block_size))
    starts = rng.integers(0, n_obs, size=(n_sims, n_blocks))
    offsets = np.arange(block_size)
    idx = (starts[:, :, None] + offsets[None, None, :]) % n_obs
    return idx.reshape(n_sims, n_blocks * block_size)[:, :n_months]


# Degrés de liberté de la loi t de Student utilisée pour le mode "paramétrique". Une gaussienne
# sous-estime la fréquence des rendements extrêmes ; nu=5 reste dans la fourchette généralement
# observée pour des rendements mensuels d'indices actions (queues épaisses, variance finie) sans
# être un choix trop agressif. Valable pour nu > 2 (condition pour une variance finie).
STUDENT_T_DOF = 5


def _student_t_scale(rng: np.random.Generator, dof: float, size: int | tuple[int, ...]) -> np.ndarray:
    """Facteur multiplicatif à appliquer à un tirage N(0,1) (ou N(0,Sigma)) pour obtenir une loi t
    de Student de même variance cible. `size` est la forme du tirage chi2 (un scalaire partagé par
    actif quand il y en a plusieurs, pour créer une dépendance de queue et pas juste des marges
    individuellement épaisses)."""
    w = rng.chisquare(dof, size=size)
    return np.sqrt((dof - 2) / w)


def simulate_index_returns(returns_hist: pd.Series, n_months: int, n_sims: int, seed: int | None, method: str,
                           block_size: int = 12, mu_override_pct: float | None = None) -> np.ndarray:
    """mu_override_pct : rendement annuel (%) à substituer à la moyenne historique, ou None pour la
    garder. La volatilité (et, en bootstrap, la forme empirique de la distribution) reste historique."""
    rng = np.random.default_rng(seed)
    target_monthly = (1 + mu_override_pct / 100) ** (1 / 12) - 1 if mu_override_pct is not None else None
    if method == "bootstrap":
        idx = block_bootstrap_indices(len(returns_hist), n_months, n_sims, block_size, rng)
        sampled = returns_hist.to_numpy(dtype=float)[idx]
        if target_monthly is not None:
            sampled = sampled + (target_monthly - returns_hist.mean())
        return sampled
    mu, sigma = returns_hist.mean(), returns_hist.std()
    if target_monthly is not None:
        mu = target_monthly
    z = rng.standard_normal(size=(n_sims, n_months))
    scale = _student_t_scale(rng, STUDENT_T_DOF, size=(n_sims, n_months))
    return mu + sigma * z * scale


def simulate_portfolio_asset_returns(aligned_hist: pd.DataFrame, n_months: int, n_sims: int, seed: int | None,
                                     method: str, block_size: int = 12,
                                     mu_override_pct: Sequence[float | None] | None = None) -> np.ndarray:
    """Rendements corrélés multi-actifs. Renvoie un tableau (n_sims, n_months, k_actifs).
    mu_override_pct : liste de rendements annuels (%) par actif (même ordre que les colonnes), avec
    None pour garder la moyenne historique de l'actif concerné. Covariance toujours historique."""
    rng = np.random.default_rng(seed)
    if method == "bootstrap":
        idx = block_bootstrap_indices(len(aligned_hist), n_months, n_sims, block_size, rng)
        sampled = aligned_hist.values[idx]
        if mu_override_pct is not None:
            hist_mean = aligned_hist.mean().values
            shift = np.array([
                ((1 + o / 100) ** (1 / 12) - 1) - hist_mean[i] if o is not None else 0.0
                for i, o in enumerate(mu_override_pct)
            ])
            sampled = sampled + shift
        return sampled
    mu_vec = aligned_hist.mean().values.copy()
    cov_matrix = aligned_hist.cov().values
    if mu_override_pct is not None:
        for i, o in enumerate(mu_override_pct):
            if o is not None:
                mu_vec[i] = (1 + o / 100) ** (1 / 12) - 1
    k = len(mu_vec)
    z = rng.multivariate_normal(np.zeros(k), cov_matrix, size=(n_sims, n_months))
    # Un même tirage chi2 par (simulation, mois), partagé entre tous les actifs : c'est ce qui crée
    # la dépendance de queue (les actifs plongent plus souvent ensemble) au lieu de marges
    # individuellement épaisses mais indépendantes.
    scale = _student_t_scale(rng, STUDENT_T_DOF, size=(n_sims, n_months))
    return mu_vec + z * scale[:, :, None]


def apply_fee(monthly_returns: np.ndarray, annual_fee_pct: float) -> np.ndarray:
    """Applique un frein géométrique mensuel équivalent aux frais annuels."""
    monthly_fee = (1 + annual_fee_pct / 100) ** (1 / 12) - 1
    return (1 + monthly_returns) / (1 + monthly_fee) - 1


def apply_social_tax(portfolio_value: np.ndarray, invested_capital: np.ndarray, apply_tax: bool, tax_rate: float = 0.172) -> np.ndarray:
    """Déduit les prélèvements sociaux sur les gains (PEA > 5 ans, valeurs nominales)."""
    if not apply_tax:
        return portfolio_value
    gain = portfolio_value - invested_capital
    return portfolio_value - tax_rate * np.maximum(gain, 0)


def returns_to_dca(monthly_returns: np.ndarray, monthly_amounts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """monthly_returns: (n_sims, n_months), déjà nets de frais. monthly_amounts: (n_months,), positif = apport,
    négatif = retrait. Renvoie (portfolio_value, invested_capital) ; le portefeuille est plafonné à 0 (pas de
    retrait au-delà du solde)."""
    n_sims, n_months = monthly_returns.shape
    value = np.zeros(n_sims)
    portfolio_value = np.empty((n_sims, n_months))
    for t in range(n_months):
        value = np.maximum(value * (1 + monthly_returns[:, t]) + monthly_amounts[t], 0)
        portfolio_value[:, t] = value
    invested_capital = np.cumsum(np.maximum(monthly_amounts, 0))
    return portfolio_value, invested_capital


def withdrawal_schedule(n_months_decum: int, monthly_amount: float, inflation_pct: float) -> np.ndarray:
    """Retraits mensuels croissant avec l'inflation (pouvoir d'achat constant)."""
    if n_months_decum == 0:
        return np.array([])
    years = np.arange(n_months_decum) / 12
    return monthly_amount * (1 + inflation_pct / 100) ** years


def inject_shock(returns: np.ndarray, shock_pct: float, shock_duration: int, start_month: int | None,
                 rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray | None]:
    """Remplace une fenêtre de rendements par un choc. `returns` peut être (n_sims, n_months) ou
    (n_sims, n_months, k) ; `start_month=None` tire un moment de choc indépendant par simulation.
    Renvoie (rendements_choqués, mois_de_départ) : mois_de_départ est un tableau (n_sims,) si
    start_month=None (un tirage par simulation, exploitable pour visualiser le risque de séquence
    des rendements, voir results.build_sequence_risk_series), sinon None (même mois pour toutes
    les simulations, rien à comparer)."""
    shocked = returns.copy()
    n_sims, n_months = shocked.shape[0], shocked.shape[1]
    monthly_shock_return = (1 + shock_pct / 100) ** (1 / shock_duration) - 1
    if start_month is None:
        starts = rng.integers(0, max(n_months - shock_duration, 1), size=n_sims)
        for s in range(n_sims):
            shocked[s, starts[s]:starts[s] + shock_duration, ...] = monthly_shock_return
        return shocked, starts
    end = min(start_month + shock_duration, n_months)
    shocked[:, start_month:end, ...] = monthly_shock_return
    return shocked, None


def to_display_values(portfolio_value: np.ndarray, invested_capital: np.ndarray, years_axis: np.ndarray,
                      inflation_pct: float, real: bool) -> tuple[np.ndarray, np.ndarray]:
    """Déflate en euros constants (année 0) si real=True, sinon renvoie les valeurs nominales."""
    if not real:
        return portfolio_value, invested_capital
    deflator = (1 + inflation_pct / 100) ** years_axis
    return portfolio_value / deflator, invested_capital / deflator


def constant_schedule(n_months: int, amount: float) -> np.ndarray:
    return np.full(n_months, amount)


def progressive_schedule(n_months: int, start_amount: float, end_amount: float) -> np.ndarray:
    return np.linspace(start_amount, end_amount, n_months)


def cap_schedule(monthly_amounts: np.ndarray, cap: float) -> np.ndarray:
    """Plafonne un échéancier de versements au cumul `cap` (ex: plafond légal PEA, 150 000 €) :
    le dernier versement qui franchirait le plafond est réduit à pile ce qu'il reste de marge, et
    tous les suivants tombent à 0 — le capital continue de fructifier après, mais plus personne ne
    peut abonder. Les retraits (montants négatifs, phase de décumulation) ne sont jamais affectés :
    seul le cumul des apports positifs compte pour le plafond."""
    amounts = np.asarray(monthly_amounts, dtype=float)
    contributions = np.maximum(amounts, 0)
    cumulative_before = np.cumsum(contributions) - contributions
    headroom = np.clip(cap - cumulative_before, 0, None)
    capped_contributions = np.minimum(contributions, headroom)
    return np.where(amounts > 0, capped_contributions, amounts)


def overflow_schedule(monthly_amounts: np.ndarray, cap: float) -> np.ndarray:
    """Partie des versements qui dépasse le plafond PEA (complément de cap_schedule) : ce qui
    serait versé sur un CTO en parallèle si l'utilisateur continue d'épargner au même rythme une
    fois le PEA plein, plutôt que d'arrêter tout versement. Les retraits ne produisent jamais de
    surplus (seuls les versements positifs comptent pour le plafond)."""
    amounts = np.asarray(monthly_amounts, dtype=float)
    capped = cap_schedule(amounts, cap)
    return np.maximum(amounts, 0) - np.maximum(capped, 0)


def summarize(
    portfolio_value: np.ndarray, invested_capital: np.ndarray, net_returns: np.ndarray,
    lower_pct: float = 10, upper_pct: float = 90, decumulation_enabled: bool = False,
) -> dict:
    final_values = portfolio_value[:, -1]
    invested = invested_capital[-1]

    vol = net_returns.std(axis=1) * np.sqrt(12)
    mean_annual = net_returns.mean(axis=1) * 12
    sharpe = np.divide(mean_annual, vol, out=np.full_like(vol, np.nan), where=vol > 0)
    running_max = np.maximum.accumulate(portfolio_value, axis=1)
    max_dd = ((portfolio_value - running_max) / running_max).min(axis=1)

    result = {
        "invested": round(invested, 0),
        "median": round(np.percentile(final_values, 50), 0),
        "p_low": round(np.percentile(final_values, lower_pct), 0),
        "p_high": round(np.percentile(final_values, upper_pct), 0),
        "prob_gain": round((final_values > invested).mean() * 100, 1),
        "volatility": round(float(np.median(vol)) * 100, 2),
        "sharpe": round(float(np.nanmedian(sharpe)), 2),
        "max_drawdown": round(float(np.median(max_dd)) * 100, 2),
    }
    if decumulation_enabled:
        result["prob_ruin"] = round((final_values <= 1.0).mean() * 100, 1)
    return result


def summarize_historique(monthly_returns: np.ndarray) -> dict:
    """Statistiques descriptives d'une trajectoire historique réellement observée (achat unique,
    pas de simulation) : à la différence de summarize(), il n'y a ici qu'une seule séquence de
    rendements réels, donc pas de percentiles ni de probabilité de gain à calculer — seulement des
    moyennes/écarts sur cette séquence. `monthly_returns` : rendements mensuels réels de la fenêtre
    affichée (1D, déjà tronquée au point de départ choisi)."""
    n = len(monthly_returns)
    growth = np.cumprod(1 + monthly_returns)
    years = n / 12
    cagr = growth[-1] ** (1 / years) - 1 if years > 0 else np.nan
    vol = monthly_returns.std() * np.sqrt(12)
    sharpe = cagr / vol if vol > 0 else np.nan
    running_max = np.maximum.accumulate(growth)
    max_dd = ((growth - running_max) / running_max).min()
    return {
        "n_years": round(float(years), 1),
        "total_return": round((float(growth[-1]) - 1) * 100, 1),
        "cagr": round(float(cagr) * 100, 2),
        "volatility": round(float(vol) * 100, 2),
        "sharpe": round(float(sharpe), 2) if not np.isnan(sharpe) else None,
        "max_drawdown": round(float(max_dd) * 100, 2),
    }


def rolling_backtest_final_values(historical_returns: np.ndarray, schedule: np.ndarray, years_axis: np.ndarray,
                                   annual_fee_pct: float, apply_tax: bool, tax_rate: float,
                                   inflation_pct: float, display_real: bool) -> np.ndarray | None:
    """Pour chaque mois de départ t tel qu'une fenêtre complète de len(schedule) mois tienne dans
    historical_returns (n_starts = n_obs - n_months + 1, sans repli circulaire contrairement au
    bootstrap : seuls des départs réellement observés dans l'historique sont utilisés), calcule la
    valeur finale du portefeuille avec ce même plan d'apport, via la même chaîne que
    results._backtest_trajectory (frais -> DCA -> fiscalité -> affichage nominal/réel).
    `historical_returns` joue ici le rôle de l'axe "n_sims" de returns_to_dca (chaque fenêtre est un
    scénario indépendant, returns_to_dca ne fait pas la différence). Renvoie un tableau (n_starts,)
    de valeurs finales, ou None si l'historique est plus court que l'horizon du plan."""
    historical_returns = np.asarray(historical_returns)
    n_obs, n_months = len(historical_returns), len(schedule)
    n_starts = n_obs - n_months + 1
    if n_starts <= 0:
        return None
    windows = np.lib.stride_tricks.sliding_window_view(historical_returns, n_months)
    net_returns = apply_fee(windows, annual_fee_pct)
    portfolio_value, invested_capital = returns_to_dca(net_returns, schedule)
    portfolio_value = apply_social_tax(portfolio_value, invested_capital, apply_tax, tax_rate)
    portfolio_value, _ = to_display_values(portfolio_value, invested_capital, years_axis, inflation_pct, display_real)
    return portfolio_value[:, -1]


def compute_objective_contribution(all_metrics: dict, schedules: dict, items: list,
                                    target_amount: float, percentile_key: str) -> list[tuple[str, float]]:
    """Apport mensuel constant nécessaire pour atteindre `target_amount` au percentile choisi
    ("p_low"/"median"/"p_high"), pour chaque item déjà simulé (label, ...).

    Exploite la linéarité de la récursion d'accumulation en l'apport mensuel (value = value*(1+r) +
    apport) : la valeur finale à un percentile donné est proportionnelle à l'apport de référence déjà
    simulé, donc `apport_requis = target * apport_ref / valeur_percentile_ref` sans relancer de Monte
    Carlo. Ne vaut que pour la stratégie "constant" en phase d'accumulation pure (le plancher à 0 en
    décumulation casserait la linéarité).
    """
    ref_schedule = schedules.get("constant")
    if ref_schedule is None or len(ref_schedule) == 0 or ref_schedule[0] <= 0:
        return []
    ref_amount = float(ref_schedule[0])
    rows = []
    for label, _ in items:
        m = all_metrics.get((label, "constant"))
        if not m:
            continue
        ref_value = m.get(percentile_key)
        if not ref_value or ref_value <= 0:
            continue
        required = target_amount * ref_amount / ref_value
        rows.append((label, required))
    return rows


# ============================================================
# VALIDATION DU MODÈLE (backtest walk-forward, PIT)
# ============================================================

def walk_forward_calibration(returns_hist: pd.Series, horizon_months: int, n_sims: int, seed: int,
                              method: str, step_months: int = 12, block_size: int = 12,
                              min_calibration_months: int = 24) -> dict:
    """Vérifie que les bandes de percentiles affichées ailleurs dans l'appli sont fiables, par un
    backtest walk-forward : pour chaque date d'origine t valide (espacées de step_months), calibre
    le modèle (`simulate_index_returns`) UNIQUEMENT sur returns_hist[:t] -- fenêtre EXPANSIBLE qui
    grandit avec t, jamais de donnée à partir de t ou au-delà, aucune fuite d'information du futur
    même pour le bootstrap par blocs (qui ne tire que dans cette même fenêtre passée) -- simule la
    croissance de 1€ sur horizon_months, puis situe la croissance RÉELLEMENT observée sur
    returns_hist[t:t+horizon_months] dans cette distribution simulée : sa "PIT" (probability
    integral transform), la fraction des simulations dont la croissance finale est inférieure ou
    égale à la croissance réelle. Si le modèle est bien calibré, les PIT sur de nombreuses origines
    doivent se répartir uniformément sur [0, 1] (voir summarize_calibration) -- ni trop souvent
    proches de 0/1 (bandes trop étroites, le réel surprend trop souvent le modèle) ni trop
    concentrées au centre (bandes trop larges, le modèle est trop prudent).

    min_calibration_months : en-dessous, une moyenne/écart-type (ou un tirage bootstrap) sur trop
    peu d'observations serait trop bruité pour être une calibration significative -- ces origines
    trop précoces sont simplement exclues, pas calculées avec une fenêtre dégradée.

    Renvoie {"origin_dates": [...], "pit": ndarray, "n_origins": int, "n_effective": int}.
    n_effective (≈ durée totale de l'historique testé / horizon_months) : les fenêtres de
    différentes origines se CHEVAUCHENT dès que step_months < horizon_months (ex: origines
    mensuelles avec un horizon de 5 ans partagent jusqu'à 59 des 60 mois de leur fenêtre avec
    l'origine suivante) -- donc pas indépendantes entre elles, à ne pas lire comme "n_origins
    observations indépendantes" (la couverture observée reste un bon diagnostic, mais son
    incertitude statistique propre est plus grande que ne le suggérerait n_origins)."""
    values = np.asarray(returns_hist.values, dtype=float)
    dates = returns_hist.index
    n_obs = len(values)
    origins = list(range(min_calibration_months, n_obs - horizon_months + 1, step_months))
    if not origins:
        return {"origin_dates": [], "pit": np.array([]), "n_origins": 0, "n_effective": 0}

    # Une graine dérivée par origine (reproductible, indépendante d'une origine à l'autre) plutôt
    # que la même graine partout, pour que les tirages Monte Carlo de deux origines différentes ne
    # soient pas de simples répétitions du même aléa.
    master_rng = np.random.default_rng(seed)
    origin_seeds = master_rng.integers(0, 2**32 - 1, size=len(origins))

    pit_values = np.empty(len(origins))
    for i, t in enumerate(origins):
        calibration_series = pd.Series(values[:t])
        realized_growth = float(np.prod(1 + values[t:t + horizon_months]))
        simulated = simulate_index_returns(
            calibration_series, horizon_months, n_sims, int(origin_seeds[i]), method, block_size=block_size,
        )
        simulated_growth = np.prod(1 + simulated, axis=1)
        pit_values[i] = float((simulated_growth <= realized_growth).mean())

    n_effective = max(1, round(n_obs / horizon_months))
    return {
        "origin_dates": [dates[t] for t in origins],
        "pit": pit_values,
        "n_origins": len(origins),
        "n_effective": n_effective,
    }


def summarize_calibration(pit_values: np.ndarray,
                          bands: Sequence[tuple[int, int]] = ((5, 95), (25, 75))) -> list[dict]:
    """Taux de couverture observé de chaque bande nominale (lower_pct, upper_pct) : la fraction des
    origines dont la PIT tombe dans cette bande. Équivalent à vérifier que la croissance réalisée
    tombe entre les percentiles simulés correspondants (voir walk_forward_calibration), sans avoir
    à conserver la distribution complète de chaque origine -- un bon modèle calibré a un taux
    observé proche du taux nominal (upper_pct - lower_pct)."""
    rows = []
    for lo, hi in bands:
        observed = (
            float(((pit_values >= lo / 100) & (pit_values <= hi / 100)).mean() * 100)
            if len(pit_values) > 0 else None
        )
        rows.append({
            "lower_pct": lo, "upper_pct": hi, "nominal_pct": hi - lo,
            "observed_pct": round(observed, 1) if observed is not None else None,
        })
    return rows


# Demi-largeur (en points de pourcentage) au-delà de laquelle un intervalle de confiance compatible
# avec la couverture nominale ne prouve rien : « compatible » avec 50 % +/- 30 pt ne dit pas que le
# modèle est bon, seulement qu'on n'a pas assez de recul pour le prendre en défaut.
CALIBRATION_CONCLUSIVE_HALF_WIDTH_PT = 15.0


def wilson_interval(proportion: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalle de confiance de Wilson (95 % par défaut) d'une proportion observée sur n
    observations, en fractions. Préféré à l'intervalle normal simple, qui sort de [0, 1] et se
    resserre à tort sur de petits échantillons (ici n est petit : quelques observations
    indépendantes)."""
    denominator = 1 + z * z / n
    center = (proportion + z * z / (2 * n)) / denominator
    half = float(z * np.sqrt(proportion * (1 - proportion) / n + z * z / (4 * n * n)) / denominator)
    return max(0.0, center - half), min(1.0, center + half)


def calibration_verdict(observed_pct: float | None, nominal_pct: float, n_effective: int) -> dict:
    """Verdict d'une bande de percentiles : la couverture observée est-elle compatible avec la
    nominale, compte tenu du nombre d'observations INDÉPENDANTES (n_effective, pas le nombre de
    dates d'origine, qui se chevauchent) ? Test binomial via l'intervalle de Wilson à 95 % :
    - "too_narrow" : la nominale est au-dessus de l'intervalle, la réalité sort trop souvent des
      bandes, le risque est sous-estimé ;
    - "too_wide" : la nominale est en dessous, les bandes sont trop prudentes ;
    - "inconclusive" : compatible, mais l'intervalle est trop large pour conclure
      (CALIBRATION_CONCLUSIVE_HALF_WIDTH_PT) ;
    - "calibrated" : compatible avec un intervalle assez étroit.
    Renvoie {"verdict", "low_pct", "high_pct"} ; verdict None sans couverture observée."""
    if observed_pct is None or n_effective < 1:
        return {"verdict": None, "low_pct": None, "high_pct": None}
    low, high = wilson_interval(observed_pct / 100, n_effective)
    low_pct, high_pct = low * 100, high * 100
    if nominal_pct > high_pct:
        verdict = "too_narrow"
    elif nominal_pct < low_pct:
        verdict = "too_wide"
    elif (high_pct - low_pct) / 2 > CALIBRATION_CONCLUSIVE_HALF_WIDTH_PT:
        verdict = "inconclusive"
    else:
        verdict = "calibrated"
    return {"verdict": verdict, "low_pct": low_pct, "high_pct": high_pct}


def combine_calibration_verdicts(verdicts: Sequence[str | None]) -> str | None:
    """Verdict global d'une méthode à partir de ses bandes : un risque sous-estimé l'emporte (c'est
    l'erreur la plus coûteuse pour un épargnant), puis des bandes trop prudentes, puis le manque de
    recul ; « calibrated » seulement si toutes les bandes le sont."""
    present = [v for v in verdicts if v is not None]
    if not present:
        return None
    for verdict in ("too_narrow", "too_wide", "inconclusive"):
        if verdict in present:
            return verdict
    return "calibrated"


def simplex_grid(k: int, total: int, step: int) -> Iterator[tuple[int, ...]]:
    """Génère tous les vecteurs entiers non-négatifs de longueur k sommant à `total`, multiples de `step`."""
    if k == 1:
        yield (total,)
        return
    for w in range(0, total + 1, step):
        for rest in simplex_grid(k - 1, total - w, step):
            yield (w,) + rest


def suggest_optimal_weights(aligned_hist: pd.DataFrame, step_pct: int = 5, shrinkage: float = 0.5,
                            mu_override_pct: Sequence[float | None] | None = None,
                            risk_free_rate_pct: float = 0.0, min_weight_pct: float = 0.0,
                            max_weight_pct: float = 100.0,
                            ) -> tuple[dict[str, float] | None, dict[str, float] | None, dict[str, float] | None]:
    """Grille exhaustive sur les poids (pas besoin de scipy vu le petit nombre d'actifs).
    Renvoie (poids_sharpe_max, poids_vol_min, poids_parite_risque), chacun un dict {nom: poids_pct},
    ou None si aucune combinaison de la grille ne respecte min_weight_pct/max_weight_pct (contrainte
    trop stricte pour le nombre d'actifs/le pas choisi -- pas une erreur, juste rien à proposer).

    Les rendements moyens historiques sont un estimateur très bruité du rendement futur
    (peu d'observations, forte variance) : les utiliser bruts pousse l'optimiseur Sharpe
    vers des solutions de coin (tout sur l'actif qui a eu le plus de chance historiquement).
    On les "shrink" donc vers leur moyenne d'ensemble (aucune vue différenciée par défaut),
    ce qui stabilise fortement l'allocation suggérée. `mu_override_pct` (liste de rendements
    annuels en %, ou None par actif) remplace directement (sans shrinkage) la moyenne
    historique de l'actif concerné : c'est déjà une hypothèse choisie, pas un estimateur bruité.

    risk_free_rate_pct : soustrait du rendement au numérateur du ratio de Sharpe (rendement
    EXCÉDENTAIRE par unité de risque, définition usuelle) -- à 0 (défaut), comportement inchangé.
    Affecte réellement le classement (pas juste un décalage constant) puisque le ratio divise par
    une volatilité différente selon la combinaison. Mise en garde si réglé trop haut (au-dessus du
    rendement attendu de TOUS les actifs) : le rendement excédentaire devient négatif partout, et
    un ratio négatif divisé par une volatilité plus grande se rapproche de zéro -- l'optimiseur
    "préfère" alors paradoxalement l'actif le plus risqué (il minimise la casse plutôt qu'il ne
    maximise un gain). Pathologie connue du ratio de Sharpe appliqué tel quel en optimisation, pas
    un bug de cette fonction -- reste correct pour un taux sans risque réaliste (quelques %).

    min_weight_pct/max_weight_pct : bornes appliquées à chaque actif INCLUS dans le portefeuille
    (poids non nul) -- un actif reste exclu entièrement (poids 0) même si min_weight_pct > 0, pour
    ne jamais rendre la contrainte infaisable en forçant un poids minimum sur TOUS les actifs à la
    fois (ex: min=20% avec 7 actifs demanderait au moins 140% au total, impossible). Permet
    d'éviter les allocations "poussière" (quelques % ici et là) ou au contraire les positions trop
    concentrées, selon ce que l'utilisateur choisit."""
    names = list(aligned_hist.columns)
    mu_sample = aligned_hist.mean().to_numpy(dtype=float) * 12
    mu = (1 - shrinkage) * mu_sample + shrinkage * mu_sample.mean()
    if mu_override_pct is not None:
        for i, o in enumerate(mu_override_pct):
            if o is not None:
                mu[i] = o / 100
    cov = aligned_hist.cov().to_numpy(dtype=float) * 12
    risk_free_rate = risk_free_rate_pct / 100

    best_sharpe_val, best_sharpe_w = -np.inf, None
    best_vol_val, best_vol_w = np.inf, None
    best_rp_val, best_rp_w = np.inf, None
    for combo in simplex_grid(len(names), 100, step_pct):
        if any(c != 0 and not (min_weight_pct <= c <= max_weight_pct) for c in combo):
            continue
        w = np.array(combo) / 100
        port_vol = np.sqrt(w @ cov @ w)
        sharpe = (w @ mu - risk_free_rate) / port_vol if port_vol > 0 else -np.inf
        if sharpe > best_sharpe_val:
            best_sharpe_val, best_sharpe_w = sharpe, w
        if port_vol < best_vol_val:
            best_vol_val, best_vol_w = port_vol, w
        if port_vol > 0:
            # Parité de risque : chaque actif contribue à parts égales à la vol du portefeuille.
            risk_contrib = w * (cov @ w) / port_vol
            rp_dispersion = np.var(risk_contrib)
            if rp_dispersion < best_rp_val:
                best_rp_val, best_rp_w = rp_dispersion, w

    sharpe_weights = dict(zip(names, (best_sharpe_w * 100).round(0))) if best_sharpe_w is not None else None
    vol_weights = dict(zip(names, (best_vol_w * 100).round(0))) if best_vol_w is not None else None
    rp_weights = dict(zip(names, (best_rp_w * 100).round(0))) if best_rp_w is not None else None
    return sharpe_weights, vol_weights, rp_weights
