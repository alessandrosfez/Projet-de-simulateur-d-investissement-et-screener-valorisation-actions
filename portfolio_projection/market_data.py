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


# Horodatage du téléchargement des données réellement RENVOYÉES par cached_ttl pendant ce
# processus, par clé de cache. Distinct de _cache, qui garde aussi des séries que plus aucun écran
# n'utilise (ancien ticker, ancien horizon...) : leur âge fausserait la date affichée par le badge
# de fraîcheur (voir data_freshness), qui doit refléter ce qui est à l'écran.
_served_download_times: dict = {}

# Au-delà, le badge de fraîcheur passe en avertissement.
DATA_STALE_AFTER_DAYS = 7


def cached_ttl(ttl_seconds: int):
    """Cache mémoire + disque : évite de retélécharger via yfinance à chaque
    redémarrage du serveur tant que les données ont moins de ttl_seconds.

    Si le rafraîchissement échoue (hors ligne, yfinance indisponible), sert la dernière version
    connue plutôt que de faire échouer l'écran, en gardant son horodatage d'origine : c'est ce
    qui permet au badge de fraîcheur de signaler des données anciennes. Sans version connue,
    l'erreur remonte comme avant."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args):
            key = (func.__name__, args)
            now = time.time()
            if key in _cache:
                value, timestamp = _cache[key]
                if now - timestamp < ttl_seconds:
                    _served_download_times[key] = timestamp
                    return value
            try:
                value = func(*args)
            except Exception:
                if key in _cache:
                    stale_value, stale_timestamp = _cache[key]
                    _served_download_times[key] = stale_timestamp
                    return stale_value
                raise
            _cache[key] = (value, now)
            _served_download_times[key] = now
            _save_cache_to_disk()
            return value
        return wrapper
    return decorator


def get_cache_download_times() -> dict:
    """Date du dernier téléchargement de chaque série en cache : {(fonction, arguments): datetime}.
    Inclut les séries que plus aucun écran n'utilise ; pour l'âge des données affichées, voir
    get_served_download_times."""
    with _cache_lock:
        entries = list(_cache.items())
    return {key: datetime.fromtimestamp(timestamp) for key, (_value, timestamp) in entries}


def get_served_download_times() -> list[float]:
    """Horodatages (time.time()) des téléchargements dont les données ont été servies pendant ce
    processus."""
    return list(_served_download_times.values())


def data_freshness(download_timestamps: list[float], now: float,
                   max_age_days: float = DATA_STALE_AFTER_DAYS) -> dict | None:
    """Âge des données affichées : la plus ANCIENNE des séries servies fait foi (une seule série
    périmée suffit à fausser un graphique). Renvoie {"oldest" (datetime), "age_days",
    "is_stale", "n_series"}, ou None si rien n'a encore été servi."""
    if not download_timestamps:
        return None
    oldest = min(download_timestamps)
    age_days = (now - oldest) / 86400
    return {
        "oldest": datetime.fromtimestamp(oldest),
        "age_days": age_days,
        "is_stale": age_days > max_age_days,
        "n_series": len(download_timestamps),
    }


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


# Les montants du portefeuille réel (achats, dividendes) sont en euros : tout cours doit l'être
# aussi. Or yfinance cote chaque titre dans la devise de SA place, éventuellement en sous-unité
# (pence). Vérifié sur les ISIN d'un export Trade Republic : Apple, Microsoft, Vanguard FTSE
# All-World et iShares Core MSCI World se résolvent en AAPL, MSFT, VWRA.L et IWDA.L, toutes en USD,
# alors que Trade Republic exécute en euros.
PORTFOLIO_CURRENCY = "EUR"
# Sous-unités de cotation : (devise principale, diviseur). Recopié de stock_valuation.
MINOR_CURRENCY_UNITS = {"GBp": ("GBP", 100), "GBX": ("GBP", 100), "ZAc": ("ZAR", 100), "ILA": ("ILS", 100)}


