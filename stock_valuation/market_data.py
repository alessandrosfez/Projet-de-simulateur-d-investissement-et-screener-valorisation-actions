"""
Récupération des données de marché via yfinance, avec cache disque (équivalent
minimal de st.cache_data(ttl=...)) pour éviter de retélécharger à chaque
redémarrage tant que les données ont moins d'1h.
"""
import atexit
import functools
import pickle
import threading
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

import engine
from constants import SECTOR_FALLBACK

# ============================================================
# CACHE (mémoire + disque)
# ============================================================

CACHE_FILE = Path(__file__).with_name(".pea_forecast_cache.pkl")
_cache_lock = threading.Lock()

# Durées de cache : une heure pour tout ce qui suit le cours (fiche Yahoo, historiques de prix),
# un jour pour les comptes annuels (BPA, flux de trésorerie, compte de résultat, bilan), qui ne
# changent qu'à la publication des résultats. Les retélécharger chaque heure coûtait environ un
# tiers du temps de chargement d'un titre pour des chiffres identiques.
PRICE_TTL_SECONDS = 3600
STATEMENTS_TTL_SECONDS = 86400
# Une entrée plus vieille que la plus longue durée de cache ne sera plus jamais servie : elle est
# écartée à l'écriture, sinon le fichier grossit sans fin d'un chargement à l'autre.
MAX_ENTRY_AGE_SECONDS = 2 * STATEMENTS_TTL_SECONDS
# Écriture sur disque regroupée : au plus une toutes les SAVE_DELAY_SECONDS. Réécrire tout le fichier
# (plusieurs Mo) après chaque appel faisait près de 300 écritures par chargement d'un marché et en
# doublait la durée.
SAVE_DELAY_SECONDS = 2.0
_save_timer: threading.Timer | None = None
_timer_lock = threading.Lock()


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
    """Écrit une copie figée du cache (les autres fils continuent d'y ajouter des entrées pendant
    l'écriture : sérialiser le dictionnaire vivant pouvait échouer), sans les entrées périmées."""
    with _cache_lock:
        now = time.time()
        snapshot = {key: entry for key, entry in list(_cache.items()) if now - entry[1] < MAX_ENTRY_AGE_SECONDS}
        try:
            tmp_path = CACHE_FILE.with_suffix(".tmp")
            with open(tmp_path, "wb") as f:
                pickle.dump(snapshot, f)
            tmp_path.replace(CACHE_FILE)
        except Exception:
            pass


def _schedule_save():
    """Programme une écriture dans SAVE_DELAY_SECONDS, sauf si une écriture est déjà programmée :
    toutes les entrées ajoutées entre-temps partent dans la même écriture."""
    global _save_timer
    with _timer_lock:
        if _save_timer is not None:
            return

        def run():
            global _save_timer
            with _timer_lock:
                _save_timer = None
            _save_cache_to_disk()

        _save_timer = threading.Timer(SAVE_DELAY_SECONDS, run)
        _save_timer.daemon = True
        _save_timer.start()


def _flush_pending_save():
    """À l'arrêt du processus : écrit tout de suite une écriture encore en attente."""
    global _save_timer
    with _timer_lock:
        pending, _save_timer = _save_timer, None
    if pending is not None:
        pending.cancel()
        _save_cache_to_disk()


atexit.register(_flush_pending_save)


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
            _schedule_save()
            return value
        return wrapper
    return decorator


@cached_ttl(PRICE_TTL_SECONDS)
def _fetch_ticker_info(ticker: str) -> dict:
    info = yf.Ticker(ticker).get_info()
    if not info or not any(info.get(k) for k in ("shortName", "longName", "quoteType", "currency")):
        raise ValueError(f"Fiche Yahoo vide pour {ticker}")
    return info


def _get_ticker_info(ticker: str) -> dict:
    """Fiche Yahoo d'un ticker, {} si indisponible. Une fiche vide (réponse passagère de Yahoo,
    constatée sur un ETF) n'est jamais mise en cache : elle aurait affiché une ligne entière de N/A
    pendant une heure, au lieu de la dernière fiche connue que cached_ttl sert en cas d'échec."""
    try:
        return _fetch_ticker_info(ticker)
    except Exception:
        return {}


