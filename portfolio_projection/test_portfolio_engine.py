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


def test_position_is_worth_the_amount_invested_on_the_purchase_date():
    """Invariant : achetée au cours de clôture du jour, une ligne vaut exactement le montant investi ce
    jour-là. Il suppose prix payé et historique dans la même devise : c'est ce qu'un ETF résolu en
    dollars (VWRA.L) cassait, avant que market_data ne convertisse les cours en euros."""
    closes = pd.Series([95.0, 98.5, 101.0], index=pd.to_datetime(["2024-03-01", "2024-03-04", "2024-03-05"]))
    transactions = pd.DataFrame([_tx("AAA", "2024-03-04", 1000.0, 98.5), _tx("BBB", "2024-03-01", 500.0, 95.0)])
    curve = m.reconstruct_equity_curve(transactions, {"AAA": closes, "BBB": closes})
    assert curve[pd.Timestamp("2024-03-01")] == pytest.approx(500.0)
    assert curve[pd.Timestamp("2024-03-04")] == pytest.approx(1000.0 + 500.0 / 95.0 * 98.5)


def test_allocation_slices_sorted_with_shares_summing_to_one():
    slices = m.allocation_slices(pd.Series({"AAA": 300.0, "BBB": 600.0, "CCC": 100.0}), max_slices=6)
    assert list(slices["key"]) == ["BBB", "AAA", "CCC"]
    assert list(slices["share"]) == pytest.approx([0.6, 0.3, 0.1])


def test_allocation_slices_fold_the_smallest_into_other():
    values = pd.Series({f"T{i}": float(v) for i, v in enumerate([50, 40, 30, 20, 10, 5, 3, 2])})
    slices = m.allocation_slices(values, max_slices=6)
    assert len(slices) == 6
    assert list(slices["key"])[:5] == ["T0", "T1", "T2", "T3", "T4"]
    assert slices["key"].iloc[-1] == m.OTHER_ALLOCATION_KEY
    assert slices["value"].iloc[-1] == pytest.approx(5 + 3 + 2)
    assert slices["share"].sum() == pytest.approx(1.0)


def test_allocation_slices_drop_unpriced_lines_instead_of_counting_zero():
    slices = m.allocation_slices(pd.Series({"AAA": 100.0, "BBB": float("nan"), "CCC": 0.0}), max_slices=6)
    assert list(slices["key"]) == ["AAA"] and slices["share"].iloc[0] == 1.0
    assert m.allocation_slices(pd.Series(dtype=float), max_slices=6).empty


@pytest.mark.parametrize("ticker,name,quote_type,expected", [
    ("PSP5.PA", None, "ETF", "S&P 500"),  # univers de simulation, sans regarder le nom
    ("ETZ.PA", None, "ETF", "Stoxx Europe 600"),
    ("ESE.PA", "BNP Paribas Easy S&P 500 UCITS ETF", "ETF", "S&P 500"),
    ("DCAM.PA", "AMUNDI PEA MONDE MSCI World UCITS ETF", "ETF", "MSCI World"),
    ("PAASI.PA", "Amundi PEA Asie Emergente (MSCI EM Asia) UCITS ETF", "ETF", "MSCI EM Asie"),
    ("VWCE.DE", "Vanguard FTSE All-World UCITS ETF USD Accumulation", "ETF", "FTSE All-World"),
    ("APC.DE", "Apple Inc.", "EQUITY", m.STOCK_INDEX_KEY),
    ("XYZ.PA", "Fonds mystère", "ETF", m.UNKNOWN_INDEX_KEY),
    ("NOPE.PA", None, None, m.UNKNOWN_INDEX_KEY),
])
def test_detect_underlying_index(ticker, name, quote_type, expected):
    assert m.detect_underlying_index(ticker, name, quote_type) == expected


