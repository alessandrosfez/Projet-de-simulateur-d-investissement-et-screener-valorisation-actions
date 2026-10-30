"""
Journal d'investissement (journal_db.py) sur un fichier temporaire (voir conftest.isolate_journal) :
jamais le vrai journal de l'utilisateur.
"""
import sqlite3

import journal_db


def test_upsert_replaces_the_entry_of_a_ticker():
    journal_db.upsert_entry("AAA.PA", "Première thèse", 50.0, "2026-12-01")
    journal_db.upsert_entry("AAA.PA", "Thèse revue", None, None)
    entries = journal_db.get_entries()
    assert len(entries) == 1
    entry = entries[0]
    assert (entry["ticker"], entry["thesis"], entry["target_price"], entry["review_date"]) == (
        "AAA.PA", "Thèse revue", None, None)


def test_entries_sorted_by_review_date_undated_last_and_delete():
    journal_db.upsert_entry("CCC.PA", "", None, None)
    journal_db.upsert_entry("BBB.PA", "", 10.0, "2027-01-15")
    journal_db.upsert_entry("AAA.PA", "", 12.0, "2026-11-01")
    assert [e["ticker"] for e in journal_db.get_entries()] == ["AAA.PA", "BBB.PA", "CCC.PA"]
    journal_db.delete_entry("BBB.PA")
    assert [e["ticker"] for e in journal_db.get_entries()] == ["AAA.PA", "CCC.PA"]


def test_migrations_are_applied_once():
    conn = sqlite3.connect(":memory:")
    journal_db.init_db(conn)
    journal_db.init_db(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(journal_db._MIGRATIONS)


def test_watchlist_keeps_order_and_drops_duplicates():
    assert journal_db.get_watchlist() == []
    journal_db.set_watchlist(["BBB.PA", "AAA.PA", "BBB.PA", ""])
    assert journal_db.get_watchlist() == ["BBB.PA", "AAA.PA"]
    journal_db.set_watchlist([])
    assert journal_db.get_watchlist() == []


def test_extra_tickers_keep_order_names_and_drop_duplicates():
    assert journal_db.get_extra_tickers() == []
    journal_db.set_extra_tickers([{"ticker": "BBB.PA", "name": "Beta"}, {"ticker": "AAA.PA", "name": ""},
                                  {"ticker": "BBB.PA", "name": "Autre"}])
    assert journal_db.get_extra_tickers() == [{"ticker": "BBB.PA", "name": "Beta"},
                                              {"ticker": "AAA.PA", "name": "AAA.PA"}]
