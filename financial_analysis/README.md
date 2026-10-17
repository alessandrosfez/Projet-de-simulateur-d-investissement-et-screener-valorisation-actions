# Analyse financière : qualité et solidité des comptes (Dash)

Lecture des états financiers d'une société cotée dans l'esprit d'une due
diligence d'audit ou de Transaction Services : **les comptes sont-ils
fiables et solides ?** Projets frères, indépendants de celui-ci :
[`../portfolio_projection`](../portfolio_projection) (combien épargner) et
[`../stock_valuation`](../stock_valuation) (quoi acheter).

Ce sont des signaux à creuser, pas des verdicts : les données viennent de
Yahoo Finance sans retraitement par un analyste.

## Fonctionnalités

- **Choix de la société** : n'importe quel ticker Yahoo Finance, ou une
  sélection rapide parmi les valeurs du CAC 40.
- **États financiers normalisés** : compte de résultat, bilan et tableau
  de flux de trésorerie annuels, ramenés à un schéma interne stable
  (chiffre d'affaires, EBIT, résultat net, CFO, créances clients, stocks,
  dettes fournisseurs, dettes locatives...). Chaque cellule indique en
  infobulle d'où vient son chiffre, et chaque poste a sa définition.
- **Couverture affichée** : yfinance ne fournit qu'environ 4 exercices,
  l'interface le rappelle à côté des chiffres.
- **Devises** : cours et capitalisation ramenés dans la devise des comptes
  (cours en pence à Londres, double cotation), avec le détail du calcul.
- **Banques et assureurs détectés** : Beneish, Altman et l'analyse du BFR
  y sont déclarés non applicables, avec un message clair plutôt que des
  chiffres absurdes.
- Interface FR/EN, thèmes clair et sombre, cache disque des appels
  yfinance.

## Notes de conception

- **Un schéma interne plutôt que les libellés yfinance** : les libellés
  (« Total Revenue », « Net PPE »...) varient d'une société et d'une
  version de yfinance à l'autre. Le moteur ne les lit qu'à un seul endroit
  (`engine.FIELD_SCHEMA`) ; tout le reste travaille sur des clés stables.
- **Ordre de recherche d'un poste** : d'abord le libellé publié exact
  (éventuellement dans un autre état : les dotations aux amortissements
  figurent aussi au tableau de flux), puis une identité comptable (marge
  brute = CA − coût des ventes), puis un poste voisin (« Receivables »,
  plus large que les seules créances clients). Une identité exacte est
  plus fidèle qu'un poste seulement proche, d'où cet ordre. La provenance
  est conservée et affichée (publié, dérivé, voisin), et les postes non
  publiés apparaissent en italique.
- **EBIT et EBITDA de Yahoo** : Yahoo calcule l'EBIT comme résultat avant
  impôt + charges d'intérêts, et l'EBITDA comme EBIT + dotations (vérifié
  à l'unité près sur Air Liquide, LVMH, Schneider et Carrefour). Ces
  identités servent de repli ; le résultat opérationnel publié, qui s'en
  écarte de quelques %, n'est qu'un voisin.
- **Jamais de 0 par défaut** : un poste introuvable vaut `None`, affiché
  « n.d. » avec la raison (absent de yfinance, ou identité non calculable
  faute de tel poste). Un 0 publié reste un 0. Un exercice sans aucune
  donnée (yfinance en ajoute souvent un) est écarté plutôt qu'affiché
  comme une colonne de « n.d. ».
- **Devises : les comptes ne sont jamais convertis**, seules les données de
  marché le sont. Vérifié sur Shell, AstraZeneca, Tesco et Unilever : à
  Londres, Yahoo donne le cours en pence (GBp), mais la capitalisation et
  le BPA en livres, même quand les comptes sont en USD ou en EUR. Le cours
  est donc divisé par 100, puis cours et capitalisation sont convertis au
  taux de change Yahoo. L'heuristique de `stock_valuation`
  (cours ÷ (P/E × BPA)) ne mesure que la sous-unité, jamais le change : elle
  sert ici de contrôle de cohérence du diviseur, avec une alerte en cas
  d'écart.
- **Banques et assureurs** : reconnus à l'industrie Yahoo (« Banks - … »,
  « Insurance - … »), pas au secteur « Financial Services », qui couvre
  aussi les gérants d'actifs ou les bourses. Les courtiers en assurance,
  gérants d'actifs et bourses restent analysés, avec un avertissement :
  leur bilan peut contenir des fonds de tiers. L'exemple de BNP Paribas
  montre l'enjeu : son EBIT reconstitué atteint 67 Md€, gonflé par 50 Md€
  de charges d'intérêts, qui sont la matière première d'une banque.
- **Échecs réseau non mis en cache** : les couches cachées de
  `market_data.py` lèvent une exception quand yfinance ne renvoie rien,
  pour qu'un échec ponctuel ne reste pas 24 h en cache à la place des
  vraies données.

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

```bash
python app.py
```

L'application est servie sur [http://localhost:8052](http://localhost:8052)
(port modifiable via la variable d'environnement `PORT`).

## Structure du code

- `constants.py` : sélection CAC 40, classement sectoriel, sous-unités
  monétaires.
- `i18n.py` : traductions FR/EN (dont la définition de chaque poste) et
  palettes de couleurs.
- `market_data.py` : appels yfinance (états financiers annuels, profil,
  taux de change) et cache disque. Ne transforme rien.
- `engine.py` : moteur de calcul pur (normalisation, classement sectoriel,
  conversion des données de marché). Aucune dépendance Dash, réseau ou
  disque.
- `charts.py` : constructeurs de graphiques Plotly.
- `layout.py` : construction de l'écran et mise en forme (montants,
  provenance, tableaux).
- `app_instance.py` / `callbacks.py` / `app.py` : instance Dash, callbacks,
  point d'entrée.

## Tests

```bash
pip install -r requirements-dev.txt
ruff check .
pytest -v
```

Les tests couvrent le moteur pur (normalisation sur des DataFrames
synthétiques, postes manquants, identités comptables, classement
sectoriel, devises) et `market_data.py` avec yfinance remplacé par des
doublures : aucun appel réseau.

## Docker

```bash
docker build -t financial-analysis .
docker run -p 8052:8052 financial-analysis
```

## Avertissement

Outil personnel à but éducatif. Les données de Yahoo Finance peuvent
différer des comptes publiés ; les analyses sont des signaux, pas un avis
d'audit ni un conseil en investissement.
