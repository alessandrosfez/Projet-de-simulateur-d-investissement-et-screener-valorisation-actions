"""
Résumé JSON de la page d'accueil (summary_api.py), sur la base en mémoire de conftest : montants
fictifs, jamais ceux du vrai portefeuille.
"""
import pytest

import app as app_module  # noqa: F401 - enregistre la route sur le serveur
import portfolio_db
from app_instance import app

HOME = "http://localhost:8049"


def _get(origin=HOME):
    return app.server.test_client().get("/api/summary", headers={"Origin": origin} if origin else {})


def test_empty_portfolio_reports_empty():
    response = _get()
    assert response.status_code == 200
    assert response.get_json() == {"status": "empty", "transactions": 0}


def test_last_snapshot_gain_and_change_since_the_previous_day():
    portfolio_db.record_value_snapshot("2026-01-05", 1000.0, 1000.0)
    portfolio_db.record_value_snapshot("2026-01-12", 1150.0, 1100.0)
    data = _get().get_json()
    assert data["status"] == "ok" and data["day"] == "2026-01-12"
    assert data["gain_eur"] == pytest.approx(50.0)
    assert data["gain_pct"] == pytest.approx(50 / 1100 * 100)
    # +150 € de valeur, dont 100 € versés : +50 € dus au marché.
    assert data["previous"] == {"day": "2026-01-05", "value_delta_eur": pytest.approx(150.0),
                                "market_delta_eur": pytest.approx(50.0)}


def test_only_the_home_page_may_read_it_from_a_browser():
    assert _get().headers["Access-Control-Allow-Origin"] == HOME
    assert _get("http://127.0.0.1:8049").headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:8049"
    assert "Access-Control-Allow-Origin" not in _get("https://example.com").headers
    assert "Access-Control-Allow-Origin" not in _get(None).headers
