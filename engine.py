"""
Moteur de calcul pur : simulation Monte Carlo (paramétrique ou bootstrap), DCA,
frais, fiscalité, et optimisation de poids de portefeuille. Aucune dépendance
sur Dash/Plotly/yfinance : c'est ce que couvre test_engine.py.
"""
import numpy as np
import pandas as pd

# ============================================================
# SIMULATION MONTE CARLO (paramétrique ou bootstrap)
# ============================================================

def block_bootstrap_indices(n_obs, n_months, n_sims, block_size, rng):
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


def _student_t_scale(rng, dof, size):
    """Facteur multiplicatif à appliquer à un tirage N(0,1) (ou N(0,Sigma)) pour obtenir une loi t
    de Student de même variance cible. `size` est la forme du tirage chi2 (un scalaire partagé par
    actif quand il y en a plusieurs, pour créer une dépendance de queue et pas juste des marges
    individuellement épaisses)."""
    w = rng.chisquare(dof, size=size)
    return np.sqrt((dof - 2) / w)


def simulate_index_returns(returns_hist: pd.Series, n_months, n_sims, seed, method, block_size=12,
                            mu_override_pct=None):
    """mu_override_pct : rendement annuel (%) à substituer à la moyenne historique, ou None pour la
    garder. La volatilité (et, en bootstrap, la forme empirique de la distribution) reste historique."""
    rng = np.random.default_rng(seed)
    target_monthly = (1 + mu_override_pct / 100) ** (1 / 12) - 1 if mu_override_pct is not None else None
    if method == "bootstrap":
        idx = block_bootstrap_indices(len(returns_hist), n_months, n_sims, block_size, rng)
        sampled = returns_hist.values[idx]
        if target_monthly is not None:
            sampled = sampled + (target_monthly - returns_hist.mean())
        return sampled
    mu, sigma = returns_hist.mean(), returns_hist.std()
    if target_monthly is not None:
        mu = target_monthly
    z = rng.standard_normal(size=(n_sims, n_months))
    scale = _student_t_scale(rng, STUDENT_T_DOF, size=(n_sims, n_months))
    return mu + sigma * z * scale


def simulate_portfolio_asset_returns(aligned_hist: pd.DataFrame, n_months, n_sims, seed, method, block_size=12,
                                      mu_override_pct=None):
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


def returns_to_dca(monthly_returns: np.ndarray, monthly_amounts: np.ndarray):
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


def inject_shock(returns: np.ndarray, shock_pct: float, shock_duration: int, start_month, rng):
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


def to_display_values(portfolio_value, invested_capital, years_axis, inflation_pct, real: bool):
    """Déflate en euros constants (année 0) si real=True, sinon renvoie les valeurs nominales."""
    if not real:
        return portfolio_value, invested_capital
    deflator = (1 + inflation_pct / 100) ** years_axis
    return portfolio_value / deflator, invested_capital / deflator


def constant_schedule(n_months: int, amount: float) -> np.ndarray:
    return np.full(n_months, amount)


def progressive_schedule(n_months: int, start_amount: float, end_amount: float) -> np.ndarray:
    return np.linspace(start_amount, end_amount, n_months)


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


def compute_objective_contribution(all_metrics: dict, schedules: dict, items: list,
                                    target_amount: float, percentile_key: str):
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


def simplex_grid(k: int, total: int, step: int):
    """Génère tous les vecteurs entiers non-négatifs de longueur k sommant à `total`, multiples de `step`."""
    if k == 1:
        yield (total,)
        return
    for w in range(0, total + 1, step):
        for rest in simplex_grid(k - 1, total - w, step):
            yield (w,) + rest


def suggest_optimal_weights(aligned_hist: pd.DataFrame, step_pct: int = 5, shrinkage: float = 0.5,
                             mu_override_pct=None):
    """Grille exhaustive sur les poids (pas besoin de scipy vu le petit nombre d'actifs).
    Renvoie (poids_sharpe_max, poids_vol_min, poids_parite_risque), chacun un dict {nom: poids_pct}.

    Les rendements moyens historiques sont un estimateur très bruité du rendement futur
    (peu d'observations, forte variance) : les utiliser bruts pousse l'optimiseur Sharpe
    vers des solutions de coin (tout sur l'actif qui a eu le plus de chance historiquement).
    On les "shrink" donc vers leur moyenne d'ensemble (aucune vue différenciée par défaut),
    ce qui stabilise fortement l'allocation suggérée. `mu_override_pct` (liste de rendements
    annuels en %, ou None par actif) remplace directement (sans shrinkage) la moyenne
    historique de l'actif concerné : c'est déjà une hypothèse choisie, pas un estimateur bruité.
    """
    names = list(aligned_hist.columns)
    mu_sample = aligned_hist.mean().values * 12
    mu = (1 - shrinkage) * mu_sample + shrinkage * mu_sample.mean()
    if mu_override_pct is not None:
        for i, o in enumerate(mu_override_pct):
            if o is not None:
                mu[i] = o / 100
    cov = aligned_hist.cov().values * 12

    best_sharpe_val, best_sharpe_w = -np.inf, None
    best_vol_val, best_vol_w = np.inf, None
    best_rp_val, best_rp_w = np.inf, None
    for combo in simplex_grid(len(names), 100, step_pct):
        w = np.array(combo) / 100
        port_vol = np.sqrt(w @ cov @ w)
        sharpe = (w @ mu) / port_vol if port_vol > 0 else -np.inf
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


