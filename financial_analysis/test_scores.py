"""
Tests des scores d'alerte (engine.py) : reproduction d'exemples chiffrés publiés (sources citées
au-dessus de chaque test), définitions des indices sur des états synthétiques, et cas limites
(donnée manquante, base nulle, seuils).
Usage : pip install -r requirements-dev.txt && pytest -v
"""
import numpy as np
import pandas as pd
import pytest

import engine as m

T, P, PP = pd.Timestamp("2024-12-31"), pd.Timestamp("2023-12-31"), pd.Timestamp("2022-12-31")


def _ns(income: dict, balance: dict, cashflow: dict, years=(T, P)) -> m.NormalizedStatements:
    """États synthétiques : {libellé yfinance: [valeur par exercice, du plus récent au plus ancien]}."""
    def frame(rows):
        return pd.DataFrame.from_dict(rows, orient="index", columns=list(years), dtype=float) if rows else pd.DataFrame()
    return m.normalize_statements(frame(income), frame(balance), frame(cashflow))


# ============================================================
# Beneish M-score
# ============================================================

# Source : Beneish (1999), « The Detection of Earnings Manipulation », version de travail de juin
# 1999 (publiée dans le Financial Analysts Journal 55(5), 24-36). Tableau 2, p. 23 : moyennes des
# 8 variables pour les 50 manipulateurs et les 1 708 non-manipulateurs de l'échantillon
# d'estimation ; tableau 3, p. 24 : coefficients du probit non pondéré. Calcul à la main :
# manipulateurs  -4,84 + 0,92×1,465 + 0,528×1,193 + 0,404×1,254 + 0,892×1,607 + 0,115×1,077
#                - 0,172×1,041 + 4,679×0,031 - 0,327×1,111 = -1,196 (au-dessus du seuil -1,78)
# non-manip.     ... = -2,246 (en dessous du seuil).

def test_beneish_reproduces_published_sample_means():
    manipulators = m.beneish_m_score_from_indices(m.BENEISH_REFERENCE_MEANS["manipulators"])
    non_manipulators = m.beneish_m_score_from_indices(m.BENEISH_REFERENCE_MEANS["non_manipulators"])
    assert manipulators == pytest.approx(-1.196, abs=1e-3)
    assert non_manipulators == pytest.approx(-2.246, abs=1e-3)
    assert manipulators > m.BENEISH_THRESHOLD > non_manipulators


def test_beneish_coefficients_match_table_3():
    assert m.BENEISH_INTERCEPT == -4.84
    assert m.BENEISH_COEFFICIENTS == {"dsri": 0.920, "gmi": 0.528, "aqi": 0.404, "sgi": 0.892, "depi": 0.115,
                                      "sgai": -0.172, "lvgi": -0.327, "tata": 4.679}


def _beneish_case(**overrides):
    """Société synthétique aux chiffres ronds, pour vérifier chaque indice à la main."""
    income = {"Total Revenue": [1200, 1000], "Gross Profit": [360, 400], "Selling General And Administration": [240, 180],
              "Depreciation Income Statement": [50, 60], "Net Income Including Noncontrolling Interests": [100, 80]}
    balance = {"Accounts Receivable": [300, 200], "Current Assets": [500, 450], "Net PPE": [450, 440],
               "Total Assets": [1000, 1000], "Current Liabilities": [300, 250],
               "Long Term Debt And Capital Lease Obligation": [200, 200]}
    cashflow = {"Operating Cash Flow": [60, 90]}
    for group in (income, balance, cashflow):
        for label, values in overrides.items():
            if label in group:
                group[label] = values
    return _ns(income, balance, cashflow)


