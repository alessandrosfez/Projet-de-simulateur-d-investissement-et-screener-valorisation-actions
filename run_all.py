"""
Lance les trois outils du dépôt en parallèle (portfolio_projection, stock_valuation et
financial_analysis : trois processus indépendants, même interpréteur Python) pour les démarrer
d'une seule commande, sans Docker. Ouvre index.html (page d'accueil statique, pas de serveur
dédié) en guise de point d'entrée unique : les outils restent des apps Dash totalement
indépendantes (voir README.md), index.html n'est qu'un aiguillage avec un lien par outil, pas une
fusion.

Usage : python run_all.py [--no-browser]
  --no-browser : n'ouvre pas la page d'accueil (lancement sur un serveur sans écran, ou
                 vérification automatique du démarrage).
Arrêt : Ctrl+C (arrête proprement tous les outils, y compris le sous-processus de rechargement
automatique que Dash/Werkzeug relance lui-même en mode debug).
"""
import argparse
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
    ("financial_analysis", "http://localhost:8052"),
]
LANDING_PAGE = ROOT / "index.html"
STARTUP_TIMEOUT = 30.0


def _kill_tree(proc: subprocess.Popen):
    """Termine le processus et ses enfants. Le serveur de dev Dash/Werkzeug, en
    mode debug (utilisé par chaque app.py), se relance lui-même dans un
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
    l'erreur se noie dans les logs entremêlés des outils plutôt que d'être signalée tout de
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
    parser = argparse.ArgumentParser(description="Lance les outils du dépôt en parallèle.")
    parser.add_argument("--no-browser", action="store_true",
                        help="ne pas ouvrir la page d'accueil (serveur sans écran, vérification automatique)")
    args = parser.parse_args()

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
    # son propre JS sonde chaque app toutes les 2s et affiche "Prêt"/"Indisponible" par outil,
    # donc l'utilisateur voit l'état réel sans avoir à lire les logs du terminal.
    if not args.no_browser:
        webbrowser.open(LANDING_PAGE.resolve().as_uri())

    # Attente en parallèle (pas l'un après l'autre) : sinon, dans le pire cas où le premier met
    # tout son budget à répondre, le diagnostic des suivants n'arriverait qu'après plusieurs
    # STARTUP_TIMEOUT cumulés.
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
        print("\nArrêt des autres outils suite à cet échec...")
        for proc in procs:
            _kill_tree(proc)
        sys.exit(1)

    print(f"\nLes {len(APPS)} outils tournent (logs entremêlés ci-dessous). Clique sur une carte dans la "
          "page d'accueil (index.html) pour accéder à l'un d'eux. Ctrl+C pour tout arrêter.\n")
    exit_code = 0
    try:
        while True:
            for proc, (folder, _) in zip(procs, APPS):
                code = proc.poll()
                if code is not None:
                    print(f"\n{folder} s'est arrêté (code {code}) : arrêt des autres outils.")
                    exit_code = 1
                    raise KeyboardInterrupt
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nArrêt de tous les outils...")
    finally:
        for proc in procs:
            _kill_tree(proc)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
