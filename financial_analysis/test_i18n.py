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
        keys |= {layout.altman_ratio_label_key(model, x) for x in engine.ALTMAN_MODELS[model]["coefficients"]}
    keys.add("plotly_separators")
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
    # Import d'états financiers
    keys |= {f"import_error_{code}" for code in engine.IMPORT_ERRORS}
    keys |= {"prov_imported", "prov_missing_not_in_import"}
    keys |= set(layout.IMPORT_UNIT_NAMES.values())
    keys |= {f"import_template_comment_{i}" for i in range(1, 6)}
    return keys


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_every_dynamic_key_is_translated(lang):
    missing = sorted(_expected_keys() - set(TRANSLATIONS[lang]))
    assert missing == []


def test_both_languages_have_the_same_keys():
    assert set(TRANSLATIONS["fr"]) == set(TRANSLATIONS["en"])


@pytest.mark.parametrize("value,spec,fr,en", [
    (2.866, ".2f", "2,87", "2.87"), (-2.7749, "+.3f", "-2,775", "-2.775"), (1234567.891, ",.2f", "1 234 567,89",
                                                                             "1 234 567.89"),
    (25.0, "g", "25", "25"), (12.5, "g", "12,5", "12.5"),
])
def test_format_number_uses_the_language_decimal_separator(value, spec, fr, en):
    assert layout.format_number(value, spec, "fr") == fr
    assert layout.format_number(value, spec, "en") == en


def test_amounts_and_ratios_follow_the_language():
    assert layout.format_amount(2.87e9, "fr") == f"2,87 {TRANSLATIONS['fr']['unit_billion']}"
    assert layout.format_amount(2.87e9, "en") == f"2.87 {TRANSLATIONS['en']['unit_billion']}"
    assert layout.format_ratio(0.123, "percent", "fr") == "12,3 %"
    assert layout.format_ratio(1.5234, "multiple", "fr") == "1,52x"


def test_score_tables_contain_no_decimal_point_in_french():
    """Garde-fou : tous les nombres des tableaux de scores (cellules et infobulles) passent par
    format_number, aucun « 2.87 » à l'anglaise ne reste dans un texte français."""
    import re

    import pandas as pd

    years = [pd.Timestamp("2024-12-31"), pd.Timestamp("2023-12-31")]

    def frame(rows):
        return pd.DataFrame.from_dict(rows, orient="index", columns=years, dtype=float)

    ns = engine.normalize_statements(
        frame({"Total Revenue": [1234.5e6, 1100.25e6], "Cost Of Revenue": [700.3e6, 640.1e6],
               "Selling General And Administration": [150.7e6, 140.2e6], "Net Income": [90.3e6, 75.1e6],
               "EBIT": [130.2e6, 110.9e6], "Depreciation Income Statement": [40.1e6, 36.7e6]}),
        frame({"Total Assets": [2000.5e6, 1800.3e6], "Current Assets": [700.1e6, 650.2e6],
               "Current Liabilities": [500.4e6, 480.6e6], "Accounts Receivable": [200.7e6, 170.1e6],
               "Net PPE": [800.2e6, 750.9e6], "Long Term Debt And Capital Lease Obligation": [400.3e6, 420.5e6],
               "Working Capital": [199.7e6, 169.6e6], "Retained Earnings": [400.1e6, 350.2e6],
               "Total Liabilities Net Minority Interest": [1100.4e6, 990.8e6],
               "Total Equity Gross Minority Interest": [900.1e6, 809.5e6]}),
        frame({"Operating Cash Flow": [130.6e6, 110.2e6]}),
    )
    beneish = [engine.beneish_m_score(ns, years[0], years[1])]
    altman = [engine.altman_z_score(ns, year, "z_double_prime") for year in years]
    texts = []
    for table in (layout.beneish_table(beneish, "fr", False), layout.altman_table(altman, "fr", False)):
        texts += [str(v) for row in table.data for k, v in row.items() if not k.startswith("_")]
        texts += [cell["value"] for row in table.tooltip_data for cell in row.values()]
    offenders = [text for text in texts if re.search(r"\d\.\d", text)]
    assert offenders == []
