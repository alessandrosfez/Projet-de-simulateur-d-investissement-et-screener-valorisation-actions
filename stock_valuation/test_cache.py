"""
Cache disque de market_data.py : écritures regroupées et entrées périmées écartées. Les vraies
fonctions sont gardées au chargement du module, avant que conftest ne les neutralise pour les autres
tests ; le fichier écrit est toujours temporaire, jamais le vrai cache.
"""
import pickle
import threading
import time

import market_data as md

REAL_SAVE = md._save_cache_to_disk
REAL_SCHEDULE = md._schedule_save


class FakeTimer:
    """Minuteur qui ne part jamais seul : le test le déclenche à la main."""
    created: list = []

    def __init__(self, delay, function):
        self.function, self.daemon = function, False
        FakeTimer.created.append(self)

    def start(self):
        pass

    def cancel(self):
        pass


def test_writes_are_grouped_and_stale_entries_dropped(monkeypatch, tmp_path):
    monkeypatch.setattr(md, "CACHE_FILE", tmp_path / "cache.pkl")
    monkeypatch.setattr(md, "_save_cache_to_disk", REAL_SAVE)
    monkeypatch.setattr(md, "_save_timer", None)
    monkeypatch.setattr(threading, "Timer", FakeTimer)
    FakeTimer.created = []
    md._cache["recent"] = ("r", time.time())
    md._cache["stale"] = ("s", time.time() - md.MAX_ENTRY_AGE_SECONDS - 10)
    for _ in range(5):
        REAL_SCHEDULE()
    assert len(FakeTimer.created) == 1  # cinq ajouts, une seule écriture programmée
    FakeTimer.created[0].function()
    with open(md.CACHE_FILE, "rb") as f:
        saved = pickle.load(f)
    assert "recent" in saved and "stale" not in saved
    REAL_SCHEDULE()  # l'écriture faite, un nouvel ajout en programme une autre
    assert len(FakeTimer.created) == 2


def test_annual_statements_are_kept_a_day_prices_an_hour():
    assert md.STATEMENTS_TTL_SECONDS == 86400 and md.PRICE_TTL_SECONDS == 3600
