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
- **Qualité des résultats** : conversion du résultat en cash (CFO / résultat
  net, FCF / résultat net) et ratio d'accruals de Sloan, par exercice, avec
  le détail de chaque calcul en infobulle.
- **Pont du résultat net au CFO** : cascade par exercice (dotations,
  variation du BFR, autres éléments), qui retombe exactement sur le CFO
  publié.
- **BFR en jours** : DSO, DIO, DPO et cycle de conversion de trésorerie,
  leur évolution sur la période, et un graphique.
- **Scores d'alerte** : Beneish M-score (8 indices, seuil −1,78, à côté des
  moyennes de l'échantillon de Beneish), Altman Z-score (Z d'origine pour
  les industriels, Z'' pour les autres, choix automatique et bascule
  manuelle, zones sûre / grise / détresse) et Piotroski F-score (9 critères
  détaillés). Chaque indice, ratio ou critère affiche le calcul complet.
- **Devises** : cours et capitalisation ramenés dans la devise des comptes
  (cours en pence à Londres, double cotation), avec le détail du calcul.
- **Banques et assureurs détectés** : Beneish, Altman, Piotroski, la
  qualité des résultats et l'analyse du BFR y sont déclarés non
  applicables, avec un message clair plutôt que des chiffres absurdes.
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
- **Chaque ratio porte son calcul** : le moteur renvoie la valeur, ses
  composantes, sa formule, ses mentions (repli sur un poste voisin) et, si
  elle manque, la raison. L'interface affiche la formule remplie avec les
  montants réels (« créances clients 2,87 Md ÷ CA 26,94 Md × 365 = 39 j »),
  de quoi refaire le calcul à la main.
- **Résultat net y compris minoritaires** pour la conversion en cash et
  les accruals : même périmètre que le CFO consolidé, qui couvre 100 % des
  filiales. Repli signalé sur la part du groupe si Yahoo ne fournit pas
  cette version. Un résultat nul ou négatif rend ces ratios n.d. :
  rapportés à une perte, ils inverseraient leur sens.
