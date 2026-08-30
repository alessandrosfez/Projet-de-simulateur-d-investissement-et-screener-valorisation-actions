"""
Tests de market_data.py avec yfinance mocké (aucun appel réseau) : resampling mensuel et
comportement du cache mémoire/disque (roundtrip TTL). Complète test_engine.py, qui ne couvre que
le moteur de calcul pur.
Usage : pip install -r requirements-dev.txt && pytest test_market_data.py -v
"""
import numpy as np
import pandas as pd
import pytest

import market_data as md


# ---------- get_monthly_returns (resampling) ----------

def test_get_monthly_returns_resamples_to_month_start(monkeypatch):
    dates = pd.date_range("2020-01-01", periods=90, freq="D")
    prices = 100 + np.arange(90) * 0.1
    fake_data = pd.DataFrame({"Close": prices}, index=dates)

    def fake_download(ticker, start=None, progress=None, auto_adjust=None):
        return fake_data

    monkeypatch.setattr(md.yf, "download", fake_download)
    result = md.get_monthly_returns("FAKE", 5)

    assert isinstance(result, pd.Series)
    # 90 jours (janvier -> mars 2020) -> 3 prix de début de mois -> 2 rendements mensuels.
    assert len(result) == 2
    expected_first_price = fake_data["Close"].resample("MS").first().iloc[0]
    expected_second_price = fake_data["Close"].resample("MS").first().iloc[1]
    assert result.iloc[0] == pytest.approx(expected_second_price / expected_first_price - 1)


def test_get_monthly_returns_raises_on_empty_data(monkeypatch):
    def fake_download(ticker, start=None, progress=None, auto_adjust=None):
        return pd.DataFrame()

    monkeypatch.setattr(md.yf, "download", fake_download)
    with pytest.raises(ValueError):
        md.get_monthly_returns("FAKE", 5)


# ---------- cache (TTL, roundtrip mémoire/disque) ----------

def test_cached_ttl_reuses_value_within_ttl_window(monkeypatch):
    calls = []

    @md.cached_ttl(100)
    def fake_fetch(x):
        calls.append(x)
        return x * 2

    current_time = [1000.0]
    monkeypatch.setattr(md.time, "time", lambda: current_time[0])

    assert fake_fetch(5) == 10
    assert fake_fetch(5) == 10  # dans la fenêtre TTL : pas de second appel réel
    assert calls == [5]


def test_cached_ttl_refetches_after_ttl_expiry(monkeypatch):
    calls = []

    @md.cached_ttl(100)
    def fake_fetch(x):
        calls.append(x)
        return x * 2

    current_time = [1000.0]
    monkeypatch.setattr(md.time, "time", lambda: current_time[0])

    assert fake_fetch(5) == 10
    current_time[0] += 200  # dépasse le TTL de 100s
    assert fake_fetch(5) == 10
    assert calls == [5, 5]


def test_cached_ttl_does_not_write_to_real_disk_cache(monkeypatch, tmp_path):
    """Vérifie que la fixture conftest.isolate_market_data_cache empêche bien toute écriture sur
    le vrai fichier de cache pendant les tests (elle neutralise _save_cache_to_disk)."""
    monkeypatch.setattr(md, "CACHE_FILE", tmp_path / "should_not_be_created.pkl")

    @md.cached_ttl(100)
    def fake_fetch(x):
        return x

    fake_fetch(1)
    assert not (tmp_path / "should_not_be_created.pkl").exists()
