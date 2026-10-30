"""
Journal d'investissement : pour chaque titre suivi, la thèse (pourquoi on s'y intéresse), un prix
cible et une date de revue. Une ligne par titre, stockée en SQLite (stdlib) dans un fichier local
ignoré par git (.stock_valuation_journal.db) : ces notes sont personnelles et ne doivent jamais
arriver dans le dépôt.

Le même fichier garde la liste de suivi (table watchlist) : stockée côté serveur plutôt que dans le
navigateur, elle survit au rechargement de la page (voir callbacks.restore_watchlist). Les titres du
journal sont pris en compte par les alertes, qu'ils soient dans la liste de suivi ou non.

Le prix cible est exprimé dans la devise de cotation du titre (celle de la colonne « Prix »), jamais
converti : comparer un cours en pence à une cible en livres fausserait l'alerte.
"""
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

DB_FILE = Path(__file__).with_name(".stock_valuation_journal.db")

# Même mécanisme que portfolio_projection/portfolio_db.py (recopié, pas importé : aucun import
# croisé entre outils) : chaque étape s'applique une fois, dans l'ordre, selon PRAGMA user_version.
# Ne jamais modifier une étape publiée, en ajouter une à la fin.
_MIGRATIONS = [
    # v1 : une entrée par titre. target_price et review_date peuvent manquer (une thèse sans cible
    # chiffrée reste utile) ; review_date au format AAAA-MM-JJ, comparable comme du texte.
    "CREATE TABLE IF NOT EXISTS journal (ticker TEXT PRIMARY KEY, thesis TEXT NOT NULL DEFAULT '', "
    "target_price REAL, review_date TEXT, updated_at TEXT NOT NULL);",
    # v2 : liste de suivi, dans l'ordre où les titres ont été ajoutés.
    "CREATE TABLE IF NOT EXISTS watchlist (ticker TEXT PRIMARY KEY, position INTEGER NOT NULL);",
    # v3 : titres ajoutés à la main (champ « Ajouter des titres »), chargés avec les marchés cochés. Le
    # nom est gardé tel que la recherche l'a donné, pour l'afficher avant tout chargement.
    "CREATE TABLE IF NOT EXISTS extra_tickers (ticker TEXT PRIMARY KEY, name TEXT NOT NULL, "
    "position INTEGER NOT NULL);",
]


def _get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_FILE)


def init_db(conn: sqlite3.Connection | None = None):
    """Crée la table si absente et applique les migrations manquantes. Appelable avec une connexion
    dédiée (tests en mémoire)."""
    own_conn = conn is None
    conn = conn or _get_connection()
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for target_version, statement in enumerate(_MIGRATIONS[version:], start=version + 1):
            conn.executescript(statement)
            # PRAGMA n'accepte pas de paramètre lié ; target_version est un entier calculé ici.
            conn.execute(f"PRAGMA user_version = {int(target_version)}")
        conn.commit()
    finally:
        if own_conn:
            conn.close()


def upsert_entry(ticker: str, thesis: str, target_price: float | None, review_date: str | None):
    """Crée ou remplace l'entrée d'un titre."""
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO journal (ticker, thesis, target_price, review_date, updated_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(ticker) DO UPDATE SET thesis = excluded.thesis, target_price = excluded.target_price, "
            "review_date = excluded.review_date, updated_at = excluded.updated_at",
            (ticker, thesis or "", target_price, review_date or None, datetime.now(UTC).isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


def delete_entry(ticker: str):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM journal WHERE ticker = ?", (ticker,))
        conn.commit()
    finally:
        conn.close()


def get_entries() -> list[dict]:
    """Toutes les entrées, la revue la plus proche d'abord (sans date de revue : à la fin)."""
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "SELECT ticker, thesis, target_price, review_date, updated_at FROM journal "
            "ORDER BY review_date IS NULL, review_date, ticker")
        columns = [c[0] for c in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_watchlist() -> list[str]:
    """Tickers de la liste de suivi, dans l'ordre d'ajout."""
    conn = _get_connection()
    try:
        return [row[0] for row in conn.execute("SELECT ticker FROM watchlist ORDER BY position")]
    finally:
        conn.close()


def set_watchlist(tickers: list[str]):
    """Remplace la liste de suivi (doublons écartés, ordre gardé)."""
    unique = list(dict.fromkeys(t for t in tickers if t))
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM watchlist")
        conn.executemany("INSERT INTO watchlist (ticker, position) VALUES (?, ?)",
                         [(t, i) for i, t in enumerate(unique)])
        conn.commit()
    finally:
        conn.close()


def get_extra_tickers() -> list[dict]:
    """Titres ajoutés à la main, [{"ticker", "name"}] dans l'ordre d'ajout."""
    conn = _get_connection()
    try:
        return [{"ticker": t, "name": n} for t, n in conn.execute("SELECT ticker, name FROM extra_tickers ORDER BY position")]
    finally:
        conn.close()


def set_extra_tickers(entries: list[dict]):
    """Remplace la liste des titres ajoutés (doublons écartés, ordre gardé)."""
    unique = {}
    for entry in entries:
        if entry.get("ticker") and entry["ticker"] not in unique:
            unique[entry["ticker"]] = entry.get("name") or entry["ticker"]
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM extra_tickers")
        conn.executemany("INSERT INTO extra_tickers (ticker, name, position) VALUES (?, ?, ?)",
                         [(t, n, i) for i, (t, n) in enumerate(unique.items())])
        conn.commit()
    finally:
        conn.close()


init_db()