def test_beneish_indices_definitions_by_hand():
    result = m.beneish_m_score(_beneish_case(), T, P)
    idx = {k: v["value"] for k, v in result["indices"].items()}
    # DSRI = (300 / 1 200) / (200 / 1 000) = 0,25 / 0,20 = 1,25
    assert idx["dsri"] == pytest.approx(1.25)
    # GMI = marge t-1 / marge t = (400 / 1 000) / (360 / 1 200) = 0,40 / 0,30 = 1,333
    assert idx["gmi"] == pytest.approx(0.40 / 0.30)
    # AQI = [1 - (500 + 450) / 1 000] / [1 - (450 + 440) / 1 000] = 0,05 / 0,11
    assert idx["aqi"] == pytest.approx(0.05 / 0.11)
    # SGI = 1 200 / 1 000
    assert idx["sgi"] == pytest.approx(1.2)
    # DEPI = taux t-1 / taux t = [60 / (60 + 440)] / [50 / (50 + 450)] = 0,12 / 0,10 = 1,2
    assert idx["depi"] == pytest.approx(1.2)
    # SGAI = (240 / 1 200) / (180 / 1 000) = 0,20 / 0,18
    assert idx["sgai"] == pytest.approx(0.20 / 0.18)
    # LVGI = [(300 + 200) / 1 000] / [(250 + 200) / 1 000] = 0,50 / 0,45
    assert idx["lvgi"] == pytest.approx(0.50 / 0.45)
    # TATA = (100 - 60) / 1 000
    assert idx["tata"] == pytest.approx(0.04)
    expected = m.beneish_m_score_from_indices(idx)
    assert result["m_score"]["value"] == pytest.approx(expected)
    assert result["pair"] == (T, P)
    assert result["contributions"]["dsri"] == pytest.approx(0.920 * 1.25)


def test_beneish_missing_sga_gives_official_na_and_indicative_neutralized():
    ns = _beneish_case(**{"Selling General And Administration": [np.nan, np.nan]})
    result = m.beneish_m_score(ns, T, P)
    assert result["m_score"]["value"] is None
    assert result["m_score"]["missing"] == ("sgai",)
    indicative = result["m_score_indicative"]
    assert indicative["neutralized"] == ("sgai",)
    values = {k: v["value"] for k, v in result["indices"].items()}
    values["sgai"] = 1.0
    assert indicative["value"] == pytest.approx(m.beneish_m_score_from_indices(values))


def test_beneish_missing_tata_has_no_indicative_score():
    """TATA est un niveau, sans valeur neutre : pas de variante indicative possible sans lui."""
    ns = _beneish_case(**{"Operating Cash Flow": [np.nan, 90]})
    result = m.beneish_m_score(ns, T, P)
    assert result["m_score"]["value"] is None
    assert result["m_score_indicative"] is None


def test_beneish_aqi_neutral_when_prior_base_is_zero():
    # t-1 : actif courant 560 + immobilisations 440 = actif total 1 000 -> base de l'AQI nulle.
    ns = _beneish_case(**{"Current Assets": [500, 560]})
    aqi = m.beneish_m_score(ns, T, P)["indices"]["aqi"]
    assert aqi["value"] == 1.0
    assert aqi["flags"] == ("aqi_neutral_by_definition",)


def test_beneish_gmi_not_meaningful_on_negative_margin():
    ns = _beneish_case(**{"Gross Profit": [-50, 400]})
    gmi = m.beneish_m_score(ns, T, P)["indices"]["gmi"]
    assert gmi["value"] is None
    assert gmi["reason"] == "non_positive_base"


def test_beneish_verdict_threshold():
    assert m.beneish_verdict(-1.70) == "manipulation_risk"
    assert m.beneish_verdict(-1.78) == "no_signal"
    assert m.beneish_verdict(-2.50) == "no_signal"


def test_consecutive_pairs_most_recent_first():
    ns = _ns({"Total Revenue": [3, 2, 1]}, {}, {}, years=(T, P, PP))
    assert m.consecutive_pairs(ns) == [(T, P), (P, PP)]


# ============================================================
# Altman Z-score
# ============================================================

# Source : Wall Street Prep, « Altman Z-Score » (wallstreetprep.com/knowledge/altman-z-score),
# exemple chiffré : fonds de roulement 20 M$, réserves 8 M$, EBIT 20 M$, capitalisation 80 M$,
# passif total 120 M$, chiffre d'affaires 60 M$, actif total 160 M$ ; Z = 1,40, zone de détresse.
# L'article utilise 0,99 pour X5 ; avec le 0,999 d'Altman (1968), Z = 1,407 : même valeur à l'arrondi
# près (écart de 0,007) et même zone.

def test_altman_reproduces_published_example():
    ratios = {"x1": 20 / 160, "x2": 8 / 160, "x3": 20 / 160, "x4": 80 / 120, "x5": 60 / 160}
    z = m.altman_z_from_ratios(ratios, "original")
    assert z == pytest.approx(1.40, abs=0.01)
    assert m.altman_zone(z, "original") == "distress"


