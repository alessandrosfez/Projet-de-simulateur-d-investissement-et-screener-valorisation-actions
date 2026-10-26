"""
Dernière analyse (last_analysis.py) et résumé JSON de la page d'accueil (summary_api.py), sur un
fichier temporaire (voir conftest).
"""
import app as app_module  # noqa: F401 - enregistre la route sur le serveur
import last_analysis
from app_instance import app

HOME = "http://localhost:8049"


def _get(origin=HOME):
    return app.server.test_client().get("/api/summary", headers={"Origin": origin} if origin else {})


def test_nothing_analysed_yet():
    assert _get().get_json() == {"last_analysis": None}


def test_redisplay_keeps_the_request_time_a_new_request_replaces_it():
    last_analysis.record_analysis("AAA.PA", "Alpha", "AAA.PA", 100.0)
    last_analysis.record_analysis("AAA.PA", "Alpha", "AAA.PA", None)  # même analyse réaffichée
    assert last_analysis.read_last_analysis()["at"] == 100.0
    last_analysis.record_analysis("import:demo.xlsx", "Démo", None, 200.0)
    assert _get().get_json() == {"last_analysis": {"key": "import:demo.xlsx", "name": "Démo", "ticker": None,
                                                   "imported": True, "at": 200.0}}


def test_unreadable_file_reads_as_none_and_cors_is_limited_to_the_home_page():
    last_analysis.LAST_ANALYSIS_FILE.write_text("{pas du json", encoding="utf-8")
    assert last_analysis.read_last_analysis() is None
    assert _get().headers["Access-Control-Allow-Origin"] == HOME
    assert "Access-Control-Allow-Origin" not in _get("https://example.com").headers
