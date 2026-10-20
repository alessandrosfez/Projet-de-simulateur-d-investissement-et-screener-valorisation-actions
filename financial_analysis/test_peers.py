"""
Tests de la comparaison sectorielle (engine.py) : choix des pairs et repli signalé, statistiques
sur les seuls pairs disponibles (jamais de 0 à la place d'une donnée manquante), rang centile, et
indicateurs extraits d'une société.
Usage : pip install -r requirements-dev.txt && pytest -v
"""
from pathlib import Path

import pytest

import engine as m

GENERAL, BANK = {"regime": "general"}, {"regime": "bank"}


def _universe(**sectors):
    return {ticker: {"sector": sector, "regime": "general"} for ticker, sector in sectors.items()}


def test_select_peers_same_sector_excluding_target_and_financials():
    universe = _universe(A="Tech", B="Tech", C="Tech", D="Tech", E="Tech", F="Energy")
    universe["G"] = {"sector": "Tech", "regime": "bank"}
    peers, scope = m.select_peers("A", "Tech", universe)
    assert peers == ["B", "C", "D", "E"] and scope == "sector"


def test_select_peers_falls_back_on_all_non_financials_below_the_threshold():
    universe = _universe(A="Tech", B="Tech", C="Energy", D="Utilities")
    universe["E"] = {"sector": "Tech", "regime": "insurer"}
    peers, scope = m.select_peers("A", "Tech", universe)
    assert scope == "all_non_financial"
    assert peers == ["B", "C", "D"]


def test_select_peers_unknown_sector_uses_the_fallback():
    peers, scope = m.select_peers(None, None, _universe(A="Tech", B="Energy"))
    assert scope == "all_non_financial" and peers == ["A", "B"]


def test_peer_distribution_ignores_missing_values_instead_of_zero():
    stats = m.peer_distribution([10.0, None, 30.0, 20.0, None, 40.0])
    assert stats["n"] == 4
    assert stats["median"] == pytest.approx(25.0)
    assert stats["q1"] == pytest.approx(17.5) and stats["q3"] == pytest.approx(32.5)
    assert m.peer_distribution([None, None]) == {"n": 0, "q1": None, "median": None, "q3": None}


def test_percentile_rank_counts_half_of_the_ties():
    peers = [10.0, 20.0, 20.0, 40.0, None]
    assert m.percentile_rank(30.0, peers) == pytest.approx(75.0)
    assert m.percentile_rank(20.0, peers) == pytest.approx(50.0)  # 1 en dessous + 2 ex aequo / 2
    assert m.percentile_rank(5.0, peers) == 0.0
    assert m.percentile_rank(None, peers) is None
    assert m.percentile_rank(1.0, [None]) is None


def test_peer_metrics_on_the_wirecard_example():
    text = (Path(__file__).with_name("examples") / "wirecard_2015_2018.csv").read_text(encoding="utf-8")
    ns = m.normalize_imported(m.parse_statements_csv(text)["dataset"])
    result = m.peer_metrics(ns, GENERAL)
    values = result["values"]
    assert result["year"] == ns.years[0]
    assert values["cfo_to_net_income"] == pytest.approx(466.9 / 347.4)
    assert values["dso"] == pytest.approx(357.4 / 2016.2 * 365)
    # Frais généraux non publiés : M-score indicatif, signalé.
    assert result["indicative"] is True and values["beneish_m_score"] == pytest.approx(-2.329, abs=1e-3)
    assert values["piotroski_f_score"] == 7.0
    assert values["altman_z_double_prime"] is not None


def test_peer_metrics_are_none_for_a_bank():
    text = (Path(__file__).with_name("examples") / "wirecard_2015_2018.csv").read_text(encoding="utf-8")
    ns = m.normalize_imported(m.parse_statements_csv(text)["dataset"])
    assert all(v is None for v in m.peer_metrics(ns, BANK)["values"].values())
