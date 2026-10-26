"""
Moteur de calcul pur pour le portefeuille réel (reconstruction de valeur, plan de
rééquilibrage, totaux). Aucune dépendance sur sqlite3/yfinance/Dash : c'est ce que
couvre test_portfolio_engine.py. Les fonctions ici prennent des DataFrames déjà
chargés (portfolio_db.get_transactions()/get_dividends()) et des séries de prix déjà
récupérées (market_data.get_daily_price_history()) -- aucun accès disque ou réseau.
"""
import datetime as dt
import math
from collections.abc import Sequence
from typing import cast

import numpy as np
import pandas as pd

from constants import (
    INDEX_NAME_KEYWORDS, PEA_CONTRIBUTION_CAP, PEA_EARLY_WITHDRAWAL_TAX_RATE, PEA_MATURITY_YEARS, PEA_TAX_RATE,
    STOCK_INDEX_KEY, TICKERS, TICKERS_UNDERLYING, UNDERLYING_INDICES, UNKNOWN_INDEX_KEY,
)
from engine import cap_schedule, overflow_schedule

# Date acceptée en entrée : chaîne ISO (format stocké en base), date ou Timestamp -- toujours
# normalisée via pd.Timestamp avant tout calcul.
DateLike = str | dt.date | pd.Timestamp

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
    return tx.groupby("ticker")["quantity"].sum().reset_index()


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
        prices = price_history.get(str(ticker))
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


def purchase_points(transactions: pd.DataFrame, equity_curve: pd.Series) -> list[tuple[pd.Timestamp, float, float]]:
    """Points d'achat à poser sur la courbe de valeur : (date, valeur de la courbe ce jour-là, montant
    acheté), un point par jour d'achat (achats du même jour additionnés). Un achat un jour sans cotation
    prend le premier jour coté suivant, comme dans reconstruct_equity_curve ; un achat après le dernier
    point de la courbe est écarté (rien où le poser)."""
    if transactions.empty or equity_curve.empty:
        return []
    curve = equity_curve.copy()
    curve.index = pd.to_datetime(curve.index)
    if curve.index.tz is not None:
        curve.index = curve.index.tz_localize(None)
    curve = curve.sort_index()
    by_day = transactions.assign(day=pd.to_datetime(transactions["date"]).dt.normalize()).groupby("day")["amount_eur"].sum()
    points = []
    for day, amount in by_day.items():
        pos = int(curve.index.searchsorted(pd.Timestamp(cast(str, day))))
        if pos < len(curve):
            points.append((cast(pd.Timestamp, curve.index[pos]), float(curve.iloc[pos]), float(amount)))
    return points


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


def allocate_contribution(target_weights: pd.DataFrame, current_values_by_ticker: pd.Series,
                          amount: float) -> tuple[pd.DataFrame, dict]:
    """Répartit un versement à venir pour se rapprocher des poids cibles SANS VENDRE (une vente en
    PEA n'est pas neutre, voir compute_rebalancing_plan) : rééquilibrage par les flux.

    Valeur cible de chaque ligne = poids cible x (portefeuille actuel + versement). Le versement
    remonte les lignes sous-pondérées au même ratio r = valeur / valeur cible, en commençant par
    les plus éloignées : on cherche r tel que la somme des max(0, r x cible - valeur) égale le
    versement (dichotomie, la somme croît avec r). Comme les lignes sur-pondérées ne reçoivent rien,
    les manques cumulés dépassent toujours le versement : r reste <= 1 et aucune ligne ne dépasse sa
    cible. Une ligne détenue sans poids cible ne reçoit rien.

    Renvoie (lignes : ticker, target_pct, current_pct, contribution_eur, after_pct, triées par
    versement décroissant ; résumé : deviation_before_pt / deviation_after_pt = écart absolu moyen
    aux cibles, en points). Lignes vides sans poids cible ou sans versement positif."""
    columns = ["ticker", "target_pct", "current_pct", "contribution_eur", "after_pct"]
    empty_summary = {"deviation_before_pt": None, "deviation_after_pt": None}
    if target_weights.empty or amount is None or amount <= 0:
        return pd.DataFrame(columns=columns), empty_summary
    total_weight = float(target_weights["weight_pct"].sum())
    if total_weight <= 0:
        return pd.DataFrame(columns=columns), empty_summary
    weights = {t: float(w) / total_weight for t, w in zip(target_weights["ticker"], target_weights["weight_pct"])}
    values = {str(t): float(v) for t, v in current_values_by_ticker.dropna().items()}
    tickers = sorted(set(weights) | set(values))
    current_total = sum(values.values())
    after_total = current_total + amount
    targets = {t: weights.get(t, 0.0) * after_total for t in tickers}

    def needed(ratio: float) -> float:
        return sum(max(0.0, ratio * targets[t] - values.get(t, 0.0)) for t in tickers)

    low, high = 0.0, 1.0
    if needed(high) <= amount:
        ratio = high
    else:
        for _ in range(100):
            mid = (low + high) / 2
            low, high = (mid, high) if needed(mid) < amount else (low, mid)
        ratio = (low + high) / 2
    contributions = {t: max(0.0, ratio * targets[t] - values.get(t, 0.0)) for t in tickers}
    # Ajustement final : la dichotomie laisse un reste de quelques centimes, rendu à la plus grosse ligne.
    leftover = amount - sum(contributions.values())
    if abs(leftover) > 1e-9:
        biggest = max(contributions, key=lambda t: contributions[t])
        contributions[biggest] += leftover

    rows = []
    for t in tickers:
        current_value = values.get(t, 0.0)
        rows.append((
            t, weights.get(t, 0.0) * 100,
            current_value / current_total * 100 if current_total else 0.0,
            contributions[t], (current_value + contributions[t]) / after_total * 100,
        ))
    df = pd.DataFrame(rows, columns=columns).sort_values(["contribution_eur", "target_pct"], ascending=False)
    summary = {
        "deviation_before_pt": float((df["current_pct"] - df["target_pct"]).abs().mean()),
        "deviation_after_pt": float((df["after_pct"] - df["target_pct"]).abs().mean()),
    }
    return df.reset_index(drop=True), summary


