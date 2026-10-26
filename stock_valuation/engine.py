"""
Moteur de calcul pur : valorisation intrinsèque (DCF) et relative (comparables)
d'une action. Aucune dépendance sur Dash/Plotly/yfinance : c'est ce que couvre
test_engine.py.
"""
import numpy as np
import pandas as pd

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


def compute_scenario_dcf_fair_values(last_fcf: float, base_growth_pct: float, base_discount_pct: float,
                                      terminal_growth_pct: float, n_years: int, net_debt: float,
                                      shares_outstanding: float, growth_offset_pct: float,
                                      discount_offset_pct: float, weight_bear: float, weight_base: float,
                                      weight_bull: float) -> dict:
    """3 scénarios DCF autour des mêmes hypothèses de base (terminal_growth_pct/n_years/net_debt/
    shares_outstanding identiques aux 3) : Bear = croissance réduite de growth_offset_pct et taux
    d'actualisation augmenté de discount_offset_pct (flux plus faibles, actualisés plus fort),
    Bull = l'inverse symétrique, Base = hypothèses inchangées. Chaque scénario réutilise
    compute_dcf_fair_value tel quel, qui renvoie déjà None si les hypothèses deviennent incohérentes
    (ex : le taux d'actualisation abaissé du scénario Bull tombe à/sous la croissance terminale) —
    ce scénario est alors simplement absent de la moyenne pondérée plutôt que de faire échouer les
    autres. Les poids (n'importe quelle unité positive, pas nécessairement déjà normalisée à 100)
    sont renormalisés en interne sur les seuls scénarios valides. Renvoie {"bear": dict|None,
    "base": dict|None, "bull": dict|None, "weighted_fair_value": float|None} ; weighted_fair_value
    vaut None si aucun scénario n'est valide ou si les poids des scénarios valides somment à 0."""
    scenarios = {
        "bear": (base_growth_pct - growth_offset_pct, base_discount_pct + discount_offset_pct, weight_bear),
        "base": (base_growth_pct, base_discount_pct, weight_base),
        "bull": (base_growth_pct + growth_offset_pct, base_discount_pct - discount_offset_pct, weight_bull),
    }
    results = {}
    weighted_sum, weight_total = 0.0, 0.0
    for key, (growth_pct, discount_pct, weight) in scenarios.items():
        result = compute_dcf_fair_value(
            last_fcf, growth_pct, discount_pct, terminal_growth_pct, n_years, net_debt, shares_outstanding,
        )
        results[key] = result
        if result is not None and weight and weight > 0:
            weighted_sum += result["fair_value_per_share"] * weight
            weight_total += weight
    results["weighted_fair_value"] = (weighted_sum / weight_total) if weight_total > 0 else None
    return results


def compute_dcf_sensitivity_grid(last_fcf: float, base_growth_pct: float, base_discount_pct: float,
                                  terminal_growth_pct: float, n_years: int, net_debt: float,
                                  shares_outstanding: float, growth_step_pct: float = 5,
                                  discount_step_pct: float = 1, grid_size: int = 5):
    """Grille grid_size x grid_size de fair_value_per_share (croissance en lignes, taux
    d'actualisation en colonnes), centrée sur les hypothèses de base avec un pas de
    growth_step_pct/discount_step_pct par cellule. grid_size doit être impair pour que le cas de
    base tombe exactement sur la cellule d'indice (half, half) où half = grid_size // 2 — c'est
    cette position d'indice, pas une comparaison de flottants sur les valeurs, qui identifie la
    cellule centrale à l'affichage. Une cellule vaut None quand ses hypothèses deviennent
    incohérentes (garde existante dans compute_dcf_fair_value), à afficher comme "N/A". Renvoie
    (growth_values, discount_values, grid) : deux listes de grid_size flottants (axes triés
    croissants) et une liste de listes grid_size x grid_size de float|None."""
    half = grid_size // 2
    growth_values = [base_growth_pct + (i - half) * growth_step_pct for i in range(grid_size)]
    discount_values = [base_discount_pct + (j - half) * discount_step_pct for j in range(grid_size)]
    grid = [
        [
            (compute_dcf_fair_value(last_fcf, g, d, terminal_growth_pct, n_years, net_debt, shares_outstanding) or {}).get("fair_value_per_share")
            for d in discount_values
        ]
        for g in growth_values
    ]
    return growth_values, discount_values, grid


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


