"""
Tests unitaires pour le moteur de calcul pur du portefeuille réel (portfolio_engine.py) :
fonctions sans réseau ni dépendance DB/Dash.
Usage : pip install pytest && pytest test_portfolio_engine.py -v
"""
import pandas as pd
import pytest

import portfolio_engine as m


def _tx(ticker, date, amount_eur, price, fee_eur=0.0):
    return {"ticker": ticker, "date": date, "amount_eur": amount_eur, "price": price, "fee_eur": fee_eur}


# ---------- reconstruct_holdings ----------

def test_reconstruct_holdings_sums_quantity_across_purchases():
    transactions = pd.DataFrame([
        _tx("AAA", "2024-01-01", 100.0, 10.0),  # 10 parts
        _tx("AAA", "2024-02-01", 50.0, 10.0),   # 5 parts
        _tx("BBB", "2024-01-01", 200.0, 20.0),  # 10 parts
    ])
    holdings = m.reconstruct_holdings(transactions).set_index("ticker")["quantity"]
    assert holdings["AAA"] == pytest.approx(15.0)
    assert holdings["BBB"] == pytest.approx(10.0)


def test_reconstruct_holdings_empty_transactions():
    result = m.reconstruct_holdings(pd.DataFrame(columns=["ticker", "date", "amount_eur", "price", "fee_eur"]))
    assert result.empty


# ---------- reconstruct_equity_curve ----------

def test_reconstruct_equity_curve_single_ticker_step_function():
    transactions = pd.DataFrame([_tx("AAA", "2024-01-02", 100.0, 10.0)])  # 10 parts
    prices = pd.Series(
        [10.0, 11.0, 12.0],
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
    )
    curve = m.reconstruct_equity_curve(transactions, {"AAA": prices})
    # Avant l'achat (01-01) : aucune position, pas de point dans la courbe.
    assert pd.Timestamp("2024-01-01") not in curve.index
    assert curve[pd.Timestamp("2024-01-02")] == pytest.approx(10 * 11.0)
    assert curve[pd.Timestamp("2024-01-03")] == pytest.approx(10 * 12.0)


def test_reconstruct_equity_curve_sums_across_tickers():
    transactions = pd.DataFrame([
        _tx("AAA", "2024-01-01", 100.0, 10.0),  # 10 parts
        _tx("BBB", "2024-01-01", 100.0, 5.0),   # 20 parts
    ])
    prices_a = pd.Series([10.0], index=pd.to_datetime(["2024-01-01"]))
    prices_b = pd.Series([5.0], index=pd.to_datetime(["2024-01-01"]))
    curve = m.reconstruct_equity_curve(transactions, {"AAA": prices_a, "BBB": prices_b})
    assert curve[pd.Timestamp("2024-01-01")] == pytest.approx(10 * 10.0 + 20 * 5.0)


def test_reconstruct_equity_curve_empty_transactions():
    assert m.reconstruct_equity_curve(pd.DataFrame(columns=["ticker", "date", "amount_eur", "price", "fee_eur"]), {}).empty


def test_reconstruct_equity_curve_missing_price_history_skips_ticker():
    transactions = pd.DataFrame([_tx("AAA", "2024-01-01", 100.0, 10.0)])
    curve = m.reconstruct_equity_curve(transactions, {})
    assert curve.empty


def test_reconstruct_equity_curve_handles_tz_aware_price_history():
    # yfinance renvoie un index tz-aware (fuseau de la place boursière) ; les dates de transaction
    # saisies à la main sont tz-naive -- comparer les deux tels quels lève un TypeError pandas.
    transactions = pd.DataFrame([_tx("AAA", "2024-01-01", 100.0, 10.0)])
    prices = pd.Series([10.0, 11.0], index=pd.to_datetime(["2024-01-01", "2024-01-02"]).tz_localize("Europe/Paris"))
    curve = m.reconstruct_equity_curve(transactions, {"AAA": prices})
    assert curve[pd.Timestamp("2024-01-02")] == pytest.approx(10 * 11.0)


# ---------- monthly_contribution_schedule ----------

