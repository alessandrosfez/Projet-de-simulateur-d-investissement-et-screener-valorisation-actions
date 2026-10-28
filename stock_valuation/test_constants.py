"""
Paniers d'actions (constants.py) : le SBF 120 contient bien 120 titres distincts, dont tout le CAC 40,
et chaque panier déclaré a son libellé dans les deux langues.
"""
import constants
from i18n import L


def test_sbf120_has_120_distinct_tickers_including_the_cac40():
    tickers = list(constants.SBF120_TICKERS.values())
    assert len(tickers) == 120 and len(set(tickers)) == 120
    assert set(constants.CAC40_TICKERS.values()) <= set(tickers)
    assert not set(constants.SBF120_OTHER_TICKERS.values()) & set(constants.CAC40_TICKERS.values())


def test_every_universe_has_tickers_and_a_label():
    for code in constants.UNIVERSE_CODES:
        assert constants.UNIVERSE_TICKERS[code]
        for lang in ("fr", "en"):
            assert L(lang, f"universe_{code}") != f"universe_{code}"
