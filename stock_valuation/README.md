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

- **Comparatif de P/E par secteur** (nuage de points : une action par point,
  médiane de chaque secteur, titres de la liste de suivi nommés) sur CAC 40,
  SBF 120 (composition reconstituée au 21/09/2026, voir `constants.py`),
  DAX 40, FTSE 100 (sélection) et un échantillon de grandes capitalisations
  américaines, avec position de chaque titre vs son propre P/E historique
  sur 5 ans (un signal souvent plus parlant que la comparaison sectorielle).
- **Tableau de criblage AG Grid** (`dash-ag-grid`) : tri et redimensionnement
  des colonnes, colonne Entreprise figée, sélection d'une ligne par case ou
  clic, définition de chaque indicateur au survol de son en-tête, couleurs
  qui suivent le mode sombre. Une valeur manquante s'affiche N/A et n'est
  jamais coloriée.
- **DCF** (flux de trésorerie actualisés) : FCF de départ moyenné sur les
  3 derniers exercices clos plutôt que le seul FCF sur 12 mois glissants,
  avec avertissement explicite (plutôt qu'un chiffre trompeur) si le FCF
  reste négatif malgré ce lissage.
- **Valorisation par comparables** : prix implicite au P/E médian des pairs
  du même secteur, affiché en cross-check du DCF — les deux méthodes ne
  dépendent pas des mêmes données, un large écart entre elles est en
  lui-même un signal à creuser.
- **Alertes de la liste de suivi** : pour chaque titre suivi (liste de suivi
  et journal), cinq signaux calculés sur tout l'univers chargé (indépendants
  des filtres du tableau) : cours au niveau ou sous ton prix cible, P/E dans les 20 % les plus bas de sa propre histoire, cours
  sous la valeur implicite au P/E médian d'au moins 3 pairs du secteur,
  cours sous le DCF aux hypothèses par défaut des curseurs, score
  composite ≥ 70. Une donnée manquante ne déclenche rien ; ce sont des
  pistes à creuser, pas des recommandations.
- **Ajouter des titres (toutes bourses)** : sous les marchés à cocher, un champ
  de recherche interroge Yahoo (nom ou ticker : Eutelsat, Novo Nordisk,
  ASML...) et propose les actions cotées avec leur place de cotation (marchés
  hors cote américains, certificats canadiens et lignes de réplication
  écartés). Un titre choisi est chargé seul et rejoint tout de suite le
  tableau, ses comparaisons sectorielles et son score ; il est gardé dans le
  fichier local du journal et chargé avec les marchés cochés à chaque fois.
- **Chargement instantané** : chaque chargement réussi est gardé dans un
  fichier local (`.stock_valuation_last_load.pkl`, ignoré par git). À
  l'ouverture de la page, ou après un changement de langue qui vidait
  auparavant le tableau, ces lignes s'affichent tout de suite et leurs
  marchés sont recochés. Une ligne sous le bouton indique leur âge
  (« données chargées il y a 3 h »). Au-delà d'une heure, durée du cache
  des appels Yahoo, un rechargement part en arrière-plan et les remplace
  quand il a fini ; s'il échoue, les lignes affichées restent en place.
- **Journal d'investissement** : pour chaque titre, une thèse, un prix cible
  (dans la devise de cotation du titre) et une date de revue. Chaque fiche
  montre l'écart du cours à la cible ; les revues dont la date est passée
  sont rappelées en tête. Stocké dans un fichier SQLite local
  (`.stock_valuation_journal.db`, ignoré par git, migrations versionnées).
  Chaque fiche porte une jauge : cours, prix cible, DCF par défaut et
  comparables P/E sur une même piste. Les titres du journal sont suivis par
  les alertes, qu'ils soient dans la liste de suivi ou non.
- **Liste de suivi durable** : enregistrée dans le même fichier local et
  restaurée à chaque ouverture de la page ou changement de langue. La valeur
  et ses options sont envoyées ensemble : la liste déroulante efface d'elle-même
  une valeur absente de ses options, ce qui vidait la liste au rechargement
  quand la valeur arrivait la première.
- **« Football field »** : une barre horizontale par méthode (DCF selon les
  scénarios bas/haut, DCF selon la grille de sensibilité, comparables P/E et
  VE/EBITDA du 1er au 3e quartile des pairs, médiane en valeur centrale),
  avec le cours actuel en trait vertical. On voit d'un coup d'oeil si les
  méthodes s'accordent et où se situe le cours dans leurs fourchettes.
- **Détail du calcul dépliable** : projection du FCF année par année,
  historique FCF/capex/flux d'exploitation des exercices utilisés, valeur
  terminale, dette nette, et formule des comparables — pour que "pourquoi
  ce chiffre ?" se réponde en dépliant plutôt qu'en devant redemander.