def test_monthly_contribution_schedule_fills_gap_months_with_zero():
    transactions = pd.DataFrame([
        _tx("AAA", "2024-01-15", 100.0, 10.0),
        _tx("AAA", "2024-03-05", 50.0, 10.0),  # February skipped
    ])
    schedule = m.monthly_contribution_schedule(transactions)
    assert schedule[pd.Timestamp("2024-01-01")] == pytest.approx(100.0)
    assert schedule[pd.Timestamp("2024-02-01")] == pytest.approx(0.0)
    assert schedule[pd.Timestamp("2024-03-01")] == pytest.approx(50.0)


def test_monthly_contribution_schedule_empty_transactions():
    assert m.monthly_contribution_schedule(pd.DataFrame(columns=["ticker", "date", "amount_eur", "price", "fee_eur"])).empty


# ---------- compute_rebalancing_plan ----------

def test_compute_rebalancing_plan_delta_math():
    target_weights = pd.DataFrame([{"ticker": "AAA", "weight_pct": 60.0}, {"ticker": "BBB", "weight_pct": 40.0}])
    current_values = pd.Series({"AAA": 40.0, "BBB": 60.0})  # total 100, currently inverted
    plan = m.compute_rebalancing_plan(target_weights, current_values).set_index("ticker")
    # Cible 60/100 = 60, actuel 40 -> sous-pondéré de 20 (positif = à renforcer).
    assert plan.loc["AAA", "delta_eur"] == pytest.approx(20.0)
    assert plan.loc["BBB", "delta_eur"] == pytest.approx(-20.0)


def test_compute_rebalancing_plan_normalizes_weights_not_summing_to_100():
    target_weights = pd.DataFrame([{"ticker": "AAA", "weight_pct": 30.0}, {"ticker": "BBB", "weight_pct": 30.0}])
    current_values = pd.Series({"AAA": 50.0, "BBB": 50.0})
    plan = m.compute_rebalancing_plan(target_weights, current_values).set_index("ticker")
    # 30/60 normalisé -> 50% chacun = déjà à l'équilibre, delta nul.
    assert plan.loc["AAA", "target_pct"] == pytest.approx(50.0)
    assert plan.loc["AAA", "delta_eur"] == pytest.approx(0.0)


def test_compute_rebalancing_plan_empty_targets():
    result = m.compute_rebalancing_plan(pd.DataFrame(columns=["ticker", "weight_pct"]), pd.Series(dtype=float))
    assert result.empty


# ---------- compute_totals ----------

def test_compute_totals_pnl_accounts_for_fees():
    transactions = pd.DataFrame([_tx("AAA", "2024-01-01", 100.0, 10.0, fee_eur=1.0)])
    dividends = pd.DataFrame([{"ticker": "AAA", "date": "2024-06-01", "amount_eur": 2.0}])
    totals = m.compute_totals(transactions, dividends, current_value_eur=120.0)
    assert totals["total_invested"] == pytest.approx(100.0)
    assert totals["total_fees"] == pytest.approx(1.0)
    assert totals["total_dividends"] == pytest.approx(2.0)
    # cost basis = 100 + 1 = 101 ; pnl = 120 - 101 = 19
    assert totals["pnl_eur"] == pytest.approx(19.0)
    assert totals["pnl_pct"] == pytest.approx(19.0 / 101.0 * 100)


def test_compute_totals_empty_portfolio_has_none_pnl_pct():
    totals = m.compute_totals(
        pd.DataFrame(columns=["ticker", "date", "amount_eur", "price", "fee_eur"]),
        pd.DataFrame(columns=["ticker", "date", "amount_eur"]),
        current_value_eur=0.0,
    )
    assert totals["pnl_pct"] is None


# ---------- CSV import ----------

def test_detect_csv_kind_transactions():
    df = pd.DataFrame([{"ticker": "AAA", "date": "2024-01-01", "amount_eur": 100.0, "price": 10.0}])
    assert m.detect_csv_kind(df) == "transactions"


def test_detect_csv_kind_dividends():
    df = pd.DataFrame([{"ticker": "AAA", "date": "2024-01-01", "amount_eur": 12.0}])
    assert m.detect_csv_kind(df) == "dividends"