def line_contributions(transactions: pd.DataFrame, dividends: pd.DataFrame,
                       current_values_by_ticker: pd.Series) -> pd.DataFrame:
    """Ce que chaque ligne a rapporté depuis son achat, en euros : valeur actuelle + dividendes
    perçus - montant investi (frais compris). gain_pct rapporte ce gain au montant investi de la
    ligne. Une ligne sans cours garde value_eur, gain_eur et gain_pct à NaN (jamais 0 : ce serait
    une fausse perte totale), rangée en dernier. Colonnes ticker, cost_eur, value_eur,
    dividends_eur, gain_eur, gain_pct ; triées du plus gros gain à la plus grosse perte."""
    columns = ["ticker", "cost_eur", "value_eur", "dividends_eur", "gain_eur", "gain_pct"]
    if transactions.empty:
        return pd.DataFrame(columns=columns)
    costs: dict[str, float] = {}
    for _, row in transactions.iterrows():
        costs[str(row["ticker"])] = costs.get(str(row["ticker"]), 0.0) + _purchase_cost(row)
    received = dividends.groupby("ticker")["amount_eur"].sum() if not dividends.empty else pd.Series(dtype=float)
    rows = []
    for ticker, cost in costs.items():
        value = current_values_by_ticker.get(ticker)
        value = float(value) if value is not None and not pd.isna(value) else np.nan
        dividends_eur = float(received.get(ticker, 0.0))
        gain = value + dividends_eur - cost
        rows.append((ticker, cost, value, dividends_eur, gain, gain / cost if cost > 0 else np.nan))
    df = pd.DataFrame(rows, columns=columns)
    return df.sort_values("gain_eur", ascending=False, na_position="last").reset_index(drop=True)


def dividend_calendar(received: pd.DataFrame, per_share_by_ticker: dict[str, pd.Series], holdings: pd.DataFrame,
                      today: DateLike, months: int = 12) -> pd.DataFrame:
    """Calendrier mensuel des dividendes : perçus sur les `months` derniers mois (saisis par
    l'utilisateur), estimés sur les `months` prochains.

    Estimation : pour chaque ligne détenue, chaque dividende par part détaché sur les 12 derniers
    mois est supposé revenir au même mois l'an prochain, multiplié par le nombre de parts actuel
    (convention « 12 derniers mois x parts »). Une ligne absente de per_share_by_ticker (Yahoo
    indisponible) n'est pas estimée, plutôt qu'estimée à 0 ; une série vide (capitalisation) ne
    produit rien. Colonnes month (1er du mois), ticker, amount_eur, kind ("received" ou "estimated")."""
    columns = ["month", "ticker", "amount_eur", "kind"]
    today = pd.Timestamp(today).normalize()
    this_month = today.replace(day=1)
    first_month = this_month - pd.DateOffset(months=months - 1)
    horizon = this_month + pd.DateOffset(months=months + 1)
    rows = []
    if not received.empty:
        past = received.assign(date=pd.to_datetime(received["date"]))
        past = past[(past["date"] >= first_month) & (past["date"] <= today)]
        for _, row in past.iterrows():
            rows.append((pd.Timestamp(row["date"]).replace(day=1), str(row["ticker"]), float(row["amount_eur"]),
                         "received"))
    quantities = dict(zip(holdings["ticker"], holdings["quantity"])) if not holdings.empty else {}
    for ticker, per_share in per_share_by_ticker.items():
        quantity = float(quantities.get(ticker, 0.0))
        if quantity <= 0 or per_share is None or per_share.empty:
            continue
        dates = pd.DatetimeIndex(pd.to_datetime(per_share.index))
        recent = (dates > today - pd.DateOffset(years=1)) & (dates <= today)
        for date, amount in zip(dates[recent], per_share.to_numpy(dtype=float)[recent]):
            next_date = pd.Timestamp(date) + pd.DateOffset(years=1)
            if today < next_date < horizon:
                rows.append((next_date.replace(day=1), ticker, float(amount) * quantity, "estimated"))
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df
    grouped = df.groupby(["month", "ticker", "kind"], as_index=False).agg(amount_eur=("amount_eur", "sum"))
    return grouped[columns].sort_values(by=["month", "ticker"]).reset_index(drop=True)


