"""
Tests de portfolio_db.py : isolés dans une base SQLite en mémoire (voir la fixture
isolate_portfolio_db, autouse, dans conftest.py) -- aucun test ici ne touche le vrai
.pea_forecast_portfolio.db.
Usage : pip install pytest && pytest test_portfolio_db.py -v
"""
import portfolio_db as db


def test_insert_and_get_transactions():
    row_id = db.insert_transaction("AAA", "2024-01-01", 100.0, 10.0, fee_eur=1.0)
    assert row_id is not None
    transactions = db.get_transactions()
    assert len(transactions) == 1
    row = transactions.iloc[0]
    assert row["ticker"] == "AAA"
    assert row["amount_eur"] == 100.0
    assert row["price"] == 10.0
    assert row["fee_eur"] == 1.0


def test_delete_transaction_removes_row():
    row_id = db.insert_transaction("AAA", "2024-01-01", 100.0, 10.0)
    db.insert_transaction("BBB", "2024-01-02", 50.0, 5.0)
    db.delete_transaction(row_id)
    remaining = db.get_transactions()
    assert len(remaining) == 1
    assert remaining.iloc[0]["ticker"] == "BBB"


def test_insert_and_get_dividends():
    db.insert_dividend("AAA", "2024-06-01", 12.5)
    dividends = db.get_dividends()
    assert len(dividends) == 1
    assert dividends.iloc[0]["amount_eur"] == 12.5


def test_delete_dividend_removes_row():
    row_id = db.insert_dividend("AAA", "2024-06-01", 12.5)
    db.delete_dividend(row_id)
    assert db.get_dividends().empty


def test_upsert_target_weight_inserts_then_updates():
    db.upsert_target_weight("AAA", 60.0)
    assert db.get_target_weights().set_index("ticker").loc["AAA", "weight_pct"] == 60.0
    db.upsert_target_weight("AAA", 70.0)
    weights = db.get_target_weights()
    assert len(weights) == 1
    assert weights.set_index("ticker").loc["AAA", "weight_pct"] == 70.0


def test_delete_target_weight_removes_row():
    db.upsert_target_weight("AAA", 60.0)
    db.delete_target_weight("AAA")
    assert db.get_target_weights().empty


def test_get_transactions_empty_db():
    assert db.get_transactions().empty


def test_get_target_weights_empty_db():
    assert db.get_target_weights().empty


def test_insert_transactions_bulk_inserts_all_rows():
    n = db.insert_transactions_bulk([
        ("AAA", "2024-01-01", 100.0, 10.0, 1.0),
        ("BBB", "2024-01-02", 200.0, 20.0, 2.0),
    ])
    assert n == 2
    transactions = db.get_transactions()
    assert len(transactions) == 2
    assert set(transactions["ticker"]) == {"AAA", "BBB"}


def test_insert_dividends_bulk_inserts_all_rows():
    n = db.insert_dividends_bulk([("AAA", "2024-06-01", 10.0), ("BBB", "2024-06-02", 20.0)])
    assert n == 2
    dividends = db.get_dividends()
    assert len(dividends) == 2
    assert set(dividends["ticker"]) == {"AAA", "BBB"}