def test_altman_from_statements_matches_the_published_example():
    ns = _ns(
        {"EBIT": [20e6, 18e6], "Total Revenue": [60e6, 55e6]},
        {"Working Capital": [20e6, 15e6], "Retained Earnings": [8e6, 6e6], "Total Assets": [160e6, 150e6],
         "Total Liabilities Net Minority Interest": [120e6, 115e6]},
        {},
    )
    result = m.altman_z_score(ns, T, "original", market_value=80e6)
    assert result["value"] == pytest.approx(m.altman_z_from_ratios(
        {"x1": 0.125, "x2": 0.05, "x3": 0.125, "x4": 80 / 120, "x5": 0.375}, "original"))
    assert result["zone"] == "distress"
    assert result["components"]["x4"]["numerator_key"] == "market_value_of_equity"
    assert result["contributions"]["x1"] == pytest.approx(1.2 * 0.125)


# Source : CliffsNotes, « Understanding the Altman Z-Score: Key Ratios and Calculations »
# (cliffsnotes.com/study-notes/33602293), exemple d'une société de services : fonds de roulement
# 80 000, réserves 150 000, EBIT 100 000, fonds propres 250 000, passif 200 000, actif 400 000 ;
# Z'' = 5,527. Réserve : l'exemple prend la capitalisation au lieu des fonds propres comptables du
# Z'' standard ; seule l'arithmétique des coefficients d'Altman et al. (2017) est vérifiée ici, en
# traitant ces 250 000 comme des fonds propres comptables.

def test_altman_z_double_prime_reproduces_published_example():
    z = m.altman_z_from_ratios({"x1": 0.20, "x2": 0.375, "x3": 0.25, "x4": 1.25}, "z_double_prime")
    assert z == pytest.approx(5.527, abs=1e-3)
    assert m.altman_zone(z, "z_double_prime") == "safe"


def test_altman_z_double_prime_uses_book_equity_and_no_x5():
    ns = _ns(
        {"EBIT": [100e3, 90e3], "Total Revenue": [900e3, 800e3]},
        {"Working Capital": [80e3, 70e3], "Retained Earnings": [150e3, 140e3], "Total Assets": [400e3, 380e3],
         "Total Liabilities Net Minority Interest": [200e3, 190e3], "Total Equity Gross Minority Interest": [250e3, 230e3]},
        {},
    )
    result = m.altman_z_score(ns, T, "z_double_prime")
    assert result["value"] == pytest.approx(5.527, abs=1e-3)
    assert "x5" not in result["components"]


def test_altman_original_without_market_value_is_na():
    ns = _ns({"EBIT": [20, 18], "Total Revenue": [60, 55]},
             {"Working Capital": [20, 15], "Retained Earnings": [8, 6], "Total Assets": [160, 150],
              "Total Liabilities Net Minority Interest": [120, 115]}, {})
    result = m.altman_z_score(ns, T, "original", market_value=None)
    assert result["value"] is None and result["zone"] is None
    assert result["missing"] == ("market_value_of_equity",)


@pytest.mark.parametrize("z,zone", [(1.80, "distress"), (1.81, "grey"), (2.99, "grey"), (3.00, "safe")])
def test_altman_original_zones(z, zone):
    assert m.altman_zone(z, "original") == zone


@pytest.mark.parametrize("z,zone", [(1.09, "distress"), (1.10, "grey"), (2.60, "grey"), (2.61, "safe")])
def test_altman_z_double_prime_zones(z, zone):
    assert m.altman_zone(z, "z_double_prime") == zone


@pytest.mark.parametrize("sector,model", [("Industrials", "original"), ("Basic Materials", "original"),
                                          ("Technology", "z_double_prime"), (None, "z_double_prime")])
def test_altman_default_model(sector, model):
    assert m.altman_default_model(sector) == model


def test_price_on_or_before_takes_last_close_up_to_the_date():
    closes = pd.Series([10.0, 11.0, 12.0], index=pd.to_datetime(["2024-12-27", "2024-12-30", "2025-01-02"]))
    assert m.price_on_or_before(closes, T) == 11.0  # 31/12 sans cotation : clôture du 30/12
    assert m.price_on_or_before(closes, pd.Timestamp("2024-12-30")) == 11.0


def test_price_on_or_before_rejects_stale_or_missing_prices():
    closes = pd.Series([10.0], index=pd.to_datetime(["2024-11-01"]))
    assert m.price_on_or_before(closes, T) is None  # dernier cours vieux de deux mois
    assert m.price_on_or_before(pd.Series(dtype=float), T) is None