# ============================================================
# DCF (flux de trésorerie actualisés) : valorisation intrinsèque d'une action
# ============================================================

def project_fcf(last_fcf: float, growth_rate_pct: float, n_years: int) -> np.ndarray:
    """FCF (free cash flow) projeté sur n_years, croissance annuelle constante."""
    years = np.arange(1, n_years + 1)
    return last_fcf * (1 + growth_rate_pct / 100) ** years


def terminal_value_gordon(final_fcf: float, terminal_growth_pct: float, discount_rate_pct: float) -> float:
    """Valeur terminale (Gordon-Shapiro) à la fin de l'horizon de projection : capitalise le
    dernier FCF projeté en rente perpétuelle croissante. N'a de sens que si discount_rate_pct >
    terminal_growth_pct (sinon dénominateur négatif ou nul), à valider par l'appelant."""
    g, r = terminal_growth_pct / 100, discount_rate_pct / 100
    return final_fcf * (1 + g) / (r - g)


def discount_to_present(cash_flows: np.ndarray, discount_rate_pct: float) -> np.ndarray:
    """Valeur actuelle de chaque flux futur (le flux d'indice i, en années depuis aujourd'hui,
    est actualisé sur i+1 ans)."""
    r = discount_rate_pct / 100
    years = np.arange(1, len(cash_flows) + 1)
    return cash_flows / (1 + r) ** years


def compute_dcf_fair_value(last_fcf: float, growth_rate_pct: float, discount_rate_pct: float,
                            terminal_growth_pct: float, n_years: int, net_debt: float,
                            shares_outstanding: float):
    """DCF non levier (FCFF) : projette le FCF, l'actualise avec une valeur terminale, retranche
    la dette nette pour passer de la valeur d'entreprise à la valeur des capitaux propres, puis
    divise par le nombre d'actions. Renvoie None si les hypothèses sont incohérentes (croissance
    terminale >= taux d'actualisation) ou si le nombre d'actions est inconnu/nul."""
    if discount_rate_pct <= terminal_growth_pct:
        return None
    if not shares_outstanding or shares_outstanding <= 0:
        return None

    projected = project_fcf(last_fcf, growth_rate_pct, n_years)
    pv_flows = discount_to_present(projected, discount_rate_pct)
    terminal_value = terminal_value_gordon(projected[-1], terminal_growth_pct, discount_rate_pct)
    pv_terminal_value = terminal_value / (1 + discount_rate_pct / 100) ** n_years

    enterprise_value = float(pv_flows.sum() + pv_terminal_value)
    equity_value = enterprise_value - net_debt
    return {
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "fair_value_per_share": equity_value / shares_outstanding,
        # Détail intermédiaire (année par année) : exposé pour l'affichage pédagogique du calcul
        # dans l'UI, pas utilisé par la formule elle-même.
        "projected_fcf": projected,
        "pv_flows": pv_flows,
        "terminal_value": float(terminal_value),
        "pv_terminal_value": float(pv_terminal_value),
    }


# ============================================================
# Comparables : valorisation relative par les multiples des pairs
# ============================================================

def compute_comparables_fair_value(price: float, own_pe: float, peer_median_pe: float):
    """Valeur implicite d'une action si elle se traitait au P/E médian de ses pairs plutôt
    qu'à son P/E actuel : price * (peer_median_pe / own_pe). Travailler par ratio au prix
    courant (plutôt que peer_median_pe * BPA) évite d'avoir besoin du BPA en unité correcte
    (certaines places, Londres notamment, cotent le prix et le BPA dans des unités différentes,
    cf. market_data._price_scale_factor). Renvoie None si une donnée manque ou est invalide."""
    if not price or not own_pe or own_pe <= 0 or not peer_median_pe or peer_median_pe <= 0:
        return None
    return price * (peer_median_pe / own_pe)
