# Valorisation d'actions : P/E, DCF & comparables (Dash)

Écran de valorisation interactif (Plotly Dash) pour comparer le P/E d'une
sélection d'actions françaises, allemandes, britanniques et américaines, et
estimer la valeur intrinsèque (DCF) et relative (comparables) d'un titre
sélectionné.

Ce ne sont pas des prédictions : chaque estimation dépend fortement des
hypothèses choisies. Projet frère :
[`../portfolio_projection`](../portfolio_projection) (simulation Monte Carlo
d'un plan d'épargne), indépendant de celui-ci.

## Fonctionnalités

- **Comparatif de P/E par secteur** (moyenne, distribution) sur CAC 40,
  DAX 40, FTSE 100 (sélection) et un échantillon de grandes capitalisations
  américaines, avec position de chaque titre vs son propre P/E historique
  sur 5 ans (un signal souvent plus parlant que la comparaison sectorielle).
- **DCF** (flux de trésorerie actualisés) : FCF de départ moyenné sur les
  3 derniers exercices clos plutôt que le seul FCF sur 12 mois glissants,
  avec avertissement explicite (plutôt qu'un chiffre trompeur) si le FCF
  reste négatif malgré ce lissage.
- **Valorisation par comparables** : prix implicite au P/E médian des pairs
  du même secteur, affiché en cross-check du DCF — les deux méthodes ne
  dépendent pas des mêmes données, un large écart entre elles est en
  lui-même un signal à creuser.
- **Détail du calcul dépliable** : projection du FCF année par année,
  historique FCF/capex/flux d'exploitation des exercices utilisés, valeur
  terminale, dette nette, et formule des comparables — pour que "pourquoi
  ce chiffre ?" se réponde en dépliant plutôt qu'en devant redemander.
- Infobulles (ⓘ) sur les hypothèses du DCF, interface FR/EN, cache disque
  des téléchargements (`yfinance`) pour limiter les appels réseau.

## Notes de conception

**FCF moyenné sur 3 ans plutôt que TTM.** Un DCF basé sur le seul free cash
flow des 12 derniers mois glissants (`freeCashflow` de Yahoo Finance) est
trompeur pour toute entreprise en pic de capex ponctuel — typiquement les
hyperscalers en pleine construction de data centers IA. Vérifié en
production sur Microsoft et Amazon : leur DCF ressortait à une fraction de
leur cours, non pas parce que le modèle était faux, mais parce que la
capex avait doublé en un an et écrasait temporairement le FCF TTM. Passer à
une moyenne sur les 3 derniers exercices clos (`market_data.
get_dcf_inputs`, avec repli sur le FCF TTM si l'historique annuel n'est pas
disponible) lisse ces à-coups sans masquer un vrai problème structurel — un
FCF qui reste négatif sur plusieurs exercices déclenche toujours
l'avertissement plutôt qu'un chiffre.

**Le bug pence/livre : un cas d'école de cohérence d'unités.** Yahoo
Finance cote certaines places boursières (Londres notamment) en pence
alors que les états financiers de l'entreprise (FCF, dette, trésorerie,
BPA) sont en livres — ou même dans une autre devise de reporting pour les
valeurs à double cotation (AstraZeneca et Shell facturent en USD tout en
cotant à Londres en GBp). Sans correction, un DCF sur n'importe quelle
valeur du FTSE 100 ressortait ~100x trop bas par rapport au prix affiché,
silencieusement (aucune erreur, juste un chiffre qui semblait juste
"très bearish"). Le module corrige ce décalage (`market_data.
_price_scale_factor`) en le déduisant empiriquement du P/E déjà correct
fourni par Yahoo (`prix / (P/E × BPA)`), ce qui fonctionne quelle que soit
la devise de reporting sans avoir à la connaître à l'avance. La
valorisation par comparables, elle, n'a jamais été affectée : en travaillant
par ratio au prix courant plutôt qu'en reconstruisant un prix à partir du
P/E des pairs, l'unité du BPA n'entre jamais en jeu.

**Comparables toujours calculés au sein du même secteur.** Le panier de
pairs est filtré sur le secteur du titre sélectionné, indépendamment du
filtre sectoriel du tableau au-dessus — comparer un P/E tech à un P/E
utilities n'aurait pas de sens. En dessous de 3 pairs valorisés (P/E
positif) dans le secteur, la valeur comparables est explicitement signalée
indisponible plutôt qu'affichée sur un échantillon trop petit pour être
significatif.

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

```bash
python app.py
```

L'application est servie sur [http://localhost:8051](http://localhost:8051)
(port modifiable via la variable d'environnement `PORT`).

## Structure du code

- `constants.py` : paniers d'actions par marché (CAC 40, DAX 40, FTSE 100, US).
- `i18n.py` : traductions FR/EN et palettes de couleurs.
- `market_data.py` : appels yfinance (P/E, FCF, dette, trésorerie...) et cache disque.
- `engine.py` : moteur de calcul pur (DCF, valorisation par comparables).
  Aucune dépendance Dash/réseau.
- `charts.py` : constructeur de graphique Plotly (état "pas encore de données").
- `layout.py` : construction de l'écran unique (pas de sidebar : un seul
  outil, tous ses contrôles sont dans le corps de la page).
- `app_instance.py` / `callbacks.py` / `app.py` : instance Dash, callbacks, point d'entrée.

## Tests

```bash
pip install -r requirements-dev.txt
pytest test_engine.py -v
```

Les tests couvrent le moteur de calcul pur (DCF, valorisation par
comparables), pas la couche interface, ni les appels réseau.

## Docker

```bash
docker build -t pea-stock-valuation .
docker run -p 8051:8051 pea-stock-valuation
```

## Avertissement

Outil personnel à but éducatif. Les estimations de valorisation reposent
sur des hypothèses réglables (croissance, taux d'actualisation, multiples
de pairs) qui ne préjugent pas des performances futures. Ceci ne constitue
pas un conseil en investissement.
