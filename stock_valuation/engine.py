"""
Moteur de calcul pur : valorisation intrinsèque (DCF) et relative (comparables)
d'une action. Aucune dépendance sur Dash/Plotly/yfinance : c'est ce que couvre
test_engine.py.
"""
import numpy as np

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