def compute_comparables_ev_ebitda_fair_value(enterprise_value: float, ev_to_ebitda: float,
                                              peer_median_ev_ebitda: float, total_debt: float,
                                              total_cash: float, shares_outstanding: float):
    """Valeur implicite par action si l'entreprise se traitait au multiple EV/EBITDA médian de ses
    pairs plutôt qu'au sien. L'EBITDA propre est déduit de enterprise_value / ev_to_ebitda plutôt
    que recalculé depuis le compte de résultat (aucun appel réseau de plus : les deux viennent
    déjà de market_data.get_dcf_inputs, où enterprise_value est reconstruit dans une unité
    cohérente avec total_debt/total_cash — voir le commentaire associé). La dette nette
    (total_debt - total_cash) est retranchée de l'EV implicite pour revenir à une valeur des
    capitaux propres, même logique que le DCF. Renvoie None si une donnée manque ou est
    invalide. Invariant utile pour les tests : si peer_median_ev_ebitda == ev_to_ebitda (même
    multiple que soi-même), le résultat doit redonner exactement le prix courant."""
    if not enterprise_value or not ev_to_ebitda or ev_to_ebitda <= 0:
        return None
    if not peer_median_ev_ebitda or peer_median_ev_ebitda <= 0:
        return None
    if not shares_outstanding or shares_outstanding <= 0:
        return None
    ebitda = enterprise_value / ev_to_ebitda
    implied_enterprise_value = ebitda * peer_median_ev_ebitda
    implied_equity_value = implied_enterprise_value - total_debt + total_cash
    return implied_equity_value / shares_outstanding


# ============================================================
# « Football field » : fourchette de valeur par méthode, à comparer au cours
# ============================================================

# Seuils des alertes de la liste de suivi : les mêmes que les couleurs du tableau de criblage
# (layout.CELL_CLASS_RULES), pour qu'une alerte et une case verte disent la même chose.
WATCHLIST_PE_HISTORY_LOW_PCT = 20
WATCHLIST_HIGH_SCORE = 70
WATCHLIST_MIN_PEERS = 3
WATCHLIST_ALERTS = ("below_target", "pe_history_low", "below_comparables", "below_dcf", "high_score")


def watchlist_alerts(price: float | None, own_pe: float | None, pe_percentile: float | None,
                     score: float | None, peer_pes: list, dcf_fair_value: float | None,
                     target_price: float | None = None) -> dict[str, float]:
    """Signaux d'achat potentiels d'un titre suivi, chacun avec la valeur qui l'a déclenché :
    - "pe_history_low" : P/E dans les 20 % les plus bas de sa propre histoire (valeur : percentile) ;
    - "below_comparables" : cours sous la valeur implicite au P/E médian d'au moins 3 pairs du
      secteur (valeur : potentiel en %, voir compute_comparables_fair_value) ;
    - "below_dcf" : cours sous la valeur intrinsèque DCF aux hypothèses par défaut (valeur :
      potentiel en %) ;
    - "high_score" : score composite >= 70 (valeur : score) ;
    - "below_target" : cours au niveau ou sous le prix cible noté dans le journal (valeur : potentiel
      en % jusqu'à la cible, 0 pile au niveau). Placé en tête : c'est le seul seuil choisi par
      l'utilisateur lui-même.
    Une donnée manquante ne déclenche rien : l'absence d'alerte n'est pas un signal contraire.
    Ce sont des pistes à creuser, pas des recommandations."""
    alerts: dict[str, float] = {}
    if pe_percentile is not None and not np.isnan(pe_percentile) and pe_percentile < WATCHLIST_PE_HISTORY_LOW_PCT:
        alerts["pe_history_low"] = float(pe_percentile)
    valid_peers = [p for p in peer_pes if p is not None and p > 0]
    if price and len(valid_peers) >= WATCHLIST_MIN_PEERS:
        implied = compute_comparables_fair_value(price, own_pe, float(np.median(valid_peers)))
        if implied is not None and implied > price:
            alerts["below_comparables"] = (implied / price - 1) * 100
    if price and dcf_fair_value is not None and dcf_fair_value > price:
        alerts["below_dcf"] = (dcf_fair_value / price - 1) * 100
    if score is not None and not np.isnan(score) and score >= WATCHLIST_HIGH_SCORE:
        alerts["high_score"] = float(score)
    if price and target_price is not None and target_price > 0 and price <= target_price:
        alerts["below_target"] = (target_price / price - 1) * 100
    return alerts


