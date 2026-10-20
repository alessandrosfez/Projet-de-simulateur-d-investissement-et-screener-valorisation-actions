"""
Cas d'école Wirecard (examples/wirecard_2015_2018.csv, relevé à la main dans les rapports annuels) :
contrôle de la saisie par les identités comptables, puis constat documenté dans le README. Les scores
d'alerte de l'outil ne signalent pas Wirecard, la seule anomalie nette étant la croissance du CA.
Usage : pip install -r requirements-dev.txt && pytest -v
"""
from pathlib import Path

import pandas as pd
import pytest

import engine as m

FILE = Path(__file__).with_name("examples") / "wirecard_2015_2018.csv"
Y15, Y16, Y17, Y18 = (pd.Timestamp(f"{year}-12-31") for year in (2015, 2016, 2017, 2018))


@pytest.fixture(scope="module")
def wirecard():
    result = m.parse_statements_csv(FILE.read_text(encoding="utf-8"))
    assert result["errors"] == []
    return result["dataset"], m.normalize_imported(result["dataset"])


def test_example_imports_four_fiscal_years(wirecard):
    dataset, ns = wirecard
    assert ns.years == [Y18, Y17, Y16, Y15]
    assert dataset["meta"]["company"] == "Wirecard AG" and dataset["meta"]["unit"] == 1e3


def test_transcription_satisfies_the_accounting_identities(wirecard):
    """Contrôle de la saisie : actif = capitaux propres + passif à l'euro près, et l'écart entre
    CA - coût des matières et la marge brute publiée vaut exactement la production immobilisée publiée
    (45,0 / 45,3 / 30,2 / 28,3 M EUR), que Wirecard inclut dans sa marge brute."""
    _dataset, ns = wirecard
    g = ns.get
    own_work_capitalised = {Y18: 45.1e6, Y17: 45.305e6, Y16: 30.201e6, Y15: 28.293e6}
    for year in ns.years:
        assert g("total_assets", year) == pytest.approx(g("equity", year) + g("total_liabilities", year), abs=1)
        gap = g("gross_profit", year) - (g("revenue", year) - g("cost_of_revenue", year))
        # 2018 publié en millions à une décimale : 0,1 M EUR d'arrondi possible.
        assert gap == pytest.approx(own_work_capitalised[year], abs=0.11e6)


def test_beneish_indices_computed_by_hand(wirecard):
    _dataset, ns = wirecard
    sgi_2018 = m.beneish_m_score(ns, Y18, Y17)["indices"]["sgi"]["value"]
    assert sgi_2018 == pytest.approx(2016.2e6 / 1489.954e6)
    dsri_2016 = m.beneish_m_score(ns, Y16, Y15)["indices"]["dsri"]["value"]
    assert dsri_2016 == pytest.approx((190.185 / 1028.358) / (113.204 / 771.340))


def test_no_beneish_signal_despite_the_fraud(wirecard):
    """Constat du README : SG&A non publié (charges par nature), d'où un M-score officiel n.d. et la
    variante indicative (SGAI neutralisé à 1, comme Beneish 1999 p. 12). Elle reste sous -1,78 sur les
    trois couples : un chiffre d'affaires fictif adossé à une trésorerie fictive ne crée pas d'accruals.
    Seule la croissance du CA (SGI > 1,3) se détache."""
    _dataset, ns = wirecard
    for year, prior in m.consecutive_pairs(ns):
        result = m.beneish_m_score(ns, year, prior)
        assert result["m_score"]["value"] is None and result["m_score"]["missing"] == ("sgai",)
        assert result["m_score_indicative"]["value"] < m.BENEISH_THRESHOLD
        assert result["indices"]["sgi"]["value"] > 1.3
    assert m.beneish_m_score(ns, Y18, Y17)["m_score_indicative"]["value"] == pytest.approx(-2.329, abs=1e-3)


def test_other_scores_look_reassuring(wirecard):
    dataset, ns = wirecard
    caps = m.imported_market_caps(dataset)
    for year in (Y18, Y17):
        assert m.altman_z_score(ns, year, "z_double_prime")["zone"] == "safe"
        assert m.altman_z_score(ns, year, "original", caps[year])["zone"] == "safe"
        assert m.cash_conversion(ns)[year]["cfo_to_net_income"]["value"] > 1.3
    assert m.piotroski_f_score(ns, Y18)["score"] == 7