- Infobulles (ⓘ) sur les hypothèses du DCF, interface FR/EN, cache disque
  des téléchargements (`yfinance`) pour limiter les appels réseau : une
  heure pour ce qui suit le cours, un jour pour les comptes annuels. Le
  fichier est écrit au plus une fois toutes les 2 s (et non après chaque
  appel), sans les entrées périmées : un marché chargé à froid passe
  d'environ 15 s à 6-7 s, avec 2 écritures au lieu de près de 300.

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
"très bearish"). Une première correction déduisait le décalage
empiriquement du P/E fourni par Yahoo (`prix / (P/E × BPA)`,
`market_data._price_scale_factor`). Elle ne mesure en fait que la
sous-unité : Yahoo exprime le BPA dans la devise de cotation, pas dans
celle des comptes (Shell : comptes en USD, BPA en livres, ratio de 100
exactement). Le DCF des doubles cotations restait donc faussé de l'écart
de change (environ 33 % pour l'USD). Et la valeur d'entreprise mélangeait
une capitalisation en livres avec une dette en pence, ce qui faussait d'un
facteur ~100 les comparables VE/EBITDA de toutes les valeurs de Londres.
Les montants des états financiers sont désormais ramenés dans l'unité du
cours par le change réel (devise des comptes → devise de cotation, taux
Yahoo) puis le diviseur de sous-unité, et la capitalisation par le seul
diviseur (`market_data._statement_to_price_units`). L'ancien facteur sert
de repli quand une devise ou le taux de change manque. Un test vérifie
l'invariant qui aurait détecté le bug : au même multiple que lui-même, un
titre doit valoir exactement son cours. La valorisation par comparables
P/E n'a jamais été affectée : en travaillant par ratio au prix courant,
l'unité du BPA n'entre jamais en jeu.

**P/E historique sur cours bruts, track record sur cours ajustés.** Le
P/E moyen sur 5 ans divise les cours passés par le BPA actuel. Par
défaut, yfinance ajuste rétroactivement ces cours des dividendes versés
depuis : pour TotalEnergies, le cours ajusté d'il y a 5 ans ne vaut que
75 % du cours réellement coté. Le P/E de l'époque était donc minoré, et
un titre distribuant paraissait plus cher que son historique. Corrigé en
lisant les cours bruts (`auto_adjust=False`, toujours ajustés des
divisions comme le BPA) : le P/E moyen sur 5 ans passe de 7,5 à 8,5 pour
TotalEnergies et de 24,5 à 27,6 pour Sanofi. Un test vérifie
l'invariant : au cours actuel, le P/E implicite redonne le P/E affiché,
y compris en pence. Le track record (rendement, volatilité, drawdown)
garde au contraire les cours ajustés : il mesure le rendement total,
dividendes réinvestis. Dans le tableau, la capitalisation porte
désormais sa devise principale (GBP, et non le GBp du cours).

**P/E historique sur le BPA de chaque exercice.** Diviser 5 ans de cours
par le BPA d'aujourd'hui supposait des bénéfices stables, ce qui est faux
pour une valeur cyclique : le BPA de TotalEnergies a varié de 5,78 à
8,67 € entre 2022 et 2025. Le P/E de chaque semaine utilise désormais le
BPA du dernier exercice publié à cette date, réputé connu 3 mois après
la clôture pour n'utiliser aucune information que le marché n'avait pas
encore (`engine.pe_from_annual_eps`). Le BPA, publié dans la devise des
comptes, est converti dans l'unité du cours au change actuel. Yahoo ne
fournissant que 4 exercices, l'historique couvre environ 3,5 ans au lieu
de 5. Il n'est pas prolongé par l'ancienne méthode, pour ne pas mélanger
deux calculs dans une même moyenne. Sans BPA annuel, repli signalé sur le
BPA actuel constant. La lecture peut s'inverser : Sanofi passe d'un P/E
moyen de 27,6 (BPA constant) à 18,3, et son P/E actuel de 22,8, qui
semblait sous sa moyenne, est en fait au 88e centile de son historique.

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
- `journal_db.py` : journal d'investissement (SQLite local).
- `last_load.py` : dernier chargement réussi, pour l'affichage instantané.
- `charts.py` : constructeur de graphique Plotly (état "pas encore de données").
- `layout.py` : construction de l'écran unique (pas de sidebar : un seul
  outil, tous ses contrôles sont dans le corps de la page) et colonnes du
  tableau de criblage (formats, couleurs conditionnelles, `test_layout.py`).
- `app_instance.py` / `callbacks.py` / `app.py` : instance Dash, callbacks, point d'entrée.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

`test_callbacks_smoke.py` appelle chaque callback de l'écran avec les valeurs initiales de ses
entrées, avant chargement puis avec un univers fictif chargé, une ligne sélectionnée, une liste de suivi et un journal (fichier temporaire, jamais le vrai), données de marché simulées (aucun appel réseau). Il échoue si un
callback lève une erreur ou renvoie un nombre de valeurs différent de ses sorties déclarées,
des erreurs qui n'apparaissaient sinon qu'à l'écran.

`test_engine.py` couvre le moteur de calcul pur (DCF, valorisation par
comparables). `test_market_data.py` couvre la couche yfinance avec un
yfinance simulé, sans appel réseau : conversion de change et d'unités,
repli du FCF annuel sur le TTM. La couche interface n'est pas testée.

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