def reviews_due(entries: list[dict], today) -> list[dict]:
    """Entrées du journal dont la date de revue (« review_date », AAAA-MM-JJ) est atteinte ou passée,
    la plus ancienne d'abord. Une entrée sans date de revue n'est jamais due."""
    today_str = pd.Timestamp(today).strftime("%Y-%m-%d")
    due = [e for e in entries if e.get("review_date") and str(e["review_date"]) <= today_str]
    return sorted(due, key=lambda e: str(e["review_date"]))


def elapsed_unit(seconds: float) -> tuple[str, int]:
    """Âge arrondi vers le bas dans l'unité la plus lisible : ("now", 0) sous une minute, puis
    minutes, heures et jours. Arrondi vers le bas : « il y a 1 h » pour 1 h 59 ne vieillit jamais
    les données."""
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return "now", 0
    if seconds < 3600:
        return "minutes", int(seconds // 60)
    if seconds < 86400:
        return "hours", int(seconds // 3600)
    return "days", int(seconds // 86400)


def gap_to_target_pct(price: float | None, target_price: float | None) -> float | None:
    """Écart du cours au prix cible, en % du prix cible : négatif sous la cible, positif au-dessus.
    None si l'un des deux manque (jamais 0 à la place)."""
    if price is None or target_price is None or target_price <= 0 or not np.isfinite(price):
        return None
    return (price / target_price - 1) * 100


FOOTBALL_FIELD_METHODS = ("dcf_scenarios", "dcf_sensitivity", "comparables_pe", "comparables_ev_ebitda")


def peer_quartile_multiples(multiples: list[float]) -> tuple[float, float, float] | None:
    """Premier quartile, médiane et troisième quartile des multiples des pairs (interpolation
    linéaire). None sous 3 pairs : même seuil que la valeur par comparables elle-même."""
    if len(multiples) < 3:
        return None
    q1, median, q3 = np.percentile(np.asarray(multiples, dtype=float), [25, 50, 75])
    return float(q1), float(median), float(q3)


def football_field_ranges(estimates: dict[str, tuple[list, float | None]]) -> list[dict]:
    """Fourchettes du football field, dans l'ordre de FOOTBALL_FIELD_METHODS : pour chaque méthode,
    (valeurs qui bornent la fourchette, valeur centrale). Bas = la plus petite valeur disponible, haut
    = la plus grande ; une valeur manquante est écartée, jamais prise pour 0, et une méthode sans
    aucune valeur disparaît du graphique. Une valeur centrale absente prend le milieu de la fourchette."""
    rows = []
    for method in FOOTBALL_FIELD_METHODS:
        if method not in estimates:
            continue
        bounds, central = estimates[method]
        values = [float(v) for v in bounds if v is not None and np.isfinite(v)]
        if central is not None and np.isfinite(central):
            values.append(float(central))
        if not values:
            continue
        low, high = min(values), max(values)
        mid = float(central) if central is not None and np.isfinite(central) else (low + high) / 2
        rows.append({"method": method, "low": low, "mid": mid, "high": high})
    return rows


# ============================================================
# Backtest du signal "P/E décoté/tendu vs son propre historique 5 ans" : ce signal est déjà
# affiché dans l'UI (cartes "5 les plus décotées/tendues vs leur propre historique 5 ans") comme
# une heuristique ; ces fonctions vérifient empiriquement si un P/E bas vs historique a
# effectivement précédé un meilleur rendement qu'un P/E haut, sur le panier chargé.
# ============================================================

# Délai usuel de publication des comptes annuels : le BPA d'un exercice n'est réputé connu du marché
# que 3 mois après sa clôture. Avant, le P/E d'une date passée utilise le BPA de l'exercice précédent :
# aucune information « du futur » dans l'historique.
EPS_PUBLICATION_LAG_DAYS = 91


def pe_from_annual_eps(closes: pd.Series, annual_eps: pd.Series,
                       lag_days: int = EPS_PUBLICATION_LAG_DAYS) -> pd.Series:
    """P/E historique : cours de chaque date / BPA du dernier exercice publié à cette date (clôture +
    lag_days). annual_eps : BPA par date de clôture d'exercice, déjà dans l'unité des cours. Les dates
    antérieures au premier BPA publié sont écartées (pas de BPA connu), de même qu'un BPA négatif ou
    nul (P/E sans signification) : jamais un P/E calculé sur un chiffre inventé."""
    eps = annual_eps.dropna()
    if closes.empty or eps.empty:
        return pd.Series(dtype=float)
    published = pd.Series(eps.to_numpy(dtype=float),
                          index=pd.DatetimeIndex(eps.index).normalize() + pd.Timedelta(days=lag_days)).sort_index()
    published = published[~published.index.duplicated(keep="last")]
    dates = pd.DatetimeIndex(closes.index)
    naive = (dates.tz_localize(None) if dates.tz is not None else dates).normalize()
    eps_known = published.reindex(published.index.union(naive)).ffill().reindex(naive).to_numpy()
    pe = pd.Series(closes.to_numpy(dtype=float) / eps_known, index=closes.index)
    return pe[np.isfinite(pe) & (eps_known > 0)]


def compute_pe_percentile_series(series: np.ndarray, min_history: int = 52) -> np.ndarray:
    """Percentile (0-100) de chaque point au sein de SA SEULE fenêtre passée (expanding window,
    series[:t+1]) : le percentile au point t n'utilise jamais une valeur future, pour ne pas
    biaiser le backtest par anticipation. Les min_history premiers points (pas assez d'historique
    pour un percentile qui veuille dire quelque chose) valent NaN."""
    n = len(series)
    out = np.full(n, np.nan)
    for t in range(min_history, n):
        window = series[: t + 1]
        out[t] = 100.0 * float((window < series[t]).mean())
    return out


def pe_signal_forward_returns(pe_series: np.ndarray, forward_periods: int = 52, min_history: int = 52,
                               low_percentile: float = 20.0, high_percentile: float = 80.0):
    """Classe chaque point assez documenté (percentile connu, voir compute_pe_percentile_series)
    selon que son P/E était bas (percentile < low_percentile), moyen, ou haut (percentile >
    high_percentile) vs son propre historique à cette date, puis calcule son rendement sur les
    forward_periods pas suivants.

    Calculé directement sur pe_series plutôt que sur une série de prix séparée : sous
    l'hypothèse de BPA constant déjà posée par market_data.get_stock_pe_history (qui produit
    cette série), le P/E est proportionnel au prix, donc le rendement relatif du P/E EST le
    rendement relatif du prix implicite — inutile de dupliquer la série de prix pour ce calcul.

    Renvoie (low_returns, mid_returns, high_returns), trois listes de floats (rendements, ex. 0.1
    pour +10%). Liste vide si pe_series est trop courte pour produire un seul point exploitable
    (il faut au moins min_history + forward_periods observations)."""
    n = len(pe_series)
    if n <= min_history + forward_periods:
        return [], [], []
    percentiles = compute_pe_percentile_series(pe_series, min_history)
    low, mid, high = [], [], []
    for t in range(n - forward_periods):
        pct = percentiles[t]
        if np.isnan(pct):
            continue
        forward_return = float(pe_series[t + forward_periods] / pe_series[t] - 1)
        if pct < low_percentile:
            low.append(forward_return)
        elif pct > high_percentile:
            high.append(forward_return)
        else:
            mid.append(forward_return)
    return low, mid, high


def summarize_pe_signal_backtest(per_stock_returns) -> dict:
    """Agrège les triplets (low, mid, high) de plusieurs titres (voir pe_signal_forward_returns)
    en un résumé poolé sur tout le panier : {"low": {...}, "mid": {...}, "high": {...}}, chacun
    {"n": int, "mean": float|None, "median": float|None}. n vaut 0 et mean/median valent None
    quand la tranche est vide (aucun point classé dedans sur l'ensemble du panier).

    Le pooling augmente la taille d'échantillon affichée, mais ces observations se chevauchent
    dans le temps (fenêtres glissantes d'un même titre) et ne sont donc pas indépendantes : n est
    un ordre de grandeur, pas un vrai nombre de tirages indépendants — à ne pas lire comme une
    significativité statistique classique."""
    low_all, mid_all, high_all = [], [], []
    for low, mid, high in per_stock_returns:
        low_all.extend(low)
        mid_all.extend(mid)
        high_all.extend(high)

    def _stats(values):
        if not values:
            return {"n": 0, "mean": None, "median": None}
        arr = np.array(values)
        return {"n": len(arr), "mean": float(arr.mean()), "median": float(np.median(arr))}

    return {"low": _stats(low_all), "mid": _stats(mid_all), "high": _stats(high_all)}


# ============================================================
# Track record (rendement/risque réalisés) : métriques purement rétrospectives, calculées sur les
# rendements mensuels passés d'un titre (voir market_data.get_stock_price_history) — un
# complément aux valorisations prospectives (DCF/comparables) ci-dessus, pas une prédiction.
# ============================================================

def annualized_return(returns: np.ndarray, periods_per_year: int = 12) -> float | None:
    """Rendement annualisé composé (CAGR) à partir d'une série de rendements périodiques
    (ex: mensuels). None si la série est vide : pas d'historique, pas de CAGR."""
    if len(returns) == 0:
        return None
    growth = float(np.prod(1 + returns))
    n_periods = len(returns)
    return growth ** (periods_per_year / n_periods) - 1


def annualized_volatility(returns: np.ndarray, periods_per_year: int = 12) -> float | None:
    """Écart-type des rendements périodiques, annualisé par la racine du nombre de périodes par
    an (les variances de rendements indépendants s'additionnent dans le temps). None si moins de
    2 points : un écart-type sur un seul point n'a pas de sens."""
    if len(returns) < 2:
        return None
    return float(np.std(returns, ddof=1) * np.sqrt(periods_per_year))


def max_drawdown(returns: np.ndarray) -> float | None:
    """Pire baisse par rapport à un plus haut précédent, sur la période couverte par returns.
    Reconstruit une valeur cumulée (base 1.0) à partir des rendements plutôt que d'exiger une
    série de prix séparée : le point de départ (1.0) est arbitraire mais le drawdown relatif ne
    dépend pas de lui. Une chute dès le tout premier point ne compte pas (aucun plus haut
    antérieur dans la série pour la mesurer) : limite acceptée, le premier point sert toujours de
    référence initiale. None si returns est vide."""
    if len(returns) == 0:
        return None
    cumulative_value = np.cumprod(1 + returns)
    running_max = np.maximum.accumulate(cumulative_value)
    drawdown = cumulative_value / running_max - 1
    return float(drawdown.min())


def sharpe_ratio(annual_return: float | None, annual_volatility: float | None, risk_free_rate: float = 0.0) -> float | None:
    """Rendement excédentaire par unité de risque. None si le rendement ou la volatilité est
    manquant, ou si la volatilité est nulle (division par zéro sans signification)."""
    if annual_return is None or not annual_volatility:
        return None
    return (annual_return - risk_free_rate) / annual_volatility