def _price_scale_factor(trailing_pe, trailing_eps, current_price) -> float:
    """Certaines places (Londres notamment) cotent le prix en pence alors que le BPA
    est en livres (ou vice versa) : on déduit un facteur d'échelle du P/E déjà
    correct fourni par Yahoo, pour garder les calculs historiques cohérents.

    Ne mesure QUE la sous-unité, jamais le change : Yahoo exprime le BPA dans la devise
    de cotation, pas dans celle des comptes (Shell : comptes en USD, BPA en livres,
    ratio de 100 exactement). Suffit pour le P/E historique (cours / BPA), pas pour
    convertir des montants des états financiers (voir _statement_to_price_units)."""
    if trailing_pe and trailing_eps and current_price:
        implied_price = trailing_pe * trailing_eps
        if implied_price > 0:
            ratio = current_price / implied_price
            if ratio > 5:
                return round(ratio)
    return 1.0


# Sous-unités monétaires utilisées par Yahoo pour certains cours : (devise principale, diviseur).
# À Londres, le cours est en pence (GBp) mais la capitalisation en livres.
MINOR_CURRENCY_UNITS = {"GBp": ("GBP", 100), "GBX": ("GBP", 100), "ZAc": ("ZAR", 100), "ILA": ("ILS", 100)}


@cached_ttl(PRICE_TTL_SECONDS)
def _fetch_fx_rate(from_currency: str, to_currency: str) -> float:
    """Dernière clôture de la paire Yahoo "XXXYYY=X" (1 XXX en YYY). Lève une exception si la paire
    n'a pas de cours, pour qu'un échec ne soit pas mis en cache."""
    closes = yf.Ticker(f"{from_currency}{to_currency}=X").history(period="5d")["Close"].dropna()
    if closes.empty or float(closes.iloc[-1]) <= 0:
        raise ValueError(f"Pas de cours pour {from_currency}{to_currency}=X")
    return float(closes.iloc[-1])


def get_fx_rate(from_currency: str, to_currency: str) -> float | None:
    if from_currency == to_currency:
        return 1.0
    try:
        return _fetch_fx_rate(from_currency, to_currency)
    except Exception:
        return None


def _statement_to_price_units(info: dict) -> tuple[float, float]:
    """(facteur des montants des états financiers, facteur de la capitalisation) pour les ramener
    dans l'unité du cours affiché, et pouvoir les comparer au cours ou les diviser par le nombre
    d'actions.

    Les états financiers (FCF, dette, trésorerie, y compris les champs totalDebt/totalCash/
    freeCashflow de Ticker.info) sont dans la devise des comptes (financialCurrency) ; le cours
    dans la devise de cotation, parfois en sous-unité (pence) ; la capitalisation dans la devise
    de cotation principale (livres). Facteur des états = change (comptes -> cotation) x diviseur
    de sous-unité ; facteur de la capitalisation = diviseur seul. Shell : 1 USD = 0,75 GBP, x 100
    pence. Sans devise connue ou sans taux de change, repli sur l'ancien facteur empirique
    (_price_scale_factor), qui ne corrige que la sous-unité."""
    quote, reporting = info.get("currency"), info.get("financialCurrency")
    if quote and reporting:
        major, divisor = MINOR_CURRENCY_UNITS.get(quote, (quote, 1))
        fx = get_fx_rate(reporting, major)
        if fx is not None:
            return fx * divisor, float(divisor)
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    legacy = _price_scale_factor(info.get("trailingPE"), info.get("trailingEps"), price)
    return legacy, legacy


def major_currency(code: str | None) -> str | None:
    """Devise principale d'un code de cotation (GBP pour GBp) : la capitalisation Yahoo est exprimée
    dans la devise principale, même quand le cours est coté en sous-unité."""
    if not code or code == "N/A":
        return code
    return MINOR_CURRENCY_UNITS.get(code, (code, 1))[0]


@cached_ttl(STATEMENTS_TTL_SECONDS)
def _get_annual_eps(ticker: str) -> pd.Series:
    """BPA dilué (repli : de base) de chaque exercice clos, par date de clôture, dans la devise des
    comptes. Série vide si Yahoo ne le fournit pas."""
    try:
        income = yf.Ticker(ticker).income_stmt
    except Exception:
        return pd.Series(dtype=float)
    if not isinstance(income, pd.DataFrame) or income.empty:
        return pd.Series(dtype=float)
    for row in ("Diluted EPS", "Basic EPS"):
        if row in income.index:
            eps = pd.to_numeric(income.loc[row], errors="coerce").dropna()
            if not eps.empty:
                eps.index = pd.to_datetime(eps.index)
                return eps.sort_index()
    return pd.Series(dtype=float)


