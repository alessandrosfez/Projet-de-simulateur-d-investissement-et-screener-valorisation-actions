"""
Petit résumé JSON (/api/summary) lu par la page d'accueil de run_all.py (index.html, port 8049),
qui l'affiche sur la carte de cet outil : la dernière société analysée (last_analysis.py).

Aucun appel réseau. Seule la page d'accueil a le droit de lire la réponse depuis le navigateur
(en-tête CORS limité à son adresse). Recopié et adapté dans chaque outil (aucun import croisé
entre outils).
"""
from flask import Flask, jsonify, request

import last_analysis

HOME_ORIGINS = {"http://localhost:8049", "http://127.0.0.1:8049"}


def build_summary() -> dict:
    return {"last_analysis": last_analysis.read_last_analysis()}


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