def test_exposure_by_index_groups_duplicates_and_flags_them():
    values = pd.Series({"PSP5.PA": 420.0, "ESE.PA": 312.0, "ETZ.PA": 209.0, "APC.DE": 59.0})
    index_of = m.resolve_underlying_indices(
        {"PSP5.PA": "S&P 500", "ESE.PA": "S&P 500", "ETZ.PA": "Stoxx Europe 600", "APC.DE": m.STOCK_INDEX_KEY},
        overrides={},
    )
    exposure = m.exposure_by_index(values, index_of)
    assert list(exposure["key"]) == ["S&P 500", "Stoxx Europe 600", m.STOCK_INDEX_KEY]
    assert exposure["share"].iloc[0] == pytest.approx(732.0 / 1000.0)
    assert exposure["tickers"].iloc[0] == ["ESE.PA", "PSP5.PA"]
    duplicates = m.duplicate_index_exposures(exposure)
    assert list(duplicates["key"]) == ["S&P 500"]


def test_manual_override_wins_and_stocks_never_count_as_duplicates():
    index_of = m.resolve_underlying_indices({"A": "S&P 500", "B": m.STOCK_INDEX_KEY, "C": m.STOCK_INDEX_KEY},
                                            overrides={"A": "Nasdaq-100"})
    assert index_of["A"] == "Nasdaq-100"
    exposure = m.exposure_by_index(pd.Series({"A": 1.0, "B": 1.0, "C": 1.0}), index_of)
    assert m.duplicate_index_exposures(exposure).empty


def test_target_vs_actual_shares_normalizes_targets_and_keeps_both_sides():
    values = pd.Series({"AAA": 600.0, "BBB": 400.0})
    targets = pd.DataFrame({"ticker": ["AAA", "CCC"], "weight_pct": [40.0, 40.0]})  # total 80 % : ramené à 100
    shares = m.target_vs_actual_shares(values, targets, max_slices=6).set_index("key")
    assert shares.loc["AAA", "actual"] == pytest.approx(0.6) and shares.loc["AAA", "target"] == pytest.approx(0.5)
    assert shares.loc["BBB", "target"] == 0.0  # détenue sans cible
    assert shares.loc["CCC", "actual"] == 0.0  # ciblée sans être détenue
    assert shares["actual"].sum() == pytest.approx(1.0) and shares["target"].sum() == pytest.approx(1.0)


def test_target_vs_actual_shares_folds_small_lines_and_needs_both_sides():
    values = pd.Series({f"T{i}": float(10 - i) for i in range(8)})
    targets = pd.DataFrame({"ticker": [f"T{i}" for i in range(8)], "weight_pct": [12.5] * 8})
    shares = m.target_vs_actual_shares(values, targets, max_slices=6)
    assert len(shares) == 6 and shares["key"].iloc[-1] == m.OTHER_ALLOCATION_KEY
    assert shares["target"].sum() == pytest.approx(1.0)
    assert m.target_vs_actual_shares(values, pd.DataFrame(columns=["ticker", "weight_pct"]), 6).empty


def test_purchase_points_sum_same_day_and_snap_to_next_trading_day():
    curve = pd.Series([100.0, 150.0, 155.0], index=pd.to_datetime(["2024-03-01", "2024-03-04", "2024-03-05"]))
    transactions = pd.DataFrame([
        _tx("AAA", "2024-03-01", 60.0, 10.0), _tx("BBB", "2024-03-01", 40.0, 5.0),
        _tx("AAA", "2024-03-02", 50.0, 10.0),  # samedi : posé sur le lundi 04/03
        _tx("AAA", "2024-04-01", 30.0, 10.0),  # après la courbe : écarté
    ])
    points = m.purchase_points(transactions, curve)
    assert points == [(pd.Timestamp("2024-03-01"), 100.0, 100.0), (pd.Timestamp("2024-03-04"), 150.0, 50.0)]
    assert m.purchase_points(transactions.iloc[0:0], curve) == []


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


# ---------- xirr / portfolio_cash_flows ----------

def test_xirr_single_flow_equals_annualized_return():
    """Un seul versement puis une valeur finale : le XIRR est exactement le rendement annualisé
    (exact/365) entre les deux dates."""
    start, end = pd.Timestamp("2020-01-01"), pd.Timestamp("2023-07-01")
    years = (end - start).days / 365
    final = 1000 * 1.08 ** years
    assert m.xirr([(start, -1000.0), (end, final)]) == pytest.approx(0.08, abs=1e-8)