@cached_ttl(PRICE_TTL_SECONDS)
def get_stock_pe_history(ticker: str) -> pd.Series:
    """Série de P/E historique hebdomadaire, sur les 5 dernières années au plus : cours de chaque
    semaine / BPA du dernier exercice PUBLIÉ à cette date (clôture + 3 mois, voir
    engine.pe_from_annual_eps). Yahoo ne fournit qu'environ 4 exercices : la série commence donc ~3
    mois après la clôture du plus ancien (3,5 ans environ), plutôt que d'être prolongée par une autre
    méthode. Le BPA, publié dans la devise des comptes, est ramené dans l'unité du cours (change du
    jour et sous-unité, voir _statement_to_price_units ; approximation : change actuel pour tout
    l'historique, sans effet hors doubles cotations).

    Sans BPA annuel, repli sur l'ancienne approximation (cours / BPA actuel constant), signalée par
    series.attrs["method"] = "current_eps" ("annual_eps" sinon) : elle suppose le BPA stable, ce qui
    est faux pour une valeur cyclique (BPA de TotalEnergies de 5,78 à 8,67 € entre 2022 et 2025).
    Série vide sans aucun BPA positif.

    Cours BRUTS (auto_adjust=False) : par défaut, yfinance ajuste rétroactivement les cours passés
    des dividendes versés depuis, ce qui minore le P/E de l'époque. Vérifié sur TotalEnergies : le
    cours ajusté d'il y a 5 ans ne vaut que 75 % du cours réellement coté (91 % pour Air Liquide).
    Les cours bruts restent ajustés des divisions, comme le BPA."""
    info = _get_ticker_info(ticker)
    try:
        hist = yf.Ticker(ticker).history(period="5y", interval="1wk", auto_adjust=False)["Close"].dropna()
    except Exception:
        return pd.Series(dtype=float)

    annual_eps = _get_annual_eps(ticker)
    if not annual_eps.empty:
        eps_scale, _market_cap_scale = _statement_to_price_units(info)
        pe = engine.pe_from_annual_eps(hist, annual_eps * eps_scale)
        if not pe.empty:
            pe.attrs["method"] = "annual_eps"
            return pe

    trailing_eps = info.get("trailingEps")
    if not trailing_eps or trailing_eps <= 0:
        return pd.Series(dtype=float)
    price_scale = _price_scale_factor(info.get("trailingPE"), trailing_eps,
                                      info.get("currentPrice") or info.get("regularMarketPrice"))
    implied_pe = (hist / price_scale) / trailing_eps
    implied_pe = implied_pe[implied_pe > 0]
    implied_pe.attrs["method"] = "current_eps"
    return implied_pe


@cached_ttl(PRICE_TTL_SECONDS)
def get_stock_price_history(ticker: str, period: str = "5y", interval: str = "1mo") -> pd.Series:
    """Série de prix de clôture, corrigée du même décalage d'échelle prix/BPA que
    get_stock_pe_history (voir _price_scale_factor), mais sans exiger de BPA positif :
    sert au calcul de rendement/volatilité/drawdown réalisés (track record), utiles
    même pour une valeur sans bénéfice net positif, contrairement au P/E historique.
    Cours ajustés des dividendes, à dessein ici (contrairement au P/E historique) : le track record
    mesure le rendement total, dividendes réinvestis."""
    info = _get_ticker_info(ticker)
    trailing_pe = info.get("trailingPE")
    trailing_eps = info.get("trailingEps")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    price_scale = _price_scale_factor(trailing_pe, trailing_eps, current_price)
    try:
        hist = yf.Ticker(ticker).history(period=period, interval=interval)["Close"].dropna()
    except Exception:
        return pd.Series(dtype=float)
    return hist / price_scale


