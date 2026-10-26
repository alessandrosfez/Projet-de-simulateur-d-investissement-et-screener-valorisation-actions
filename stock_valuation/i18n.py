"""
Traductions (FR/EN) et palettes de couleurs. Aucune dépendance sur les autres
modules du projet.
"""
import string

PALETTES = {
    # Palette de référence validée (variante claire ; la sombre est dans chart_theme.SERIES_DARK).
    "default": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    "colorblind": ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#F0E442", "#56B4E9"],
    "pastel": ["#8ECFC9", "#FFBE7A", "#FA7F6F", "#82B0D2", "#BEB8DC", "#E7DAD2"],
    "contrast": ["#000000", "#E31A1C", "#1F78B4", "#33A02C", "#FF7F00", "#6A3D9A"],
}
PALETTE_CODES = list(PALETTES.keys())

PALETTE_NAMES = {
    "fr": {"default": "Défaut", "colorblind": "Daltonien", "pastel": "Pastel", "contrast": "Contrasté"},
    "en": {"default": "Default", "colorblind": "Colorblind-friendly", "pastel": "Pastel", "contrast": "High contrast"},
}

PALETTE = PALETTES["default"]  # palette par défaut, utilisée si aucune n'est fournie explicitement

TRANSLATIONS = {
    "fr": {
        "nav_label": "Navigation entre les outils",
        "nav_home": "Accueil",
        "nav_projection": "Projection",
        "nav_valuation": "Valorisation",
        "nav_analysis": "Analyse financière",
        "app_title": "Valorisation d'actions : P/E, DCF & comparables",
        "app_subtitle": "Comparaison de valorisation (P/E sectoriel, DCF, comparables) sur des actions "
                        "françaises, allemandes, britanniques et américaines. Ce ne sont pas des "
                        "prédictions : chaque estimation dépend fortement des hypothèses choisies.",
        "footer_disclaimer": "Données de marché (cours, P/E, flux de trésorerie disponible, dette, "
                        "trésorerie, nombre d'actions) fournies par Yahoo Finance via la librairie "
                        "yfinance. Résultats issus de modèles de valorisation (DCF, comparables) fondés "
                        "sur des hypothèses réglables : ce ne sont ni des prédictions ni un conseil en "
                        "investissement personnalisé.",
        "lang_label": "Langue",
        "dark_mode_label": "Mode sombre",
        "palette_label": "Palette de couleurs",
        "intro1": "Compare le P/E Ratio (cours / bénéfice) d'une sélection d'actions françaises, "
                 "allemandes, britanniques et américaines pour repérer les plus chères et les moins "
                 "chères. Ces listes sont des sélections maintenues à la main dans le code (pas la "
                 "composition officielle exacte et complète des indices, notamment pour le FTSE 100 et "
                 "les actions américaines où seul un échantillon est inclus pour garder un temps de "
                 "chargement raisonnable).",
        "intro_more_toggle": "ⓘ En savoir plus (éligibilité PEA, limites du P/E, contenu du tableau)",
        "intro2": "📌 Le PEA n'accepte que des actions de sociétés domiciliées dans l'UE/EEE (ou via "
                 "certains ETF/trackers pour le reste du monde) : les valeurs françaises, allemandes, "
                 "néerlandaises, espagnoles et italiennes y sont éligibles, mais pas les actions "
                 "britanniques, suisses ou américaines listées ici. Celles-ci relèvent d'un "
                 "compte-titres ordinaire (CTO).",
        "intro3": "⚠️ Un P/E bas ne veut pas dire \"sous-évalué\" ni un P/E haut \"survalorisé\" : cela "
                 "dépend fortement du secteur (tech vs énergie par ex.) et des perspectives de "
                 "croissance. Le comparatif par secteur ci-dessous, et le filtre sur un secteur unique, "
                 "permettent une comparaison plus équitable qu'un classement brut tous secteurs "
                 "confondus.",
        "intro4": "Le tableau inclut aussi le P/B (prix / valeur comptable), le rendement du dividende, "
                 "la devise de cotation, et un P/E moyen historique propre à chaque action avec sa "
                 "position (percentile) par rapport à cet historique (un signal souvent plus parlant "
                 "que la comparaison sectorielle). Ce P/E historique divise le cours de chaque semaine "
                 "par le BPA du dernier exercice publié à cette date (3 mois après sa clôture) : Yahoo "
                 "ne fournissant que 4 exercices, il couvre environ 3,5 ans. Sans BPA annuel, repli "
                 "signalé sur le BPA actuel constant, moins fiable pour une valeur cyclique. "
                 "Sélectionne une ligne du tableau pour voir son évolution.",
        "markets_label": "Marchés à inclure",
        "universe_cac40": "CAC 40 (France)",
        "universe_dax40": "DAX 40 (Allemagne)",
        "universe_ftse100": "FTSE 100 (Royaume-Uni, sélection)",
        "universe_us": "Actions américaines (sélection de grandes capitalisations)",
        "universe_aex": "AEX (Pays-Bas, sélection)",
        "universe_ibex35": "IBEX 35 (Espagne, sélection)",
        "universe_ftsemib": "FTSE MIB (Italie, sélection)",
        "universe_smi": "SMI (Suisse, sélection)",
        "load_btn": "Charger / actualiser les données",
        "load_progress_text": "{done} / {total} chargées...",
        "freshness_now": "Données chargées à l'instant ({when})",
        "freshness_minutes": "Données chargées il y a {count} min ({when})",
        "freshness_hours": "Données chargées il y a {count} h ({when})",
        "freshness_days": "Données chargées il y a {count} j ({when})",
        "auto_refresh_failed": "Actualisation impossible pour l'instant (Yahoo Finance injoignable ?) : les données du dernier chargement restent affichées.",
        "select_market_warning": "Sélectionne au moins un marché.",
        "no_data_fetched": "Aucune donnée récupérée. Vérifie ta connexion ou réessaie plus tard.",
        "unavailable_tickers": "Données indisponibles pour : {names} (ticker à vérifier ou données non "
                              "fournies par Yahoo Finance).",
        "sector_compare_title": "Comparatif par secteur",
        "pe_backtest_title": "Validité du signal P/E historique",
        "pe_backtest_intro": "Les cartes \"décotées/tendues vs historique\" plus bas reposent sur "
                             "une heuristique : un P/E bas par rapport à l'historique propre du "
                             "titre serait un signal positif. Ce qui suit vérifie si ça s'est "
                             "historiquement confirmé sur le panier chargé : rendement à 1 an "
                             "selon que le P/E d'un titre était bas, moyen ou haut par rapport à "
                             "SA PROPRE histoire au moment considéré (jamais par rapport à une "
                             "donnée future : voir le détail du calcul plus bas).",
        "pe_backtest_hint_default": "Charge des valeurs pour voir ce backtest.",
        "pe_backtest_insufficient_data": "Pas assez d'historique de P/E sur ce panier pour un "
                                         "backtest exploitable.",
        "pe_backtest_low_label": "P/E bas (percentile < 20 %)",
        "pe_backtest_mid_label": "P/E moyen (20e-80e percentile)",
        "pe_backtest_high_label": "P/E haut (percentile > 80 %)",
        "pe_backtest_no_data": "Aucune observation sur ce panier.",
        "pe_backtest_stats_caption": "Médiane {median} · n={n}",
        "pe_backtest_caveat": "Rendement à 1 an (52 semaines) suivant chaque point, calculé sur "
                             "le P/E implicite de chaque titre (approximatif : BPA supposé "
                             "constant, voir plus haut), regroupés par tranche de percentile vs "
                             "l'historique propre à chaque titre à cette date. Les fenêtres se "
                             "chevauchent (un même titre contribue plusieurs points proches dans "
                             "le temps) : n est un ordre de grandeur, pas un nombre "
                             "d'observations indépendantes — à lire comme une tendance, pas une "
                             "preuve statistique.",
        "sector_filter_label": "Filtrer sur un secteur (optionnel, comparaison plus équitable)",
        "sector_all": "Tous les secteurs",
        "screening_filters_label": "Filtres de sélection (optionnel)",
        "filter_pe_max_label": "P/E max",
        "filter_peg_max_label": "PEG max",
        "filter_div_min_label": "Rendement dividende min (%)",
        "filter_score_min_label": "Score min",
        "watchlist_label": "Valeurs suivies (watchlist)",
        "watchlist_placeholder": "Ajouter des valeurs à ta watchlist...",
        "watchlist_only_label": "N'afficher que ma watchlist",
        "empty_stocks_title": "Aucune donnée chargée pour l'instant",
        "empty_stocks_text": "Coche un ou plusieurs marchés puis clique sur « Charger / actualiser les données » : comparatif sectoriel, tableau de criblage, DCF et alertes de ta liste de suivi apparaîtront ici.",
        "watch_alerts_title": "Alertes de ta liste de suivi",
        "watch_alerts_help": "Titres de ta liste de suivi et de ton journal. Cinq signaux, calculés sur tout "
                              "l'univers chargé (indépendants des filtres du tableau) : cours au niveau ou sous "
                              "ton prix cible ; P/E dans les 20 % les plus bas de sa propre histoire ; cours sous la "
                              "valeur implicite au P/E médian d'au moins 3 pairs du secteur ; cours sous la valeur "
                              "intrinsèque DCF aux hypothèses par défaut (croissance {growth} %, actualisation "
                              "{discount} %, croissance terminale {terminal} %, {horizon} ans) ; score composite ≥ 70. Une donnée manquante ne "
                              "déclenche rien. Des pistes à creuser, pas des recommandations d'achat.",
        "watch_alert_pe_history_low": "P/E bas vs son historique (percentile {value:.0f})",
        "watch_alert_below_comparables": "Sous les comparables P/E (potentiel {value:+.0f} %)",
        "watch_alert_below_dcf": "Sous le DCF par défaut (potentiel {value:+.0f} %)",
        "watch_alert_high_score": "Score {value:.0f}",
        "watch_alerts_quiet": "Rien à signaler pour l'instant : {names}.",
        "watch_alert_below_target": "Sous ton prix cible de {target} (potentiel {value:+.0f} %)",
        "journal_title": "Journal d'investissement",
        "journal_help": "Pour chaque titre : pourquoi il t'intéresse, à quel prix tu l'achèterais et quand revoir "
                        "ta position. Enregistré sur cet ordinateur seulement (fichier local, jamais envoyé). Le "
                        "prix cible est dans la devise de cotation du titre, celle de la colonne « Prix ».",
        "journal_ticker_label": "Titre",
        "journal_ticker_placeholder": "Choisir un titre...",
        "journal_target_label": "Prix cible",
        "journal_review_label": "Date de revue",
        "journal_thesis_label": "Thèse",
        "journal_thesis_placeholder": "Pourquoi ce titre ? Ce qui te ferait changer d'avis...",
        "journal_save_btn": "Enregistrer",
        "journal_edit_btn": "Modifier",
        "journal_delete_btn": "Supprimer",
        "journal_need_ticker": "Choisis d'abord un titre.",
        "journal_bad_target": "Le prix cible doit être positif (laisse vide pour ne pas en fixer).",
        "journal_saved": "Entrée de {ticker} enregistrée.",
        "journal_empty": "Aucune entrée pour l'instant : choisis un titre, note ta thèse, ton prix cible et une "
                         "date pour y revenir.",
        "journal_review_on": "Revue le {day}",
        "journal_review_due": "Revue à faire, prévue le {day}",
        "journal_target_chip": "Cible {target}",
        "journal_gap_below": "Potentiel {gap:+.0f} % jusqu'à la cible",
        "journal_gap_above": "{gap:.1f} % au-dessus de la cible",
        "journal_price_missing": "Cours non chargé",
        "journal_gauge_price": "Cours",
        "journal_gauge_target": "Ta cible",
        "journal_gauge_dcf": "DCF par défaut",
        "journal_gauge_comparables": "Comparables P/E",
        "journal_reminder": "Revue à faire ({count}) : {names}.",
        "pe_ratio_by_stock_title": "P/E Ratio par valeur",
        "detail_title": "Détail",
        "detail_hint": "Clique sur une ligne pour voir l'évolution de son P/E historique ci-dessous.",
        "history_title": "Évolution du P/E historique",
        "history_hint_default": "Clique sur une ligne du tableau ci-dessus.",
        "history_unavailable": "Historique indisponible pour {name}.",
        "history_unavailable_full": "Historique de P/E indisponible pour {name} (BPA non fourni par "
                                    "Yahoo Finance).",
        "history_chart_title": "P/E historique : {name}",
        "history_mean_annotation": "Moyenne historique",
        "history_method_annual_eps": "Cours de chaque semaine / BPA du dernier exercice publié (clôture + 3 mois).",
        "history_method_current_eps": "BPA annuels indisponibles : approximation au BPA actuel constant, peu fiable "
                                      "pour une valeur cyclique.",
        "history_current_annotation": "P/E actuel",
        "history_low_zone": "décoté vs son historique (sous {pe:.1f}x, 20e percentile)",
        "history_high_zone": "tendu vs son historique (au-dessus de {pe:.1f}x, 80e percentile)",
        "history_mean_value": "moyenne {pe:.1f}x",
        "history_current_point": "Aujourd'hui : {pe:.1f}x (percentile {pct:.0f})",
        "history_current_point_no_pct": "Aujourd'hui : {pe:.1f}x",
        "history_current_hover": "P/E actuel, sur le BPA des 12 derniers mois (la courbe utilise le BPA annuel publié)",
        "quality_title": "Qualité de l'entreprise",
        "quality_hint_default": "Sélectionne une ligne du tableau ci-dessus.",
        "quality_roic_label": "ROIC (rendement du capital investi)",
        "quality_roe_label": "ROE (rendement des capitaux propres)",
        "quality_roa_label": "ROA (rendement des actifs)",
        "quality_revenue_growth_label": "Croissance du chiffre d'affaires",
        "quality_gross_margin_label": "Marge brute",
        "quality_operating_margin_label": "Marge opérationnelle",
        "quality_profit_margin_label": "Marge nette",
        "quality_debt_to_equity_label": "Dette / capitaux propres",
        "quality_current_ratio_label": "Ratio de liquidité générale",
        "quality_quick_ratio_label": "Ratio de liquidité immédiate",
        "track_record_title": "Performance réalisée (5 ans)",
        "track_record_hint_default": "Sélectionne une ligne du tableau ci-dessus, ou aucun historique de prix disponible pour ce titre.",
        "track_record_cagr_label": "Rendement annualisé (CAGR)",
        "track_record_volatility_label": "Volatilité annualisée",
        "track_record_max_drawdown_label": "Pire baisse (max drawdown)",
        "track_record_sharpe_label": "Ratio de Sharpe",
        "track_record_methodology_hint": "Calculé sur les rendements mensuels des 5 dernières années (ou moins si l'historique est plus court) : purement rétrospectif, ne présage pas de la performance future.",
        "download_btn": "Télécharger (CSV)",
        "load_hint_placeholder": "Clique sur « Charger / actualiser les données » ci-dessus.",
        "cheapest_title": "5 P/E les plus bas (potentiellement les moins chères)",
        "priciest_title": "5 P/E les plus hauts (potentiellement les plus chères)",
        "below_history_title": "5 les plus décotées vs leur propre historique",
        "above_history_title": "5 les plus tendues vs leur propre historique",
        "history_card_item": "{name} : P/E actuel {pe:.1f} vs moyenne historique {mean:.1f} (percentile {pct:.0f})",
        "sector_box_caption": "Chaque point est une action (survole pour son nom et son P/E), le trait vertical la médiane de son secteur, les titres de ta liste de suivi sont agrandis et nommés. Échelle logarithmique : un P/E extrême n'écrase pas les autres.",
        "sector_strip_title": "P/E de chaque action, par secteur (trié par P/E médian)",
        "sector_median_label": "médiane du secteur",
        "sector_unknown": "Secteur non renseigné",
        "pe_by_stock_chart_title": "P/E Ratio (trailing) : du moins cher au plus cher",
        "basket_avg_annotation": "Moyenne du panier",
        "col_company": "Entreprise",
        "col_ticker": "Ticker",
        "col_score": "Score",
        "col_sector": "Secteur",
        "col_currency": "Devise",
        "col_price": "Prix",
        "col_pe_trailing": "P/E (trailing)",
        "col_pe_forward": "P/E (prévisionnel)",
        "col_peg": "PEG",
        "col_ev_ebitda": "EV/EBITDA",
        "col_pb": "P/B",
        "col_div_yield": "Rendement dividende (%)",
        "col_pe_5y_mean": "P/E moyen historique",
        "col_pe_5y_pct": "Position vs historique (percentile)",
        "col_market_cap": "Capitalisation",
        "col_score_help": "Moyenne de 3 rangs percentiles (0-100, 100 = meilleur) calculés sur l'univers chargé : "
                          "valorisation (P/E et PEG, plus bas = meilleur), qualité (ROIC et marge nette, plus haut "
                          "= meilleur), track record (Sharpe réalisé). Une action sans aucune de ces données "
                          "affiche N/A. Un outil de tri, pas un conseil d'investissement.",
        "col_pe_trailing_help": "Cours / bénéfice par action des 12 derniers mois glissants. Combien "
                                "d'années de bénéfice actuel le marché paie pour l'action.",
        "col_pe_forward_help": "Cours / bénéfice par action estimé pour l'exercice à venir (consensus "
                               "des analystes). Anticipe la croissance ou le recul des bénéfices, "
                               "contrairement au P/E trailing qui ne regarde que le passé.",
        "col_peg_help": "P/E (trailing) / taux de croissance annuel attendu des bénéfices (%). Rapporte "
                        "le P/E à la croissance : un P/E élevé peut être justifié par une forte "
                        "croissance (PEG proche de 1), ou au contraire trop cher payé pour cette "
                        "croissance (PEG élevé).",
        "col_ev_ebitda_help": "Valeur d'entreprise (capitalisation + dette nette) / EBITDA (résultat "
                              "avant intérêts, impôts, dépréciation et amortissement). Moins sensible "
                              "que le P/E aux différences de structure de dette ou de politique "
                              "d'amortissement entre entreprises.",
        "col_pb_help": "Cours / valeur comptable par action (capitaux propres / nombre d'actions). "
                      "Compare le prix payé à l'actif net de l'entreprise selon ses comptes.",
        "col_div_yield_help": "Dividende annuel versé / cours de l'action. Le revenu issu du dividende "
                              "seul, sans tenir compte d'une éventuelle plus-value ou moins-value.",
        "col_pe_5y_mean_help": "Moyenne du P/E historique hebdomadaire : cours / BPA du dernier exercice "
                               "publié à cette date (clôture + 3 mois), sur environ 3,5 ans. Repli signalé "
                               "sur le BPA actuel constant si les BPA annuels manquent.",
        "col_pe_5y_pct_help": "Position du P/E actuel dans la distribution de son propre P/E historique : "
                              "0 = jamais aussi bas sur la période, 100 = jamais aussi haut.",
        "dcf_title": "Estimation DCF (flux de trésorerie actualisés)",
        "dcf_intro": "Valorisation intrinsèque de l'action sélectionnée ci-dessus, à partir de son "
                     "free cash flow récent (moyenne des 3 derniers exercices clos quand "
                     "disponible, sinon les 12 derniers mois glissants ; données Yahoo Finance) "
                     "projeté selon les hypothèses ci-dessous. Ce n'est pas une prédiction : le "
                     "résultat est très sensible aux hypothèses de croissance et de taux "
                     "d'actualisation : à ajuster selon ta propre analyse, pas à prendre tel quel.",
        "dcf_growth_label": "Croissance du FCF (%/an)",
        "dcf_discount_label": "Taux d'actualisation, WACC (%)",
        "dcf_terminal_growth_label": "Croissance terminale (%)",
        "dcf_horizon_label": "Horizon de projection (années)",
        "dcf_growth_help": "Taux de croissance annuel attendu du Free Cash Flow (FCF) sur l'horizon de projection, avant le calcul de la valeur terminale.",
        "dcf_discount_help": "Taux d'actualisation (WACC) : coût moyen pondéré du capital utilisé pour ramener les flux futurs à leur valeur d'aujourd'hui. Plus il est élevé, moins les flux lointains pèsent dans la valorisation.",
        "dcf_terminal_growth_help": "Taux de croissance perpétuel du FCF après l'horizon de projection, utilisé dans le modèle de Gordon-Shapiro pour calculer la valeur terminale. Doit rester inférieur au taux d'actualisation.",
        "dcf_horizon_help": "Nombre d'années sur lesquelles le FCF est projeté explicitement avant de basculer sur la valeur terminale.",
        "dcf_hint_default": "Sélectionne une ligne du tableau ci-dessus pour estimer sa valeur intrinsèque.",
        "dcf_unavailable": "DCF indisponible pour {name} (free cash flow ou nombre d'actions non fournis par Yahoo Finance).",
        "dcf_negative_fcf": "DCF non pertinent pour {name} : son free cash flow récent (moyenne des derniers exercices disponibles, ou à défaut les 12 derniers mois glissants) est négatif. Projeter puis actualiser un flux négatif donne un résultat trompeur (souvent le signe d'une phase d'investissement importante, pas nécessairement une difficulté) — la valorisation par comparables ci-dessous reste utilisable.",
        "dcf_invalid_assumptions": "La croissance terminale doit être strictement inférieure au taux d'actualisation.",
        "dcf_fair_value_label": "Valeur intrinsèque estimée",
        "dcf_current_price_label": "Prix actuel",
        "dcf_upside_label": "Potentiel",
        "dcf_chart_title": "Fourchettes de valorisation vs prix actuel : {name}",
        "football_dcf_scenarios": "DCF, scénarios",
        "football_dcf_sensitivity": "DCF, sensibilité",
        "football_comparables_pe": "Comparables P/E",
        "football_comparables_ev_ebitda": "Comparables VE/EBITDA",
        "football_low": "bas",
        "football_mid": "central",
        "football_high": "haut",
        "football_empty": "Aucune méthode de valorisation exploitable pour {name}.",
        "plotly_separators": ", ",
        "comp_fair_value_label": "Valeur implicite (comparables P/E)",
        "comp_hint": "Prix si l'action se traitait au P/E médian de {n} pairs du secteur \"{sector}\" ({peer_pe:.1f}x) plutôt qu'à son P/E actuel ({own_pe:.1f}x).",
        "comp_insufficient_peers": "Pas assez de pairs valorisés (P/E positif) dans ce secteur pour calculer une valeur comparables P/E (minimum 3).",
        "comp_ev_fair_value_label": "Valeur implicite (comparables EV/EBITDA)",
        "comp_ev_hint": "Prix si l'action se traitait au multiple EV/EBITDA médian de {n} pairs du secteur \"{sector}\" ({peer_ev_ebitda:.1f}x) plutôt qu'à son multiple actuel ({own_ev_ebitda:.1f}x). Moins sensible que le P/E aux différences de structure de dette entre pairs.",
        "comp_ev_insufficient_peers": "Pas assez de pairs valorisés (EV/EBITDA positif) dans ce secteur pour calculer une valeur comparables EV/EBITDA (minimum 3).",
        "dcf_detail_summary": "Voir le détail du calcul",
        "dcf_detail_starting_fcf": "FCF de départ = moyenne des exercices ci-dessous : {fcf}",
        "dcf_detail_starting_fcf_ttm": "FCF de départ (12 derniers mois glissants ; historique annuel indisponible pour ce titre) : {fcf}",
        "dcf_detail_table_ocf": "Flux d'exploitation",
        "dcf_detail_table_capex": "Capex",
        "dcf_detail_table_year": "Année",
        "dcf_detail_table_fcf": "FCF projeté",
        "dcf_detail_table_pv": "Valeur actualisée",
        "dcf_detail_terminal": "Valeur terminale (Gordon-Shapiro) à l'année {n} : {terminal_value} → actualisée à aujourd'hui : {pv_terminal_value}",
        "dcf_detail_ev": "Valeur d'entreprise = somme des flux actualisés + valeur terminale actualisée = {enterprise_value}",
        "dcf_detail_net_debt": "Dette nette = dette totale − trésorerie = {net_debt}",
        "dcf_detail_equity": "Valeur des capitaux propres = valeur d'entreprise − dette nette = {equity_value}",
        "dcf_detail_per_share": "Valeur intrinsèque par action = capitaux propres ÷ actions en circulation ({shares}) = {fair_value}",
        "comp_detail_formula": "Valeur implicite = prix actuel × (P/E médian des {n} pairs ÷ P/E actuel) = {price} × ({peer_pe} ÷ {own_pe}) = {comp_fair_value}",
        "comp_ev_detail_formula": "EBITDA = valeur d'entreprise ÷ multiple actuel ({own_ev_ebitda}). Valeur d'entreprise implicite = EBITDA × multiple médian des {n} pairs ({peer_ev_ebitda}). Valeur implicite par action = (valeur d'entreprise implicite − dette nette) ÷ actions en circulation = {comp_ev_fair_value}",
        "dcf_scenario_toggle": "📊 Scénarios Bear/Base/Bull (optionnel)",
        "dcf_growth_offset_label": "Écart de croissance Bear/Bull (pts)",
        "dcf_discount_offset_label": "Écart de taux d'actualisation Bear/Bull (pts)",
        "dcf_weight_bear_label": "Poids Bear",
        "dcf_weight_base_label": "Poids Base",
        "dcf_weight_bull_label": "Poids Bull",
        "dcf_bear_fair_value_label": "Valeur intrinsèque (Bear)",
        "dcf_bull_fair_value_label": "Valeur intrinsèque (Bull)",
        "dcf_weighted_fair_value_label": "Valeur intrinsèque pondérée",
        "dcf_scenario_weights_caption": "Poids normalisés : Bear {bear:.0f}% · Base {base:.0f}% · Bull {bull:.0f}%",
        "dcf_sensitivity_summary": "Voir la grille de sensibilité (croissance × taux d'actualisation)",
    },
    "en": {
        "nav_label": "Navigation between the tools",
        "nav_home": "Home",
        "nav_projection": "Projection",
        "nav_valuation": "Valuation",
        "nav_analysis": "Financial analysis",
        "app_title": "Stock Valuation: P/E, DCF & Comparables",
        "app_subtitle": "Valuation comparison (sector P/E, DCF, comparables) on French, German, British "
                        "and American stocks. These are not predictions: every estimate depends heavily "
                        "on the assumptions chosen.",
        "footer_disclaimer": "Market data (prices, P/E, free cash flow, debt, cash, share count) "
                        "provided by Yahoo Finance via the yfinance library. Results come from "
                        "valuation models (DCF, comparables) based on adjustable assumptions: they are "
                        "neither predictions nor personalized investment advice.",
        "lang_label": "Language",
        "dark_mode_label": "Dark mode",
        "palette_label": "Color palette",
        "intro1": "Compares the P/E Ratio (price / earnings) of a selection of French, German, British "
                 "and American stocks to spot the most expensive and cheapest ones. These lists are "
                 "hand-maintained selections in the code (not the exact, full official index "
                 "composition, notably for the FTSE 100 and US stocks where only a sample is included "
                 "to keep loading times reasonable).",
        "intro_more_toggle": "ⓘ Learn more (PEA eligibility, P/E limitations, table contents)",
        "intro2": "📌 A PEA only accepts shares of companies domiciled in the EU/EEA (or via certain "
                 "ETFs/trackers for the rest of the world): French, German, Dutch, Spanish and "
                 "Italian stocks are eligible, but not the British, Swiss or American stocks listed "
                 "here. Those belong in an ordinary brokerage account (CTO).",
        "intro3": "⚠️ A low P/E doesn't mean \"undervalued\" and a high P/E doesn't mean \"overvalued\": "
                 "it depends heavily on the sector (tech vs energy, for instance) and growth prospects. "
                 "The sector comparison below, and the single-sector filter, allow for a fairer "
                 "comparison than a raw ranking across all sectors.",
        "intro4": "The table also includes the P/B (price / book value), dividend yield, trading "
                 "currency, and a historical average P/E specific to each stock along with its "
                 "position (percentile) relative to that history (a signal that's often more meaningful "
                 "than the sector comparison). This historical P/E divides each week's price by the EPS of "
                 "the latest fiscal year published at that date (3 months after its close): Yahoo only "
                 "provides 4 fiscal years, so it covers about 3.5 years. Without annual EPS, it falls back, "
                 "flagged, on the current EPS held constant, less reliable for a cyclical stock. Select a "
                 "row in the table to see its history.",
        "markets_label": "Markets to include",
        "universe_cac40": "CAC 40 (France)",
        "universe_dax40": "DAX 40 (Germany)",
        "universe_ftse100": "FTSE 100 (UK, selection)",
        "universe_us": "US stocks (large-cap selection)",
        "universe_aex": "AEX (Netherlands, selection)",
        "universe_ibex35": "IBEX 35 (Spain, selection)",
        "universe_ftsemib": "FTSE MIB (Italy, selection)",
        "universe_smi": "SMI (Switzerland, selection)",
        "load_btn": "Load / refresh data",
        "load_progress_text": "{done} / {total} loaded...",
        "freshness_now": "Data loaded just now ({when})",
        "freshness_minutes": "Data loaded {count} min ago ({when})",
        "freshness_hours": "Data loaded {count} h ago ({when})",
        "freshness_days": "Data loaded {count} d ago ({when})",
        "auto_refresh_failed": "Could not refresh for now (Yahoo Finance unreachable?): the last loaded data stays on screen.",
        "select_market_warning": "Select at least one market.",
        "no_data_fetched": "No data retrieved. Check your connection or try again later.",
        "unavailable_tickers": "Data unavailable for: {names} (check the ticker or data not provided by "
                              "Yahoo Finance).",
        "sector_compare_title": "Sector comparison",
        "pe_backtest_title": "Historical P/E signal validity",
        "pe_backtest_intro": "The \"discounted/stretched vs history\" cards further down rely on "
                             "a heuristic : a low P/E relative to the stock's own history would "
                             "be a positive signal. What follows checks whether that has "
                             "historically held on the loaded basket : 1-year return depending "
                             "on whether a stock's P/E was low, mid, or high relative to ITS OWN "
                             "history at that point in time (never relative to future data : see "
                             "the calculation detail below).",
        "pe_backtest_hint_default": "Load some stocks to see this backtest.",
        "pe_backtest_insufficient_data": "Not enough P/E history on this basket for a usable "
                                         "backtest.",
        "pe_backtest_low_label": "Low P/E (< 20th percentile)",
        "pe_backtest_mid_label": "Mid P/E (20th-80th percentile)",
        "pe_backtest_high_label": "High P/E (> 80th percentile)",
        "pe_backtest_no_data": "No observations on this basket.",
        "pe_backtest_stats_caption": "Median {median} · n={n}",
        "pe_backtest_caveat": "1-year (52-week) return following each point, computed on each "
                             "stock's implied P/E (approximate : EPS assumed constant, see "
                             "above), grouped by percentile band vs each stock's own history at "
                             "that date. Windows overlap (a single stock contributes several "
                             "nearby points in time) : n is an order of magnitude, not a count of "
                             "independent observations — read this as a trend, not statistical "
                             "proof.",
        "sector_filter_label": "Filter by sector (optional, fairer comparison)",
        "sector_all": "All sectors",
        "screening_filters_label": "Screening filters (optional)",
        "filter_pe_max_label": "Max P/E",
        "filter_peg_max_label": "Max PEG",
        "filter_div_min_label": "Min dividend yield (%)",
        "filter_score_min_label": "Min score",
        "watchlist_label": "Watchlist",
        "watchlist_placeholder": "Add stocks to your watchlist...",
        "watchlist_only_label": "Show only my watchlist",
        "empty_stocks_title": "No data loaded yet",
        "empty_stocks_text": "Tick one or more markets then click “Load / refresh data”: sector comparison, screening table, DCF and watchlist alerts will appear here.",
        "watch_alerts_title": "Watchlist alerts",
        "watch_alerts_help": "Stocks from your watchlist and your journal. Five signals, computed over the whole "
                              "loaded universe (independent of the table filters): price at or below your target "
                              "price; P/E in the lowest 20% of its own history; price below the value implied by "
                              "the median P/E of at least 3 sector peers; price below the DCF intrinsic value at the "
                              "default assumptions (growth {growth}%, discount {discount}%, terminal growth {terminal}%, {horizon} years); composite "
                              "score ≥ 70. Missing data triggers nothing. Leads to dig into, not buy "
                              "recommendations.",
        "watch_alert_pe_history_low": "Low P/E vs its history (percentile {value:.0f})",
        "watch_alert_below_comparables": "Below P/E comparables (upside {value:+.0f}%)",
        "watch_alert_below_dcf": "Below default DCF (upside {value:+.0f}%)",
        "watch_alert_high_score": "Score {value:.0f}",
        "watch_alerts_quiet": "Nothing to report for now: {names}.",
        "watch_alert_below_target": "Below your target price of {target} (upside {value:+.0f}%)",
        "journal_title": "Investment journal",
        "journal_help": "For each stock: why it interests you, the price you would buy at and when to review your "
                        "position. Saved on this computer only (local file, never sent). The target price is in the "
                        "stock's quote currency, the one of the “Price” column.",
        "journal_ticker_label": "Stock",
        "journal_ticker_placeholder": "Pick a stock...",
        "journal_target_label": "Target price",
        "journal_review_label": "Review date",
        "journal_thesis_label": "Thesis",
        "journal_thesis_placeholder": "Why this stock? What would change your mind...",
        "journal_save_btn": "Save",
        "journal_edit_btn": "Edit",
        "journal_delete_btn": "Delete",
        "journal_need_ticker": "Pick a stock first.",
        "journal_bad_target": "The target price must be positive (leave it empty to set none).",
        "journal_saved": "Entry for {ticker} saved.",
        "journal_empty": "No entry yet: pick a stock, write down your thesis, your target price and a date to come "
                         "back to it.",
        "journal_review_on": "Review on {day}",
        "journal_review_due": "Review due since {day}",
        "journal_target_chip": "Target {target}",
        "journal_gap_below": "Upside {gap:+.0f}% to target",
        "journal_gap_above": "{gap:.1f}% above target",
        "journal_price_missing": "Price not loaded",
        "journal_gauge_price": "Price",
        "journal_gauge_target": "Your target",
        "journal_gauge_dcf": "Default DCF",
        "journal_gauge_comparables": "P/E comparables",
        "journal_reminder": "Reviews due ({count}): {names}.",
        "pe_ratio_by_stock_title": "P/E Ratio by stock",
        "detail_title": "Detail",
        "detail_hint": "Click a row to see its historical P/E below.",
        "history_title": "Historical P/E",
        "history_hint_default": "Click a row in the table above.",
        "history_unavailable": "History unavailable for {name}.",
        "history_unavailable_full": "P/E history unavailable for {name} (EPS not provided by Yahoo "
                                    "Finance).",
        "history_chart_title": "Historical P/E: {name}",
        "history_mean_annotation": "Historical average",
        "history_method_annual_eps": "Each week's price / EPS of the latest published fiscal year (close + 3 months).",
        "history_method_current_eps": "Annual EPS unavailable: approximation with the current EPS held constant, "
                                      "unreliable for a cyclical stock.",
        "history_current_annotation": "Current P/E",
        "history_low_zone": "cheap vs its history (below {pe:.1f}x, 20th percentile)",
        "history_high_zone": "stretched vs its history (above {pe:.1f}x, 80th percentile)",
        "history_mean_value": "average {pe:.1f}x",
        "history_current_point": "Today: {pe:.1f}x (percentile {pct:.0f})",
        "history_current_point_no_pct": "Today: {pe:.1f}x",
        "history_current_hover": "Current P/E, on the last 12 months' EPS (the curve uses the published annual EPS)",
        "quality_title": "Business quality",
        "quality_hint_default": "Select a row in the table above.",
        "quality_roic_label": "ROIC (return on invested capital)",
        "quality_roe_label": "ROE (return on equity)",
        "quality_roa_label": "ROA (return on assets)",
        "quality_revenue_growth_label": "Revenue growth",
        "quality_gross_margin_label": "Gross margin",
        "quality_operating_margin_label": "Operating margin",
        "quality_profit_margin_label": "Net margin",
        "quality_debt_to_equity_label": "Debt / equity",
        "quality_current_ratio_label": "Current ratio",
        "quality_quick_ratio_label": "Quick ratio",
        "track_record_title": "Realized performance (5y)",
        "track_record_hint_default": "Select a row in the table above, or no price history is available for this stock.",
        "track_record_cagr_label": "Annualized return (CAGR)",
        "track_record_volatility_label": "Annualized volatility",
        "track_record_max_drawdown_label": "Max drawdown",
        "track_record_sharpe_label": "Sharpe ratio",
        "track_record_methodology_hint": "Computed from the last 5 years of monthly returns (or less if shorter history is available): purely backward-looking, not predictive of future performance.",
        "download_btn": "Download (CSV)",
        "load_hint_placeholder": "Click « Load / refresh data » above.",
        "cheapest_title": "5 lowest P/E (potentially cheapest)",
        "priciest_title": "5 highest P/E (potentially most expensive)",
        "below_history_title": "5 most discounted vs their own history",
        "above_history_title": "5 most stretched vs their own history",
        "history_card_item": "{name}: current P/E {pe:.1f} vs historical mean {mean:.1f} (percentile {pct:.0f})",
        "sector_box_caption": "Each dot is a stock (hover for its name and P/E), the vertical mark the median of its sector, your watchlist stocks are enlarged and named. Log scale: an extreme P/E does not squash the others.",
        "sector_strip_title": "P/E of each stock, by sector (sorted by median P/E)",
        "sector_median_label": "sector median",
        "sector_unknown": "Sector not provided",
        "pe_by_stock_chart_title": "P/E Ratio (trailing): cheapest to most expensive",
        "basket_avg_annotation": "Basket average",
        "col_company": "Company",
        "col_ticker": "Ticker",
        "col_score": "Score",
        "col_sector": "Sector",
        "col_currency": "Currency",
        "col_price": "Price",
        "col_pe_trailing": "P/E (trailing)",
        "col_pe_forward": "P/E (forward)",
        "col_peg": "PEG",
        "col_ev_ebitda": "EV/EBITDA",
        "col_pb": "P/B",
        "col_div_yield": "Dividend yield (%)",
        "col_pe_5y_mean": "Historical average P/E",
        "col_pe_5y_pct": "Position vs history (percentile)",
        "col_market_cap": "Market cap",
        "col_score_help": "Average of 3 percentile ranks (0-100, 100 = best) computed across the loaded "
                          "universe: valuation (P/E and PEG, lower = better), quality (ROIC and net margin, "
                          "higher = better), track record (realized Sharpe ratio). A stock with none of this "
                          "data shows N/A. A sorting aid, not investment advice.",
        "col_pe_trailing_help": "Price / earnings per share over the trailing 12 months. How many "
                                "years of current earnings the market is paying for the stock.",
        "col_pe_forward_help": "Price / estimated earnings per share for the upcoming fiscal year "
                               "(analyst consensus). Anticipates earnings growth or decline, unlike "
                               "the trailing P/E which only looks at the past.",
        "col_peg_help": "Trailing P/E / expected annual earnings growth rate (%). Relates the P/E to "
                        "growth: a high P/E can be justified by strong growth (PEG near 1), or "
                        "conversely too expensive for that growth (high PEG).",
        "col_ev_ebitda_help": "Enterprise value (market cap + net debt) / EBITDA (earnings before "
                              "interest, taxes, depreciation and amortization). Less sensitive than "
                              "the P/E to differences in debt structure or amortization policy "
                              "between companies.",
        "col_pb_help": "Price / book value per share (equity / shares outstanding). Compares the "
                      "price paid to the company's net assets per its accounts.",
        "col_div_yield_help": "Annual dividend paid / share price. The income from the dividend "
                              "alone, not accounting for any capital gain or loss.",
        "col_pe_5y_mean_help": "Average weekly historical P/E: price / EPS of the latest fiscal year "
                               "published at that date (close + 3 months), over about 3.5 years. Flagged "
                               "fallback on the current EPS held constant if annual EPS are missing.",
        "col_pe_5y_pct_help": "Where the current P/E sits within its own historical P/E distribution: "
                              "0 = never as low over the period, 100 = never as high.",
        "dcf_title": "DCF estimate (discounted cash flow)",
        "dcf_intro": "Intrinsic valuation of the stock selected above, based on its recent free "
                     "cash flow (averaged over the last 3 closed fiscal years when available, "
                     "otherwise trailing twelve months; Yahoo Finance data) projected under the "
                     "assumptions below. This is not a prediction: the result is very sensitive "
                     "to the growth and discount-rate assumptions: adjust them to your own "
                     "analysis rather than taking the output at face value.",
        "dcf_growth_label": "FCF growth (%/year)",
        "dcf_discount_label": "Discount rate, WACC (%)",
        "dcf_terminal_growth_label": "Terminal growth (%)",
        "dcf_horizon_label": "Projection horizon (years)",
        "dcf_growth_help": "Expected annual growth rate of Free Cash Flow (FCF) over the projection horizon, before the terminal value is computed.",
        "dcf_discount_help": "Discount rate (WACC): the weighted average cost of capital used to bring future cash flows back to today's value. The higher it is, the less distant cash flows weigh in the valuation.",
        "dcf_terminal_growth_help": "Perpetual FCF growth rate assumed after the projection horizon, used in the Gordon-Shapiro model to compute the terminal value. Must stay below the discount rate.",
        "dcf_horizon_help": "Number of years over which FCF is explicitly projected before switching to the terminal value.",
        "dcf_hint_default": "Select a row in the table above to estimate its intrinsic value.",
        "dcf_unavailable": "DCF unavailable for {name} (free cash flow or share count not provided by Yahoo Finance).",
        "dcf_negative_fcf": "DCF not meaningful for {name}: its recent free cash flow (averaged over the available fiscal years, or trailing twelve months otherwise) is negative. Projecting and discounting a negative flow gives a misleading result (often a sign of a heavy investment phase, not necessarily distress) — the comparables valuation below still holds.",
        "dcf_invalid_assumptions": "Terminal growth must be strictly lower than the discount rate.",
        "dcf_fair_value_label": "Estimated intrinsic value",
        "dcf_current_price_label": "Current price",
        "dcf_upside_label": "Upside",
        "dcf_chart_title": "Valuation ranges vs current price: {name}",
        "football_dcf_scenarios": "DCF, scenarios",
        "football_dcf_sensitivity": "DCF, sensitivity",
        "football_comparables_pe": "P/E comparables",
        "football_comparables_ev_ebitda": "EV/EBITDA comparables",
        "football_low": "low",
        "football_mid": "central",
        "football_high": "high",
        "football_empty": "No usable valuation method for {name}.",
        "plotly_separators": ". ",
        "comp_fair_value_label": "Implied value (P/E comparables)",
        "comp_hint": "Price if the stock traded at the median P/E of {n} peers in the \"{sector}\" sector ({peer_pe:.1f}x) instead of its current P/E ({own_pe:.1f}x).",
        "comp_insufficient_peers": "Not enough valued peers (positive P/E) in this sector to compute a P/E comparables value (minimum 3).",
        "comp_ev_fair_value_label": "Implied value (EV/EBITDA comparables)",
        "comp_ev_hint": "Price if the stock traded at the median EV/EBITDA multiple of {n} peers in the \"{sector}\" sector ({peer_ev_ebitda:.1f}x) instead of its current multiple ({own_ev_ebitda:.1f}x). Less sensitive than P/E to differences in debt structure between peers.",
        "comp_ev_insufficient_peers": "Not enough valued peers (positive EV/EBITDA) in this sector to compute an EV/EBITDA comparables value (minimum 3).",
        "dcf_detail_summary": "Show calculation detail",
        "dcf_detail_starting_fcf": "Starting FCF = average of the fiscal years below: {fcf}",
        "dcf_detail_starting_fcf_ttm": "Starting FCF (trailing twelve months; annual history unavailable for this stock): {fcf}",
        "dcf_detail_table_ocf": "Operating cash flow",
        "dcf_detail_table_capex": "Capex",
        "dcf_detail_table_year": "Year",
        "dcf_detail_table_fcf": "Projected FCF",
        "dcf_detail_table_pv": "Present value",
        "dcf_detail_terminal": "Terminal value (Gordon-Shapiro) at year {n}: {terminal_value} → discounted to today: {pv_terminal_value}",
        "dcf_detail_ev": "Enterprise value = sum of discounted flows + discounted terminal value = {enterprise_value}",
        "dcf_detail_net_debt": "Net debt = total debt − cash = {net_debt}",
        "dcf_detail_equity": "Equity value = enterprise value − net debt = {equity_value}",
        "dcf_detail_per_share": "Intrinsic value per share = equity value ÷ shares outstanding ({shares}) = {fair_value}",
        "comp_detail_formula": "Implied value = current price × (peer median P/E ÷ own P/E) = {price} × ({peer_pe} ÷ {own_pe}) = {comp_fair_value}",
        "comp_ev_detail_formula": "EBITDA = enterprise value ÷ current multiple ({own_ev_ebitda}). Implied enterprise value = EBITDA × peer median multiple ({peer_ev_ebitda}) over {n} peers. Implied value per share = (implied enterprise value − net debt) ÷ shares outstanding = {comp_ev_fair_value}",
        "dcf_scenario_toggle": "📊 Bear/Base/Bull scenarios (optional)",
        "dcf_growth_offset_label": "Bear/Bull growth offset (pts)",
        "dcf_discount_offset_label": "Bear/Bull discount rate offset (pts)",
        "dcf_weight_bear_label": "Bear weight",
        "dcf_weight_base_label": "Base weight",
        "dcf_weight_bull_label": "Bull weight",
        "dcf_bear_fair_value_label": "Intrinsic value (Bear)",
        "dcf_bull_fair_value_label": "Intrinsic value (Bull)",
        "dcf_weighted_fair_value_label": "Probability-weighted intrinsic value",
        "dcf_scenario_weights_caption": "Normalized weights: Bear {bear:.0f}% · Base {base:.0f}% · Bull {bull:.0f}%",
        "dcf_sensitivity_summary": "Show sensitivity grid (growth × discount rate)",
    },
}