def test_xirr_regular_flows_at_constant_return_recovers_that_return():
    """Versements mensuels réguliers, chacun capitalisé au même taux annuel jusqu'à la date finale :
    le XIRR doit retrouver ce taux, quel que soit le calendrier des versements."""
    rate = 0.06
    dates = pd.date_range("2018-01-01", periods=36, freq="MS")
    end = pd.Timestamp("2021-06-15")
    final = sum(100 * (1 + rate) ** ((end - d).days / 365) for d in dates)
    flows = [(d, -100.0) for d in dates] + [(end, final)]
    assert m.xirr(flows) == pytest.approx(rate, abs=1e-7)


def test_xirr_negative_return():
    start, end = pd.Timestamp("2022-01-01"), pd.Timestamp("2023-01-01")
    assert m.xirr([(start, -1000.0), (end, 900.0)]) == pytest.approx(-0.10, abs=1e-8)


def test_xirr_undefined_cases_return_none():
    assert m.xirr([]) is None
    assert m.xirr([(pd.Timestamp("2022-01-01"), -1000.0)]) is None
    assert m.xirr([(pd.Timestamp("2022-01-01"), -1000.0), (pd.Timestamp("2023-01-01"), -5.0)]) is None


def test_portfolio_cash_flows_signs_and_fees():
    transactions = pd.DataFrame([_tx("AAA", "2024-01-01", 1000.0, 10.0, fee_eur=2.0)])
    dividends = pd.DataFrame([{"ticker": "AAA", "date": "2024-06-01", "amount_eur": 15.0}])
    flows = m.portfolio_cash_flows(transactions, dividends, 1100.0, "2025-01-01")
    assert flows == [
        (pd.Timestamp("2024-01-01"), -1002.0),
        (pd.Timestamp("2024-06-01"), 15.0),
        (pd.Timestamp("2025-01-01"), 1100.0),
    ]


def test_portfolio_cash_flows_no_transaction():
    empty_tx = pd.DataFrame(columns=["ticker", "date", "amount_eur", "price", "fee_eur"])
    empty_div = pd.DataFrame(columns=["ticker", "date", "amount_eur"])
    assert m.portfolio_cash_flows(empty_tx, empty_div, 0.0, "2025-01-01") == []
    assert m.xirr(m.portfolio_cash_flows(empty_tx, empty_div, 0.0, "2025-01-01")) is None


# ---------- time_weighted_return ----------

def _constant_growth_prices(start, n_days, annual_rate, start_price=100.0):
    dates = pd.date_range(start, periods=n_days, freq="D")
    years = (dates - dates[0]).days / 365
    return pd.Series(start_price * (1 + annual_rate) ** years, index=dates)


def test_twr_independent_of_contribution_timing():
    """Prix à croissance constante : le TWR doit valoir cette croissance, que l'investisseur ait
    versé un peu au début et beaucoup à la fin, ou l'inverse -- c'est précisément ce que le TWR
    neutralise, contrairement au XIRR."""
    prices = _constant_growth_prices("2020-01-01", 3 * 365 + 1, 0.07)
    for amounts in ([100.0, 5000.0], [5000.0, 100.0]):
        transactions = pd.DataFrame([
            _tx("AAA", "2020-01-01", amounts[0], float(prices.loc["2020-01-01"])),
            _tx("AAA", "2021-07-01", amounts[1], float(prices.loc["2021-07-01"])),
        ])
        curve = m.reconstruct_equity_curve(transactions, {"AAA": prices})
        empty_div = pd.DataFrame(columns=["ticker", "date", "amount_eur"])
        result = m.time_weighted_return(curve, transactions, empty_div)
        assert result["twr_annualized"] == pytest.approx(0.07, abs=1e-4)


def test_twr_fees_reduce_return():
    prices = _constant_growth_prices("2020-01-01", 2 * 365 + 1, 0.05)
    empty_div = pd.DataFrame(columns=["ticker", "date", "amount_eur"])
    no_fee = pd.DataFrame([_tx("AAA", "2020-01-01", 1000.0, 100.0)])
    with_fee = pd.DataFrame([
        _tx("AAA", "2020-01-01", 1000.0, 100.0),
        _tx("AAA", "2021-01-01", 1000.0, float(prices.loc["2021-01-01"]), fee_eur=20.0),
    ])
    twr_no_fee = m.time_weighted_return(m.reconstruct_equity_curve(no_fee, {"AAA": prices}), no_fee, empty_div)
    twr_fee = m.time_weighted_return(m.reconstruct_equity_curve(with_fee, {"AAA": prices}), with_fee, empty_div)
    assert twr_fee["twr"] < twr_no_fee["twr"]


