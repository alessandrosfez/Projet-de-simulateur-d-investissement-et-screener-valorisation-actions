"""
Isole les tests du cache disque de market_data.py : `market_data._cache` est un dict chargé une
seule fois au niveau module, partagé entre tous les tests du process. Sans cette fixture, les
tests liraient/écriraient le vrai `.pea_forecast_cache.pkl` et pourraient interférer entre eux
selon l'ordre d'exécution.
"""
import pytest

import market_data


@pytest.fixture(autouse=True)
def isolate_market_data_cache(monkeypatch):
    monkeypatch.setattr(market_data, "_cache", {})
    monkeypatch.setattr(market_data, "_save_cache_to_disk", lambda: None)
