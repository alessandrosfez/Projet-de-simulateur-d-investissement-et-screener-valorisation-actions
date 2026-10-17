"""
Vérifie que chaque clé de traduction construite dynamiquement (f"field_{clé}", f"ratio_{indicateur}"...)
existe en FR ET en EN : L() retombe silencieusement sur la clé brute quand elle manque, ce qui
afficherait « analysis_earnings_quality » à l'utilisateur au lieu d'un texte (cas réellement
rencontré pendant le développement).
Usage : pip install -r requirements-dev.txt && pytest -v
"""
import pytest

import engine
import layout
from i18n import TRANSLATIONS


def _expected_keys() -> set[str]:
    keys = set()
    for spec in engine.FIELD_SCHEMA:
        keys |= {f"field_{spec.key}", f"field_{spec.key}_help"}
    keys |= {f"analysis_{analysis}" for analysis in engine.ANALYSES}
    keys |= {f"regime_{regime}" for regime in ("bank", "insurer", "general")}
    keys |= {f"statement_{statement}" for statement in engine.STATEMENTS}
    for metric in layout.RATIO_KINDS:
        keys |= {f"ratio_{metric}", f"ratio_{metric}_help", f"formula_{metric}"}
    keys |= {f"flag_{flag}" for flag in engine.RATIO_FLAGS}
    keys |= {f"reason_{reason}" for reason in engine.RATIO_REASONS}
    keys |= {f"denominator_{denominator}" for denominator in engine.RATIO_DENOMINATORS}
    keys |= {f"bridge_step_{step}" for step in engine.BRIDGE_STEPS}
    keys |= {f"prov_{source}" for source in ("published", "equivalent", "derived")}
    keys |= {"prov_missing_not_in_yfinance", "prov_missing_derivation"}
    # Scores d'alerte
    for index in engine.BENEISH_INDICES:
        keys |= {f"beneish_{index}", f"beneish_{index}_help", f"formula_beneish_{index}"}
    keys |= {f"beneish_verdict_{verdict}" for verdict in ("manipulation_risk", "no_signal")}
    keys |= {f"flag_{flag}" for flag in engine.SCORE_FLAGS}
    keys |= {"reason_non_positive_base"}
    for model in engine.ALTMAN_MODELS:
        keys.add(f"altman_model_{model}")
        keys |= {f"altman_{x}" for x in engine.ALTMAN_MODELS[model]["coefficients"]}
        keys |= {f"altman_{x}_help" for x in engine.ALTMAN_MODELS[model]["coefficients"]}
    keys |= {f"zone_{zone}" for zone in ("safe", "grey", "distress")}
    for criterion in engine.PIOTROSKI_CRITERIA:
        keys |= {f"piotroski_{criterion}", f"piotroski_{criterion}_help"}
    keys |= {f"piotroski_detail_{detail}" for detail in layout.PIOTROSKI_DETAIL_KINDS}
    # Vision Transaction Services
    keys |= {f"bridge_line_{key}" for key in engine.NET_DEBT_LINE_KEYS}
    keys |= {f"source_{source}" for source in engine.NET_DEBT_SOURCES}
    keys |= {f"flag_{flag}" for flag in engine.TRANSACTION_FLAGS}
    for row in layout.EFFECT_ROWS:
        keys |= {f"effects_{row}", f"effects_{row}_help"}
    return keys


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_every_dynamic_key_is_translated(lang):
    missing = sorted(_expected_keys() - set(TRANSLATIONS[lang]))
    assert missing == []


def test_both_languages_have_the_same_keys():
    assert set(TRANSLATIONS["fr"]) == set(TRANSLATIONS["en"])
