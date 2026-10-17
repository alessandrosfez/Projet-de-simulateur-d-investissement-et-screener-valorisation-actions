"""
Tests de market_data.py avec yfinance remplacé par des doublures (aucun appel réseau) : lecture des
trois états annuels, échecs non mis en cache, taux de change.
Usage : pip install -r requirements-dev.txt && pytest -v
"""
from unittest.mock import MagicMock

import pandas as pd

import market_data as md


def _fake_ticker(financials=None, balance_sheet=None, cashflow=None, info=None):
    fake = MagicMock()
    fake.financials = financials if financials is not None else pd.DataFrame()
    fake.balance_sheet = balance_sheet if balance_sheet is not None else pd.DataFrame()
    fake.cashflow = cashflow if cashflow is not None else pd.DataFrame()
    fake.get_info.return_value = info or {}
    return fake


def test_get_annual_statements_returns_the_three_statements(monkeypatch):
    income = pd.DataFrame({pd.Timestamp("2024-12-31"): [1000.0]}, index=["Total Revenue"])
    monkeypatch.setattr(md.yf, "Ticker", lambda ticker: _fake_ticker(financials=income))
    statements = md.get_annual_statements("FAKE")
    assert set(statements) == {"income", "balance", "cashflow"}
    assert statements["income"].equals(income)
    assert statements["balance"].empty


def test_empty_statements_are_not_cached(monkeypatch):
    """Un échec ponctuel de yfinance (rien de renvoyé) ne doit pas rester 24 h en cache à la place
    des vraies données : le second appel doit retenter."""
    calls = []

    def fake_ticker(ticker):
        calls.append(ticker)
        return _fake_ticker()

    monkeypatch.setattr(md.yf, "Ticker", fake_ticker)
    assert all(frame.empty for frame in md.get_annual_statements("FAKE").values())
    md.get_annual_statements("FAKE")
    assert len(calls) == 2
    assert not md._cache


def test_get_company_profile_keeps_quote_and_reporting_currency_separate(monkeypatch):
    info = {"shortName": "Shell", "currency": "GBp", "financialCurrency": "USD", "currentPrice": 3938.0,
            "marketCap": 224e9, "sector": "Energy", "industry": "Oil & Gas Integrated", "quoteType": "EQUITY"}
    monkeypatch.setattr(md.yf, "Ticker", lambda ticker: _fake_ticker(info=info))
    profile = md.get_company_profile("SHEL.L")
    assert profile["quote_currency"] == "GBp"
    assert profile["reporting_currency"] == "USD"
    assert profile["price"] == 3938.0  # brut : la conversion est faite par engine.py


def test_unknown_ticker_profile_is_not_cached(monkeypatch):
    monkeypatch.setattr(md.yf, "Ticker", lambda ticker: _fake_ticker(info={}))
    assert md.get_company_profile("NOPE")["name"] == "NOPE"
    assert not md._cache


def test_fx_rate_same_currency_needs_no_network(monkeypatch):
    def fail(ticker):
        raise AssertionError("aucun appel réseau attendu")

    monkeypatch.setattr(md.yf, "Ticker", fail)
    assert md.get_fx_rate("EUR", "EUR") == 1.0
    assert md.get_fx_rate(None, "EUR") is None


def test_fx_rate_reads_last_close_of_yahoo_pair(monkeypatch):
    seen = []

    def fake_ticker(symbol):
        seen.append(symbol)
        fake = MagicMock()
        fake.history.return_value = pd.DataFrame({"Close": [1.30, 1.33]})
        return fake

    monkeypatch.setattr(md.yf, "Ticker", fake_ticker)
    assert md.get_fx_rate("GBP", "USD") == 1.33
    assert seen == ["GBPUSD=X"]


def test_fx_rate_unavailable_returns_none(monkeypatch):
    def fake_ticker(symbol):
        fake = MagicMock()
        fake.history.return_value = pd.DataFrame({"Close": []})
        return fake

    monkeypatch.setattr(md.yf, "Ticker", fake_ticker)
    assert md.get_fx_rate("XXX", "USD") is None
    assert not md._cache