def test_twr_dividends_received_in_cash_add_to_return():
    """Un dividende perçu en cash quitte la courbe de valeur (cours bruts) mais reste du rendement :
    le TWR doit être supérieur à la seule croissance des cours."""
    prices = _constant_growth_prices("2020-01-01", 2 * 365 + 1, 0.0)  # cours plats
    transactions = pd.DataFrame([_tx("AAA", "2020-01-01", 1000.0, 100.0)])
    dividends = pd.DataFrame([{"ticker": "AAA", "date": "2021-01-01", "amount_eur": 30.0}])
    curve = m.reconstruct_equity_curve(transactions, {"AAA": prices})
    result = m.time_weighted_return(curve, transactions, dividends)
    assert result["twr"] == pytest.approx(0.03, abs=1e-9)


def test_twr_no_transaction_returns_none():
    empty_tx = pd.DataFrame(columns=["ticker", "date", "amount_eur", "price", "fee_eur"])
    empty_div = pd.DataFrame(columns=["ticker", "date", "amount_eur"])
    assert m.time_weighted_return(pd.Series(dtype=float), empty_tx, empty_div) is None


# ---------- indice de référence ----------

def test_benchmark_same_flows_recovers_benchmark_growth_rate():
    """Les mêmes flux investis dans une référence à croissance constante : le XIRR du portefeuille
    fictif doit retrouver ce taux de croissance (sans frais)."""
    prices = _constant_growth_prices("2019-01-01", 4 * 365 + 1, 0.09)
    transactions = pd.DataFrame([
        _tx("REAL", "2019-01-01", 500.0, 10.0),
        _tx("REAL", "2020-03-15", 800.0, 10.0),
        _tx("REAL", "2021-11-02", 300.0, 10.0),
    ])
    curve = m.benchmark_equity_curve(transactions, prices)
    end = curve.index[-1]
    flows = m.benchmark_cash_flows(transactions, float(curve.iloc[-1]), end)
    assert m.xirr(flows) == pytest.approx(0.09, abs=1e-6)


def test_benchmark_buys_on_next_trading_day():
    """Un achat daté d'un jour sans cotation (week-end) est exécuté à la clôture du jour coté
    suivant, comme dans reconstruct_equity_curve."""
    dates = pd.to_datetime(["2024-01-05", "2024-01-08"])  # vendredi, lundi
    prices = pd.Series([10.0, 20.0], index=dates)
    transactions = pd.DataFrame([_tx("REAL", "2024-01-06", 100.0, 1.0)])  # samedi
    curve = m.benchmark_equity_curve(transactions, prices)
    assert list(curve.index) == [pd.Timestamp("2024-01-08")]
    assert curve.iloc[0] == pytest.approx(100.0)


def test_benchmark_no_transaction_is_empty():
    empty_tx = pd.DataFrame(columns=["ticker", "date", "amount_eur", "price", "fee_eur"])
    assert m.benchmark_equity_curve(empty_tx, pd.Series([1.0], index=pd.to_datetime(["2024-01-01"]))).empty
    assert m.benchmark_cash_flows(empty_tx, 0.0, "2024-01-01") == []


# ---------- répartition du prochain versement (rééquilibrage sans vente) ----------

def _weights(**pct):
    return pd.DataFrame({"ticker": list(pct), "weight_pct": list(pct.values())})


def test_contribution_goes_to_the_most_underweight_line_first():
    # 1 000 € : A 700 (cible 50 %), B 300 (cible 50 %). Versement 200 € -> total 1 200, cible 600
    # chacun : A est déjà au-dessus, tout va à B (300 -> 500), qui reste sous sa cible.
    lines, summary = m.allocate_contribution(_weights(A=50, B=50), pd.Series({"A": 700.0, "B": 300.0}), 200.0)
    by_ticker = lines.set_index("ticker")["contribution_eur"]
    assert by_ticker["B"] == pytest.approx(200.0) and by_ticker["A"] == pytest.approx(0.0)
    assert summary["deviation_after_pt"] < summary["deviation_before_pt"]


