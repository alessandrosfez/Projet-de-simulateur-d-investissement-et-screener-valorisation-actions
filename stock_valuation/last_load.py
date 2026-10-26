"""
Dernier chargement réussi du tableau (lignes, marchés cochés, heure), gardé dans un fichier local
ignoré par git (.stock_valuation_last_load.pkl). À l'ouverture de la page, ces lignes s'affichent
tout de suite au lieu d'un écran vide ; si elles ont plus d'une heure (durée du cache de
market_data), un rechargement part en arrière-plan et les remplace quand il a fini
(voir callbacks.restore_last_load).

Ce ne sont que des données de marché publiques, jamais de données personnelles. Un fichier
illisible (version précédente, écriture interrompue) est traité comme absent : on repart d'un
écran vide plutôt que d'afficher des lignes douteuses.
"""
import pickle
import time
from pathlib import Path

LAST_LOAD_FILE = Path(__file__).with_name(".stock_valuation_last_load.pkl")

# Au-delà, les lignes affichées sont rechargées en arrière-plan : même durée que le cache disque des
# appels Yahoo (market_data.cached_ttl(3600)), en deçà un rechargement renverrait les mêmes données.
STALE_AFTER_SECONDS = 3600


def save_last_load(rows: list[dict], universes: list[str], saved_at: float | None = None) -> float:
    """Enregistre le chargement (écriture dans un fichier temporaire puis remplacement, pour ne
    jamais laisser un fichier à moitié écrit). Renvoie l'heure enregistrée (secondes epoch)."""
    saved_at = time.time() if saved_at is None else saved_at
    tmp_path = LAST_LOAD_FILE.with_suffix(".tmp")
    try:
        with open(tmp_path, "wb") as f:
            pickle.dump({"saved_at": saved_at, "universes": sorted(universes), "rows": rows}, f)
        tmp_path.replace(LAST_LOAD_FILE)
    except OSError:
        pass  # disque plein ou dossier en lecture seule : l'affichage en cours n'en dépend pas
    return saved_at


def read_last_load() -> dict | None:
    """{"saved_at", "universes", "rows"} du dernier chargement, ou None s'il n'y en a pas."""
    if not LAST_LOAD_FILE.exists():
        return None
    try:
        with open(LAST_LOAD_FILE, "rb") as f:
            data = pickle.load(f)
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get("rows") or "saved_at" not in data:
        return None
    return data