OTHER_ALLOCATION_KEY = "__other__"


def allocation_slices(current_values: pd.Series, max_slices: int) -> pd.DataFrame:
    """Répartition actuelle du portefeuille réel pour un graphique en anneau : une ligne par ticker
    (colonnes key, value, share), de la plus grosse à la plus petite. Au-delà de max_slices lignes,
    les plus petites sont regroupées dans une seule part OTHER_ALLOCATION_KEY, rangée en dernier :
    au-delà de quelques parts, un anneau devient illisible et les couleurs se répètent. Les lignes
    sans valeur (cours indisponible) ou de valeur nulle sont écartées, pas comptées pour 0 : c'est à
    l'appelant de signaler les lignes manquantes."""
    values = current_values.dropna()
    values = values[values > 0].sort_values(ascending=False)
    if values.empty:
        return pd.DataFrame(columns=["key", "value", "share"])
    if len(values) > max_slices:
        kept = values.iloc[:max_slices - 1]
        values = pd.concat([kept, pd.Series({OTHER_ALLOCATION_KEY: float(values.iloc[max_slices - 1:].sum())})])
    total = float(values.sum())
    return pd.DataFrame({"key": [str(k) for k in values.index], "value": values.to_numpy(dtype=float),
                         "share": values.to_numpy(dtype=float) / total})


def target_vs_actual_shares(current_values: pd.Series, target_weights: pd.DataFrame, max_slices: int) -> pd.DataFrame:
    """Part actuelle et part cible de chaque ticker (colonnes key, actual, target), pour comparer les deux
    répartitions. Parts cibles ramenées à un total de 100 % (l'avertissement « pondérations ≠ 100 % »
    est affiché à part), une ligne détenue sans cible ou ciblée sans être détenue a une part nulle de
    l'autre côté. Tri par la plus grande des deux parts ; au-delà de max_slices tickers, les plus
    petits sont regroupés dans OTHER_ALLOCATION_KEY."""
    values = current_values.dropna()
    values = values[values > 0]
    targets = (target_weights.set_index("ticker")["weight_pct"].astype(float) if not target_weights.empty
               else pd.Series(dtype=float))
    targets = targets[targets > 0]
    if values.empty or targets.empty:
        return pd.DataFrame(columns=["key", "actual", "target"])
    keys = sorted(set(values.index) | set(targets.index))
    frame = pd.DataFrame({
        "key": [str(k) for k in keys],
        "actual": [float(values.get(k, 0.0)) / float(values.sum()) for k in keys],
        "target": [float(targets.get(k, 0.0)) / float(targets.sum()) for k in keys],
    })
    frame = frame.assign(_size=frame[["actual", "target"]].max(axis=1)).sort_values("_size", ascending=False)
    frame = frame.drop(columns="_size").reset_index(drop=True)
    if len(frame) > max_slices:
        head, tail = frame.iloc[:max_slices - 1], frame.iloc[max_slices - 1:]
        other = pd.DataFrame([{"key": OTHER_ALLOCATION_KEY, "actual": float(tail["actual"].sum()),
                               "target": float(tail["target"].sum())}])
        frame = pd.concat([head, other], ignore_index=True)
    return frame


_TICKER_TO_UNDERLYING: dict[str, str] = {
    ticker: TICKERS_UNDERLYING[name] for name, tickers in TICKERS.items() for ticker in tickers.values()
}


