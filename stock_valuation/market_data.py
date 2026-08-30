"""
Récupération des données de marché via yfinance, avec cache disque (équivalent
minimal de st.cache_data(ttl=...)) pour éviter de retélécharger à chaque
redémarrage tant que les données ont moins d'1h.
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


DCF_FCF_AVERAGING_YEARS = 3


@cached_ttl(3600)
def _get_annual_fcf_history(ticker: str) -> pd.DataFrame:
    """FCF annuel et ses deux composantes (flux de trésorerie d'exploitation, capex) quand Yahoo
    Finance les fournit, un exercice clos par ligne, le plus récent en premier. DataFrame vide si
    la ligne "Free Cash Flow" n'est pas disponible pour ce titre. Les composantes (colonnes
    "Operating Cash Flow"/"Capital Expenditure") servent uniquement à l'affichage pédagogique du
    calcul dans l'UI : c'est bien la seule colonne "Free Cash Flow" qui sert de base au DCF."""
    try:
        cf = yf.Ticker(ticker).cashflow
    except Exception:
        return pd.DataFrame()
    if cf is None or cf.empty or "Free Cash Flow" not in cf.index:
        return pd.DataFrame()
    rows = [r for r in ["Free Cash Flow", "Operating Cash Flow", "Capital Expenditure"] if r in cf.index]
    return cf.loc[rows].T.dropna(subset=["Free Cash Flow"])


@cached_ttl(3600)
def _get_annual_income_statement(ticker: str) -> pd.DataFrame:
    """Compte de résultat annuel (Ticker.financials transposé, un exercice clos par ligne, le plus
    récent en premier), limité aux lignes utiles au calcul du ROIC. DataFrame vide si l'appel
    échoue ou si aucune des lignes attendues n'est disponible pour ce titre."""
    try:
        fin = yf.Ticker(ticker).financials
    except Exception:
        return pd.DataFrame()
    if fin is None or fin.empty:
        return pd.DataFrame()
    rows = [r for r in ["EBIT", "Pretax Income", "Tax Provision"] if r in fin.index]
    if not rows:
        return pd.DataFrame()
    return fin.loc[rows].T


@cached_ttl(3600)
def _get_annual_balance_sheet(ticker: str) -> pd.DataFrame:
    """Bilan annuel (Ticker.balance_sheet transposé), même convention que
    _get_annual_income_statement, limité aux lignes utiles au calcul du ROIC."""
    try:
        bs = yf.Ticker(ticker).balance_sheet
    except Exception:
        return pd.DataFrame()
    if bs is None or bs.empty:
        return pd.DataFrame()
    rows = [r for r in ["Total Debt", "Stockholders Equity", "Cash And Cash Equivalents"] if r in bs.index]
    if not rows:
        return pd.DataFrame()
    return bs.loc[rows].T


def _pct(x) -> float:
    return round(x * 100, 2) if x is not None else None


def get_stock_quality_metrics(ticker: str) -> dict:
    """Marges, rendements et ratios de liquidité lus directement sur Ticker.info (aucun appel
    réseau supplémentaire : déjà mis en cache par _get_ticker_info dès que le titre a été chargé
    une première fois), plus le ROIC (rendement du capital investi) calculé sur le dernier exercice
    clos : NOPAT (EBIT après impôt effectif) / capitaux investis (dette + capitaux propres -
    trésorerie). `roic` vaut None si le compte de résultat ou le bilan manque une donnée
    nécessaire, si le résultat avant impôt est nul/négatif (taux d'impôt effectif non
    significatif), ou si les capitaux investis sont <= 0.

    EBIT/dette/capitaux propres/trésorerie sont remis à l'échelle du prix courant via
    _price_scale_factor, exactement comme le FCF dans get_dcf_inputs : les mêmes places boursières
    cotant en pence (Londres) ou dans une autre devise de reporting (valeurs à double cotation)
    affecteraient un ROIC calculé sans cette correction. Dette/capitaux propres/trésorerie
    proviennent uniquement du bilan (une seule famille de données), jamais mélangés avec les champs
    de _get_ticker_info : deux endpoints yfinance différents ne garantissent pas la même échelle
    même pour la même entreprise, et le facteur d'échelle (déduit du prix/P/E/BPA) ne rattraperait
    pas un décalage entre les deux."""
    info = _get_ticker_info(ticker)
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    price_scale = _price_scale_factor(info.get("trailingPE"), info.get("trailingEps"), price)

    roic = None
    income = _get_annual_income_statement(ticker)
    balance = _get_annual_balance_sheet(ticker)
    if not income.empty and not balance.empty:
        li, lb = income.iloc[0], balance.iloc[0]
        ebit = li.get("EBIT")
        pretax = li.get("Pretax Income")
        tax = li.get("Tax Provision")
        debt = lb.get("Total Debt")
        equity = lb.get("Stockholders Equity")
        cash = lb.get("Cash And Cash Equivalents")
        if pd.notna(ebit) and pd.notna(pretax) and pretax and pd.notna(debt) and pd.notna(equity):
            eff_tax_rate = min(max((float(tax) / float(pretax)) if pd.notna(tax) else 0.0, 0.0), 1.0)
            nopat = float(ebit) * price_scale * (1 - eff_tax_rate)
            invested_capital = (float(debt) + float(equity) - float(cash or 0)) * price_scale
            if invested_capital > 0:
                roic = round(nopat / invested_capital * 100, 2)

    return {
        "roic": roic,
        "return_on_equity": _pct(info.get("returnOnEquity")),
        "return_on_assets": _pct(info.get("returnOnAssets")),
        "gross_margin": _pct(info.get("grossMargins")),
        "operating_margin": _pct(info.get("operatingMargins")),
        "profit_margin": _pct(info.get("profitMargins")),
        "revenue_growth": _pct(info.get("revenueGrowth")),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "quick_ratio": info.get("quickRatio"),
    }


