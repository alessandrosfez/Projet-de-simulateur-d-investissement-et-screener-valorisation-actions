# Outils PEA & Compte-Titres : Projection, Valorisation & Analyse financière

Trois outils Dash indépendants, construits autour de la même discipline
quantitative appliquée à l'investissement en PEA/compte-titres : le
premier répond à *combien épargner*, le deuxième à *quoi acheter*, le
troisième à *les comptes sont-ils fiables et solides ?*

- **[`portfolio_projection/`](portfolio_projection/)** : simulation Monte
  Carlo d'un plan d'épargne (par indice ou portefeuille pondéré),
  calibrée sur l'historique réel d'indices et d'ETF disponibles en PEA :
  quelle trajectoire de capital attendre d'un plan d'épargne donné, avec
  quelle incertitude. Un onglet « Mon portefeuille réel » suit aussi le
  PEA effectivement constitué (achats, dividendes, performance,
  rééquilibrage, jalons fiscaux) et le confronte à ce que la simulation
  aurait prévu.
- **[`stock_valuation/`](stock_valuation/)** : écran de valorisation
  d'actions individuelles (P/E sectoriel, DCF, comparables) sur CAC 40,
  DAX 40, FTSE 100 et un échantillon d'actions américaines : une fois le
  montant à investir décidé, sur quels titres, et à quel prix par rapport
  à leur valeur estimée.
- **[`financial_analysis/`](financial_analysis/)** : analyse de la qualité
  financière d'une société, dans l'esprit d'une due diligence d'audit ou de
  Transaction Services : conversion du résultat en cash, BFR, scores
  d'alerte (Beneish, Altman, Piotroski), dette nette et EBITDA ajusté, loi
  de Benford. Avant d'acheter un titre, ses comptes tiennent-ils ?

Chaque dossier est un projet Dash **complet et autonome** (aucun import
croisé entre eux) : son propre `app.py`, ses propres dépendances, son
propre Dockerfile, sa propre suite de tests, et un README qui détaille sa
méthodologie. Ils partagent une architecture volontairement identique
(moteur de calcul pur testé séparément de la couche Dash, cache disque des
appels `yfinance`) plutôt que du code partagé, pour que chacun reste
indépendamment clonable et compréhensible : quand du code d'un outil sert
à un autre, il est recopié et adapté, pas importé.

Ils partagent aussi un thème visuel, recopié dans chaque dossier
(`chart_theme.py`), pour se lire comme un seul ensemble :
- **fonds de graphique transparents**, qui prennent la couleur de la carte
  qui les contient ;
- **police Inter**, grilles discrètes, infobulles aux couleurs des cartes ;
- **palette « Défaut » validée** pour le contraste et le daltonisme, avec
  une variante claire et une sombre. L'ancienne palette, celle de Plotly,
  échouait au contrôle de luminance dans les deux modes.
- **couleurs d'état** (zone sûre, grise, détresse) distinctes des couleurs
  de séries, toujours accompagnées d'un libellé ;
- **icônes Bootstrap** sur les actions principales, **squelettes de
  chargement** à la place des spinners, et une mise en page qui tient sur
  un téléphone (réglages repliés sous le titre, sans défilement
  horizontal).

Aucun n'est un outil de prédiction ni un avis : chaque projection montre
une bande de scénarios possibles, pas un chiffre garanti ; chaque
estimation de valorisation dépend fortement des hypothèses choisies ;
chaque score d'alerte est un signal à creuser, pas un verdict. Outils
personnels à but éducatif, pas un conseil en investissement.

## Démarrage rapide

```bash
pip install -r portfolio_projection/requirements.txt -r stock_valuation/requirements.txt -r financial_analysis/requirements.txt
python run_all.py
```

Lance les trois outils en parallèle (http://localhost:8050,
http://localhost:8051 et http://localhost:8052) et ouvre `index.html`, une
page d'accueil statique avec un lien vers chacun, un aperçu dessiné de
son écran principal et leur statut de démarrage en direct (thème clair ou
sombre selon le système) ; Ctrl+C pour tout arrêter. `python run_all.py
--no-browser` lance les outils sans ouvrir la page d'accueil (serveur sans
écran). Pur confort de lancement : `run_all.py` et `index.html` ne créent
aucun lien entre les projets, qui restent des process Dash indépendants,
juste un point d'entrée commun.

Pour lancer un seul outil (ou via Docker), voir le README du dossier
correspondant.
