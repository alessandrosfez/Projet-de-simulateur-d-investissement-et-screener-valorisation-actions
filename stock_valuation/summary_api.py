"""
Petit résumé JSON (/api/summary) lu par la page d'accueil de run_all.py (index.html, port 8049),
qui l'affiche sur la carte de cet outil : entrées du journal, revues dues, titres au niveau ou sous
leur prix cible, âge des données.

Lu uniquement dans les fichiers locaux (journal_db, last_load) : aucun appel réseau. Le cours
comparé au prix cible est celui du dernier chargement, daté par « loaded_at » ; un titre absent de ce
chargement n'est compté ni dessous ni dessus. Seule la page d'accueil a le droit de lire la
réponse depuis le navigateur (en-tête CORS limité à son adresse). Recopié et adapté dans chaque
outil (aucun import croisé entre outils).
"""
import pandas as pd
from flask import Flask, jsonify, request

import journal_db
import last_load
from engine import reviews_due

HOME_ORIGINS = {"http://localhost:8049", "http://127.0.0.1:8049"}


def build_summary() -> dict:
    entries = journal_db.get_entries()
    saved = last_load.read_last_load()
    rows = {r["Ticker"]: r for r in (saved or {}).get("rows", [])}

    def name(ticker):
        return rows.get(ticker, {}).get("Entreprise") or ticker

    below = [name(e["ticker"]) for e in entries
             if e["target_price"] is not None and rows.get(e["ticker"], {}).get("price") is not None
             and rows[e["ticker"]]["price"] <= e["target_price"]]
    due = reviews_due(entries, pd.Timestamp.today().normalize())
    return {
        "journal_entries": len(entries),
        "reviews_due": [name(e["ticker"]) for e in due],
        "below_target": below,
        "loaded_at": None if saved is None else saved["saved_at"],
        "loaded_stocks": len(rows),
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
