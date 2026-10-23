# Projection PEA & Compte-Titres : simulation Monte Carlo (Dash)

Application web interactive (Plotly Dash) pour projeter l'évolution future
d'un portefeuille PEA/CTO par simulation Monte Carlo, calibrée sur
l'historique d'indices ou d'ETF réellement disponibles en PEA.

Ce n'est pas un outil de prédiction : chaque graphique montre une bande de
scénarios possibles (percentiles), pas un chiffre garanti. Projet frère :
[`../stock_valuation`](../stock_valuation) (valorisation d'actions
individuelles), indépendant de celui-ci.

Un onglet **Mon portefeuille réel** suit le PEA effectivement constitué
(achats, dividendes, valeur dans le temps, rééquilibrage) et le compare à ce
qu'une simulation aurait donné.

## Fonctionnalités

- **Deux modes d'affichage** : Prévision (simulation Monte Carlo, bandes de
  percentiles) ou Historique (croissance brute réellement observée, base 100,
  sans apports/frais/fiscalité — un vrai "qu'a fait le marché ?", avec ses
  propres statistiques : rendement annualisé, volatilité, max drawdown).
- **Deux onglets de simulation** : par indice (chaque indice simulé isolément) ou
  portefeuille pondéré (plusieurs allocations comparées avec les mêmes
  tirages aléatoires, rééquilibrage mensuel).
- **Mon portefeuille réel** : saisie ou import CSV (format maison ou export
  Trade Republic) des transactions et dividendes, valeur reconstruite dans le
  temps, réel vs simulé, projection depuis aujourd'hui avec la pondération
  actuelle, corrélations entre les lignes détenues, plan de rééquilibrage.
- **Répartition actuelle** : anneau des lignes détenues, à leur valeur de
  marché en euros, avec le total au centre et le nom de chaque fonds en
  légende. Une couleur fixe par ligne, attribuée par ticker et non par rang,
  pour qu'une ligne qui grossit ne change pas de couleur. Au-delà de six
  lignes, les plus petites sont regroupées en « Autres ». Une ligne sans
  cours est signalée sous le graphique plutôt que comptée pour 0.
- **Performance réelle** : XIRR (rendement pondéré par les flux), TWR
  (rendement pondéré par le temps) et comparaison à un indice de référence
  choisi (mêmes versements investis dans ce ticker : valeur et XIRR côte à
  côte avec le réel).