def detect_underlying_index(ticker: str, name: str | None, quote_type: str | None) -> str:
    """Indice suivi par une ligne : ETF de l'univers de simulation (constants.TICKERS) d'abord, puis
    action individuelle (quoteType Yahoo « EQUITY »), puis mots-clés du nom du fonds
    (constants.INDEX_NAME_KEYWORDS), sinon UNKNOWN_INDEX_KEY. Un résultat faux se corrige à la main
    (voir resolve_underlying_indices) : c'est une aide, pas une vérité."""
    if ticker in _TICKER_TO_UNDERLYING:
        return _TICKER_TO_UNDERLYING[ticker]
    if quote_type == "EQUITY":
        return STOCK_INDEX_KEY
    upper = f" {(name or '').upper()} "
    for index_name, keywords in INDEX_NAME_KEYWORDS:
        if any(keyword in upper for keyword in keywords):
            return index_name
    return UNKNOWN_INDEX_KEY


def resolve_underlying_indices(detected: dict[str, str], overrides: dict[str, str]) -> dict[str, str]:
    """Indice retenu par ticker : la correction manuelle l'emporte sur la détection."""
    return {ticker: overrides.get(ticker, index_key) for ticker, index_key in detected.items()}


def exposure_by_index(current_values: pd.Series, index_of: dict[str, str]) -> pd.DataFrame:
    """Valeur et part du portefeuille par indice suivi (colonnes key, value, share, tickers), de la plus
    grosse à la plus petite. Même règle que allocation_slices : une ligne sans valeur est écartée."""
    values = current_values.dropna()
    values = values[values > 0]
    if values.empty:
        return pd.DataFrame(columns=["key", "value", "share", "tickers"])
    groups: dict[str, list[str]] = {}
    for ticker in values.index:
        groups.setdefault(index_of.get(str(ticker), UNKNOWN_INDEX_KEY), []).append(str(ticker))
    total = float(values.sum())
    rows = [{"key": key, "value": float(values[tickers].sum()), "tickers": sorted(tickers)}
            for key, tickers in groups.items()]
    frame = pd.DataFrame(rows).sort_values("value", ascending=False, ignore_index=True)
    frame["share"] = frame["value"] / total
    return frame[["key", "value", "share", "tickers"]]


def duplicate_index_exposures(exposure: pd.DataFrame) -> pd.DataFrame:
    """Indices suivis par au moins deux lignes : doublons sans diversification entre eux. Les actions
    individuelles et les lignes non identifiées ne forment pas un indice et sont exclues."""
    if exposure.empty:
        return exposure
    mask = exposure["tickers"].map(len).ge(2) & ~exposure["key"].isin([STOCK_INDEX_KEY, UNKNOWN_INDEX_KEY])
    return exposure[mask].reset_index(drop=True)


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
# Performance réelle : XIRR, TWR, indice de référence
# ============================================================
# Conventions communes, alignées sur compute_totals :
# - Un achat coûte amount_eur + fee_eur (le cash réellement sorti), mais seul amount_eur devient
#   des parts (quantité = amount_eur / price, voir reconstruct_holdings) : les frais pèsent donc
#   sur la performance au lieu d'être ignorés.
# - Un dividende est un flux de trésorerie PERÇU à sa date (cash sur le compte PEA), pas
#   réinvesti : le modèle ne crée aucune part à partir d'un dividende, comme compute_totals.
#   Ce cash compte dans le rendement (sinon un ETF distribuant paraîtrait moins bon qu'un ETF
#   capitalisant à performance égale), mais n'est pas réintégré dans la courbe de valeur, d'où
#   son ajout explicite ci-dessous.
# La courbe de valeur (reconstruct_equity_curve) doit donc être valorisée aux cours BRUTS (non
#   ajustés des dividendes, voir market_data.get_daily_price_history) : des cours ajustés
#   intègrent déjà les dividendes passés, qui seraient alors comptés deux fois.


def _year_fraction(start: pd.Timestamp, end: pd.Timestamp) -> float:
    return (end - start).days / 365.0


def _purchase_cost(row: pd.Series) -> float:
    """amount_eur + fee_eur d'une ligne d'achat, frais absents (None/NaN) comptés à 0."""
    fee = row.get("fee_eur")
    return float(row["amount_eur"]) + (0.0 if fee is None or pd.isna(fee) else float(fee))


# En dessous d'un an d'historique, un rendement annualisé (XIRR, TWR) extrapole quelques semaines à
# une année entière : quelques pourcents sur deux mois deviennent des dizaines de pourcents par an.
# L'écran affiche alors le gain de la période (period_gain) en valeur principale.
SHORT_HISTORY_YEARS = 1.0


def invested_cost(transactions: pd.DataFrame) -> float:
    """Montant investi, frais compris : somme des amount_eur + fee_eur des achats."""
    return float(sum(_purchase_cost(row) for _, row in transactions.iterrows()))