# Remplacement simultané : la virgule des milliers devient une espace, le point décimal une virgule.
_FRENCH_DIGITS = str.maketrans({",": " ", ".": ","})
# En anglais, seule la virgule des milliers devient une espace (convention de l'outil : « 1 234.56 »).
_ENGLISH_DIGITS = str.maketrans({",": " "})


def num(value, spec: str, lang: str) -> str:
    """Nombre selon spec (« .2f », « ,.2f », « +.1f »...) aux conventions de la langue : virgule
    décimale et espace des milliers en français (« 1 234,56 »), point décimal en anglais."""
    return format(value, spec).translate(_FRENCH_DIGITS if lang == "fr" else _ENGLISH_DIGITS)


class _FrenchNumberFormatter(string.Formatter):
    """Formatage des gabarits français : un nombre passé à « {peer_pe:.1f} » sort avec une virgule
    décimale (« 12,4x »), au lieu des conventions anglaises de .format(). Les chaînes passent
    telles quelles."""

    def format_field(self, value, format_spec):
        text = super().format_field(value, format_spec)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            text = text.translate(_FRENCH_DIGITS)
        return text


_FRENCH_FORMATTER = _FrenchNumberFormatter()


def L(lang: str, key: str, **kwargs) -> str:
    """Traduit `key` dans la langue `lang` (repli sur le français puis sur la clé elle-même).
    Les `**kwargs` sont appliqués via .format() pour les chaînes paramétrées, avec les conventions
    numériques françaises quand le texte est en français."""
    text = TRANSLATIONS.get(lang, TRANSLATIONS["fr"]).get(key, TRANSLATIONS["fr"].get(key, key))
    if not kwargs:
        return text
    return _FRENCH_FORMATTER.format(text, **kwargs) if lang not in TRANSLATIONS or lang == "fr" else text.format(**kwargs)
