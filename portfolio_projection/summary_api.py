"""
Petit résumé JSON (/api/summary) lu par la page d'accueil de run_all.py (index.html, port 8049),
qui l'affiche sur la carte de cet outil : valeur du portefeuille réel au dernier relevé, plus-value,
écart avec le relevé précédent.

Lu uniquement dans la base locale (relevés quotidiens de portfolio_db.record_value_snapshot) :
aucun appel réseau, la page d'accueil ne doit jamais attendre Yahoo. Seule la page d'accueil a le
droit de lire la réponse depuis le navigateur (en-tête CORS limité à son adresse) : une autre page
web ouverte dans le navigateur ne peut pas lire ces montants. Recopié et adapté dans chaque outil
(aucun import croisé entre outils).
"""
from flask import Flask, jsonify, request

import portfolio_db
import portfolio_engine

# Adresses de la page d'accueil servie par run_all.py (localhost et 127.0.0.1 sont deux origines
# distinctes pour le navigateur).
HOME_ORIGINS = {"http://localhost:8049", "http://127.0.0.1:8049"}


def build_summary() -> dict:
    """{"status": "empty"} sans relevé ; sinon le dernier relevé et l'évolution depuis le relevé
    d'un jour précédent (None s'il n'y en a pas). Un relevé n'existe que si toutes les lignes avaient
    un cours ce jour-là : les montants ne sont jamais calculés avec un cours manquant pris pour 0."""
    snapshots = portfolio_db.get_value_snapshots()
    if snapshots.empty:
        return {"status": "empty", "transactions": int(len(portfolio_db.get_transactions()))}
    last = snapshots.iloc[-1]
    value, invested = float(last["value_eur"]), float(last["invested_eur"])
    since = portfolio_engine.since_last_visit(snapshots, str(last["day"]), value, invested)
    return {
        "status": "ok",
        "day": str(last["day"]),
        "value_eur": value,
        "invested_eur": invested,
        "gain_eur": value - invested,
        "gain_pct": (value / invested - 1) * 100 if invested > 0 else None,
        "previous": None if since is None else {
            "day": since["day"].strftime("%Y-%m-%d"),
            "value_delta_eur": since["value_delta"],
            "market_delta_eur": since["market_delta"],
        },
    }


def register(server: Flask):
    """Ajoute la route au serveur Flask de l'app Dash."""

    @server.route("/api/summary")
    def summary():
        response = jsonify(build_summary())
        origin = request.headers.get("Origin")
        if origin in HOME_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        response.headers["Cache-Control"] = "no-store"
        return response
