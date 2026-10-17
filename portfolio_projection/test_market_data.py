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


# ---------- fraîcheur des données ----------

def _flaky_fetcher(ttl=100):
    """Fonction cachée dont on contrôle le succès ou l'échec, pour simuler une coupure réseau."""
    state = {"fail": False, "calls": 0}

    @md.cached_ttl(ttl)
    def fetch(x):
        state["calls"] += 1
        if state["fail"]:
            raise ConnectionError("hors ligne")
        return x * 10

    return fetch, state


def test_cached_ttl_serves_stale_value_with_original_timestamp_when_refresh_fails(monkeypatch):
    fetch, state = _flaky_fetcher(ttl=100)
    clock = [1000.0]
    monkeypatch.setattr(md.time, "time", lambda: clock[0])
    assert fetch(3) == 30

    clock[0] = 1000.0 + 10 * 86400  # 10 jours plus tard, bien après le TTL
    state["fail"] = True
    assert fetch(3) == 30  # dernière version connue plutôt qu'une erreur
    assert state["calls"] == 2  # le rafraîchissement a bien été tenté
    assert md.get_served_download_times() == [1000.0]  # horodatage d'origine conservé
    freshness = md.data_freshness(md.get_served_download_times(), clock[0])
    assert freshness["is_stale"] is True
    assert freshness["age_days"] == pytest.approx(10.0)


def test_cached_ttl_raises_when_refresh_fails_without_known_value():
    fetch, state = _flaky_fetcher()
    state["fail"] = True
    with pytest.raises(ConnectionError):
        fetch(3)
    assert md.get_served_download_times() == []


def test_served_download_times_ignore_cached_series_no_longer_used(monkeypatch):
    """Une série en cache que plus aucun écran ne demande (ancien ticker...) ne doit pas faire
    vieillir la date affichée : seules les séries servies comptent."""
    monkeypatch.setattr(md.time, "time", lambda: 5000.0)
    md._cache[("old_series", ("GONE",))] = ("valeur", 1.0)
    fetch, _state = _flaky_fetcher()
    fetch(1)
    assert md.get_served_download_times() == [5000.0]
    assert set(md.get_cache_download_times()) == {("old_series", ("GONE",)), ("fetch", (1,))}


def test_get_cache_download_times_returns_datetimes():
    md._cache[("some_series", ("X",))] = ("valeur", 1_700_000_000.0)
    times = md.get_cache_download_times()
    assert times[("some_series", ("X",))] == md.datetime.fromtimestamp(1_700_000_000.0)


def test_data_freshness_empty_is_none():
    assert md.data_freshness([], now=1000.0) is None


def test_data_freshness_uses_oldest_series_and_threshold():
    day = 86400
    now = 100 * day
    fresh = md.data_freshness([now - 1 * day, now - 7 * day], now)
    assert fresh["age_days"] == pytest.approx(7.0)
    assert fresh["is_stale"] is False  # pile au seuil : pas encore périmé
    assert fresh["n_series"] == 2
    stale = md.data_freshness([now - 1 * day, now - 8 * day], now)
    assert stale["is_stale"] is True
    assert stale["oldest"] == md.datetime.fromtimestamp(now - 8 * day)


class _FakeTicker:
    """Remplace yf.Ticker : historique quotidien contrôlé par le test, aucun appel réseau."""
    history_by_ticker = {}

    def __init__(self, ticker):
        self.ticker = ticker

    def get_info(self):
        return {"currentPrice": 10.0}

    def history(self, start=None, interval=None, auto_adjust=None):
        return pd.DataFrame({"Close": self.history_by_ticker.get(self.ticker, pd.Series(dtype=float))})


def test_daily_price_history_empty_when_unavailable_without_caching_the_empty_result(monkeypatch):
    monkeypatch.setattr(md.yf, "Ticker", _FakeTicker)
    _FakeTicker.history_by_ticker = {}
    assert md.get_daily_price_history("NOPE", "2024-01-01").empty
    # Une série vide ne doit pas être mise en cache à la place de vraies données.
    assert not any(key[0] == "_fetch_daily_close" for key in md._cache)


def test_daily_price_history_keeps_last_known_data_when_yfinance_returns_nothing(monkeypatch):
    monkeypatch.setattr(md.yf, "Ticker", _FakeTicker)
    clock = [1000.0]
    monkeypatch.setattr(md.time, "time", lambda: clock[0])
    prices = pd.Series([10.0, 11.0], index=pd.to_datetime(["2024-01-02", "2024-01-03"]))
    _FakeTicker.history_by_ticker = {"AAA": prices}
    first = md.get_daily_price_history("AAA", "2024-01-01")
    assert list(first) == [10.0, 11.0]

    clock[0] += 2 * 3600  # TTL dépassé
    _FakeTicker.history_by_ticker = {}  # yfinance ne renvoie plus rien (coupure réseau)
    again = md.get_daily_price_history("AAA", "2024-01-01")
    assert list(again) == [10.0, 11.0]
