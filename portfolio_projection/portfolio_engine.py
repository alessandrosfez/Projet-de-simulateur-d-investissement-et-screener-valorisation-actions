"""
Moteur de calcul pur pour le portefeuille réel (reconstruction de valeur, plan de
rééquilibrage, totaux). Aucune dépendance sur sqlite3/yfinance/Dash : c'est ce que
couvre test_portfolio_engine.py. Les fonctions ici prennent des DataFrames déjà
chargés (portfolio_db.get_transactions()/get_dividends()) et des séries de prix déjà
récupérées (market_data.get_daily_price_history()) -- aucun accès disque ou réseau.
"""
import pandas as pd

from constants import TICKERS

# Ticker (indice brut ou ETF) -> nom de l'indice, pour ticker_display_label ci-dessous.
_TICKER_TO_INDEX_NAME = {}
for _name, _tks in TICKERS.items():
    _TICKER_TO_INDEX_NAME[_tks["indice"]] = _name
    _TICKER_TO_INDEX_NAME[_tks["etf"]] = _name


def reconstruct_holdings(transactions: pd.DataFrame) -> pd.DataFrame:
    """Quantité détenue cumulée par ticker, à partir des achats (amount_eur / price par
    ligne, sommés). Une ligne par ticker, colonnes ticker/quantity. DataFrame vide si
    aucune transaction."""
    if transactions.empty:
        return pd.DataFrame(columns=["ticker", "quantity"])
    tx = transactions.copy()
    tx["quantity"] = tx["amount_eur"] / tx["price"]
    return tx.groupby("ticker", as_index=False)["quantity"].sum()


def reconstruct_equity_curve(transactions: pd.DataFrame, price_history: dict[str, pd.Series]) -> pd.Series:
    """Valeur de marché réelle du portefeuille, jour par jour, depuis la 1ère
    transaction. Pour chaque ticker : la quantité détenue est une fonction "escalier"
    (constante entre deux achats, augmente à chaque transaction) -- reindex(...).ffill()
    la projette sur le calendrier de cotation réel (price_history[ticker] ne fournit des
    prix qu'aux dates où l'instrument a coté), avant de multiplier par le prix du jour.
    Les tickers sont ensuite sommés, alignés sur l'union de leurs calendriers respectifs.
    Série vide si transactions est vide ou si aucun prix n'est disponible."""
    if transactions.empty:
        return pd.Series(name="value", dtype=float)

    tx = transactions.copy()
    tx["quantity"] = tx["amount_eur"] / tx["price"]
    tx["date"] = pd.to_datetime(tx["date"])

    value_by_date = pd.Series(dtype=float)
    for ticker, group in tx.groupby("ticker"):
        prices = price_history.get(ticker)
        if prices is None or prices.empty:
            continue
        prices = prices.copy()
        prices.index = pd.to_datetime(prices.index)
        if prices.index.tz is not None:
            # yfinance renvoie un index tz-aware (fuseau de la place boursière, ex: Europe/Paris) ;
            # les dates de transaction saisies à la main n'ont pas de fuseau -- comparer les deux
            # tels quels lève TypeError ("Invalid comparison between dtype=datetime64[tz] and
            # Timestamp"). La valeur de clôture quotidienne ne dépend pas de l'heure, donc
            # supprimer le fuseau (pas le convertir) est sans perte ici.
            prices.index = prices.index.tz_localize(None)
        held = group.groupby("date")["quantity"].sum().sort_index().cumsum()
        prices = prices[prices.index >= held.index.min()]
        if prices.empty:
            continue
        held_on_price_dates = held.reindex(prices.index.union(held.index)).ffill().reindex(prices.index)
        value_by_date = value_by_date.add(held_on_price_dates * prices, fill_value=0.0)

    return value_by_date.sort_index().rename("value")


def monthly_contribution_schedule(transactions: pd.DataFrame) -> pd.Series:
    """Apports réels mensuels (somme de amount_eur par mois civil), du mois de la 1ère
    transaction au mois courant, mois sans achat inclus (valeur 0) -- le "vrai" calendrier
    de DCA à passer à engine.returns_to_dca. Série vide si aucune transaction."""
    if transactions.empty:
        return pd.Series(dtype=float)
    tx = transactions.copy()
    tx["date"] = pd.to_datetime(tx["date"])
    monthly = tx.set_index("date")["amount_eur"].resample("MS").sum()
    full_index = pd.date_range(monthly.index.min(), pd.Timestamp.today().normalize().replace(day=1), freq="MS")
    return monthly.reindex(full_index, fill_value=0.0)


