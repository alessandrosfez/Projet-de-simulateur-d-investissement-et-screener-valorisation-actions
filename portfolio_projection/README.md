# Projection PEA & Compte-Titres : simulation Monte Carlo (Dash)

Application web interactive (Plotly Dash) pour projeter l'évolution future
d'un portefeuille PEA/CTO par simulation Monte Carlo, calibrée sur
l'historique d'indices ou d'ETF réellement disponibles en PEA.

Ce n'est pas un outil de prédiction : chaque graphique montre une bande de
scénarios possibles (percentiles), pas un chiffre garanti. Projet frère :
[`../stock_valuation`](../stock_valuation) (valorisation d'actions
individuelles), indépendant de celui-ci.

Un onglet **Mon portefeuille réel** permet aussi de suivre un PEA réellement
constitué (transactions, dividendes, valeur effective, rééquilibrage) à côté
des projections.

## Fonctionnalités

- **Deux modes d'affichage** : Prévision (simulation Monte Carlo, bandes de
  percentiles) ou Historique (croissance brute réellement observée, base 100,
  sans apports/frais/fiscalité — un vrai "qu'a fait le marché ?", avec ses
  propres statistiques : rendement annualisé, volatilité, max drawdown).
- **Onglets de simulation** : par indice (chaque indice simulé isolément) ou
  portefeuille pondéré (plusieurs allocations comparées avec les mêmes
  tirages aléatoires, rééquilibrage mensuel).
- **Mon portefeuille réel** : saisie ou import CSV (format maison ou export
  Trade Republic) des transactions et dividendes, valeur reconstruite dans le
  temps, réel vs simulé, projection depuis aujourd'hui avec la pondération
  actuelle, corrélations entre les lignes détenues, plan de rééquilibrage.
- **Validation du modèle** : backtest walk-forward qui vérifie si les bandes
  de percentiles sont fiables (taux de couverture observé vs nominal,
  histogramme des PIT), loi de Student et bootstrap par blocs comparés côte
  à côte.
- **Simulation** (mode Prévision) paramétrique (loi de Student, queues
  épaisses) ou bootstrap par blocs de l'historique réel.
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
- Infobulles (ⓘ) sur les concepts clés (Sharpe, drawdown, méthode de
  simulation...), interface FR/EN, export/import de configuration en JSON,
  cache disque des téléchargements (`yfinance`) pour limiter les appels
  réseau.

## Notes de conception

- **Loi t de Student plutôt que gaussienne** (mode paramétrique) : une
  gaussienne sous-estime nettement la fréquence des rendements extrêmes.
  Le degré de liberté (`STUDENT_T_DOF = 5` dans `engine.py`) reste dans la
  fourchette généralement observée pour des rendements mensuels d'indices
  actions (queues épaisses, variance finie) sans être un choix agressif.
  Un même tirage chi² est partagé entre tous les actifs d'une simulation
  multi-actifs pour créer une dépendance de queue (les actifs plongent
  plus souvent ensemble), pas juste des marges individuellement épaisses.
- **Bootstrap par blocs plutôt que par tirage indépendant** (mode
  historique) : rééchantillonner mois par mois détruirait l'autocorrélation
  des crises (un krach dure plusieurs mois consécutifs). Le bootstrap par
  blocs (taille réglable, 12 mois par défaut) préserve l'enchaînement d'une
  séquence réelle comme 2008, au prix de rester borné aux scénarios déjà
  vus dans l'historique.
- **Mode objectif sans re-simulation** : calculer l'apport mensuel
  nécessaire pour atteindre un capital cible pourrait sembler exiger de
  relancer Monte Carlo à chaque changement de curseur. `engine.
  compute_objective_contribution` exploite plutôt la linéarité de la
  récursion d'accumulation en l'apport mensuel (`valeur = valeur×(1+r) +
  apport`) : la valeur finale à un percentile donné est proportionnelle à
  l'apport déjà simulé, donc l'apport requis se déduit par une règle de
  trois — pas de nouveau tirage aléatoire, résultat instantané. Ne vaut que
  pour la stratégie d'apport constant en accumulation pure (le plancher à 0
  en décumulation casserait la linéarité).
