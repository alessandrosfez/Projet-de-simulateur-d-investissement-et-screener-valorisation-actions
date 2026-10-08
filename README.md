# Outils PEA & Compte-Titres : Projection & Valorisation

Deux outils Dash indépendants, construits autour de la même discipline
quantitative appliquée à l'investissement en PEA/compte-titres — l'un
répond à *combien épargner*, l'autre à *quoi acheter* :

- **[`portfolio_projection/`](portfolio_projection/)** — simulation Monte
  Carlo d'un plan d'épargne (par indice ou portefeuille pondéré),
  calibrée sur l'historique réel d'indices et d'ETF disponibles en PEA :
  quelle trajectoire de capital attendre d'un plan d'épargne donné, avec
  quelle incertitude. Pour suivre un PEA déjà constitué (positions et valeur
  réelles dans le temps) plutôt que projeter un plan hypothétique, voir le
  projet `invest_db` (hors de ce dépôt), mieux adapté à ce besoin.
- **[`stock_valuation/`](stock_valuation/)** — écran de valorisation
  d'actions individuelles (P/E sectoriel, DCF, comparables) sur CAC 40,
  DAX 40, FTSE 100 et un échantillon d'actions américaines : une fois le
  montant à investir décidé, sur quels titres, et à quel prix par rapport
  à leur valeur estimée.

Chaque dossier est un projet Dash **complet et autonome** (aucun import
croisé entre les deux) : son propre `app.py`, ses propres dépendances, son
propre Dockerfile, sa propre suite de tests, et un README qui détaille sa
méthodologie. Ils partagent une architecture volontairement identique
(moteur de calcul pur testé séparément de la couche Dash, cache disque des
appels `yfinance`) plutôt que du code partagé, pour que chacun reste
indépendamment clonable et compréhensible.

Aucun des deux n'est un outil de prédiction : chaque projection montre une
bande de scénarios possibles, pas un chiffre garanti ; chaque estimation de
valorisation dépend fortement des hypothèses choisies. Outils personnels à
but éducatif, pas un conseil en investissement.

## Démarrage rapide

```bash
pip install -r portfolio_projection/requirements.txt -r stock_valuation/requirements.txt
python run_both.py
```

Lance les deux outils en parallèle (http://localhost:8050 et
http://localhost:8051) et ouvre `index.html`, une page d'accueil statique
avec un lien vers chacun (et leur statut de démarrage en direct) ; Ctrl+C
pour tout arrêter. Pur confort de lancement : `run_both.py` et `index.html`
ne créent aucun lien entre les deux projets, qui restent deux process Dash
indépendants — juste un point d'entrée commun.

Pour lancer un seul des deux (ou via Docker), voir le README du dossier
correspondant.