def _quote_currency(info: dict) -> tuple[str | None, float]:
    """Devise principale de cotation et diviseur de sous-unité ((None, 1) si Yahoo ne la donne pas)."""
    code = info.get("currency")
    if not code:
        return None, 1.0
    major, divisor = MINOR_CURRENCY_UNITS.get(code, (code, 1))
    return major, float(divisor)


@cached_ttl(3600)
def _fetch_fx_history(currency: str, start_date: str) -> pd.Series:
    """Clôtures quotidiennes de la paire Yahoo « XXXEUR=X » (1 XXX en euros), index de dates sans
    fuseau. Lève une exception sans données, pour ne jamais mettre en cache une série vide."""
    closes = yf.Ticker(f"{currency}{PORTFOLIO_CURRENCY}=X").history(start=start_date, interval="1d")["Close"].dropna()
    closes = closes[closes > 0]
    if closes.empty:
        raise ValueError(f"Pas de cours pour {currency}{PORTFOLIO_CURRENCY}=X")
    closes.index = _naive_dates(closes.index)
    return closes[~closes.index.duplicated(keep="last")]


def _naive_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(index)
    return (index.tz_localize(None) if index.tz is not None else index).normalize()


def _fx_rate_on_dates(currency: str, dates: pd.DatetimeIndex, start_date: str) -> pd.Series:
    """Taux XXX -> EUR à chaque date de dates : dernier cours de change connu à cette date (les
    marchés des changes et des actions n'ont pas exactement les mêmes jours de cotation)."""
    fx = _fetch_fx_history(currency, start_date)
    target = _naive_dates(dates)
    return fx.reindex(fx.index.union(target)).ffill().reindex(target)


def _to_portfolio_currency(prices: pd.Series, info: dict, start_date: str) -> pd.Series:
    """Cours en euros : division par la sous-unité (pence -> livres) puis change du jour. Devise
    inconnue : repli sur l'ancien facteur pence/livre déduit du P/E (voir _price_scale_factor). Un
    jour sans taux de change connu est écarté plutôt que valorisé dans la mauvaise devise."""
    major, divisor = _quote_currency(info)
    if major is None:
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        return prices / _price_scale_factor(info.get("trailingPE"), info.get("trailingEps"), price)
    prices = prices / divisor
    if major == PORTFOLIO_CURRENCY:
        return prices
    rates = _fx_rate_on_dates(major, prices.index, start_date)
    return (prices * rates.to_numpy()).dropna()


