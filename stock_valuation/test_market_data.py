"""
Tests de market_data.py avec yfinance mocké (aucun appel réseau) : la correction pence/livre
(_price_scale_factor, un bug réellement livré en production sur le FTSE 100 avant sa correction,
voir le README), la conversion de change des doubles cotations et la cohérence d'unités de la
valeur d'entreprise, puis le repli FCF annuel -> TTM. Complète test_engine.py, qui ne couvre que le
moteur de calcul pur.
Usage : pip install -r requirements-dev.txt && pytest test_market_data.py -v
"""
from unittest.mock import MagicMock

import pandas as pd
import pytest

import engine
import market_data as md


# ---------- _price_scale_factor (pure, sans mock) ----------

def test_price_scale_factor_detects_lse_pence_mismatch():
    """Cas réel ayant affecté le FTSE 100 en production : prix coté en pence, BPA en livres."""
    scale = md._price_scale_factor(trailing_pe=15.0, trailing_eps=2.0, current_price=3000.0)
    assert scale == 100.0


def test_price_scale_factor_no_scaling_needed():
    scale = md._price_scale_factor(trailing_pe=15.0, trailing_eps=2.0, current_price=30.0)
    assert scale == 1.0


def test_price_scale_factor_missing_inputs_fall_back_to_one():
    assert md._price_scale_factor(None, 2.0, 30.0) == 1.0
    assert md._price_scale_factor(15.0, None, 30.0) == 1.0
    assert md._price_scale_factor(15.0, 2.0, None) == 1.0
    assert md._price_scale_factor(15.0, 0, 30.0) == 1.0


def test_price_scale_factor_small_ratio_not_treated_as_mismatch():
    """Un écart de moins de 5x est traité comme du bruit de calcul normal (BPA légèrement daté par
    rapport au prix), pas comme un décalage d'unité pence/livre à corriger."""
    scale = md._price_scale_factor(trailing_pe=15.0, trailing_eps=2.0, current_price=60.0)  # ratio = 2
    assert scale == 1.0


# ---------- _get_annual_fcf_history / get_dcf_inputs (yfinance mocké) ----------

def test_get_annual_fcf_history_parses_most_recent_first(monkeypatch):
    idx = ["Free Cash Flow", "Operating Cash Flow", "Capital Expenditure"]
    cols = pd.to_datetime(["2023-12-31", "2022-12-31", "2021-12-31"])
    cf = pd.DataFrame(
        [[100.0, 90.0, 80.0], [150.0, 140.0, 130.0], [-50.0, -60.0, -70.0]],
        index=idx, columns=cols,
    )
    fake_ticker = MagicMock()
    fake_ticker.cashflow = cf
    monkeypatch.setattr(md.yf, "Ticker", lambda ticker: fake_ticker)

    result = md._get_annual_fcf_history("FAKE")

    assert list(result["Free Cash Flow"]) == [100.0, 90.0, 80.0]
    assert result.index.tolist() == list(cols)


def test_get_dcf_inputs_falls_back_to_ttm_when_no_annual_history(monkeypatch):
    fake_ticker = MagicMock()
    fake_ticker.get_info.return_value = {
        "currentPrice": 100.0, "trailingPE": 20.0, "trailingEps": 5.0,
        "totalDebt": 500.0, "totalCash": 100.0, "sharesOutstanding": 1000.0,
        "currency": "USD", "freeCashflow": 200.0,
    }
    fake_ticker.cashflow = pd.DataFrame()  # pas d'historique annuel pour ce titre
    monkeypatch.setattr(md.yf, "Ticker", lambda ticker: fake_ticker)

    result = md.get_dcf_inputs("FAKE")

    assert result["fcf_history"] == []
    assert result["fcf"] == pytest.approx(200.0)  # price_scale = 1.0 (ratio prix/implicite = 1 ici)


def test_get_dcf_inputs_applies_price_scale_to_fcf_debt_and_cash(monkeypatch):
    """Régression directe du bug pence/livre sur les intrants DCF (pas seulement sur
    _price_scale_factor isolément) : FCF, dette et trésorerie doivent tous être mis à l'échelle."""
    fake_ticker = MagicMock()
    fake_ticker.get_info.return_value = {
        "currentPrice": 3000.0, "trailingPE": 15.0, "trailingEps": 2.0,  # ratio = 100 (pence/livre)
        "totalDebt": 500.0, "totalCash": 100.0, "sharesOutstanding": 1000.0,
        "currency": "GBp", "freeCashflow": 200.0,
    }
    fake_ticker.cashflow = pd.DataFrame()
    monkeypatch.setattr(md.yf, "Ticker", lambda ticker: fake_ticker)

    result = md.get_dcf_inputs("FAKE")

    assert result["fcf"] == pytest.approx(200.0 * 100)
    assert result["total_debt"] == pytest.approx(500.0 * 100)
    assert result["total_cash"] == pytest.approx(100.0 * 100)