def test_detect_csv_kind_neither():
    df = pd.DataFrame([{"foo": 1, "bar": 2}])
    assert m.detect_csv_kind(df) is None


def test_validate_transactions_rows_accepts_valid_row():
    df = pd.DataFrame([{"ticker": "aaa", "date": "2024-01-15", "amount_eur": 100.0, "price": 10.0, "fee_eur": 1.0}])
    valid_rows, errors = m.validate_transactions_rows(df)
    assert errors == []
    assert valid_rows == [{"ticker": "AAA", "date": "2024-01-15", "amount_eur": 100.0, "price": 10.0, "fee_eur": 1.0}]


def test_validate_transactions_rows_defaults_missing_fee_to_zero():
    df = pd.DataFrame([{"ticker": "AAA", "date": "2024-01-15", "amount_eur": 100.0, "price": 10.0}])
    valid_rows, errors = m.validate_transactions_rows(df)
    assert errors == []
    assert valid_rows[0]["fee_eur"] == 0.0


def test_validate_transactions_rows_rejects_missing_ticker():
    df = pd.DataFrame([{"ticker": None, "date": "2024-01-15", "amount_eur": 100.0, "price": 10.0}])
    valid_rows, errors = m.validate_transactions_rows(df)
    assert valid_rows == []
    assert errors == [(2, "missing_ticker")]


def test_validate_transactions_rows_rejects_invalid_date():
    df = pd.DataFrame([{"ticker": "AAA", "date": "not-a-date", "amount_eur": 100.0, "price": 10.0}])
    valid_rows, errors = m.validate_transactions_rows(df)
    assert valid_rows == []
    assert errors == [(2, "invalid_date")]


def test_validate_transactions_rows_rejects_missing_amount():
    df = pd.DataFrame([{"ticker": "AAA", "date": "2024-01-15", "amount_eur": None, "price": 10.0}])
    valid_rows, errors = m.validate_transactions_rows(df)
    assert errors == [(2, "missing_amount")]


def test_validate_transactions_rows_rejects_non_positive_price():
    df = pd.DataFrame([{"ticker": "AAA", "date": "2024-01-15", "amount_eur": 100.0, "price": 0.0}])
    valid_rows, errors = m.validate_transactions_rows(df)
    assert errors == [(2, "invalid_amount")]


def test_validate_transactions_rows_mixed_valid_and_invalid():
    df = pd.DataFrame([
        {"ticker": "AAA", "date": "2024-01-15", "amount_eur": 100.0, "price": 10.0},
        {"ticker": "BBB", "date": "2024-01-16", "amount_eur": -5.0, "price": 10.0},
    ])
    valid_rows, errors = m.validate_transactions_rows(df)
    assert len(valid_rows) == 1
    assert valid_rows[0]["ticker"] == "AAA"
    assert errors == [(3, "invalid_amount")]


def test_validate_dividends_rows_accepts_valid_row():
    df = pd.DataFrame([{"ticker": "aaa", "date": "2024-06-01", "amount_eur": 12.5}])
    valid_rows, errors = m.validate_dividends_rows(df)
    assert errors == []
    assert valid_rows == [{"ticker": "AAA", "date": "2024-06-01", "amount_eur": 12.5}]


def test_validate_dividends_rows_rejects_non_positive_amount():
    df = pd.DataFrame([{"ticker": "AAA", "date": "2024-06-01", "amount_eur": 0.0}])
    valid_rows, errors = m.validate_dividends_rows(df)
    assert valid_rows == []
    assert errors == [(2, "invalid_amount")]


# ---------- Trade Republic CSV export ----------

def _tr_row(account_type="PEA", category="TRADING", tx_type="BUY", symbol="FR0011550193",
            date="2026-08-17", shares=4.0, price=21.7, amount=-86.80, fee=None):
    return {
        "account_type": account_type, "category": category, "type": tx_type, "symbol": symbol,
        "date": date, "shares": shares, "price": price, "amount": amount, "fee": fee,
    }


def test_detect_csv_kind_trade_republic():
    df = pd.DataFrame([_tr_row()])
    assert m.detect_csv_kind(df) == "trade_republic"


