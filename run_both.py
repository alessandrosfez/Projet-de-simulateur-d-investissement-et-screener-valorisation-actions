"""
Lance portfolio_projection/app.py et stock_valuation/app.py en parallèle (deux
processus indépendants, même interpréteur Python) pour démarrer les deux
outils d'une seule commande, sans Docker. Ouvre index.html (page d'accueil
statique, pas de serveur dédié) en guise de point d'entrée unique : les deux
outils restent deux apps Dash totalement indépendantes (voir README.md),
index.html n'est qu'un aiguillage avec deux liens, pas une fusion des deux.

Usage : python run_both.py
Arrêt : Ctrl+C (arrête proprement les deux, y compris le sous-processus de
rechargement automatique que Dash/Werkzeug relance lui-même en mode debug).
"""
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
APPS = [
    ("portfolio_projection", "http://localhost:8050"),
    ("stock_valuation", "http://localhost:8051"),
]
LANDING_PAGE = ROOT / "index.html"
STARTUP_TIMEOUT = 30.0


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


def _port_free(port: int) -> bool:
    """Teste si le port est déjà occupé (ex. une instance précédente encore en vie) avant même de
    démarrer le sous-processus : sans ce contrôle, Dash échoue à l'intérieur du sous-processus et
    l'erreur se noie dans les logs entremêlés des deux outils plutôt que d'être signalée tout de
    suite, clairement."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) != 0


def _wait_ready(proc: subprocess.Popen, url: str, timeout: float = STARTUP_TIMEOUT):
    """Attend que le serveur Dash réponde, en surveillant aussi que le sous-processus ne plante
    pas entre-temps. Sans cette seconde vérification, un crash immédiat (port déjà pris côté
    Dash/Werkzeug, erreur d'import...) ressemble à un démarrage juste lent jusqu'à épuisement du
    timeout complet, au lieu d'être signalé tout de suite pour ce qu'il est.
    Renvoie ("ready", None), ("crashed", code-retour) ou ("timeout", None)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        code = proc.poll()
        if code is not None:
            return "crashed", code
        try:
            urllib.request.urlopen(url, timeout=1)
            return "ready", None
        except Exception:
            time.sleep(0.3)
    return "timeout", None


def main():
    ports = [urlparse(url).port for _, url in APPS]
    busy_ports = [port for port in ports if not _port_free(port)]
    if busy_ports:
        print(f"Port(s) déjà occupé(s) : {', '.join(map(str, busy_ports))}. "
              "Une instance tourne-t-elle déjà ? Arrête-la avant de relancer.")
        sys.exit(1)

    procs = []
    for folder, url in APPS:
        print(f"Lancement de {folder} -> {url}")
        procs.append(subprocess.Popen([sys.executable, "app.py"], cwd=ROOT / folder))

    # Page d'accueil ouverte tout de suite (statique, pas besoin d'attendre quoi que ce soit) :
    # son propre JS sonde les deux apps toutes les 2s et affiche "Prêt"/"Indisponible" par outil,
    # donc l'utilisateur voit l'état réel sans avoir à lire les logs du terminal.
    webbrowser.open(LANDING_PAGE.resolve().as_uri())

    # Attente en parallèle (pas l'un après l'autre) : sinon, dans le pire cas où le premier met
    # tout son budget à répondre, le diagnostic du second n'arriverait qu'après ~2x STARTUP_TIMEOUT.
    crashed = False
    with ThreadPoolExecutor(max_workers=len(APPS)) as executor:
        futures = {
            executor.submit(_wait_ready, proc, url): (folder, url)
            for proc, (folder, url) in zip(procs, APPS)
        }
        for future in as_completed(futures):
            folder, url = futures[future]
            status, code = future.result()
            if status == "ready":
                print(f"{folder} est prêt ({url}).")
            elif status == "crashed":
                print(f"{folder} a planté au démarrage (code {code}) : voir les logs ci-dessus.")
                crashed = True
            else:
                print(f"{folder} ne répond pas encore après {STARTUP_TIMEOUT:.0f}s, "
                      f"ouvre {url} manuellement une fois prêt.")

    if crashed:
        print("\nArrêt de l'autre outil suite à cet échec...")
        for proc in procs:
            _kill_tree(proc)
        sys.exit(1)

    print("\nLes deux outils tournent (logs entremêlés ci-dessous). Clique sur une carte dans la "
          "page d'accueil ouverte dans ton navigateur pour accéder à l'un ou l'autre. "
          "Ctrl+C pour tout arrêter.\n")
    exit_code = 0
    try:
        while True:
            for proc, (folder, _) in zip(procs, APPS):
                code = proc.poll()
                if code is not None:
                    print(f"\n{folder} s'est arrêté (code {code}) : arrêt de l'autre outil.")
                    exit_code = 1
                    raise KeyboardInterrupt
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nArrêt des deux outils...")
    finally:
        for proc in procs:
            _kill_tree(proc)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