def test_market_value_of_equity_in_reporting_currency():
    # 3 938 pence -> 39,38 £ × 5 689 M d'actions × 1,333 USD/£.
    assert m.market_value_of_equity(3938.0, 5.689e9, 100.0, 1.333) == pytest.approx(39.38 * 5.689e9 * 1.333)
    assert m.market_value_of_equity(3938.0, 5.689e9, 100.0, None) is None


# ============================================================
# Piotroski F-score
# ============================================================

# Source : Stablebread, « How to Identify Financially Strong Companies With the Piotroski F-Score »
# (stablebread.com/piotroski-f-score), exemple de Lowe's (M$) : résultat net 7 726 / 6 437, actif
# total 41 795 / 43 708, CFO 8 140, dette à long terme 35 384 / 32 876, actif courant 19 071 / 21 442,
# passif courant 15 568 / 19 511, CA 86 377 / 97 059, marge brute 28 844 / 32 257 ; F-score de 7
# (levier et rotation de l'actif à 0). L'article rapporte tout à l'actif de CLÔTURE, d'où
# asset_base="end". Il ne donne pas le nombre d'actions et juge l'émission nulle : on reprend donc un
# nombre d'actions inchangé.

def _lowes():
    return _ns(
        {"Net Income": [7726, 6437], "Total Revenue": [86377, 97059], "Gross Profit": [28844, 32257]},
        {"Total Assets": [41795, 43708], "Long Term Debt": [35384, 32876], "Current Assets": [19071, 21442],
         "Current Liabilities": [15568, 19511], "Ordinary Shares Number": [570, 570]},
        {"Operating Cash Flow": [8140, np.nan]},
    )


def test_piotroski_reproduces_published_lowes_example():
    result = m.piotroski_f_score(_lowes(), T, asset_base="end")
    criteria = {k: v["value"] for k, v in result["criteria"].items()}
    assert criteria == {
        "roa_positive": 1, "cfo_positive": 1, "roa_improved": 1, "cfo_exceeds_net_income": 1,
        "leverage_decreased": 0, "current_ratio_improved": 1, "no_equity_issuance": 1,
        "gross_margin_improved": 1, "asset_turnover_improved": 0,
    }
    assert result["score"] == 7 and result["n_available"] == 9
    # Ratios intermédiaires publiés : ROA 18,5 % et 14,7 %, levier 84,7 % et 75,2 %.
    assert result["criteria"]["roa_improved"]["details"]["roa_t"] == pytest.approx(0.185, abs=1e-3)
    assert result["criteria"]["roa_improved"]["details"]["roa_p"] == pytest.approx(0.147, abs=1e-3)
    assert result["criteria"]["leverage_decreased"]["details"]["leverage_t"] == pytest.approx(0.847, abs=1e-3)


def test_piotroski_beginning_base_needs_three_balance_sheets():
    """Définition de Piotroski : ROA sur l'actif d'ouverture. Avec deux exercices seulement, le ROA de
    t est calculable (actif de t-1) mais pas celui de t-1 : les critères de variation sont n.d., et le
    score porte sur les seuls critères calculables."""
    result = m.piotroski_f_score(_lowes(), T, asset_base="beginning")
    assert result["criteria"]["roa_positive"]["value"] == 1
    assert result["criteria"]["roa_positive"]["details"]["roa_t"] == pytest.approx(7726 / 43708)
    assert result["criteria"]["roa_improved"]["value"] is None
    assert result["criteria"]["roa_improved"]["missing"] == ("roa_p",)
    assert result["n_available"] < 9
    assert result["score"] == sum(c["value"] for c in result["criteria"].values() if c["value"] is not None)


def test_piotroski_equity_issuance_detected_from_share_count():
    ns = _ns({"Net Income": [10, 8]}, {"Total Assets": [100, 100], "Ordinary Shares Number": [105, 100]}, {})
    assert m.piotroski_f_score(ns, T, asset_base="end")["criteria"]["no_equity_issuance"]["value"] == 0


def test_piotroski_oldest_year_has_no_comparison():
    result = m.piotroski_f_score(_lowes(), P, asset_base="end")
    assert result["prior_year"] is None
    assert result["criteria"]["roa_improved"]["value"] is None