def test_extract_trade_republic_buys_ignores_non_buy_rows():
    # Virement (TRANSFER_IN) et activation PEA (PEA_MARKETING) : hors-sujet, pas des erreurs.
    df = pd.DataFrame([
        _tr_row(category="CASH", tx_type="PEA_MARKETING", symbol="", shares=None, price=None, amount=1.0),
        _tr_row(account_type="DEFAULT", category="CASH", tx_type="TRANSFER_IN", symbol="", shares=None,
                 price=None, amount=100.0),
        _tr_row(),
    ])
    rows, errors = m.extract_trade_republic_buys(df)
    assert errors == []
    assert len(rows) == 1
    assert rows[0]["isin"] == "FR0011550193"


def test_extract_trade_republic_buys_recomputes_amount_from_shares_times_price():
    # La colonne "amount" du fichier (-237.31) arrondit différemment de shares*price (237.307) :
    # on garde shares*price pour que amount_eur / price reconstruise exactement `shares`.
    df = pd.DataFrame([_tr_row(shares=7.0, price=33.901, amount=-237.31, fee=-1.0)])
    rows, errors = m.extract_trade_republic_buys(df)
    assert errors == []
    assert rows[0]["amount_eur"] == pytest.approx(7.0 * 33.901)
    assert rows[0]["fee_eur"] == pytest.approx(1.0)


def test_extract_trade_republic_buys_rejects_non_positive_shares():
    df = pd.DataFrame([_tr_row(shares=0.0)])
    rows, errors = m.extract_trade_republic_buys(df)
    assert rows == []
    assert errors == [(2, "invalid_amount")]


def test_extract_trade_republic_buys_rejects_missing_isin():
    df = pd.DataFrame([_tr_row(symbol="")])
    rows, errors = m.extract_trade_republic_buys(df)
    assert rows == []
    assert errors == [(2, "missing_ticker")]


def test_extract_trade_republic_buys_defaults_missing_fee_to_zero():
    df = pd.DataFrame([_tr_row(fee=None)])
    rows, errors = m.extract_trade_republic_buys(df)
    assert errors == []
    assert rows[0]["fee_eur"] == 0.0


# ---------- clamp_to_slider ----------

def test_clamp_to_slider_within_bounds_rounds_to_step():
    assert m.clamp_to_slider(347.0, 100, 1000, 10) == 350.0


def test_clamp_to_slider_below_min():
    assert m.clamp_to_slider(42.0, 100, 1000, 10) == 100.0


def test_clamp_to_slider_above_max():
    assert m.clamp_to_slider(50_000.0, 100, 1000, 10) == 1000.0


def test_clamp_to_slider_exact_value_unchanged():
    assert m.clamp_to_slider(350.0, 100, 1000, 10) == 350.0


# ---------- known_tickers ----------

def test_known_tickers_union_sorted_and_deduplicated():
    transactions = pd.DataFrame([_tx("BBB", "2024-01-01", 100.0, 10.0)])
    dividends = pd.DataFrame([{"ticker": "AAA", "date": "2024-06-01", "amount_eur": 5.0}])
    target_weights = pd.DataFrame([{"ticker": "AAA", "weight_pct": 50.0}, {"ticker": "CCC", "weight_pct": 50.0}])
    assert m.known_tickers(transactions, dividends, target_weights) == ["AAA", "BBB", "CCC"]


def test_known_tickers_all_empty():
    empty_tx = pd.DataFrame(columns=["ticker", "date", "amount_eur", "price", "fee_eur"])
    empty_div = pd.DataFrame(columns=["ticker", "date", "amount_eur"])
    empty_weights = pd.DataFrame(columns=["ticker", "weight_pct"])
    assert m.known_tickers(empty_tx, empty_div, empty_weights) == []


# ---------- ticker_display_label ----------

def test_ticker_display_label_known_etf_adds_index_name():
    assert m.ticker_display_label("CW8.PA") == "CW8.PA (MSCI World)"


def test_ticker_display_label_known_indice_adds_index_name():
    assert m.ticker_display_label("^GSPC") == "^GSPC (S&P 500)"


def test_ticker_display_label_unknown_ticker_unchanged():
    assert m.ticker_display_label("AAPL") == "AAPL"
