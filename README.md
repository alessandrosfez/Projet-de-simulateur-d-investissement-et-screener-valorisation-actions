# Outils PEA & Compte-Titres : Projection & Valorisation (Dash)

Application web interactive (Plotly Dash) articulée autour de deux volets :
la **projection** de l'évolution future d'un portefeuille PEA/CTO par
simulation Monte Carlo (calibrée sur l'historique d'indices ou d'ETF
réellement disponibles en PEA), et la **valorisation** d'actions
individuelles (P/E sectoriel, DCF, comparables) pour éclairer le choix des
titres qui composent ce portefeuille.

Ce n'est pas un outil de prédiction : chaque graphique de projection montre
une bande de scénarios possibles (percentiles), pas un chiffre garanti ; et
chaque estimation de valorisation dépend fortement des hypothèses choisies.

## Fonctionnalités

- **Deux modes** : par indice (chaque indice simulé isolément) ou portefeuille
  pondéré (plusieurs allocations comparées avec les mêmes tirages aléatoires,
  rééquilibrage mensuel).
- **Simulation** paramétrique (loi de Student, queues épaisses) ou bootstrap
  par blocs de l'historique réel, avec backtest historique superposé aux
  bandes de percentiles pour comparer projection et réalité passée.
- **Risque de séquence des rendements** : impact du timing d'un krach (début
  vs fin de la phase d'accumulation) sur le capital final.
- **Poids suggérés** : Sharpe maximal, volatilité minimale, parité de risque,
  avec shrinkage réglable et surcharge manuelle des rendements attendus.
- **Frais, inflation, fiscalité** (PEA > 5 ans, CTO avec PFU ou barème/TMI),
  affichage en euros nominaux ou constants.
- **Phase de retraits** (décumulation) après la phase d'accumulation, avec
  choc de marché optionnel (ampleur, durée, timing aléatoire ou fixe).
- **Mode objectif** : calcule l'apport mensuel nécessaire pour atteindre un
  capital cible.
- **Onglet valorisation actions** (CAC 40, DAX 40, FTSE 100, échantillon
  d'actions américaines) :
  - Comparatif de P/E par secteur (moyenne, distribution) et position de
    chaque titre vs son propre P/E historique sur 5 ans.
  - **DCF** (flux de trésorerie actualisés) : FCF de départ moyenné sur les
    3 derniers exercices clos plutôt que le seul FCF sur 12 mois glissants,
    pour lisser les pics de capex ponctuels (ex. hyperscalers en pleine
    construction de data centers IA) ; avertissement explicite (plutôt qu'un
    chiffre trompeur) si le FCF reste négatif malgré ce lissage.
  - **Valorisation par comparables** : prix implicite au P/E médian des
    pairs du même secteur, affiché en cross-check du DCF.
  - Détail du calcul dépliable : projection du FCF année par année,
    historique FCF/capex/flux d'exploitation des exercices utilisés, valeur
    terminale, dette nette, et formule des comparables.
- Infobulles (ⓘ) sur les concepts clés (Sharpe, drawdown, méthode de
  simulation, hypothèses du DCF...), interface FR/EN, export/import de
  configuration en JSON, cache disque des téléchargements (`yfinance`) pour
  limiter les appels réseau.

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

```bash
python app.py
```

L'application est servie sur [http://localhost:8050](http://localhost:8050).

## Structure du code

- `constants.py` : indices/ETF PEA, paniers d'actions par marché, taux de fiscalité.
- `i18n.py` : traductions FR/EN et palettes de couleurs.
- `market_data.py` : appels yfinance et cache disque.
- `engine.py` : moteur de calcul pur (simulation Monte Carlo, DCA, frais,
  fiscalité, poids optimaux, DCF, valorisation par comparables). Aucune
  dépendance Dash/réseau.
- `charts.py` : constructeurs de graphiques Plotly.
- `results.py` : agrège les résultats du moteur en métriques/figures affichables.
- `layout.py` : construction de la sidebar et des onglets.
- `app_instance.py` / `callbacks.py` / `app.py` : instance Dash, callbacks, point d'entrée.

## Tests

```bash
pip install -r requirements-dev.txt
pytest test_engine.py -v
```

Les tests couvrent le moteur de calcul pur (frais, fiscalité, bootstrap,
DCA, simulation Monte Carlo, poids optimaux, mode objectif, DCF,
valorisation par comparables), pas la couche interface, ni les appels
réseau.

## Docker

```bash
docker build -t pea-forecast-dash .
docker run -p 8050:8050 pea-forecast-dash
```

## Avertissement

Outil personnel à but éducatif. Les projections reposent sur des hypothèses
statistiques (rendements/volatilité/corrélations historiques) qui ne
préjugent pas des performances futures. Ceci ne constitue pas un conseil en
investissement.