- **Poids suggérés avec shrinkage** : les rendements moyens historiques sont
  un estimateur très bruité du rendement futur (peu d'observations, forte
  variance) ; les utiliser bruts pousse l'optimiseur Sharpe vers des
  solutions de coin (tout sur l'actif qui a eu le plus de chance sur la
  période). Le shrinkage (réglable, 50 % par défaut) les ramène vers leur
  moyenne d'ensemble, ce qui stabilise fortement l'allocation suggérée.
- **Validation walk-forward sans fuite du futur** (`engine.
  walk_forward_calibration`) : pour chaque date d'origine t, le modèle est
  calibré uniquement sur l'historique antérieur à t (fenêtre expansible :
  c'est ce dont disposait réellement un investisseur à cette date), y
  compris pour le bootstrap par blocs qui ne tire que dans cette fenêtre.
  On simule la croissance de 1 € sur l'horizon H, puis on situe la
  croissance réellement observée dans cette distribution : son rang
  percentile (PIT). Un modèle bien calibré donne des PIT uniformes sur
  [0, 1] ; la couverture d'une bande se déduit directement des PIT, sans
  conserver chaque distribution simulée. Un test espionne les appels au
  simulateur pour garantir que la fenêtre de calibration de chaque origine
  est exactement l'historique antérieur à t.
- **Fenêtres chevauchantes, à ne pas surinterpréter** : deux origines
  successives partagent presque tous les mois de leur horizon dès que le
  pas est plus petit que H, donc elles ne sont pas indépendantes. Le nombre
  effectif d'observations est d'environ (durée de l'historique / H), bien
  moins que le nombre d'origines testées ; l'interface l'affiche à côté du
  résultat. L'onglet utilise par défaut l'indice brut, sur 50 ans
  d'historique, car les ETF PEA ont trop peu d'historique pour plus d'une
  poignée d'origines.
- **Ce que la validation montre** : sur des données synthétiques tirées de
  la loi même du modèle, la couverture est proche du nominal quand la
  fenêtre de calibration est longue. Avec des fenêtres réalistes, et sur
  l'historique réel du S&P 500, la bande 5–95 % ne couvre qu'environ 80 %
  des réalisations : le modèle utilise la moyenne et la volatilité estimées
  comme si elles étaient connues, sans tenir compte de l'incertitude de ces
  estimations, donc les bandes affichées sont un peu trop étroites.

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

```bash
python app.py
```

L'application est servie sur [http://localhost:8050](http://localhost:8050)
(port modifiable via la variable d'environnement `PORT`).

## Structure du code

- `constants.py` : indices/ETF PEA, taux de fiscalité, plafond PEA.
- `i18n.py` : traductions FR/EN et palettes de couleurs.
- `market_data.py` : appels yfinance (historique d'indices/ETF, prix courants,
  résolution d'ISIN, noms d'instruments) et cache disque.
- `engine.py` : moteur de calcul pur (simulation Monte Carlo, DCA, frais,
  fiscalité, poids optimaux, mode objectif, validation walk-forward). Aucune
  dépendance Dash/réseau.
- `portfolio_engine.py` : moteur pur du portefeuille réel (positions, courbe
  de valeur, rééquilibrage, totaux, validation des imports CSV).
- `portfolio_db.py` : stockage SQLite du portefeuille réel.
- `charts.py` : constructeurs de graphiques Plotly.
- `results.py` : agrège les résultats du moteur en métriques/figures affichables.
- `layout.py` : construction de la sidebar et des quatre onglets.
- `app_instance.py` / `callbacks.py` / `app.py` : instance Dash, callbacks, point d'entrée.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

Les tests couvrent les moteurs de calcul purs (frais, fiscalité, bootstrap,
DCA, simulation Monte Carlo, poids optimaux, mode objectif, validation
walk-forward, portefeuille réel), pas la couche interface, ni les appels
réseau.

## Docker

```bash
docker build -t pea-portfolio-projection .
docker run -p 8050:8050 pea-portfolio-projection
```

## Avertissement

Outil personnel à but éducatif. Les projections reposent sur des hypothèses
statistiques (rendements/volatilité/corrélations historiques) qui ne
préjugent pas des performances futures. Ceci ne constitue pas un conseil en
investissement.
