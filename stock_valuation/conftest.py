"""
Isole les tests du cache disque de market_data.py : `market_data._cache` est un dict chargé une
seule fois au niveau module, partagé entre tous les tests du process. Sans cette fixture, les
tests liraient/écriraient le vrai `.pea_forecast_cache.pkl` et pourraient interférer entre eux
selon l'ordre d'exécution. Même isolement pour le journal d'investissement (journal_db.py).
"""
import pytest

import journal_db
import last_load
import market_data


@pytest.fixture(autouse=True)
def isolate_market_data_cache(monkeypatch):
    monkeypatch.setattr(market_data, "_cache", {})
    monkeypatch.setattr(market_data, "_save_cache_to_disk", lambda: None)


@pytest.fixture(autouse=True)
def isolate_journal(monkeypatch, tmp_path):
    """Journal d'investissement dans un fichier temporaire : aucun test ne lit ni n'écrit le vrai
    journal de l'utilisateur (.stock_valuation_journal.db)."""
    monkeypatch.setattr(journal_db, "DB_FILE", tmp_path / "journal.db")
    journal_db.init_db()


@pytest.fixture(autouse=True)
def isolate_last_load(monkeypatch, tmp_path):
    """Dernier chargement dans un fichier temporaire, absent au départ : aucun test ne lit les
    données réellement chargées sur cette machine (.stock_valuation_last_load.pkl)."""
    monkeypatch.setattr(last_load, "LAST_LOAD_FILE", tmp_path / "last_load.pkl")
