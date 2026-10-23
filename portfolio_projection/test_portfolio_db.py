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


# ---------- réglages et migration du schéma ----------

def test_pea_opening_date_roundtrip_and_clear():
    assert db.get_pea_opening_date() is None
    db.set_pea_opening_date("2021-03-15")
    assert db.get_pea_opening_date() == "2021-03-15"
    db.set_pea_opening_date("2020-01-02")  # mise à jour, pas de doublon
    assert db.get_pea_opening_date() == "2020-01-02"
    db.set_pea_opening_date(None)
    assert db.get_pea_opening_date() is None


def test_migration_upgrades_existing_database_without_losing_data(tmp_path):
    """Base créée avec l'ancien schéma (avant la table settings, user_version 0) et contenant déjà
    des données : init_db doit ajouter ce qui manque sans rien perdre, et rester idempotente."""
    import sqlite3

    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL, date TEXT NOT NULL,
            amount_eur REAL NOT NULL, price REAL NOT NULL, fee_eur REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE dividends (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL, date TEXT NOT NULL,
            amount_eur REAL NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE target_weights (ticker TEXT PRIMARY KEY, weight_pct REAL NOT NULL);
        INSERT INTO transactions (ticker, date, amount_eur, price, fee_eur, created_at)
            VALUES ('AAA', '2022-05-01', 1000.0, 50.0, 1.0, '2022-05-01T00:00:00');
    """)
    old.commit()
    assert old.execute("PRAGMA user_version").fetchone()[0] == 0
    old.close()

    for _ in range(2):  # deux démarrages successifs : la migration ne doit s'appliquer qu'une fois
        conn = sqlite3.connect(path)
        db.init_db(conn)
        conn.close()

    conn = sqlite3.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db._MIGRATIONS)
    assert conn.execute("SELECT ticker, amount_eur FROM transactions").fetchall() == [("AAA", 1000.0)]
    conn.execute("INSERT INTO settings (key, value) VALUES ('pea_opening_date', '2022-01-10')")
    conn.execute("INSERT INTO index_overrides (ticker, index_key) VALUES ('AAA', 'S&P 500')")  # v2 présente
    conn.close()


def test_index_override_roundtrip_and_clear():
    assert db.get_index_overrides() == {}
    db.set_index_override("ESE.PA", "S&P 500")
    db.set_index_override("ESE.PA", "Nasdaq-100")  # mise à jour, pas de doublon
    assert db.get_index_overrides() == {"ESE.PA": "Nasdaq-100"}
    db.set_index_override("ESE.PA", None)
    assert db.get_index_overrides() == {}
