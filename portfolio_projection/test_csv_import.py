"""
Import CSV du portefeuille réel (callbacks/portefeuille_reel.import_csv) sur la base en mémoire de
conftest : réimporter le même export n'ajoute rien, un export complété n'ajoute que les nouvelles
lignes. ISIN, tickers et montants fictifs ; aucun appel réseau.
"""
import base64

import app as app_module  # noqa: F401 - enregistre les callbacks
import portfolio_db
from callbacks import portefeuille_reel

HEADER = "account_type,category,type,symbol,date,shares,price,amount,fee\n"
BUY_1 = "PEA,TRADING,BUY,FR0000000001,2026-01-05,2,50.0,-100.0,-1.0\n"
BUY_2 = "PEA,TRADING,BUY,FR0000000001,2026-02-02,3,40.0,-120.0,-1.0\n"


def _upload(text: str) -> str:
    return "data:text/csv;base64," + base64.b64encode(text.encode("utf-8")).decode("ascii")


def _offline(monkeypatch):
    monkeypatch.setattr(portefeuille_reel, "resolve_isin_to_ticker", lambda isin: "SPA.PA")
    monkeypatch.setattr(portefeuille_reel, "get_current_price", lambda ticker: 50.0)


def test_reimporting_the_same_export_adds_nothing(monkeypatch):
    _offline(monkeypatch)
    portefeuille_reel.import_csv(_upload(HEADER + BUY_1), "fr")
    assert len(portfolio_db.get_transactions()) == 1
    trigger, message = portefeuille_reel.import_csv(_upload(HEADER + BUY_1), "fr")
    assert len(portfolio_db.get_transactions()) == 1
    assert "déjà enregistrée" in str(message)


def test_a_completed_export_adds_only_the_new_rows(monkeypatch):
    _offline(monkeypatch)
    portefeuille_reel.import_csv(_upload(HEADER + BUY_1), "fr")
    _trigger, message = portefeuille_reel.import_csv(_upload(HEADER + BUY_1 + BUY_2), "fr")
    rows = portfolio_db.get_transactions()
    assert sorted(rows["date"]) == ["2026-01-05", "2026-02-02"]
    assert "1 ligne(s) importée(s)" in str(message) and "1 ligne(s) sur 2" in str(message)