@cached_ttl(3600)
def _fetch_current_price_eur(ticker: str) -> float | None:
    info = _get_ticker_info(ticker)
    price = (
        info.get("currentPrice") or info.get("regularMarketPrice")
        or info.get("previousClose") or info.get("regularMarketPreviousClose")
    )
    if price is None:
        return None
    today = pd.Timestamp.today().normalize()
    start = (today - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    converted = _to_portfolio_currency(pd.Series([float(price)], index=pd.DatetimeIndex([today])), info, start)
    return float(converted.iloc[0]) if not converted.empty else None


def get_current_price(ticker: str) -> float | None:
    """Prix courant d'un ticker quelconque, EN EUROS (voir _to_portfolio_currency) -- sert à
    valoriser les positions du portefeuille réel et à valider un ticker à la saisie (voir
    callbacks/portefeuille_reel.py, formulaires d'ajout). None si indisponible (ticker
    invalide/délisté, ou taux de change introuvable : jamais un cours en dollars présenté comme
    un cours en euros).

    currentPrice/regularMarketPrice sont souvent absents pour les ETF (champs surtout
    peuplés pour les actions individuelles chez Yahoo, constaté en pratique en dehors
    des heures de cotation) -- repli sur la dernière clôture connue plutôt que de
    traiter l'instrument comme introuvable : sans ça, un ETF réellement détenu
    disparaissait silencieusement de la valorisation du portefeuille réel (montant
    investi resté correct, valeur actuelle sous-évaluée d'autant)."""
    try:
        return _fetch_current_price_eur(ticker)
    except Exception:
        return None


@cached_ttl(3600)
def _fetch_daily_close_eur(ticker: str, start_date: str, auto_adjust: bool) -> pd.Series:
    """Couche cachée des deux historiques quotidiens ci-dessous, en euros. Lève une exception si
    yfinance ne renvoie rien (souvent sans erreur explicite en cas de coupure réseau) plutôt que de
    renvoyer une série vide : une série vide serait mise en cache à la place des bonnes données,
    alors qu'une exception laisse cached_ttl servir la dernière version connue. Le nom porte « eur »
    pour que le cache disque ne resserve jamais une série d'avant la conversion de devise."""
    info = _get_ticker_info(ticker)
    hist = yf.Ticker(ticker).history(start=start_date, interval="1d", auto_adjust=auto_adjust)["Close"].dropna()
    if hist.empty:
        raise ValueError(f"Pas d'historique quotidien pour {ticker}")
    converted = _to_portfolio_currency(hist, info, start_date)
    if converted.empty:
        raise ValueError(f"Pas de taux de change pour convertir {ticker} en {PORTFOLIO_CURRENCY}")
    return converted


def get_daily_price_history(ticker: str, start_date: str) -> pd.Series:
    """Historique de prix de clôture QUOTIDIEN depuis start_date (ISO "YYYY-MM-DD"), en euros comme
    get_current_price, au change de chaque jour (pas seulement au dernier) -- nécessaire pour reconstruire la valeur du portefeuille réel à une date passée, pas
    seulement sa valeur actuelle. Série vide si le ticker est invalide ou n'a pas coté sur la
    période. Premier (et seul) point de collecte quotidien de cette app : get_monthly_returns
    ci-dessus ne fait que du mensuel, suffisant pour la calibration Monte Carlo mais pas pour
    valoriser un achat à sa date exacte.

    Cours BRUTS (auto_adjust=False), pas ajustés des dividendes comme le fait yfinance par défaut :
    on veut la valeur de marché réelle des positions à chaque date passée. Un cours ajusté abaisse
    rétroactivement les cours d'un titre distribuant (ex: CAC.PA, ~70 € ajusté contre ~74 € réel
    début 2024), ce qui sous-évaluerait la courbe passée et compterait deux fois les dividendes
    déjà saisis en cash (voir portfolio_engine, section performance réelle)."""
    try:
        return _fetch_daily_close_eur(ticker, start_date, False)
    except Exception:
        return pd.Series(dtype=float)


def get_daily_total_return_history(ticker: str, start_date: str) -> pd.Series:
    """Historique quotidien AJUSTÉ des dividendes (dividendes réinvestis) depuis start_date : sert
    d'indice de référence pour le portefeuille réel (portfolio_engine.benchmark_equity_curve),
    convention usuelle d'une référence "dividendes réinvestis" -- contrairement à
    get_daily_price_history, qui veut les cours bruts. Même conversion en euros : une référence
    cotée en dollars (un ETF S&P 500 de Londres) mesure ainsi le rendement d'un investisseur en
    euros, change compris, comme le portefeuille réel auquel elle est comparée.
    Série vide si le ticker est invalide ou n'a pas coté sur la période."""
    try:
        return _fetch_daily_close_eur(ticker, start_date, True)
    except Exception:
        return pd.Series(dtype=float)


@cached_ttl(86400)
def get_ticker_name(ticker: str) -> str | None:
    """Nom lisible d'un ticker quelconque (shortName, repli longName) -- sert à annoter dans
    l'UI les tickers du portefeuille réel qui ne font pas partie de l'univers simulé
    (constants.TICKERS), pour qu'un ticker peu parlant (ex: "PAASI.PA") reste identifiable sans
    recherche externe (voir callbacks/portefeuille_reel.py, _ticker_display_label). Cache TTL plus long que
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
