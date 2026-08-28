"""
Récupération des données de marché via yfinance, avec cache disque (équivalent
minimal de st.cache_data(ttl=...)) pour éviter de retélécharger à chaque
redémarrage tant que les données ont moins d'1h.
"""
import functools
import pickle
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from constants import TICKERS

# ============================================================
# CACHE (mémoire + disque)
# ============================================================

CACHE_FILE = Path(__file__).with_name(".pea_forecast_cache.pkl")
_cache_lock = threading.Lock()


def _load_cache_from_disk() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}


_cache: dict = _load_cache_from_disk()


def _save_cache_to_disk():
    with _cache_lock:
        try:
            tmp_path = CACHE_FILE.with_suffix(".tmp")
            with open(tmp_path, "wb") as f:
                pickle.dump(_cache, f)
            tmp_path.replace(CACHE_FILE)
        except Exception:
            pass


def cached_ttl(ttl_seconds: int):
    """Cache mémoire + disque : évite de retélécharger via yfinance à chaque
    redémarrage du serveur tant que les données ont moins de ttl_seconds."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args):
            key = (func.__name__, args)
            now = time.time()
            if key in _cache:
                value, timestamp = _cache[key]
                if now - timestamp < ttl_seconds:
                    return value
            value = func(*args)
            _cache[key] = (value, now)
            _save_cache_to_disk()
            return value
        return wrapper
    return decorator


# ============================================================
# CALIBRATION (historique -> rendements mensuels / corrélations)
# ============================================================

@cached_ttl(3600)
def get_monthly_returns(ticker: str, lookback_years: int) -> pd.Series:
    """Rendements mensuels historiques d'un indice, sur les N dernières années."""
    start = (datetime.today() - timedelta(days=365 * lookback_years)).strftime("%Y-%m-%d")
    data = yf.download(ticker, start=start, progress=False, auto_adjust=True)
    if data.empty:
        raise ValueError(f"Pas de données pour {ticker}")
    monthly_prices = data["Close"].squeeze().resample("MS").first().dropna()
    return monthly_prices.pct_change().dropna()


def get_aligned_returns(names: list, lookback_years: int, source_key: str) -> pd.DataFrame:
    """Rendements mensuels alignés (dates communes) pour plusieurs indices."""
    series = {name: get_monthly_returns(TICKERS[name][source_key], lookback_years) for name in names}
    return pd.concat(series, axis=1).dropna()