def _ticker_factory(info: dict, fx_rates: dict):
    """yf.Ticker remplacé : le ticker de la société renvoie `info`, une paire de devises "XXXYYY=X"
    renvoie le taux de fx_rates."""
    def factory(symbol):
        fake = MagicMock()
        if symbol.endswith("=X"):
            fake.history.return_value = pd.DataFrame({"Close": [fx_rates[symbol]]})
        else:
            fake.get_info.return_value = info
            fake.cashflow = pd.DataFrame()
        return fake
    return factory


def test_get_dcf_inputs_converts_dual_listing_accounts_currency(monkeypatch):
    """Régression du bug de change sur les doubles cotations : Shell cote en pence (GBp) mais publie
    ses comptes en USD. Les montants des états financiers doivent être convertis en livres (1 USD =
    0,75 GBP ici) puis en pence ; l'ancien facteur empirique ne faisait que x 100."""
    info = {
        "currentPrice": 3938.0, "trailingPE": 11.65, "trailingEps": 3.38, "currency": "GBp",
        "financialCurrency": "USD", "totalDebt": 500.0, "totalCash": 100.0, "freeCashflow": 200.0,
        "marketCap": 1000.0, "sharesOutstanding": 10.0,
    }
    monkeypatch.setattr(md.yf, "Ticker", _ticker_factory(info, {"USDGBP=X": 0.75}))

    result = md.get_dcf_inputs("SHEL.L")

    assert result["fcf"] == pytest.approx(200.0 * 0.75 * 100)
    assert result["total_debt"] == pytest.approx(500.0 * 0.75 * 100)
    assert result["total_cash"] == pytest.approx(100.0 * 0.75 * 100)
    # Capitalisation en livres -> pence (x 100, pas de change), dette nette déjà en pence.
    assert result["enterprise_value"] == pytest.approx(1000.0 * 100 + (500.0 - 100.0) * 75)


def test_enterprise_value_units_make_ev_ebitda_comparables_return_the_price(monkeypatch):
    """Invariant de compute_comparables_ev_ebitda_fair_value : au même multiple que soi-même, la
    valeur implicite redonne exactement le cours. Faux tant que la valeur d'entreprise mélangeait une
    capitalisation en livres avec une dette en pence : le résultat sortait 100 fois trop bas pour
    toute valeur de Londres (ici une société type Tesco, comptes en livres)."""
    shares = 6.5e9
    price = 535.0  # pence
    info = {
        "currentPrice": price, "trailingPE": 17.8, "trailingEps": 0.30, "currency": "GBp",
        "financialCurrency": "GBP", "totalDebt": 15e9, "totalCash": 3e9, "freeCashflow": 2e9,
        "marketCap": price / 100 * shares, "sharesOutstanding": shares, "enterpriseToEbitda": 9.0,
    }
    monkeypatch.setattr(md.yf, "Ticker", _ticker_factory(info, {}))

    inputs = md.get_dcf_inputs("TSCO.L")
    fair_value = engine.compute_comparables_ev_ebitda_fair_value(
        inputs["enterprise_value"], inputs["ev_to_ebitda"], inputs["ev_to_ebitda"],
        inputs["total_debt"], inputs["total_cash"], inputs["shares_outstanding"],
    )
    assert fair_value == pytest.approx(price)


def test_unknown_accounts_currency_falls_back_on_empirical_factor(monkeypatch):
    info = {"currentPrice": 3000.0, "trailingPE": 15.0, "trailingEps": 2.0, "currency": "GBp",
            "financialCurrency": "USD", "freeCashflow": 200.0, "sharesOutstanding": 1000.0}
    # Pas de cours pour USDGBP=X : repli sur le facteur empirique (x 100), comme avant.
    monkeypatch.setattr(md.yf, "Ticker", _ticker_factory(info, {"USDGBP=X": float("nan")}))
    assert md.get_dcf_inputs("FAKE")["fcf"] == pytest.approx(200.0 * 100)