def test_contribution_equalizes_relative_gaps_and_never_overshoots_targets():
    # Total après versement 1 000 : cibles A 400, B 400, C 200. Valeurs A 400, B 100, C 0 : 500 € à
    # placer, le ratio commun r vérifie (400r - 100) + 200r = 500, soit r = 1 -> B 300, C 200.
    lines, _ = m.allocate_contribution(_weights(A=40, B=40, C=20), pd.Series({"A": 400.0, "B": 100.0}), 500.0)
    by_ticker = lines.set_index("ticker")
    assert by_ticker.loc["B", "contribution_eur"] == pytest.approx(300.0, abs=0.01)
    assert by_ticker.loc["C", "contribution_eur"] == pytest.approx(200.0, abs=0.01)
    assert by_ticker["contribution_eur"].sum() == pytest.approx(500.0)
    assert (by_ticker["after_pct"] <= by_ticker["target_pct"] + 1e-6).all()


def test_contribution_partial_fill_keeps_a_common_ratio():
    # Cibles 50/50 sur 1 100 € (550 chacune), A 0 € et B 800 € : B est au-dessus de sa cible, les
    # 300 € vont tous à A, qui reste sous la sienne (ratio 300 / 550).
    lines, _ = m.allocate_contribution(_weights(A=50, B=50), pd.Series({"B": 800.0}), 300.0)
    by_ticker = lines.set_index("ticker")["contribution_eur"]
    assert by_ticker["A"] == pytest.approx(300.0) and by_ticker["B"] == pytest.approx(0.0)
    # Deux lignes sous-pondérées, 300 € : cibles 30 / 30 / 40 sur 1 000 €, valeurs A 100, B 0,
    # C 600. On cherche r : (300r - 100) + 300r = 300, soit r = 2/3 -> A 100 €, B 200 €, toutes deux
    # à 200 € (2/3 de leur cible).
    lines, _ = m.allocate_contribution(_weights(A=30, B=30, C=40), pd.Series({"A": 100.0, "C": 600.0}), 300.0)
    by_ticker = lines.set_index("ticker")["contribution_eur"]
    assert by_ticker["A"] == pytest.approx(100.0, abs=0.01) and by_ticker["B"] == pytest.approx(200.0, abs=0.01)
    assert by_ticker["C"] == pytest.approx(0.0)


def test_held_line_without_target_receives_nothing_and_empty_inputs():
    lines, _ = m.allocate_contribution(_weights(A=100), pd.Series({"A": 100.0, "X": 500.0}), 50.0)
    assert lines.set_index("ticker").loc["X", "contribution_eur"] == pytest.approx(0.0)
    assert m.allocate_contribution(_weights(), pd.Series(dtype=float), 100.0)[0].empty
    assert m.allocate_contribution(_weights(A=100), pd.Series({"A": 1.0}), 0.0)[0].empty


# ---------- gain de la période (historique de moins d'un an) ----------

def test_invested_cost_includes_fees_and_tolerates_missing_fee():
    transactions = pd.DataFrame([
        _tx("AAA", "2026-08-17", 100.0, 10.0, fee_eur=1.0),
        _tx("BBB", "2026-09-01", 200.0, 20.0, fee_eur=None),
    ])
    assert m.invested_cost(transactions) == pytest.approx(301.0)


def test_period_gain_counts_dividends_and_is_not_annualized():
    # 301 € versés, valeur 290 € + 20 € de dividendes : +9 €, soit +2,99 % sur la période.
    assert m.period_gain(290.0, 20.0, 301.0) == pytest.approx(9.0 / 301.0)
    assert m.period_gain(250.0, 0.0, 301.0) == pytest.approx(-51.0 / 301.0)
    assert m.period_gain(0.0, 0.0, 0.0) is None


def test_history_years_from_first_purchase():
    transactions = pd.DataFrame([_tx("AAA", "2026-10-02", 100.0, 10.0), _tx("AAA", "2026-08-17", 100.0, 10.0)])
    assert m.history_years(transactions, "2026-10-24") == pytest.approx(68 / 365)
    assert m.history_years(transactions, "2026-10-24") < m.SHORT_HISTORY_YEARS
    empty_tx = pd.DataFrame(columns=["ticker", "date", "amount_eur", "price", "fee_eur"])
    assert m.history_years(empty_tx, "2026-10-24") is None


