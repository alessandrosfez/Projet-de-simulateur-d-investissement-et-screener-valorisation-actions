"""
Tests de mise en forme des cartes de performance réelle (results.py) : avec moins d'un an
d'historique, le gain de la période est la valeur principale et les taux annualisés ne sont qu'une
mention ; au-delà, retour au XIRR et au TWR annualisés. Deux groupes nommés séparent ton
portefeuille de la référence.
Usage : pip install -r requirements-dev.txt && pytest -v
"""
from results import build_performance_cards


def _texts(component, out=None):
    out = [] if out is None else out
    if isinstance(component, str):
        out.append(component)
    elif isinstance(component, (list, tuple)):
        for child in component:
            _texts(child, out)
    elif hasattr(component, "children"):
        _texts(component.children, out)
    return out


PERF = {
    "xirr": 0.05, "twr": {"twr": 0.004, "twr_annualized": 0.02, "n_years": 0.2}, "real_value": 1000.0,
    "gain": 0.02, "benchmark_label": "CW8.PA (MSCI World)", "benchmark_value": 1010.0,
    "benchmark_xirr": 0.06, "benchmark_gain": 0.03,
}


def test_short_history_shows_period_gain_first_and_annualized_rates_as_a_note():
    texts = "".join(_texts(build_performance_cards({**PERF, "short_history": True}, "fr")))
    assert "Ton portefeuille" in texts and "Référence : CW8.PA (MSCI World)" in texts
    assert "+2,0 % sur la période" in texts and "+3,0 % sur la période" in texts
    assert "XIRR annualisé : +5,00 %/an, peu fiable sous 1 an" in texts
    assert "toi − référence : -1,0 pt" in texts
    assert "XIRR de ton portefeuille" not in texts


def test_long_history_keeps_annualized_xirr_and_names_it_as_yours():
    texts = "".join(_texts(build_performance_cards({**PERF, "short_history": False}, "fr")))
    assert "XIRR de ton portefeuille" in texts and "+5,00 %/an" in texts
    assert "XIRR de la référence" in texts and "+6,00 %/an" in texts
    assert "sur la période" not in texts


def test_without_benchmark_only_your_group_is_shown():
    perf = {key: value for key, value in PERF.items() if not key.startswith("benchmark")}
    texts = "".join(_texts(build_performance_cards({**perf, "short_history": True}, "en")))
    assert "Your portfolio" in texts and "Benchmark:" not in texts
