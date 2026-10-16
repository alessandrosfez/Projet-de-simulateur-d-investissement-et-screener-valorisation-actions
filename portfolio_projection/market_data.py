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


def get_aligned_returns_for_tickers(tickers: list, lookback_years: int) -> pd.DataFrame:
    """Équivalent de get_aligned_returns, mais pour des tickers Yahoo bruts plutôt que les noms
    d'indices de TICKERS : le portefeuille réel (voir portfolio_db.py) accepte n'importe quel
    ticker, pas seulement les 4 indices/ETF simulés par les onglets 1 et 2."""
    series = {ticker: get_monthly_returns(ticker, lookback_years) for ticker in tickers}
    return pd.concat(series, axis=1).dropna()


# ============================================================
# PORTEFEUILLE RÉEL (prix courants/historiques pour un ticker quelconque)
# ============================================================

@cached_ttl(3600)
def _get_ticker_info(ticker: str) -> dict:
    return yf.Ticker(ticker).get_info()


def _price_scale_factor(trailing_pe, trailing_eps, current_price) -> float:
    """Certaines places (Londres notamment) cotent le prix en pence alors que le BPA
    est en livres (ou vice versa) : on déduit un facteur d'échelle du P/E déjà
    correct fourni par Yahoo, pour garder les calculs de valeur cohérents. Porté tel
    quel depuis stock_valuation/market_data.py (même logique, projets indépendants)."""
    if trailing_pe and trailing_eps and current_price:
        implied_price = trailing_pe * trailing_eps
        if implied_price > 0:
            ratio = current_price / implied_price
            if ratio > 5:
                return round(ratio)
    return 1.0


@cached_ttl(3600)
def get_current_price(ticker: str) -> float | None:
    """Prix courant d'un ticker quelconque, corrigé de l'éventuel décalage d'échelle
    pence/livre -- sert à valoriser les positions du portefeuille réel et à valider
    un ticker à la saisie (voir callbacks.py, formulaires d'ajout). None si
    indisponible (ticker invalide/délisté).

    currentPrice/regularMarketPrice sont souvent absents pour les ETF (champs surtout
    peuplés pour les actions individuelles chez Yahoo, constaté en pratique en dehors
    des heures de cotation) -- repli sur la dernière clôture connue plutôt que de
    traiter l'instrument comme introuvable : sans ça, un ETF réellement détenu
    disparaissait silencieusement de la valorisation du portefeuille réel (montant
    investi resté correct, valeur actuelle sous-évaluée d'autant)."""
    info = _get_ticker_info(ticker)
    price = (
        info.get("currentPrice") or info.get("regularMarketPrice")
        or info.get("previousClose") or info.get("regularMarketPreviousClose")
    )
    if price is None:
        return None
    price_scale = _price_scale_factor(info.get("trailingPE"), info.get("trailingEps"), price)
    return price / price_scale


@cached_ttl(3600)
def get_daily_price_history(ticker: str, start_date: str) -> pd.Series:
    """Historique de prix de clôture QUOTIDIEN depuis start_date (ISO "YYYY-MM-DD"), corrigé du
    même décalage d'échelle que get_current_price sur toute la série (pas seulement le dernier
    point) -- nécessaire pour reconstruire la valeur du portefeuille réel à une date passée, pas
    seulement sa valeur actuelle. Série vide si le ticker est invalide ou n'a pas coté sur la
    période. Premier (et seul) point de collecte quotidien de cette app : get_monthly_returns
    ci-dessus ne fait que du mensuel, suffisant pour la calibration Monte Carlo mais pas pour
    valoriser un achat à sa date exacte."""
    info = _get_ticker_info(ticker)
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    price_scale = _price_scale_factor(info.get("trailingPE"), info.get("trailingEps"), price)
    try:
        hist = yf.Ticker(ticker).history(start=start_date, interval="1d")["Close"].dropna()
    except Exception:
        return pd.Series(dtype=float)
    return hist / price_scale


@cached_ttl(86400)
def get_ticker_name(ticker: str) -> str | None:
    """Nom lisible d'un ticker quelconque (shortName, repli longName) -- sert à annoter dans
    l'UI les tickers du portefeuille réel qui ne font pas partie de l'univers simulé
    (constants.TICKERS), pour qu'un ticker peu parlant (ex: "PAASI.PA") reste identifiable sans
    recherche externe (voir callbacks._ticker_display_label). Cache TTL plus long que
    get_current_price : le nom d'un instrument change rarement, contrairement à son prix. None
    si indisponible (ticker invalide/délisté)."""
    info = _get_ticker_info(ticker)
    return info.get("shortName") or info.get("longName")


@cached_ttl(3600)
def resolve_isin_to_ticker(isin: str) -> str | None:
    """Résout un code ISIN (ex: FR0011550193) en ticker Yahoo Finance (ex: ETZ.PA). Les exports de
    courtiers européens (ex: Trade Republic) identifient les instruments par ISIN, pas par ticker
    boursier -- yfinance résout un ISIN directement via Ticker(isin).get_info()["symbol"] (vérifié
    empiriquement sur plusieurs ISIN d'ETF PEA réels, dont certains correspondant exactement aux
    tickers déjà vérifiés à la main dans constants.py). None si l'ISIN est invalide ou inconnu."""
    try:
        info = yf.Ticker(isin).get_info()
    except Exception:
        return None
    return info.get("symbol")