def history_years(transactions: pd.DataFrame, valuation_date: DateLike) -> float | None:
    """Durée en années entre le premier achat et valuation_date (même base exact/365 que xirr).
    None sans transaction."""
    if transactions.empty:
        return None
    first = pd.to_datetime(transactions["date"]).min()
    return _year_fraction(first, pd.Timestamp(valuation_date))


def period_gain(final_value: float, dividends_total: float, cost: float) -> float | None:
    """Gain de la période rapporté au montant investi : (valeur finale + dividendes perçus - coût)
    / coût, en fraction. Non annualisé, et sans biais pour des achats échelonnés : c'est ce que
    l'argent versé a rapporté jusqu'ici. Le même calcul s'applique au portefeuille fictif de la
    référence (dividendes à 0, déjà réinvestis dans ses cours ajustés), pour comparer les deux.
    None si rien n'a été investi."""
    if cost <= 0:
        return None
    return (final_value + dividends_total - cost) / cost


def xirr(cash_flows: Sequence[tuple[DateLike, float]]) -> float | None:
    """Taux de rendement annuel r (base exact/365) qui annule la valeur actuelle des flux datés
    [(date, montant), ...] -- négatif = sortie de cash (achat), positif = entrée (dividende,
    valeur finale). Rendement "pondéré par les flux" (money-weighted) : il dépend du moment où
    l'argent a été investi, contrairement au TWR.

    Résolu par dichotomie plutôt que par Newton (pas de scipy dans les dépendances) : la VAN est
    décroissante en r dès que les sorties précèdent les entrées, donc un changement de signe sur
    [-99,99 %, +1000 %] suffit à garantir la convergence. None s'il y a moins de 2 flux, si tous
    les flux sont de même signe, ou si aucun taux de cet intervalle n'annule la VAN."""
    if len(cash_flows) < 2:
        return None
    flows = sorted((pd.Timestamp(d), float(a)) for d, a in cash_flows)
    amounts = [a for _, a in flows]
    if all(a >= 0 for a in amounts) or all(a <= 0 for a in amounts):
        return None
    t0 = flows[0][0]
    years = [_year_fraction(t0, d) for d, _ in flows]

    def npv(rate: float) -> float:
        return sum(a / (1 + rate) ** y for a, y in zip(amounts, years))

    low, high = -0.9999, 10.0
    npv_low, npv_high = npv(low), npv(high)
    if npv_low * npv_high > 0:
        return None
    for _ in range(200):
        mid = (low + high) / 2
        npv_mid = npv(mid)
        if npv_low * npv_mid <= 0:
            high = mid
        else:
            low, npv_low = mid, npv_mid
        if high - low < 1e-10:
            break
    return (low + high) / 2


def portfolio_cash_flows(transactions: pd.DataFrame, dividends: pd.DataFrame, current_value_eur: float,
                         valuation_date: DateLike) -> list[tuple[pd.Timestamp, float]]:
    """Flux datés du portefeuille réel pour xirr : chaque achat -(amount_eur + fee_eur), chaque
    dividende +amount_eur, et la valeur actuelle comme flux final positif à valuation_date (comme
    si tout était revendu ce jour-là, avant toute fiscalité). Liste vide sans transaction."""
    if transactions.empty:
        return []
    flows = [
        (pd.Timestamp(row["date"]), -_purchase_cost(row))
        for _, row in transactions.iterrows()
    ]
    if not dividends.empty:
        flows += [(pd.Timestamp(row["date"]), float(row["amount_eur"])) for _, row in dividends.iterrows()]
    flows.append((pd.Timestamp(valuation_date), float(current_value_eur)))
    return flows


def _external_flows_by_curve_date(curve_index: pd.DatetimeIndex, transactions: pd.DataFrame,
                                   dividends: pd.DataFrame) -> pd.Series:
    """Flux externes regroupés sur la date de cotation où ils prennent effet dans la courbe de
    valeur : le premier jour coté à partir de leur date (reconstruct_equity_curve fait entrer un
    achat d'un jour non coté au jour coté suivant), ou le dernier jour de la courbe s'il n'y en a
    plus. Achat = +(amount_eur + fee_eur) injecté ; dividende = -amount_eur sorti de la position
    (vers le cash), d'où le signe opposé."""
    flows = pd.Series(0.0, index=curve_index)

    def add(date: DateLike, amount: float) -> None:
        pos = int(curve_index.searchsorted(pd.Timestamp(date)))
        flows.iloc[min(pos, len(curve_index) - 1)] += amount

    for _, row in transactions.iterrows():
        add(row["date"], _purchase_cost(row))
    if not dividends.empty:
        for _, row in dividends.iterrows():
            add(row["date"], -float(row["amount_eur"]))
    return flows