# ---------- jalons PEA ----------

def test_pea_milestones_before_five_years():
    result = m.pea_milestones("2022-03-10", "2026-03-09")
    assert result["maturity_date"] == pd.Timestamp("2027-03-10")
    assert result["is_mature"] is False
    assert result["days_remaining"] == 366  # 2026-03-09 -> 2027-03-10


def test_pea_milestones_exactly_five_years_is_mature():
    result = m.pea_milestones("2021-06-01", "2026-06-01")
    assert result["is_mature"] is True
    assert result["days_remaining"] == 0


def test_pea_milestones_leap_day_opening_never_matures_early():
    result = m.pea_milestones("2020-02-29", "2025-02-27")
    assert result["maturity_date"] == pd.Timestamp("2025-02-28")
    assert result["is_mature"] is False


def test_pea_cap_usage_counts_purchases_with_fees():
    transactions = pd.DataFrame([
        _tx("AAA", "2024-01-01", 10_000.0, 10.0, fee_eur=50.0),
        _tx("BBB", "2024-06-01", 4_950.0, 10.0),
    ])
    result = m.pea_cap_usage(transactions)
    assert result["consumed"] == pytest.approx(15_000.0)
    assert result["remaining"] == pytest.approx(135_000.0)
    assert result["pct"] == pytest.approx(10.0)
    assert result["excess"] == 0.0


def test_pea_cap_usage_reports_excess_beyond_cap():
    transactions = pd.DataFrame([_tx("AAA", "2024-01-01", 160_000.0, 10.0)])
    result = m.pea_cap_usage(transactions)
    assert result["consumed"] == pytest.approx(150_000.0)
    assert result["remaining"] == pytest.approx(0.0)
    assert result["excess"] == pytest.approx(10_000.0)
    assert result["months_to_cap"] is None


def test_pea_cap_usage_projects_cap_date_at_current_pace():
    transactions = pd.DataFrame([_tx("AAA", "2024-01-01", 149_000.0, 10.0)])
    result = m.pea_cap_usage(transactions, monthly_pace=300.0, today="2026-01-15")
    assert result["months_to_cap"] == 4  # 1000 € restants / 300 € par mois, arrondi au mois supérieur
    assert result["projected_cap_date"] == pd.Timestamp("2026-05-15")


def test_pea_cap_usage_no_transaction():
    empty_tx = pd.DataFrame(columns=["ticker", "date", "amount_eur", "price", "fee_eur"])
    result = m.pea_cap_usage(empty_tx, monthly_pace=0.0)
    assert result["consumed"] == 0.0
    assert result["remaining"] == 150_000.0
    assert result["months_to_cap"] is None


def test_latent_tax_after_five_years_social_charges_only():
    result = m.latent_withdrawal_tax(current_value=13_000.0, total_dividends=0.0, cost_basis=10_000.0,
                                     is_mature=True)
    assert result["gain"] == pytest.approx(3_000.0)
    assert result["rate"] == pytest.approx(0.172)
    assert result["tax"] == pytest.approx(516.0)
    assert result["net_value"] == pytest.approx(12_484.0)


def test_latent_tax_before_five_years_flat_tax():
    result = m.latent_withdrawal_tax(current_value=13_000.0, total_dividends=0.0, cost_basis=10_000.0,
                                     is_mature=False)
    assert result["rate"] == pytest.approx(0.30)
    assert result["tax"] == pytest.approx(900.0)


def test_latent_tax_dividend_cash_counts_in_gain():
    result = m.latent_withdrawal_tax(current_value=10_000.0, total_dividends=500.0, cost_basis=10_000.0,
                                     is_mature=True)
    assert result["gross_value"] == pytest.approx(10_500.0)
    assert result["tax"] == pytest.approx(0.172 * 500.0)


@pytest.mark.parametrize("is_mature", [True, False])
def test_latent_tax_loss_means_no_tax(is_mature):
    result = m.latent_withdrawal_tax(current_value=8_000.0, total_dividends=0.0, cost_basis=10_000.0,
                                     is_mature=is_mature)
    assert result["is_loss"] is True
    assert result["tax"] == 0.0
    assert result["net_value"] == pytest.approx(8_000.0)
