"""
Traductions (FR/EN) et palettes de couleurs. Aucune dépendance sur les autres
modules du projet.
"""

PALETTES = {
    "default": ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3"],
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
                 "la devise de cotation, et un P/E moyen sur 5 ans propre à chaque action avec sa "
                 "position (percentile) par rapport à cet historique (un signal souvent plus parlant "
                 "que la comparaison sectorielle). Ce P/E historique est approximatif : calculé à BPA "
                 "actuel constant appliqué au cours historique, donc moins fiable pour une valeur très "
                 "cyclique ou en forte croissance des bénéfices. Sélectionne une ligne du tableau pour "
                 "voir son évolution complète sur 5 ans.",
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
        "watchlist_label": "Valeurs suivies (watchlist)",
        "watchlist_placeholder": "Ajouter des valeurs à ta watchlist...",
        "watchlist_only_label": "N'afficher que ma watchlist",
        "pe_ratio_by_stock_title": "P/E Ratio par valeur",
        "detail_title": "Détail",
        "detail_hint": "Clique sur une ligne pour voir l'évolution de son P/E sur 5 ans ci-dessous.",
        "history_title": "Évolution du P/E sur 5 ans",
        "history_hint_default": "Clique sur une ligne du tableau ci-dessus.",
        "history_unavailable": "Historique indisponible pour {name}.",
        "history_unavailable_full": "Historique de P/E indisponible pour {name} (BPA non fourni par "
                                    "Yahoo Finance).",
        "history_chart_title": "P/E implicite sur 5 ans : {name}",
        "history_mean_annotation": "Moyenne 5 ans",
        "history_current_annotation": "P/E actuel",
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
        "download_btn": "Télécharger (CSV)",
        "load_hint_placeholder": "Clique sur « Charger / actualiser les données » ci-dessus.",
        "cheapest_title": "5 P/E les plus bas (potentiellement les moins chères)",
        "priciest_title": "5 P/E les plus hauts (potentiellement les plus chères)",
        "below_history_title": "5 les plus décotées vs leur propre historique 5 ans",
        "above_history_title": "5 les plus tendues vs leur propre historique 5 ans",
        "axis_pe_avg": "P/E moyen",
        "sector_avg_pe_title": "P/E moyen par secteur",
        "sector_dist_pe_title": "Distribution du P/E par secteur",
        "sector_box_caption": "À droite : chaque point est une action du secteur (survole pour son "
                              "nom et son P/E). La boîte situe la moitié centrale des valeurs "
                              "autour de la médiane, les traits l'étendue typique du reste.",
        "pe_by_stock_chart_title": "P/E Ratio (trailing) : du moins cher au plus cher",
        "basket_avg_annotation": "Moyenne du panier",
        "col_company": "Entreprise",
        "col_ticker": "Ticker",
        "col_sector": "Secteur",
        "col_currency": "Devise",
        "col_price": "Prix",
        "col_pe_trailing": "P/E (trailing)",
        "col_pe_forward": "P/E (prévisionnel)",
        "col_peg": "PEG",
        "col_ev_ebitda": "EV/EBITDA",
        "col_pb": "P/B",
        "col_div_yield": "Rendement dividende (%)",
        "col_pe_5y_mean": "P/E moyen 5 ans (approx.)",
        "col_pe_5y_pct": "Position vs historique 5 ans (percentile)",
        "col_market_cap": "Capitalisation",
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
        "col_pe_5y_mean_help": "Moyenne du P/E implicite sur les 5 dernières années (prix historique / "
                               "BPA actuel, approximatif : voir le détail du calcul plus bas).",
        "col_pe_5y_pct_help": "Position du P/E actuel dans la distribution de son propre P/E sur 5 ans : "
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
        "dcf_chart_title": "Valeur intrinsèque (DCF) vs prix actuel : {name}",
        "comp_fair_value_label": "Valeur implicite (comparables)",
        "comp_hint": "Prix si l'action se traitait au P/E médian de {n} pairs du secteur \"{sector}\" ({peer_pe:.1f}x) plutôt qu'à son P/E actuel ({own_pe:.1f}x).",
        "comp_insufficient_peers": "Pas assez de pairs valorisés (P/E positif) dans ce secteur pour calculer une valeur comparables (minimum 3).",
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
                 "currency, and a 5-year average P/E specific to each stock along with its position "
                 "(percentile) relative to that history (a signal that's often more meaningful than the "
                 "sector comparison). This historical P/E is approximate: computed with the current EPS "
                 "held constant and applied to the historical price, so it's less reliable for a highly "
                 "cyclical stock or one with fast-growing earnings. Select a row in the table to see its "
                 "full 5-year history.",
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
        "watchlist_label": "Watchlist",
        "watchlist_placeholder": "Add stocks to your watchlist...",
        "watchlist_only_label": "Show only my watchlist",
        "pe_ratio_by_stock_title": "P/E Ratio by stock",
        "detail_title": "Detail",
        "detail_hint": "Click a row to see its 5-year P/E history below.",
        "history_title": "5-year P/E history",
        "history_hint_default": "Click a row in the table above.",
        "history_unavailable": "History unavailable for {name}.",
        "history_unavailable_full": "P/E history unavailable for {name} (EPS not provided by Yahoo "
                                    "Finance).",
        "history_chart_title": "5-year implied P/E: {name}",
        "history_mean_annotation": "5-year average",
        "history_current_annotation": "Current P/E",
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
        "download_btn": "Download (CSV)",
        "load_hint_placeholder": "Click « Load / refresh data » above.",
        "cheapest_title": "5 lowest P/E (potentially cheapest)",
        "priciest_title": "5 highest P/E (potentially most expensive)",
        "below_history_title": "5 most discounted vs their own 5-year history",
        "above_history_title": "5 most stretched vs their own 5-year history",
        "axis_pe_avg": "Average P/E",
        "sector_avg_pe_title": "Average P/E by sector",
        "sector_dist_pe_title": "P/E distribution by sector",
        "sector_box_caption": "On the right: each dot is a stock in the sector (hover for its name "
                              "and P/E). The box marks the central half of the values around the "
                              "median, the whiskers the typical range of the rest.",
        "pe_by_stock_chart_title": "P/E Ratio (trailing): cheapest to most expensive",
        "basket_avg_annotation": "Basket average",
        "col_company": "Company",
        "col_ticker": "Ticker",
        "col_sector": "Sector",
        "col_currency": "Currency",
        "col_price": "Price",
        "col_pe_trailing": "P/E (trailing)",
        "col_pe_forward": "P/E (forward)",
        "col_peg": "PEG",
        "col_ev_ebitda": "EV/EBITDA",
        "col_pb": "P/B",
        "col_div_yield": "Dividend yield (%)",
        "col_pe_5y_mean": "5-year average P/E (approx.)",
        "col_pe_5y_pct": "Position vs 5-year history (percentile)",
        "col_market_cap": "Market cap",
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
        "col_pe_5y_mean_help": "Average implied P/E over the trailing 5 years (historical price / "
                               "current EPS, approximate: see the calculation detail below).",
        "col_pe_5y_pct_help": "Where the current P/E sits within its own 5-year P/E distribution: "
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
        "dcf_chart_title": "Intrinsic value (DCF) vs current price: {name}",
        "comp_fair_value_label": "Implied value (comparables)",
        "comp_hint": "Price if the stock traded at the median P/E of {n} peers in the \"{sector}\" sector ({peer_pe:.1f}x) instead of its current P/E ({own_pe:.1f}x).",
        "comp_insufficient_peers": "Not enough valued peers (positive P/E) in this sector to compute a comparables value (minimum 3).",
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


def L(lang: str, key: str, **kwargs) -> str:
    """Traduit `key` dans la langue `lang` (repli sur le français puis sur la clé elle-même).
    Les `**kwargs` sont appliqués via .format() pour les chaînes paramétrées."""
    text = TRANSLATIONS.get(lang, TRANSLATIONS["fr"]).get(key, TRANSLATIONS["fr"].get(key, key))
    return text.format(**kwargs) if kwargs else text