def time_weighted_return(equity_curve: pd.Series, transactions: pd.DataFrame,
                         dividends: pd.DataFrame) -> dict | None:
    """Rendement pondéré par le temps (TWR) : rendements des sous-périodes séparées par chaque date
    de flux, chaînés -- neutralise l'effet du calendrier des versements (un gros versement juste
    avant une baisse ne pénalise pas le TWR), donc mesure la qualité des placements eux-mêmes, là
    où le XIRR mesure l'expérience réelle de l'investisseur.

    Sur chaque sous-période (date de flux précédente -> date de flux suivante, sur la courbe) :
    r = (V_fin - flux_externe_fin) / V_début - 1, où V_fin inclut déjà les parts achetées ce
    jour-là (voir _external_flows_by_curve_date) ; les frais, injectés sans créer de parts,
    pèsent donc sur la sous-période où ils sont payés. Renvoie {"twr", "twr_annualized",
    "n_years"} (fractions, pas %), ou None sans courbe exploitable."""
    curve = equity_curve.dropna()
    if curve.empty or transactions.empty:
        return None
    curve.index = pd.to_datetime(curve.index)
    flows = _external_flows_by_curve_date(curve.index, transactions, dividends)

    flow_dates = list(flows.index[flows != 0])
    start = flow_dates[0]
    boundaries = flow_dates + ([curve.index[-1]] if curve.index[-1] != flow_dates[-1] else [])
    growth = 1.0
    for prev, nxt in zip(boundaries[:-1], boundaries[1:]):
        v_start = float(curve.loc[prev])
        if v_start <= 0:
            continue
        growth *= (float(curve.loc[nxt]) - float(flows.loc[nxt])) / v_start
    n_years = _year_fraction(start, curve.index[-1])
    twr = growth - 1
    twr_annualized = growth ** (1 / n_years) - 1 if n_years > 0 and growth > 0 else None
    return {"twr": twr, "twr_annualized": twr_annualized, "n_years": n_years}


def benchmark_equity_curve(transactions: pd.DataFrame, benchmark_prices: pd.Series) -> pd.Series:
    """Portefeuille fictif : les MÊMES achats (mêmes dates, mêmes amount_eur) investis dans un
    ticker de référence, au cours de clôture du premier jour coté à partir de chaque date. Les
    frais réels (fee_eur) restent dans les flux de comparaison (voir benchmark_cash_flows), pour
    comparer à coût identique. benchmark_prices est censé être ajusté des dividendes (dividendes
    réinvestis, convention usuelle d'un indice de référence "dividendes réinvestis", voir
    market_data.get_daily_total_return_history). Série vide sans transaction ni prix."""
    prices = benchmark_prices.dropna()
    if transactions.empty or prices.empty:
        return pd.Series(name="value", dtype=float)
    prices = prices.copy()
    prices.index = pd.to_datetime(prices.index)
    if prices.index.tz is not None:
        prices.index = prices.index.tz_localize(None)
    units = pd.Series(0.0, index=prices.index)
    for _, row in transactions.iterrows():
        pos = int(prices.index.searchsorted(pd.Timestamp(row["date"])))
        if pos >= len(prices):
            continue
        units.iloc[pos] += float(row["amount_eur"]) / float(prices.iloc[pos])
    held = units.cumsum()
    first = held[held > 0].index.min()
    return (held * prices).loc[first:].rename("value")


def benchmark_cash_flows(transactions: pd.DataFrame, benchmark_final_value: float,
                         valuation_date: DateLike) -> list[tuple[pd.Timestamp, float]]:
    """Flux du portefeuille fictif pour xirr : les mêmes sorties que le réel -(amount_eur +
    fee_eur), aucun dividende séparé (déjà réinvestis dans les cours ajustés), et la valeur
    finale du portefeuille fictif à valuation_date."""
    if transactions.empty:
        return []
    flows = [
        (pd.Timestamp(row["date"]), -_purchase_cost(row))
        for _, row in transactions.iterrows()
    ]
    flows.append((pd.Timestamp(valuation_date), float(benchmark_final_value)))
    return flows


