"""
Dernière société analysée (nom, ticker ou fichier importé, heure de la demande), gardée dans un
petit fichier local ignoré par git (.financial_analysis_last.json) pour la carte de cet outil sur la
page d'accueil de run_all.py (voir summary_api.py).

Enregistrée par callbacks.render_analysis une fois l'analyse affichée, pas au clic : une analyse
qui échoue (ticker inconnu, aucune donnée) ne remplace jamais la précédente. L'heure est celle de la
demande (« requested_at », posée par submit_analysis et import_statements) : un nouvel affichage de
la même analyse (changement de langue ou de thème) ne la rajeunit pas.
"""
import json
import time
from pathlib import Path

LAST_ANALYSIS_FILE = Path(__file__).with_name(".financial_analysis_last.json")


def read_last_analysis() -> dict | None:
    """{"key", "name", "ticker", "imported", "at"}, ou None si rien n'est enregistré ou lisible."""
    try:
        data = json.loads(LAST_ANALYSIS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("key") else None


def record_analysis(key: str, name: str | None, ticker: str | None, requested_at: float | None):
    """Enregistre l'analyse affichée, sauf si c'est déjà celle enregistrée pour la même demande."""
    current = read_last_analysis()
    if current and current["key"] == key and (requested_at is None or current.get("at") == requested_at):
        return
    data = {"key": key, "name": name or key, "ticker": ticker, "imported": ticker is None,
            "at": requested_at if requested_at is not None else time.time()}
    tmp_path = LAST_ANALYSIS_FILE.with_suffix(".tmp")
    try:
        tmp_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(LAST_ANALYSIS_FILE)
    except OSError:
        pass  # dossier en lecture seule : l'analyse affichée n'en dépend pas
