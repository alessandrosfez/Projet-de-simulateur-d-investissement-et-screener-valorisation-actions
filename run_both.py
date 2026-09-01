"""
Lance portfolio_projection/app.py et stock_valuation/app.py en parallèle (deux
processus indépendants, même interpréteur Python) pour démarrer les deux
outils d'une seule commande, sans Docker.

Usage : python run_both.py
Arrêt : Ctrl+C (arrête proprement les deux, y compris le sous-processus de
rechargement automatique que Dash/Werkzeug relance lui-même en mode debug).
"""
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
APPS = [
    ("portfolio_projection", "http://localhost:8050"),
    ("stock_valuation", "http://localhost:8051"),
]


def _kill_tree(proc: subprocess.Popen):
    """Termine le processus et ses enfants. Le serveur de dev Dash/Werkzeug, en
    mode debug (utilisé par les deux app.py), se relance lui-même dans un
    sous-processus pour le rechargement à chaud : un simple proc.terminate() sur
    le parent laisserait ce sous-processus orphelin et le port occupé."""
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _wait_for_server(url: str, timeout: float = 30.0) -> bool:
    """Attend que le serveur Dash réponde avant d'ouvrir le navigateur : l'ouvrir trop tôt affiche
    une page "connexion refusée" le temps que le serveur de dev finisse de démarrer."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    procs = []
    for folder, url in APPS:
        print(f"Lancement de {folder} -> {url}")
        procs.append(subprocess.Popen([sys.executable, "app.py"], cwd=ROOT / folder))

    for folder, url in APPS:
        if _wait_for_server(url):
            webbrowser.open(url)
        else:
            print(f"{folder} ne répond pas encore après 30s, ouvre {url} manuellement une fois prêt.")

    print("\nLes deux outils tournent (logs entremêlés ci-dessous). Ctrl+C pour tout arrêter.\n")
    try:
        while True:
            for proc, (folder, _) in zip(procs, APPS):
                code = proc.poll()
                if code is not None:
                    print(f"\n{folder} s'est arrêté (code {code}) : arrêt de l'autre outil.")
                    raise KeyboardInterrupt
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nArrêt des deux outils...")
    finally:
        for proc in procs:
            _kill_tree(proc)


if __name__ == "__main__":
    main()