def compute_rebalancing_plan(target_weights: pd.DataFrame, current_values_by_ticker: pd.Series) -> pd.DataFrame:
    """Compare la pondération CIBLE (target_weights, colonnes ticker/weight_pct, pas
    forcément normalisée à 100) à la répartition RÉELLE actuelle (current_values_by_ticker,
    valeur de marché par ticker), à somme de portefeuille inchangée : traduit l'écart en
    euros, PAS en "il faut vendre" -- une vente en PEA n'est pas fiscalement neutre, donc
    delta_eur se lit comme "montant à rediriger depuis les prochains versements", jamais
    comme une instruction de vente (voir layout/i18n pour le libellé affiché).

    DataFrame vide si target_weights est vide (rien à comparer)."""
    if target_weights.empty:
        return pd.DataFrame(columns=["ticker", "target_pct", "current_pct", "current_value_eur", "delta_eur"])

    total_target = target_weights["weight_pct"].sum()
    normalized_target = dict(zip(
        target_weights["ticker"],
        target_weights["weight_pct"] / total_target * 100 if total_target else target_weights["weight_pct"],
    ))
    total_value = float(current_values_by_ticker.sum()) if not current_values_by_ticker.empty else 0.0

    tickers = sorted(set(normalized_target) | set(current_values_by_ticker.index))
    rows = []
    for ticker in tickers:
        target_pct = normalized_target.get(ticker, 0.0)
        current_value = float(current_values_by_ticker.get(ticker, 0.0))
        current_pct = (current_value / total_value * 100) if total_value else 0.0
        delta_eur = target_pct / 100 * total_value - current_value
        rows.append((ticker, target_pct, current_pct, current_value, delta_eur))

    df = pd.DataFrame(rows, columns=["ticker", "target_pct", "current_pct", "current_value_eur", "delta_eur"])
    return df.sort_values("delta_eur", ascending=False).reset_index(drop=True)


def compute_totals(transactions: pd.DataFrame, dividends: pd.DataFrame, current_value_eur: float) -> dict:
    """Résumé chiffré du portefeuille réel : capital investi (coût d'achat, pas la valeur
    de marché), frais cumulés, dividendes perçus, valeur actuelle et P&L (euros et %).
    P&L calculé contre le capital investi net des frais : les frais ont réellement réduit
    le rendement, les ignorer gonflerait artificiellement la performance affichée."""
    total_invested = float(transactions["amount_eur"].sum()) if not transactions.empty else 0.0
    total_fees = float(transactions["fee_eur"].sum()) if not transactions.empty else 0.0
    total_dividends = float(dividends["amount_eur"].sum()) if not dividends.empty else 0.0

    cost_basis = total_invested + total_fees
    pnl_eur = current_value_eur - cost_basis
    pnl_pct = (pnl_eur / cost_basis * 100) if cost_basis else None

    return {
        "total_invested": total_invested,
        "total_fees": total_fees,
        "total_dividends": total_dividends,
        "current_value": current_value_eur,
        "pnl_eur": pnl_eur,
        "pnl_pct": pnl_pct,
    }


# ============================================================
# Import CSV (validation structurelle uniquement : pas de vérification réseau du ticker, qui vit
# dans callbacks.py/market_data.py -- cette couche ne fait que garantir qu'une ligne est
# exploitable par portfolio_db.insert_*_bulk, pas qu'elle référence un instrument réel.
# ============================================================

TRANSACTION_CSV_COLUMNS = ["ticker", "date", "amount_eur", "price"]
DIVIDEND_CSV_COLUMNS = ["ticker", "date", "amount_eur"]
# Empreinte de colonnes d'un export Trade Republic ("Service > Relevés de compte > Export des
# transactions") : confirmée sur un export réel, pas devinée -- account_type/category/type/symbol
# distinguent sans ambiguïté ce format du schéma maison ci-dessus (qui n'a aucune de ces colonnes).
TRADE_REPUBLIC_CSV_COLUMNS = ["account_type", "category", "type", "symbol", "shares", "price", "amount", "date"]