def get_dcf_inputs(ticker: str) -> dict:
    """Intrants DCF les plus récents pour une action : FCF, dette totale, trésorerie, nombre
    d'actions, prix courant. Le FCF est la moyenne des DCF_FCF_AVERAGING_YEARS derniers exercices
    clos (via le tableau de flux de trésorerie) plutôt que le seul FCF glissant sur 12 mois
    (freeCashflow) : ça lisse les à-coups de capex ponctuels qui rendraient un DCF basé sur un
    seul point trompeur (ex : les hyperscalers en pleine construction de data centers IA ont un
    FCF TTM ponctuellement très déprimé alors que leur FCF "normal" reste élevé). `fcf_history`
    donne le détail (exercice, FCF, flux d'exploitation, capex) des exercices utilisés dans cette
    moyenne, pour que l'UI puisse montrer d'où vient le chiffre plutôt que l'afficher tel quel.
    Repli sur le FCF TTM de Yahoo Finance (et fcf_history vide) si l'historique annuel n'est pas
    disponible pour ce titre. Réutilise _get_ticker_info (déjà mis en cache par get_stock_valuation
    si l'action a déjà été chargée) : aucun appel réseau supplémentaire dans ce cas pour les champs
    autres que le FCF. `fcf`/`shares_outstanding` valent None si Yahoo Finance ne les fournit pas
    du tout pour ce titre (fréquent pour certaines actions non américaines), à l'appelant de gérer
    ce cas comme "DCF indisponible".

    FCF/dette/trésorerie sont remis à l'échelle du prix courant via _price_scale_factor : certaines
    places (Londres notamment) cotent le prix en pence (GBp) alors que les états financiers (FCF,
    dette, trésorerie, BPA) sont en livres, voire dans une autre devise de reporting pour les valeurs
    à double cotation (ex : AstraZeneca, Shell facturent en USD) — sans cette correction, le DCF
    ressortirait ~100x trop bas par rapport au prix affiché (le facteur est déduit empiriquement du
    P/E déjà correct fourni par Yahoo, donc fonctionne quelle que soit la devise de reporting)."""
    info = _get_ticker_info(ticker)
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    price_scale = _price_scale_factor(info.get("trailingPE"), info.get("trailingEps"), price)

    fcf_history = _get_annual_fcf_history(ticker)
    fcf_history_records = []
    if not fcf_history.empty:
        recent = fcf_history.iloc[:DCF_FCF_AVERAGING_YEARS]
        fcf = float(recent["Free Cash Flow"].mean()) * price_scale
        for fiscal_year_end, row in recent.iterrows():
            fcf_history_records.append({
                "year": fiscal_year_end.year,
                "fcf": float(row["Free Cash Flow"]) * price_scale,
                "operating_cash_flow": float(row["Operating Cash Flow"]) * price_scale
                    if "Operating Cash Flow" in row and pd.notna(row["Operating Cash Flow"]) else None,
                "capex": float(row["Capital Expenditure"]) * price_scale
                    if "Capital Expenditure" in row and pd.notna(row["Capital Expenditure"]) else None,
            })
    else:
        raw_fcf = info.get("freeCashflow")
        fcf = raw_fcf * price_scale if raw_fcf else raw_fcf
    return {
        "fcf": fcf,
        "fcf_history": fcf_history_records,
        "total_debt": (info.get("totalDebt") or 0) * price_scale,
        "total_cash": (info.get("totalCash") or 0) * price_scale,
        "shares_outstanding": info.get("sharesOutstanding"),
        "price": price,
        "currency": info.get("currency") or "N/A",
    }