- **Jalons PEA** : date d'ouverture enregistrée, date des 5 ans et compte à
  rebours, part du plafond de 150 000 € consommée (avec la date estimée où
  il serait atteint au rythme actuel), impôt dû en cas de retrait
  aujourd'hui (avant ou après 5 ans).
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
- **Portefeuille réel** : saisie des achats et dividendes (ou import CSV,
  dont l'export Trade Republic), courbe de valeur reconstruite jour par jour,
  totaux (capital investi, frais, dividendes, P&L), plan de rééquilibrage vers des
  pondérations cibles, graphique « réel vs simulé », et reprise du rythme
  d'apport réel comme paramètre de simulation. Stockage SQLite local.
- Infobulles (ⓘ) sur les concepts clés (Sharpe, drawdown, méthode de
  simulation...), interface FR/EN, export/import de configuration en JSON,
  cache disque des téléchargements (`yfinance`) pour limiter les appels
  réseau.
- **Fraîcheur des données** : un badge discret dans l'en-tête indique la
  date des données de marché affichées (« données du JJ/MM ») et passe en
  avertissement au-delà de 7 jours.

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
- **Dividendes et frais dans la performance réelle** (même convention que
  les totaux de l'onglet) : un achat coûte montant + frais, mais seul le
  montant devient des parts, donc les frais pèsent sur le rendement. Un
  dividende est du cash perçu à sa date, pas réinvesti (le modèle ne crée
  aucune part à partir d'un dividende) ; il compte quand même dans le XIRR
  et le TWR, sinon un ETF distribuant paraîtrait moins bon qu'un ETF
  capitalisant à performance égale. Tout est calculé avant fiscalité.
- **Tous les cours en euros** : les montants saisis (achats, dividendes)
  sont en euros, mais yfinance cote chaque titre dans la devise de sa
  place. Or les ISIN d'un export Trade Republic se résolvent souvent vers
  une cotation en dollars : Apple → AAPL, Vanguard FTSE All-World →
  VWRA.L, iShares Core MSCI World → IWDA.L. La quantité (montant € ÷ prix
  €) était juste, mais la valeur était calculée avec le cours en dollars :
  VWRA.L surévalué d'environ 12 %, et une courbe qui ignorait le change.
  Les cours courants et historiques sont désormais divisés par la
  sous-unité éventuelle (pence) puis convertis au change Yahoo de chaque
  jour (XXXEUR=X, dernier taux connu un jour sans cotation). Sans taux de
  change, le cours est n.d. plutôt que laissé en dollars. Un test vérifie
  l'invariant qui aurait détecté le problème : achetée au cours du jour,
  une ligne vaut exactement le montant investi ce jour-là. La calibration
  Monte Carlo des tickers du portefeuille réel reste, elle, sur les
  rendements dans la devise de cotation (sans effet de change).
- **Cours bruts pour le réel, ajustés pour la référence** : yfinance ajuste
  par défaut les cours passés des dividendes (CAC.PA début 2024 : ~70 €
  ajusté contre ~74 € réel). Pour valoriser les positions réelles, on prend
  les cours bruts : ce sont les vraies valeurs de marché, et les dividendes
  déjà saisis en cash ne sont pas comptés deux fois. La référence utilise au
  contraire les cours ajustés (dividendes réinvestis), convention usuelle
  d'un indice de référence. Elle reçoit les mêmes sorties de cash que le réel
  (mêmes dates, montant + frais), achetées à la clôture du premier jour coté.
- **XIRR par dichotomie** : la valeur actuelle nette des flux est
  décroissante en r dès que les achats précèdent les entrées, donc une
  dichotomie sur [-99,99 %, +1000 %] converge à coup sûr, sans dépendre de
  scipy.
- **XIRR et TWR répondent à deux questions** : le XIRR mesure le rendement
  réellement obtenu sur ton argent (il dépend du moment des versements), le
  TWR chaîne les rendements entre deux flux et neutralise ce calendrier
  (c'est la performance des placements eux-mêmes). Un achat effectué un
  jour sans cotation prend effet au jour coté suivant, comme dans la
  courbe de valeur.
- **Migrations versionnées de la base** (`portfolio_db._MIGRATIONS`) : la
  version du schéma est stockée dans `PRAGMA user_version`, et une base
  existante ne reçoit que les étapes qui lui manquent, sans toucher à ses
  données. La v1 ajoute une table de réglages clé/valeur (date d'ouverture
  du PEA), pour éviter une nouvelle migration à chaque nouveau réglage.
- **Jalons PEA** : le délai de 5 ans court à partir de l'ouverture du PEA,
  pas du premier achat ; sans date renseignée, le premier achat sert
  d'estimation (signalée comme telle). Les versements ne sont pas saisis,
  donc le plafond est calculé sur les achats (montant + frais), avec la même
  logique de plafond que la simulation (`engine.cap_schedule`) :
  approximation surestimée si des achats ont été financés par des
  dividendes. L'impôt latent porte sur le gain = valeur des positions +
  dividendes perçus en cash − coût des achats. Cette formule reste juste
  même si des dividendes ont été réinvestis par un achat. Le taux est de
  17,2 % après 5 ans et de 30 % (PFU, avec clôture du plan) avant ; aucun
  impôt en moins-value.
- **Fraîcheur : dernière version connue en cas d'échec** : le cache se
  rafraîchit toutes les heures, donc en temps normal les données affichées
  ont moins d'une heure. Elles ne peuvent vieillir que si un
  rafraîchissement échoue (hors ligne, yfinance indisponible) : dans ce
  cas, `cached_ttl` sert la dernière version connue avec son horodatage
  d'origine, au lieu de faire échouer l'écran, et le badge le signale.
  Les historiques quotidiens lèvent une erreur quand yfinance ne renvoie
  rien, au lieu de mettre en cache une série vide à la place des bonnes
  données.
- **Le badge reflète ce qui est à l'écran** : il prend la plus ancienne
  des séries servies pendant la session, pas de tout le cache, qui garde
  aussi des séries que plus aucun écran n'utilise (ancien ticker, ancien
  horizon) et qui déclencheraient l'avertissement en permanence.

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

- `constants.py` : indices/ETF PEA, taux de fiscalité (dont retrait avant
  5 ans), plafond PEA.
- `i18n.py` : traductions FR/EN et palettes de couleurs.
- `market_data.py` : appels yfinance (historique d'indices/ETF, prix courants,
  cours quotidiens bruts et ajustés, résolution d'ISIN, noms d'instruments),
  cache disque et date de téléchargement de chaque série.
- `engine.py` : moteur de calcul pur (simulation Monte Carlo, DCA, frais,
  fiscalité, poids optimaux, mode objectif, validation walk-forward). Aucune
  dépendance Dash/réseau.
- `portfolio_engine.py` : moteur pur du portefeuille réel (positions, courbe
  de valeur, rééquilibrage, totaux, XIRR, TWR, indice de référence, jalons
  PEA et fiscalité latente, validation des imports CSV).
- `portfolio_db.py` : stockage SQLite du portefeuille réel (transactions,
  dividendes, pondérations cibles) et réglages, avec migrations versionnées
  du schéma.
- `charts.py` : constructeurs de graphiques Plotly.
- `results.py` : agrège les résultats du moteur en métriques/figures affichables.
- `layout.py` : construction de la sidebar et des quatre onglets.
- `callbacks/` : callbacks Dash, un module par onglet (`par_indice.py`,
  `portefeuille.py`, `portefeuille_reel.py`, `validation.py`) plus
  `shared.py` (affichage conditionnel, langue, configuration JSON, badge de
  fraîcheur). Importer le paquet suffit à tout enregistrer ; aucun module
  n'utilise de fonction d'un autre.
- `app_instance.py` / `app.py` : instance Dash, point d'entrée.

## Tests

```bash
pip install -r requirements-dev.txt
ruff check .
pytest -v
mypy --disallow-untyped-defs --disallow-incomplete-defs engine.py portfolio_engine.py
```

Les deux moteurs de calcul purs sont entièrement annotés et vérifiés par
mypy en CI (avec `pandas-stubs`, sans quoi pandas serait vu comme non
typé). `--disallow-untyped-defs` est indispensable : sans lui, mypy ignore
silencieusement le corps de toute fonction non annotée.

Les tests couvrent les moteurs de calcul purs (frais, fiscalité, bootstrap,
DCA, simulation Monte Carlo, poids optimaux, mode objectif, validation
walk-forward, portefeuille réel), la base SQLite (en mémoire) et le cache
de `market_data.py` (TTL, dernière version connue, fraîcheur) avec yfinance
remplacé par des doublures : pas la couche interface, et aucun appel
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