def detect_csv_kind(df: pd.DataFrame) -> str | None:
    """'transactions'/'dividends' pour le schéma maison (voir TRANSACTION_CSV_COLUMNS/
    DIVIDEND_CSV_COLUMNS), 'trade_republic' pour un export Trade Republic brut (symbol contient un
    ISIN, pas un ticker -- la résolution ISIN -> ticker Yahoo se fait réseau, donc hors de ce
    module, voir market_data.resolve_isin_to_ticker + callbacks.import_csv). None si le fichier ne
    correspond à aucun des trois. Testé dans cet ordre : un fichier ayant les colonnes dividendes
    ET price serait quand même détecté "transactions" en premier."""
    cols = set(df.columns)
    if set(TRANSACTION_CSV_COLUMNS).issubset(cols):
        return "transactions"
    if set(DIVIDEND_CSV_COLUMNS).issubset(cols):
        return "dividends"
    if set(TRADE_REPUBLIC_CSV_COLUMNS).issubset(cols):
        return "trade_republic"
    return None


def extract_trade_republic_buys(df: pd.DataFrame) -> tuple[list[dict], list[tuple[int, str]]]:
    """Isole les achats réels du compte PEA dans un export Trade Republic (account_type == "PEA",
    category == "TRADING", type == "BUY") et les convertit vers notre schéma interne -- toute
    autre ligne (virements, activation PEA, etc.) est silencieusement ignorée, ce n'est pas une
    erreur, juste hors-sujet pour le portefeuille réel (qui ne modélise que les positions, pas la
    trésorerie). Renvoie (lignes, erreurs) ; chaque ligne a une clé "isin" (PAS encore "ticker" --
    la résolution ISIN -> ticker Yahoo est réseau, donc faite par l'appelant, voir
    market_data.resolve_isin_to_ticker).

    amount_eur recalculé depuis shares * price, pas depuis la colonne "amount" du fichier (qui
    arrondit indépendamment et peut légèrement diverger, ex: 7 * 33.901 = 237.307 affiché -237.31) :
    garantit que amount_eur / price reconstruit exactement `shares`, l'invariant dont dépend
    portfolio_engine.reconstruct_holdings."""
    rows, errors = [], []
    for i, row in df.iterrows():
        line = i + 2
        if row.get("account_type") != "PEA" or row.get("category") != "TRADING" or row.get("type") != "BUY":
            continue
        isin = "" if pd.isna(row.get("symbol")) else str(row.get("symbol")).strip()
        if not isin:
            errors.append((line, "missing_ticker"))
            continue
        if pd.isna(row.get("date")):
            errors.append((line, "missing_date"))
            continue
        try:
            parsed_date = pd.to_datetime(row["date"])
        except (ValueError, TypeError):
            errors.append((line, "invalid_date"))
            continue
        shares_raw, price_raw = row.get("shares"), row.get("price")
        if pd.isna(shares_raw) or pd.isna(price_raw):
            errors.append((line, "missing_amount"))
            continue
        try:
            shares = float(shares_raw)
            price = float(price_raw)
        except (TypeError, ValueError):
            errors.append((line, "invalid_amount"))
            continue
        if shares <= 0 or price <= 0:
            errors.append((line, "invalid_amount"))
            continue
        fee_raw = row.get("fee")
        try:
            fee = 0.0 if pd.isna(fee_raw) else abs(float(fee_raw))
        except (TypeError, ValueError):
            fee = 0.0
        rows.append({
            "isin": isin, "date": parsed_date.strftime("%Y-%m-%d"),
            "amount_eur": shares * price, "price": price, "fee_eur": fee,
        })
    return rows, errors


