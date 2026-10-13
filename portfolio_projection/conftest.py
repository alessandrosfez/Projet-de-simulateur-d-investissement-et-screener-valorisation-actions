"""
Isole les tests du cache disque de market_data.py : `market_data._cache` est un dict chargé une
seule fois au niveau module, partagé entre tous les tests du process. Sans cette fixture, les
tests liraient/écriraient le vrai `.pea_forecast_cache.pkl` et pourraient interférer entre eux
selon l'ordre d'exécution.
"""
import sqlite3

import pytest

import market_data
import portfolio_db


@pytest.fixture(autouse=True)
def isolate_market_data_cache(monkeypatch):
    monkeypatch.setattr(market_data, "_cache", {})
    monkeypatch.setattr(market_data, "_save_cache_to_disk", lambda: None)


class _PersistentMemoryConnection(sqlite3.Connection):
    """Sous-classe de sqlite3.Connection dont .close() ne fait rien : une base ':memory:' est
    détruite à la fermeture de SA connexion -- chaque fonction de portfolio_db.py ouvre/ferme sa
    propre connexion (voir _get_connection), donc sans ça la base en mémoire disparaîtrait dès le
    premier appel d'un test, pas seulement à la fin de celui-ci. Une vraie sous-classe plutôt
    qu'un objet qui délègue via __getattr__ : pandas.read_sql_query vérifie isinstance(conn,
    sqlite3.Connection), qu'un simple wrapper ne satisferait pas."""

    def close(self):
        pass

    def _really_close(self):
        sqlite3.Connection.close(self)


@pytest.fixture(autouse=True)
def isolate_portfolio_db(monkeypatch):
    """Isole les tests de portfolio_db.py (et de tout code qui l'appelle) dans une base SQLite en
    mémoire fraîche par test, plutôt que le vrai .pea_forecast_portfolio.db partagé entre tous les
    tests du process -- même raisonnement que isolate_market_data_cache ci-dessus."""
    conn = sqlite3.connect(":memory:", factory=_PersistentMemoryConnection)
    portfolio_db.init_db(conn)
    monkeypatch.setattr(portfolio_db, "_get_connection", lambda: conn)
    yield
    conn._really_close()
