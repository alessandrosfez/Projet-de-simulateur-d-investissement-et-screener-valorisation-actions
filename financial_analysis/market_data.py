"""
Récupération des données yfinance (états financiers annuels, profil de la société, taux de
change), avec cache disque. Ce module ne fait que récupérer et mettre en cache : toute
transformation (normalisation, conversion de devise, ratios) vit dans engine.py.

Cache recopié de stock_valuation (même mécanisme, aucun import croisé, voir le README racine).
"""
import functools
import pickle
import threading
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

# ============================================================
# CACHE (mémoire + disque)
# ============================================================

# Même nom de fichier que les deux autres outils : déjà ignoré par le .gitignore racine.
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


# Les états financiers annuels ne changent qu'une fois par an : un TTL long (24 h) évite de les
# retélécharger à chaque session, contrairement aux cours (1 h).
STATEMENTS_TTL = 86400
MARKET_TTL = 3600


# Les couches cachées ci-dessous lèvent une exception quand yfinance ne renvoie rien, au lieu de
# renvoyer un résultat vide : un échec réseau ponctuel serait sinon mis en cache (24 h pour les
# états financiers) à la place des vraies données. Les fonctions publiques rattrapent l'exception
# et renvoient un résultat vide, sans le mettre en cache.

@cached_ttl(MARKET_TTL)
def _fetch_ticker_info(ticker: str) -> dict:
    info = yf.Ticker(ticker).get_info()
    if not info or not (info.get("shortName") or info.get("longName") or info.get("quoteType")):
        raise ValueError(f"Aucune information Yahoo Finance pour {ticker}")
    return info


def _get_ticker_info(ticker: str) -> dict:
    try:
        return _fetch_ticker_info(ticker)
    except Exception:
        return {}


def get_company_profile(ticker: str) -> dict:
    """Identité et données de marché de la société, telles que fournies par Yahoo Finance, sans
    conversion : devise de cotation (currency, éventuellement en sous-unité comme GBp) et devise
    des comptes (financialCurrency) sont renvoyées séparément, la conversion se fait dans
    engine.market_values_in_reporting_currency."""
    info = _get_ticker_info(ticker)
    return {
        "name": info.get("shortName") or info.get("longName") or ticker,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "quote_currency": info.get("currency"),
        "reporting_currency": info.get("financialCurrency"),
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "trailing_pe": info.get("trailingPE"),
        "trailing_eps": info.get("trailingEps"),
    }


STATEMENT_ATTRIBUTES = (("income", "financials"), ("balance", "balance_sheet"), ("cashflow", "cashflow"))


@cached_ttl(STATEMENTS_TTL)
def _fetch_annual_statements(ticker: str) -> dict[str, pd.DataFrame]:
    t = yf.Ticker(ticker)
    statements = {}
    for key, attribute in STATEMENT_ATTRIBUTES:
        try:
            frame = getattr(t, attribute)
        except Exception:
            frame = None
        statements[key] = frame if isinstance(frame, pd.DataFrame) else pd.DataFrame()
    if all(frame.empty for frame in statements.values()):
        raise ValueError(f"Aucun état financier annuel pour {ticker}")
    return statements


def get_annual_statements(ticker: str) -> dict[str, pd.DataFrame]:
    """Comptes de résultat, bilans et tableaux de flux ANNUELS bruts de yfinance (index = libellés,
    colonnes = dates de clôture, valeurs dans la devise des comptes). yfinance n'en fournit
    qu'environ 4 exercices. Un état indisponible est un DataFrame vide, jamais une erreur : la
    normalisation (engine.normalize_statements) signale alors chaque poste manquant."""
    try:
        return _fetch_annual_statements(ticker)
    except Exception:
        return {key: pd.DataFrame() for key, _attribute in STATEMENT_ATTRIBUTES}


@cached_ttl(MARKET_TTL)
def _fetch_fx_rate(from_currency: str, to_currency: str) -> float:
    """Dernier cours de clôture de la paire Yahoo "XXXYYY=X" (1 XXX en YYY)."""
    closes = yf.Ticker(f"{from_currency}{to_currency}=X").history(period="5d")["Close"].dropna()
    if closes.empty or float(closes.iloc[-1]) <= 0:
        raise ValueError(f"Pas de cours pour {from_currency}{to_currency}=X")
    return float(closes.iloc[-1])


def get_fx_rate(from_currency: str | None, to_currency: str | None) -> float | None:
    """Taux de change from -> to. 1.0 sans appel réseau si les deux devises coïncident, None si
    l'une est inconnue ou si la paire n'est pas cotée sur Yahoo Finance."""
    if not from_currency or not to_currency:
        return None
    if from_currency == to_currency:
        return 1.0
    try:
        return _fetch_fx_rate(from_currency, to_currency)
    except Exception:
        return None