def validate_transactions_rows(df: pd.DataFrame) -> tuple[list[dict], list[tuple[int, str]]]:
    """Valide chaque ligne (ticker/date/montant/prix présents et cohérents -- PAS la validité
    réseau du ticker). Renvoie (lignes_valides, erreurs), erreurs étant une liste de (numéro_de_
    ligne, code_erreur) -- le code erreur est traduit par l'appelant (voir callbacks.py), cette
    couche reste indépendante de la langue. numéro_de_ligne compte depuis 2 (1 pour l'en-tête,
    1 pour l'indexation à partir de 1) afin de correspondre à ce que l'utilisateur voit en ouvrant
    le fichier dans un tableur."""
    valid_rows, errors = [], []
    for i, row in df.iterrows():
        line = i + 2
        ticker = "" if pd.isna(row.get("ticker")) else str(row.get("ticker")).strip().upper()
        if not ticker:
            errors.append((line, "missing_ticker"))
            continue
        if pd.isna(row.get("date")):
            errors.append((line, "missing_date"))
            continue
        try:
            parsed_date = pd.to_datetime(row["date"])
        except (ValueError, TypeError):
            errors.append((line, "invalid_date"))
            continue
        amount_raw, price_raw = row.get("amount_eur"), row.get("price")
        if pd.isna(amount_raw) or pd.isna(price_raw):
            errors.append((line, "missing_amount"))
            continue
        try:
            amount = float(amount_raw)
            price = float(price_raw)
        except (TypeError, ValueError):
            errors.append((line, "invalid_amount"))
            continue
        if amount <= 0 or price <= 0:
            errors.append((line, "invalid_amount"))
            continue
        fee_raw = row.get("fee_eur", 0.0)
        try:
            fee = 0.0 if pd.isna(fee_raw) else float(fee_raw)
        except (TypeError, ValueError):
            fee = 0.0
        valid_rows.append({
            "ticker": ticker, "date": parsed_date.strftime("%Y-%m-%d"),
            "amount_eur": amount, "price": price, "fee_eur": fee,
        })
    return valid_rows, errors


def validate_dividends_rows(df: pd.DataFrame) -> tuple[list[dict], list[tuple[int, str]]]:
    """Même validation que validate_transactions_rows pour le schéma dividendes (pas de prix/frais)."""
    valid_rows, errors = [], []
    for i, row in df.iterrows():
        line = i + 2
        ticker = "" if pd.isna(row.get("ticker")) else str(row.get("ticker")).strip().upper()
        if not ticker:
            errors.append((line, "missing_ticker"))
            continue
        if pd.isna(row.get("date")):
            errors.append((line, "missing_date"))
            continue
        try:
            parsed_date = pd.to_datetime(row["date"])
        except (ValueError, TypeError):
            errors.append((line, "invalid_date"))
            continue
        amount_raw = row.get("amount_eur")
        if pd.isna(amount_raw):
            errors.append((line, "missing_amount"))
            continue
        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            errors.append((line, "invalid_amount"))
            continue
        if amount <= 0:
            errors.append((line, "invalid_amount"))
            continue
        valid_rows.append({"ticker": ticker, "date": parsed_date.strftime("%Y-%m-%d"), "amount_eur": amount})
    return valid_rows, errors


def clamp_to_slider(value: float, minv: float, maxv: float, step: float) -> float:
    """Borne value à [minv, maxv] puis arrondit au multiple de step le plus proche -- évite qu'une
    moyenne réelle hors des bornes d'un dcc.Slider (ex: 42€/mois, ou 50 000€/mois) ne lui soit
    passée telle quelle."""
    clamped = min(max(value, minv), maxv)
    return round(clamped / step) * step


def known_tickers(transactions: pd.DataFrame, dividends: pd.DataFrame, target_weights: pd.DataFrame) -> list[str]:
    """Tickers déjà vus quelque part dans le portefeuille réel (achats, dividendes, pondérations
    cibles), triés -- alimente les options des menus déroulants ticker (voir layout.build_tab3) :
    un raccourci pour resélectionner un titre déjà utilisé, PAS une restriction (un ticker encore
    jamais vu reste saisissable en texte libre, voir le mécanisme "creatable" côté client dans
    app.py)."""
    tickers = set()
    if not transactions.empty:
        tickers |= set(transactions["ticker"])
    if not dividends.empty:
        tickers |= set(dividends["ticker"])
    if not target_weights.empty:
        tickers |= set(target_weights["ticker"])
    return sorted(tickers)


def ticker_display_label(ticker: str) -> str:
    """Libellé affiché pour un ticker dans les menus déroulants (voir layout.build_tab3) :
    ajoute le nom de l'indice entre parenthèses quand le ticker correspond à un ETF/indice
    connu de l'univers de simulation (constants.TICKERS), pour lever l'ambiguïté des tickers
    ETF peu parlants (ex: "CW8.PA" -> "CW8.PA (MSCI World)"). Inchangé pour un ticker hors de
    cet univers (le portefeuille réel accepte n'importe quel ticker)."""
    index_name = _TICKER_TO_INDEX_NAME.get(ticker)
    return f"{ticker} ({index_name})" if index_name else ticker
