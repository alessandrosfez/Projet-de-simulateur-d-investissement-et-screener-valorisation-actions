"""
Résumé JSON de la page d'accueil (summary_api.py), sur un journal et un dernier chargement
temporaires (voir conftest) : titres et cours fictifs.
"""
import time

import app as app_module  # noqa: F401 - enregistre la route sur le serveur
import journal_db
import last_load
from app_instance import app

HOME = "http://localhost:8049"


def _get(origin=HOME):
    return app.server.test_client().get("/api/summary", headers={"Origin": origin} if origin else {})


def test_nothing_saved_yet():
    assert _get().get_json() == {"journal_entries": 0, "reviews_due": [], "below_target": [],
                                 "loaded_at": None, "loaded_stocks": 0}


def test_counts_due_reviews_and_stocks_under_their_target():
    saved_at = time.time() - 60
    last_load.save_last_load([{"Ticker": "AAA.PA", "Entreprise": "Alpha", "price": 40.0},
                              {"Ticker": "BBB.PA", "Entreprise": "Beta", "price": 90.0}], ["cac40"], saved_at)
    journal_db.upsert_entry("AAA.PA", "", 45.0, "2020-01-01")   # sous la cible, revue due
    journal_db.upsert_entry("BBB.PA", "", 80.0, "2099-01-01")   # au-dessus de la cible
    journal_db.upsert_entry("ZZZ.PA", "", 10.0, None)           # absent du chargement : ni l'un ni l'autre
    data = _get().get_json()
    assert data == {"journal_entries": 3, "reviews_due": ["Alpha"], "below_target": ["Alpha"],
                    "loaded_at": saved_at, "loaded_stocks": 2}


def test_only_the_home_page_may_read_it_from_a_browser():
    assert _get().headers["Access-Control-Allow-Origin"] == HOME
    assert "Access-Control-Allow-Origin" not in _get("https://example.com").headers