# ============================================================
# Import CSV (validation structurelle uniquement : pas de vérification réseau du ticker, qui vit
# dans callbacks/portefeuille_reel.py et market_data.py -- cette couche ne fait que garantir qu'une ligne est
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
    module, voir market_data.resolve_isin_to_ticker + callbacks/portefeuille_reel.py, import_csv). None si le fichier ne
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
        line = cast(int, i) + 2
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
    ligne, code_erreur) -- le code erreur est traduit par l'appelant (voir callbacks/portefeuille_reel.py), cette
    couche reste indépendante de la langue. numéro_de_ligne compte depuis 2 (1 pour l'en-tête,
    1 pour l'indexation à partir de 1) afin de correspondre à ce que l'utilisateur voit en ouvrant
    le fichier dans un tableur."""
    valid_rows, errors = [], []
    for i, row in df.iterrows():
        line = cast(int, i) + 2
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
        line = cast(int, i) + 2
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


DEFAULT_DRIFT_THRESHOLD_PT = 5.0


def drift_alerts(plan: pd.DataFrame, threshold_pt: float) -> pd.DataFrame:
    """Lignes dont la part actuelle s'écarte de leur cible de plus de threshold_pt points (plan : voir
    compute_rebalancing_plan), de la plus éloignée à la moins éloignée, avec gap_pt (actuel - cible,
    en points) et delta_eur (montant à y diriger, négatif pour une ligne au-dessus de sa cible, que
    les prochains versements doivent alors ignorer : aucune vente proposée)."""
    columns = ["ticker", "current_pct", "target_pct", "gap_pt", "delta_eur"]
    if plan.empty or threshold_pt is None:
        return pd.DataFrame(columns=columns)
    gaps = plan.assign(gap_pt=plan["current_pct"] - plan["target_pct"])
    flagged = gaps[gaps["gap_pt"].abs() > float(threshold_pt)]
    order = flagged["gap_pt"].abs().sort_values(ascending=False).index
    return flagged.loc[order, columns].reset_index(drop=True)


def since_last_visit(snapshots: pd.DataFrame, today: DateLike, current_value: float,
                     current_invested: float) -> dict | None:
    """Évolution depuis le dernier relevé d'un jour ANTÉRIEUR à today (voir
    portfolio_db.record_value_snapshot) : {"day", "value_delta", "market_delta"}. value_delta est la
    variation de valeur, versements compris ; market_delta la part due au marché seul, c'est-à-dire
    la variation de la plus-value (valeur - montant investi). None sans relevé antérieur."""
    if snapshots.empty:
        return None
    today_str = pd.Timestamp(today).strftime("%Y-%m-%d")
    earlier = snapshots[snapshots["day"] < today_str]
    if earlier.empty:
        return None
    last = earlier.iloc[-1]
    return {
        "day": pd.Timestamp(str(last["day"])),
        "value_delta": float(current_value) - float(last["value_eur"]),
        "market_delta": (float(current_value) - float(current_invested))
        - (float(last["value_eur"]) - float(last["invested_eur"])),
    }


READABLE_NAME_MAX_CHARS = 24


def fund_issuer(fund_name: str | None) -> str | None:
    """Émetteur d'un ETF : premier mot de son nom (« AMUNDI PEA S&P 500 » -> « Amundi », « BNP Paribas
    Easy... » -> « BNP »). Sigle court gardé en majuscules."""
    if not fund_name or not fund_name.split():
        return None
    word = fund_name.split()[0].strip(",.")
    return word if len(word) <= 4 and word.isupper() else word.capitalize()


def readable_line_names(index_of: dict[str, str], fund_names: dict[str, str | None]) -> dict[str, str]:
    """Nom court et lisible de chaque ligne pour les graphiques, à la place d'un ticker (« PSP5.PA »)
    ou d'un nom de fonds à rallonge : l'indice suivi pour un ETF (« S&P 500 »), le nom de la société
    pour une action. Deux lignes qui suivent le même indice sont distinguées par leur émetteur
    (« S&P 500 · Amundi », « S&P 500 · BNP »), puis par leur ticker si l'émetteur ne suffit pas.
    index_of : voir resolve_underlying_indices ; fund_names : nom Yahoo de chaque ticker (ou None)."""
    def root(ticker: str) -> str:
        return ticker.split(".")[0]

    def shorten(text: str) -> str:
        text = " ".join(text.split())
        return text if len(text) <= READABLE_NAME_MAX_CHARS else text[:READABLE_NAME_MAX_CHARS - 1].rstrip() + "…"

    base = {}
    for ticker, index_key in index_of.items():
        name = fund_names.get(ticker)
        if index_key in UNDERLYING_INDICES:
            base[ticker] = index_key
        elif name:
            base[ticker] = shorten(name)
        else:
            base[ticker] = root(ticker)
    names = dict(base)
    for label in set(base.values()):
        same = [t for t in base if base[t] == label]
        if len(same) < 2:
            continue
        issuers = {t: fund_issuer(fund_names.get(t)) for t in same}
        distinct = len({issuers[t] for t in same}) == len(same) and all(issuers.values())
        for t in same:
            names[t] = f"{label} · {issuers[t] if distinct else root(t)}"
    return names


def ticker_display_label(ticker: str) -> str:
    """Libellé affiché pour un ticker dans les menus déroulants (voir layout.build_tab3) :
    ajoute le nom de l'indice entre parenthèses quand le ticker correspond à un ETF/indice
    connu de l'univers de simulation (constants.TICKERS), pour lever l'ambiguïté des tickers
    ETF peu parlants (ex: "CW8.PA" -> "CW8.PA (MSCI World)"). Inchangé pour un ticker hors de
    cet univers (le portefeuille réel accepte n'importe quel ticker)."""
    index_name = _TICKER_TO_INDEX_NAME.get(ticker)
    return f"{ticker} ({index_name})" if index_name else ticker


# ============================================================
# Jalons PEA : 5 ans, plafond des versements, fiscalité latente
# ============================================================

def pea_milestones(opening_date: DateLike, today: DateLike, maturity_years: int = PEA_MATURITY_YEARS) -> dict:
    """Date des 5 ans (date d'ouverture + 5 ans, au jour près) et compte à rebours. Une ouverture
    un 29 février tombe au 28 février (pd.DateOffset borne au dernier jour du mois), ce qui reste
    du côté prudent : on n'annonce jamais la maturité un jour trop tôt."""
    opening = pd.Timestamp(opening_date).normalize()
    today = pd.Timestamp(today).normalize()
    maturity_date = opening + pd.DateOffset(years=maturity_years)
    return {
        "opening_date": opening,
        "maturity_date": maturity_date,
        "is_mature": today >= maturity_date,
        "days_remaining": max((maturity_date - today).days, 0),
        "years_held": max(_year_fraction(opening, today), 0.0),
    }


def pea_cap_usage(transactions: pd.DataFrame, monthly_pace: float = 0.0, today: DateLike | None = None,
                  cap: float = PEA_CONTRIBUTION_CAP) -> dict:
    """Part du plafond légal des versements consommée par les versements réels. Les versements
    (dépôts de cash sur le PEA) ne sont pas saisis dans l'appli : les ACHATS (montant + frais, le
    cash réellement sorti) en servent d'approximation -- surestimée si des achats ont été
    financés par des dividendes, qui ne comptent pas comme des versements.

    Réutilise engine.cap_schedule / overflow_schedule (même logique que la simulation) sur les
    achats dans l'ordre chronologique : consumed est ce qui tient sous le plafond, excess ce qui
    l'aurait dépassé (impossible en réalité, donc signe d'une approximation trop grossière ou
    d'une saisie erronée). Si monthly_pace > 0, estime aussi quand le plafond serait atteint en
    continuant au même rythme."""
    if transactions.empty:
        amounts = np.array([])
    else:
        tx = transactions.copy()
        tx["date"] = pd.to_datetime(tx["date"])
        amounts = np.array([_purchase_cost(row) for _, row in tx.sort_values("date").iterrows()])
    consumed = float(cap_schedule(amounts, cap).sum())
    excess = float(overflow_schedule(amounts, cap).sum())
    remaining = cap - consumed
    months_to_cap = math.ceil(remaining / monthly_pace) if monthly_pace > 0 and remaining > 0 else None
    projected_cap_date = (
        pd.Timestamp(today).normalize() + pd.DateOffset(months=months_to_cap)
        if months_to_cap is not None and today is not None else None
    )
    return {
        "cap": cap,
        "consumed": consumed,
        "remaining": remaining,
        "pct": consumed / cap * 100 if cap else 0.0,
        "excess": excess,
        "months_to_cap": months_to_cap,
        "projected_cap_date": projected_cap_date,
    }


def latent_withdrawal_tax(current_value: float, total_dividends: float, cost_basis: float, is_mature: bool,
                          mature_rate: float = PEA_TAX_RATE,
                          early_rate: float = PEA_EARLY_WITHDRAWAL_TAX_RATE) -> dict:
    """Impôt dû si tout était retiré aujourd'hui. Valeur retirée = positions + dividendes perçus en
    cash (restés sur le compte PEA, même convention que la performance réelle). Gain = cette
    valeur - coût des achats (montant + frais) : la formule reste juste même si des dividendes ont
    été réinvestis par un achat (l'achat gonfle le coût d'autant que le cash des dividendes
    gonfle la valeur, les deux s'annulent).

    Après 5 ans : prélèvements sociaux seuls sur le gain (mature_rate). Avant : PFU (early_rate)
    et clôture du plan. En moins-value, aucun impôt -- jamais d'impôt négatif."""
    gross_value = current_value + total_dividends
    gain = gross_value - cost_basis
    rate = mature_rate if is_mature else early_rate
    tax = rate * max(gain, 0.0)
    return {
        "gross_value": gross_value,
        "gain": gain,
        "rate": rate,
        "tax": tax,
        "net_value": gross_value - tax,
        "is_loss": gain < 0,
    }
