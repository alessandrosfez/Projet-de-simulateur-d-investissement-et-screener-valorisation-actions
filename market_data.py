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


@cached_ttl(3600)
def _get_ticker_info(ticker: str) -> dict:
    return yf.Ticker(ticker).get_info()


def _price_scale_factor(trailing_pe, trailing_eps, current_price) -> float:
    """Certaines places (Londres notamment) cotent le prix en pence alors que le BPA
    est en livres (ou vice versa) : on déduit un facteur d'échelle du P/E déjà
    correct fourni par Yahoo, pour garder les calculs historiques cohérents."""
    if trailing_pe and trailing_eps and current_price:
        implied_price = trailing_pe * trailing_eps
        if implied_price > 0:
            ratio = current_price / implied_price
            if ratio > 5:
                return round(ratio)
    return 1.0


@cached_ttl(3600)
def get_stock_pe_history(ticker: str) -> pd.Series:
    """Série de P/E implicite sur 5 ans (prix historique / BPA actuel), corrigée d'un
    éventuel décalage d'échelle prix/BPA. Approximatif : suppose le BPA à peu près
    stable sur la période, ce qui n'est pas vrai pour une valeur très cyclique ou en
    forte croissance des bénéfices, à prendre comme indication, pas comme vérité.
    Série vide si le BPA n'est pas disponible."""
    info = _get_ticker_info(ticker)
    trailing_pe = info.get("trailingPE")
    trailing_eps = info.get("trailingEps")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not trailing_eps or trailing_eps <= 0:
        return pd.Series(dtype=float)

    price_scale = _price_scale_factor(trailing_pe, trailing_eps, current_price)
    try:
        hist = yf.Ticker(ticker).history(period="5y", interval="1wk")["Close"].dropna()
    except Exception:
        return pd.Series(dtype=float)
    implied_pe = (hist / price_scale) / trailing_eps
    return implied_pe[implied_pe > 0]


@cached_ttl(3600)
def get_stock_valuation(ticker: str) -> dict:
    """Prix et ratios de valorisation courants d'une action (P/E, P/B, rendement du
    dividende), plus sa position par rapport à son propre P/E historique sur 5 ans
    (voir get_stock_pe_history)."""
    info = _get_ticker_info(ticker)
    trailing_pe = info.get("trailingPE")

    pe_history = get_stock_pe_history(ticker)
    pe_5y_mean, pe_5y_percentile = None, None
    if len(pe_history) > 20:
        pe_5y_mean = float(pe_history.mean())
        if trailing_pe:
            pe_5y_percentile = float((pe_history < trailing_pe).mean() * 100)

    return {
        "name": info.get("shortName") or info.get("longName") or ticker,
        "sector": info.get("sector") or "N/A",
        "currency": info.get("currency") or "N/A",
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "trailing_pe": trailing_pe,
        "forward_pe": info.get("forwardPE"),
        "price_to_book": info.get("priceToBook"),
        "dividend_yield": info.get("dividendYield"),
        "market_cap": info.get("marketCap"),
        "pe_5y_mean": pe_5y_mean,
        "pe_5y_percentile": pe_5y_percentile,
    }


def get_dcf_inputs(ticker: str) -> dict:
    """Intrants DCF les plus récents pour une action : FCF déjà calculé par Yahoo Finance
    (freeCashflow, TTM), dette totale, trésorerie, nombre d'actions, prix courant. Réutilise
    _get_ticker_info (déjà mis en cache par get_stock_valuation si l'action a déjà été chargée) :
    aucun appel réseau supplémentaire dans ce cas. `fcf`/`shares_outstanding` valent None si
    Yahoo Finance ne les fournit pas pour ce titre (fréquent pour certaines actions non
    américaines), à l'appelant de gérer ce cas comme "DCF indisponible"."""
    info = _get_ticker_info(ticker)
    return {
        "fcf": info.get("freeCashflow"),
        "total_debt": info.get("totalDebt") or 0,
        "total_cash": info.get("totalCash") or 0,
        "shares_outstanding": info.get("sharesOutstanding"),
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "currency": info.get("currency") or "N/A",
    }