@cached_ttl(PRICE_TTL_SECONDS)
def get_stock_valuation(ticker: str) -> dict:
    """Prix et ratios de valorisation courants d'une action (P/E, PEG, P/B, rendement du
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
        "sector": info.get("sector") or SECTOR_FALLBACK.get(ticker, {}).get("sector") or "N/A",
        "currency": info.get("currency") or "N/A",
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "trailing_pe": trailing_pe,
        "forward_pe": info.get("forwardPE"),
        # `or` serait piégeux ici : un trailingPegRatio légitimement égal à 0.0 (croissance
        # estimée nulle) serait pris pour une valeur manquante et silencieusement remplacé par
        # pegRatio. Repli explicite sur None uniquement.
        "peg_ratio": (info.get("trailingPegRatio") if info.get("trailingPegRatio") is not None
                      else info.get("pegRatio")),
        "ev_to_ebitda": info.get("enterpriseToEbitda"),
        "price_to_book": info.get("priceToBook"),
        "dividend_yield": info.get("dividendYield"),
        "market_cap": info.get("marketCap"),
        "pe_5y_mean": pe_5y_mean,
        "pe_5y_percentile": pe_5y_percentile,
    }


DCF_FCF_AVERAGING_YEARS = 3


@cached_ttl(STATEMENTS_TTL_SECONDS)
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


@cached_ttl(STATEMENTS_TTL_SECONDS)
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


@cached_ttl(STATEMENTS_TTL_SECONDS)
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

    FCF/dette/trésorerie et capitalisation sont ramenés dans l'unité du cours affiché via
    _statement_to_price_units : certaines places (Londres notamment) cotent le prix en pence (GBp)
    alors que les états financiers sont en livres, voire dans une autre devise pour les valeurs à
    double cotation (Shell et AstraZeneca publient en USD, Unilever en EUR). L'ancien facteur
    empirique ne corrigeait que les pence : le DCF de ces valeurs était faussé de l'écart de change
    (environ 33 % pour l'USD), et la valeur d'entreprise mélangeait une capitalisation en livres avec
    une dette en pence, ce qui faussait d'un facteur ~100 les comparables VE/EBITDA de toutes les
    valeurs de Londres."""
    info = _get_ticker_info(ticker)
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    price_scale, market_cap_scale = _statement_to_price_units(info)

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

    total_debt = (info.get("totalDebt") or 0) * price_scale
    total_cash = (info.get("totalCash") or 0) * price_scale
    market_cap = info.get("marketCap")
    # Recalculée plutôt que lue sur Ticker.info["enterpriseValue"], et entièrement dans l'unité du
    # cours : la capitalisation Yahoo est en devise principale (livres, pas pence), d'où son propre
    # facteur, la dette nette étant déjà convertie ci-dessus. Le ratio enterpriseToEbitda, sans
    # dimension, est gardé tel quel.
    enterprise_value = (market_cap * market_cap_scale + total_debt - total_cash) if market_cap else None
    return {
        "fcf": fcf,
        "fcf_history": fcf_history_records,
        "total_debt": total_debt,
        "total_cash": total_cash,
        "shares_outstanding": info.get("sharesOutstanding"),
        "price": price,
        "currency": info.get("currency") or "N/A",
        "enterprise_value": enterprise_value,
        "ev_to_ebitda": info.get("enterpriseToEbitda"),
    }


# ============================================================
# RECHERCHE DE TITRES (champ « Ajouter des titres »)
# ============================================================

# Bourses écartées des résultats : marchés hors cote américains (PNK, OQB, OQX), certificats canadiens
# (NEO) et lignes de réplication (DXE) d'un titre déjà coté sur son marché principal. Elles doublonnent
# la cotation d'origine sans apporter de comptes ni d'historique propres.
SEARCH_EXCLUDED_EXCHANGES = {"PNK", "OQB", "OQX", "NEO", "DXE"}
SEARCH_MAX_RESULTS = 12


@cached_ttl(STATEMENTS_TTL_SECONDS)
def _search_quotes(query: str) -> list:
    return yf.Search(query, max_results=SEARCH_MAX_RESULTS, news_count=0).quotes


def search_equities(query: str | None) -> list[dict]:
    """Actions cotées dont le nom ou le ticker correspond à query, selon la recherche de Yahoo :
    [{"ticker", "name", "exchange"}], dans l'ordre de pertinence de Yahoo. Une même société cotée sur
    plusieurs places apparaît une fois par place (Paris, Xetra, Londres...) : à l'utilisateur de choisir
    la sienne, la place indiquée à côté. Liste vide sous deux caractères ou si Yahoo ne répond pas."""
    query = (query or "").strip()
    if len(query) < 2:
        return []
    try:
        quotes = _search_quotes(query.lower())
    except Exception:
        return []
    results = []
    for quote in quotes:
        symbol = quote.get("symbol")
        if not symbol or quote.get("quoteType") != "EQUITY" or quote.get("exchange") in SEARCH_EXCLUDED_EXCHANGES:
            continue
        results.append({"ticker": symbol, "name": quote.get("longname") or quote.get("shortname") or symbol,
                        "exchange": quote.get("exchDisp") or quote.get("exchange") or ""})
    return results