- **Accruals sur actif moyen** : (résultat net − CFO) / ((actif
  d'ouverture + de clôture) / 2), sur le modèle de Sloan (1996). Le plus
  ancien exercice est n.d. faute de bilan d'ouverture.
- **IFRS 16 et CFO** : les remboursements de dettes locatives sont classés
  en flux de financement, ce qui gonfle le CFO des sociétés très
  locataires. Carrefour affiche ainsi un CFO/RN de plus de 10x en 2025 :
  l'infobulle du ratio le rappelle.
- **Pont résultat → CFO bouclé par un résidu** : yfinance ne détaille pas
  de façon homogène les éléments non monétaires (impôts différés,
  rémunérations en actions, plus-values de cession...). La ligne « autres
  éléments » est donc le résidu qui fait retomber le pont sur le CFO
  publié. Un élément identifié mais absent une année donnée n'est pas pris
  pour 0 : il est signalé comme inclus dans ce résidu.
- **BFR sur soldes de clôture** : pratique courante en Transaction
  Services, et disponible sur les 4 exercices plutôt que 3 avec des soldes
  moyens. DSO sur le chiffre d'affaires, DIO et DPO sur le coût des
  ventes. Sans coût des ventes (charges présentées par nature, fréquent en
  Europe), DIO et DPO sont n.d. : les calculer sur le CA changerait leur
  sens. Sans stocks publiés (Capgemini, société de services), DIO et cycle
  de conversion sont n.d. plutôt que de supposer des stocks nuls. Les
  postes « Receivables »/« Payables » de Yahoo, plus larges, ne servent
  qu'en repli, avec la mention « surestimé ».
- **Banques et assureurs** : la conversion en cash et les accruals y sont
  aussi non applicables, leur CFO étant dominé par les flux de dépôts et de
  crédits (des dizaines de milliards d'une année sur l'autre).
- **Sources des scores, vérifiées sur pièce** : coefficients et moyennes de
  Beneish lus dans l'article d'origine (version de travail de juin 1999,
  tableaux 2 et 3), coefficients d'Altman (1968, X5 à 0,999, souvent
  arrondi à 1,0) et Z'' (Altman 1995, repris par Altman et al. 2017),
  critères de Piotroski (2000). Les tests reproduisent un exemple chiffré
  publié pour chaque score (sources citées dans `test_scores.py`).
- **Beneish : couples d'exercices et données manquantes** : les 8 indices
  comparent t à t-1, pour chaque couple consécutif disponible (3 couples
  avec 4 exercices), le plus récent étant résumé. Les coefficients ont été
  estimés conjointement : dès qu'un indice manque, le M-score officiel est
  n.d. Une variante indicative remplace alors les indices manquants par 1
  (aucune variation), ce que faisait Beneish lui-même pour DEPI et SGAI
  quand COMPUSTAT ne fournissait pas la donnée ; TATA, un niveau sans
  valeur neutre, n'est jamais neutralisé. Le SGAI manque souvent pour les
  sociétés européennes, qui ne publient pas de SG&A séparé (Air Liquide).
- **Beneish : écarts assumés avec l'article** : TATA est calculé par les
  flux de trésorerie, (résultat net − CFO) / actif, plutôt que par les
  variations de postes du bilan, méthode moins sujette aux erreurs de
  mesure (Hribar et Collins, 2002). La dette à long terme du LVGI inclut
  les dettes locatives non courantes (IFRS 16), les courantes étant déjà
  dans le passif courant. L'AQI suit l'article : 1 − (actif courant +
  immobilisations corporelles) / actif total, sans les titres de placement
  qu'ajoutent certaines sources secondaires.
- **Altman : choix du modèle** : le Z d'origine a été calibré sur des
  industriels cotés de 1946-1965. Il est choisi automatiquement pour les
  secteurs Yahoo Industrials et Basic Materials, et le Z'' (fonds propres
  comptables, sans le ratio CA / actif, très variable selon les secteurs)
  pour les autres ; une bascule manuelle reste possible. Score de niveau,
  calculé pour chaque exercice. Pour le Z d'origine, la capitalisation de
  chaque exercice est historique : cours de clôture du jour de clôture
  (ou du dernier jour coté avant), nombre d'actions du bilan, change du
  même jour.
- **Piotroski : fidèle à l'article** : ROA et rotation de l'actif rapportés
  à l'actif d'ouverture, levier à l'actif moyen, dette à long terme hors
  dettes locatives. Il faut donc trois bilans pour les critères de
  variation : avec 4 exercices, le F-score est complet pour les deux
  derniers. Un critère non calculable est n.d., et le score est affiché
  sur les seuls critères calculables (« 4 / 6 »), à ne pas comparer tel
  quel aux seuils sur 9. Le critère « pas d'augmentation de capital » est
  jugé sur le nombre d'actions, ce qui compte les attributions d'actions
  gratuites comme une émission (faux positif régulier chez Air Liquide).
- **Limites communes** : ces scores ont été calibrés sur des sociétés
  américaines, à d'autres époques (1946-1965 pour Altman, 1982-1992 pour
  Beneish, 1976-1996 pour Piotroski) et sous d'autres normes comptables
  que les IFRS. Les seuils n'ont jamais été réestimés sur des sociétés
  européennes récentes : ce sont des signaux à creuser, pas des verdicts.
  Ils sont non applicables aux banques et assureurs.
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
  conversion des données de marché, qualité des résultats, pont résultat →
  CFO, BFR en jours, scores de Beneish, Altman et Piotroski). Aucune
  dépendance Dash, réseau ou disque.
- `charts.py` : constructeurs de graphiques Plotly (cascade, jours de BFR).
- `layout.py` : construction de l'écran et mise en forme (montants,
  ratios et détail de leur calcul, provenance, tableaux).
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
sectoriel, devises, ratios de qualité des résultats et de BFR sur des cas
calculés à la main) et `market_data.py` avec yfinance remplacé par des
doublures : aucun appel réseau. `test_scores.py` reproduit un exemple
chiffré publié pour chaque score (source citée au-dessus de chaque test)
et couvre les cas limites (donnée manquante, base nulle, seuils). `test_i18n.py` vérifie que chaque clé de
traduction construite dynamiquement existe en FR et en EN.

## Docker

```bash
docker build -t financial-analysis .
docker run -p 8052:8052 financial-analysis
```

## Avertissement

Outil personnel à but éducatif. Les données de Yahoo Finance peuvent
différer des comptes publiés ; les analyses sont des signaux, pas un avis
d'audit ni un conseil en investissement.
