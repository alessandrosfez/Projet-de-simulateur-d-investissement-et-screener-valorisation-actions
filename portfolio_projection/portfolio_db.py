"""
Persistance du portefeuille réel (achats effectifs, dividendes perçus, pondérations
cibles) : un seul portefeuille, pas de table d'instruments séparée (tout ticker est
accepté, voir market_data.get_current_price) -- stockage SQLite minimal (stdlib),
pas de dépendance ORM : le schéma est trop simple (3 tables à plat, aucune jointure)
pour que SQLAlchemy apporte quoi que ce soit ici.

La quantité détenue n'est volontairement pas stockée sur une transaction : toujours
recalculée (amount_eur / price) à la lecture, pour ne jamais désynchroniser si l'un
des deux est corrigé après coup (voir insert_transaction).
"""
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

DB_FILE = Path(__file__).with_name(".pea_forecast_portfolio.db")


def _get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_FILE)


# Migrations du schéma, appliquées dans l'ordre à partir de la version courante de la base
# (PRAGMA user_version, 0 pour une base créée avant ce mécanisme) : une base existante reçoit
# seulement les étapes qui lui manquent, sans toucher aux données déjà présentes. Ne jamais
# modifier une étape déjà publiée -- en ajouter une nouvelle à la fin.
_MIGRATIONS = [
    # v1 : réglages clé/valeur du portefeuille (date d'ouverture du PEA, ...) plutôt qu'une table
    # par réglage, pour ne pas devoir migrer à nouveau à chaque nouveau paramètre.
    "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);",
]


def _apply_migrations(conn: sqlite3.Connection):
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for target_version, statement in enumerate(_MIGRATIONS[version:], start=version + 1):
        conn.executescript(statement)
        # PRAGMA n'accepte pas de paramètre lié ; target_version est un entier calculé ici.
        conn.execute(f"PRAGMA user_version = {int(target_version)}")
    conn.commit()


def init_db(conn: sqlite3.Connection | None = None):
    """Crée les tables si absentes puis applique les migrations manquantes (voir _MIGRATIONS).
    Appelée une fois à l'import (effet de bord volontaire, même convention que
    market_data._cache chargé à l'import) ; aussi appelable directement avec une connexion
    dédiée (tests en mémoire, voir test_portfolio_db.py)."""
    own_conn = conn is None
    conn = conn or _get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                amount_eur REAL NOT NULL,
                price REAL NOT NULL,
                fee_eur REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS dividends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                amount_eur REAL NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS target_weights (
                ticker TEXT PRIMARY KEY,
                weight_pct REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_transactions_ticker_date ON transactions(ticker, date);
        """)
        conn.commit()
        _apply_migrations(conn)
    finally:
        if own_conn:
            conn.close()


PEA_OPENING_DATE_KEY = "pea_opening_date"


def get_setting(key: str) -> str | None:
    conn = _get_connection()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def set_setting(key: str, value: str | None):
    """value=None supprime le réglage (retour au comportement par défaut) plutôt que de stocker
    une chaîne vide, qu'il faudrait ensuite distinguer d'une vraie valeur à chaque lecture."""
    conn = _get_connection()
    try:
        if value is None:
            conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        else:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        conn.commit()
    finally:
        conn.close()


def get_pea_opening_date() -> str | None:
    """Date d'ouverture du PEA (ISO "YYYY-MM-DD"), ou None si jamais renseignée."""
    return get_setting(PEA_OPENING_DATE_KEY)


def set_pea_opening_date(date: str | None):
    set_setting(PEA_OPENING_DATE_KEY, date)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def insert_transaction(ticker: str, date: str, amount_eur: float, price: float, fee_eur: float = 0.0) -> int:
    conn = _get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO transactions (ticker, date, amount_eur, price, fee_eur, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticker, date, amount_eur, price, fee_eur, _now_iso()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def insert_dividend(ticker: str, date: str, amount_eur: float) -> int:
    conn = _get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO dividends (ticker, date, amount_eur, created_at) VALUES (?, ?, ?, ?)",
            (ticker, date, amount_eur, _now_iso()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def insert_transactions_bulk(rows: list[tuple]) -> int:
    """rows : liste de (ticker, date, amount_eur, price, fee_eur). Une connexion/un commit pour
    tout le lot (executemany), plutôt qu'un aller-retour par ligne comme insert_transaction
    appelée en boucle -- pensé pour l'import CSV, qui peut soumettre des centaines de lignes
    d'un coup."""
    conn = _get_connection()
    try:
        created_at = _now_iso()
        conn.executemany(
            "INSERT INTO transactions (ticker, date, amount_eur, price, fee_eur, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(ticker, date, amount_eur, price, fee_eur, created_at) for ticker, date, amount_eur, price, fee_eur in rows],
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def insert_dividends_bulk(rows: list[tuple]) -> int:
    """rows : liste de (ticker, date, amount_eur). Même idée que insert_transactions_bulk."""
    conn = _get_connection()
    try:
        created_at = _now_iso()
        conn.executemany(
            "INSERT INTO dividends (ticker, date, amount_eur, created_at) VALUES (?, ?, ?, ?)",
            [(ticker, date, amount_eur, created_at) for ticker, date, amount_eur in rows],
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def delete_transaction(row_id: int):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM transactions WHERE id = ?", (row_id,))
        conn.commit()
    finally:
        conn.close()


def delete_dividend(row_id: int):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM dividends WHERE id = ?", (row_id,))
        conn.commit()
    finally:
        conn.close()


def get_transactions() -> pd.DataFrame:
    conn = _get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT id, ticker, date, amount_eur, price, fee_eur FROM transactions ORDER BY date DESC, id DESC",
            conn,
        )
    finally:
        conn.close()
    return df


def get_dividends() -> pd.DataFrame:
    conn = _get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT id, ticker, date, amount_eur FROM dividends ORDER BY date DESC, id DESC", conn,
        )
    finally:
        conn.close()
    return df


def upsert_target_weight(ticker: str, weight_pct: float):
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO target_weights (ticker, weight_pct) VALUES (?, ?) "
            "ON CONFLICT(ticker) DO UPDATE SET weight_pct = excluded.weight_pct",
            (ticker, weight_pct),
        )
        conn.commit()
    finally:
        conn.close()


def delete_target_weight(ticker: str):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM target_weights WHERE ticker = ?", (ticker,))
        conn.commit()
    finally:
        conn.close()


def get_target_weights() -> pd.DataFrame:
    conn = _get_connection()
    try:
        df = pd.read_sql_query("SELECT ticker, weight_pct FROM target_weights ORDER BY ticker", conn)
    finally:
        conn.close()
    return df


init_db()
