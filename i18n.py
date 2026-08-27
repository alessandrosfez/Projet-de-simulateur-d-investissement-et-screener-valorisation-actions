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
        "app_title": "Outils PEA & Compte-Titres — Projection & Valorisation",
        "app_subtitle": "Simulation Monte Carlo de tes versements (PEA ou compte-titres, par indice ou "
                        "portefeuille pondéré) et comparaison de valorisation (P/E) sur des actions "
                        "françaises, allemandes, britanniques et américaines. Les projections ne sont pas "
                        "des prédictions : chaque graphique montre une bande de scénarios possibles, pas "
                        "un chiffre garanti.",
        "lang_label": "Langue",
        "palette_label": "Palette de couleurs",
        "tab_par_indice": "Par indice",
        "tab_portefeuille": "Portefeuille pondéré",
        "tab_valorisation": "Valorisation actions (P/E)",
        "section_data": "Données & simulation",
        "section_withdrawals_crisis": "Retraits & crise",
        "section_contributions": "Apports",
        "section_fees_tax": "Frais, fiscalité & enveloppe",
        "section_display_sim": "Affichage & simulation",
        "section_config": "Configuration",
        "source_label": "Source des données",
        "source_indice": " Indice brut (longue historique)",
        "source_etf": " ETF PEA réel (frais/tracking inclus)",
        "lookback_label": "Historique de calibration (années)",
        "horizon_label": "Horizon de projection (années)",
        "decumulation_title": "Phase de retraits (optionnel)",
        "decumulation_checkbox": " Activer une phase de retraits après l'horizon",
        "decumulation_years_label": "Durée des retraits (années)",
        "withdrawal_label": "Retrait mensuel (€/mois, 1ère année)",
        "method_label": "Méthode de simulation",
        "method_normal": " Paramétrique (loi t de Student, queues épaisses)",
        "method_bootstrap": " Bootstrap historique",
        "mu_override_toggle": "✏️ Rendement attendu personnalisé (optionnel)",
        "mu_override_note": (
            "Remplace la moyenne historique par ton hypothèse de rendement annuel (%) pour l'actif "
            "concerné, en gardant sa volatilité et ses corrélations historiques. Laisse vide pour garder "
            "la moyenne historique.\n"
            "Des hypothèses de rendement à long terme (\"Capital Market Assumptions\") sont publiées "
            "périodiquement par des gérants comme Vanguard (VCMM) ou BlackRock (BlackRock Investment "
            "Institute) — à aller chercher toi-même, il n'existe pas d'API publique pour les récupérer "
            "automatiquement."
        ),
        "mu_override_placeholder": "hist.",
        "block_size_label": "Taille des blocs (mois)",
        "block_size_help": "Longueur des séquences historiques consécutives rééchantillonnées. 12 = on "
                           "retire des années entières d'affilée, ce qui préserve l'enchaînement d'une "
                           "crise (ex: 2008).",
        "crisis_title": "Scénario de crise (optionnel)",
        "crisis_checkbox": " Injecter un choc de marché",
        "shock_pct_label": "Ampleur du choc (%)",
        "shock_duration_label": "Durée du choc (mois)",
        "shock_timing_label": "Moment du choc",
        "shock_random": " Aléatoire (par simulation)",
        "shock_fixed": " Année précise",
        "shock_year_label": "Année du choc",
        "contrib_constant_title": "Apport constant",
        "contrib_constant_label": "Apport constant (€/mois)",
        "contrib_progressive_title": "Apport progressif",
        "contrib_initial_label": "Apport initial (€/mois)",
        "contrib_final_label": "Apport final (€/mois)",
        "fee_label": "Frais annuels/complémentaires (%)",
        "fee_help": "En mode ETF réel, ce pourcentage s'ajoute au TER déjà intégré dans l'historique du "
                   "fonds. En mode indice brut, il représente l'estimation totale des frais.",
        "inflation_label": "Inflation annuelle (%)",
        "display_label": "Affichage",
        "display_nominal": " Nominal",
        "display_real": " Euros constants (inflation)",
        "envelope_label": "Enveloppe",
        "envelope_pea": " PEA",
        "envelope_cto": " Compte-titres ordinaire (CTO)",
        "cto_method_label": "Méthode d'imposition (CTO)",
        "cto_flat": " Flat tax (30 %)",
        "cto_bareme": " Barème progressif + prélèvements sociaux",
        "cto_tmi_label": "Tranche marginale d'imposition (TMI)",
        "compare_checkbox": " Comparer PEA vs CTO (graphique dédié)",
        "band_width_label": "Largeur de la bande de confiance (%)",
        "n_sims_label": "Nombre de simulations Monte Carlo",
        "seed_label": "Graine aléatoire",
        "objective_title": "🎯 Mode objectif",
        "objective_checkbox": " Calculer l'apport nécessaire pour un objectif",
        "objective_amount_label": "Montant visé (€)",
        "objective_percentile_label": "Niveau de confiance",
        "objective_p_low": "Prudent (percentile bas)",
        "objective_median": "Médian",
        "objective_p_high": "Optimiste (percentile haut)",
        "objective_result_line": "{label} : {amount:,.0f} €/mois nécessaires pour atteindre {target:,.0f} € dans {years} ans ({percentile})",
        "objective_decumulation_note": "Mode objectif indisponible avec la décumulation activée (le calcul suppose une phase d'accumulation pure).",
        "objective_unavailable": "Objectif non atteignable avec ce scénario (résultat de référence nul ou négatif).",
        "config_export_btn": "💾 Exporter (JSON)",
        "config_upload_placeholder": "Glisser un fichier JSON ou cliquer pour charger une configuration",
        "tax_label_pea": " Net de prélèvements sociaux (17,2 % sur les gains)",
        "tax_help_pea": "PEA : exonéré d'impôt sur le revenu après 5 ans, restent les 17,2 % de "
                       "prélèvements sociaux sur les gains. Avant 5 ans, un retrait est fiscalement bien "
                       "plus pénalisant (sortie du plan).",
        "tax_label_cto_flat": " Net de fiscalité (flat tax {rate:.0f} % sur les gains)",
        "tax_help_cto_flat": "Compte-titres : prélèvement forfaitaire unique (12,8 % impôt + 17,2 % "
                             "prélèvements sociaux), sans condition de durée de détention.",
        "tax_label_cto_bareme": " Net de fiscalité (TMI {tmi} % + 17,2 % = {rate:.1f} %)",
        "tax_help_cto_bareme": "Compte-titres, barème progressif : applique ta tranche marginale "
                              "d'imposition (TMI) + 17,2 % de prélèvements sociaux sur la totalité du "
                              "gain. Approximatif : ne modélise pas l'abattement de 40 % sur les "
                              "dividendes propre à ce régime.",
        "tab1_warning_select_index": "Sélectionne au moins un indice.",
        "tab1_no_data": "Aucune donnée disponible.",
        "trajectories_title": "Trajectoires simulées",
        "metrics_title": "Métriques par scénario",
        "metrics_title_portfolio": "Métriques par portefeuille et stratégie",
        "download_metrics_btn": "Télécharger les métriques (CSV)",
        "compare_pea_cto_title": "PEA vs CTO",
        "tax_net_note": "Valeurs nettes de {rate:.1f} % de fiscalité sur les gains.",
        "prob_gain_prefix": "Probabilité de gain : ",
        "years_axis": "Années",
        "value_axis": "Valeur (€)",
        "invested_capital_trace": "Capital investi",
        "withdrawal_start_annotation": "Début des retraits",
        "schedule_constant": "Apport constant",
        "schedule_progressive": "Apport progressif",
        "band_subtitle": "médiane et bande P{lower:g}-P{upper:g}",
        "col_scenario": "Scénario",
        "metric_invested": "Capital investi (€)",
        "metric_median": "Valeur finale médiane (€)",
        "metric_p_low": "Valeur finale P{pct} (€)",
        "metric_p_high": "Valeur finale P{pct} (€)",
        "metric_prob_gain": "Probabilité de gain (%)",
        "metric_volatility": "Volatilité annualisée médiane (%)",
        "metric_sharpe": "Sharpe médian",
        "metric_max_drawdown": "Max drawdown médian (%)",
        "metric_prob_ruin": "Probabilité d'épuisement du capital (%)",
        "envelope_compare_title": "Valeur finale médiane nette — PEA vs CTO",
        "pea_trace_label": "PEA (net, {rate:.1f} %)",
        "cto_trace_label": "CTO (net, {rate:.1f} %)",
        "n_portfolios_label": "Nombre de portefeuilles à comparer",
        "portfolio_default_name": "Portefeuille {n}",
        "weight_label": "Poids — {name} (%)",
        "caption_zero": "Au moins un poids doit être supérieur à 0.",
        "caption_normalized_prefix": "Poids normalisés : ",
        "portfolio_warning_zero": "Définis au moins un portefeuille avec un poids supérieur à 0.",
        "no_aligned_data": "Pas de données alignées.",
        "corr_title": "Corrélations historiques",
        "corr_chart_title": "Corrélations historiques entre indices",
        "suggested_weights_title": "Poids suggérés (optimisation historique)",
        "sharpe_title": "Sharpe maximal",
        "vol_title": "Volatilité minimale",
        "rp_title": "Parité de risque",
        "weights_explain_toggle": "ℹ️ Comment sont calculés ces poids ?",
        "weights_explain_text": (
            "Sharpe maximal : meilleur couple rendement/risque sur l'historique. Les rendements moyens "
            "étant un estimateur bruité, ils sont atténués (\"shrinkage\") vers leur moyenne pour éviter "
            "de tout miser sur l'actif qui a eu le plus de chance sur la période.\n"
            "Volatilité minimale : la combinaison la moins volatile, sans tenir compte du rendement.\n"
            "Parité de risque : chaque actif contribue à parts égales au risque du portefeuille — "
            "allocation diversifiée par construction, indépendante des rendements attendus.\n"
            "Ces suggestions restent basées sur la fenêtre d'historique choisie : un point de départ, "
            "pas une vérité absolue."
        ),
        "shrinkage_label": "Contraction vers la moyenne (%)",
        "shrinkage_help": (
            "0% = confiance totale dans la moyenne historique de chaque actif (plus instable). "
            "100% = tous les actifs sont supposés avoir le même rendement attendu (allocation Sharpe "
            "guidée uniquement par le risque). Sans effet sur un actif dont le rendement est personnalisé "
            "ci-dessus."
        ),
        "apply_btn": "Appliquer à Portefeuille 1",
        "intro1": "Compare le P/E Ratio (cours / bénéfice) d'une sélection d'actions françaises, "
                 "allemandes, britanniques et américaines pour repérer les plus chères et les moins "
                 "chères. Ces listes sont des sélections maintenues à la main dans le code (pas la "
                 "composition officielle exacte et complète des indices, notamment pour le FTSE 100 et "
                 "les actions américaines où seul un échantillon est inclus pour garder un temps de "
                 "chargement raisonnable).",
        "intro2": "📌 Le PEA n'accepte que des actions de sociétés domiciliées dans l'UE/EEE (ou via "
                 "certains ETF/trackers pour le reste du monde) : les valeurs allemandes et une partie "
                 "des françaises y sont éligibles, mais pas les actions britanniques ou américaines "
                 "listées ici — celles-ci relèvent d'un compte-titres ordinaire (CTO).",
        "intro3": "⚠️ Un P/E bas ne veut pas dire \"sous-évalué\" ni un P/E haut \"survalorisé\" : cela "
                 "dépend fortement du secteur (tech vs énergie par ex.) et des perspectives de "
                 "croissance. Le comparatif par secteur ci-dessous, et le filtre sur un secteur unique, "
                 "permettent une comparaison plus équitable qu'un classement brut tous secteurs "
                 "confondus.",
        "intro4": "Le tableau inclut aussi le P/B (prix / valeur comptable), le rendement du dividende, "
                 "la devise de cotation, et un P/E moyen sur 5 ans propre à chaque action avec sa "
                 "position (percentile) par rapport à cet historique — un signal souvent plus parlant "
                 "que la comparaison sectorielle. Ce P/E historique est approximatif : calculé à BPA "
                 "actuel constant appliqué au cours historique, donc moins fiable pour une valeur très "
                 "cyclique ou en forte croissance des bénéfices. Sélectionne une ligne du tableau pour "
                 "voir son évolution complète sur 5 ans.",
        "markets_label": "Marchés à inclure",
        "universe_cac40": "CAC 40 (France)",
        "universe_dax40": "DAX 40 (Allemagne)",
        "universe_ftse100": "FTSE 100 (Royaume-Uni, sélection)",
        "universe_us": "Actions américaines (sélection de grandes capitalisations)",
        "load_btn": "Charger / actualiser les données",
        "select_market_warning": "Sélectionne au moins un marché.",
        "no_data_fetched": "Aucune donnée récupérée. Vérifie ta connexion ou réessaie plus tard.",
        "unavailable_tickers": "Données indisponibles pour : {names} (ticker à vérifier ou données non "
                              "fournies par Yahoo Finance).",
        "sector_compare_title": "Comparatif par secteur",
        "sector_filter_label": "Filtrer sur un secteur (optionnel — comparaison plus équitable)",
        "sector_all": "Tous les secteurs",
        "pe_ratio_by_stock_title": "P/E Ratio par valeur",
        "detail_title": "Détail",
        "detail_hint": "Clique sur une ligne pour voir l'évolution de son P/E sur 5 ans ci-dessous.",
        "history_title": "Évolution du P/E sur 5 ans",
        "history_hint_default": "Clique sur une ligne du tableau ci-dessus.",
        "history_unavailable": "Historique indisponible pour {name}.",
        "history_unavailable_full": "Historique de P/E indisponible pour {name} (BPA non fourni par "
                                    "Yahoo Finance).",
        "history_chart_title": "P/E implicite sur 5 ans — {name}",
        "history_mean_annotation": "Moyenne 5 ans",
        "history_current_annotation": "P/E actuel",
        "download_btn": "Télécharger (CSV)",
        "load_hint_placeholder": "Clique sur « Charger / actualiser les données » ci-dessus.",
        "cheapest_title": "5 P/E les plus bas (potentiellement les moins chères)",
        "priciest_title": "5 P/E les plus hauts (potentiellement les plus chères)",
        "below_history_title": "5 les plus décotées vs leur propre historique 5 ans",
        "above_history_title": "5 les plus tendues vs leur propre historique 5 ans",
        "axis_pe_avg": "P/E moyen",
        "sector_avg_pe_title": "P/E moyen par secteur",
        "sector_dist_pe_title": "Distribution du P/E par secteur",
        "pe_by_stock_chart_title": "P/E Ratio (trailing) — du moins cher au plus cher",
        "basket_avg_annotation": "Moyenne du panier",
        "col_company": "Entreprise",
        "col_ticker": "Ticker",
        "col_sector": "Secteur",
        "col_currency": "Devise",
        "col_price": "Prix",
        "col_pe_trailing": "P/E (trailing)",
        "col_pe_forward": "P/E (prévisionnel)",
        "col_pb": "P/B",
        "col_div_yield": "Rendement dividende (%)",
        "col_pe_5y_mean": "P/E moyen 5 ans (approx.)",
        "col_pe_5y_pct": "Position vs historique 5 ans (percentile)",
        "col_market_cap": "Capitalisation",
    },
    "en": {
        "app_title": "PEA & Brokerage Account Tools — Projection & Valuation",
        "app_subtitle": "Monte Carlo simulation of your contributions (PEA or brokerage account, per "
                        "index or weighted portfolio) and valuation comparison (P/E) on French, German, "
                        "British and American stocks. Projections are not predictions: every chart shows "
                        "a band of possible scenarios, not a guaranteed figure.",
        "lang_label": "Language",
        "palette_label": "Color palette",
        "tab_par_indice": "By index",
        "tab_portefeuille": "Weighted portfolio",
        "tab_valorisation": "Stock valuation (P/E)",
        "section_data": "Data & simulation",
        "section_withdrawals_crisis": "Withdrawals & crisis",
        "section_contributions": "Contributions",
        "section_fees_tax": "Fees, tax & account type",
        "section_display_sim": "Display & simulation",
        "section_config": "Configuration",
        "source_label": "Data source",
        "source_indice": " Raw index (long history)",
        "source_etf": " Real PEA ETF (fees/tracking included)",
        "lookback_label": "Calibration history (years)",
        "horizon_label": "Projection horizon (years)",
        "decumulation_title": "Withdrawal phase (optional)",
        "decumulation_checkbox": " Enable a withdrawal phase after the horizon",
        "decumulation_years_label": "Withdrawal duration (years)",
        "withdrawal_label": "Monthly withdrawal (€/month, 1st year)",
        "method_label": "Simulation method",
        "method_normal": " Parametric (Student-t, fat tails)",
        "method_bootstrap": " Historical bootstrap",
        "mu_override_toggle": "✏️ Custom expected return (optional)",
        "mu_override_note": (
            "Replaces the historical mean with your own annual return assumption (%) for that asset, "
            "while keeping its historical volatility and correlations. Leave empty to keep the "
            "historical mean.\n"
            "Long-run return assumptions (\"Capital Market Assumptions\") are published periodically by "
            "asset managers such as Vanguard (VCMM) or BlackRock (BlackRock Investment Institute) — "
            "look them up yourself, there is no public API to fetch them automatically."
        ),
        "mu_override_placeholder": "hist.",
        "block_size_label": "Block size (months)",
        "block_size_help": "Length of consecutive historical sequences resampled. 12 = whole years are "
                           "drawn at once, preserving the sequence of a crisis (e.g. 2008).",
        "crisis_title": "Crisis scenario (optional)",
        "crisis_checkbox": " Inject a market shock",
        "shock_pct_label": "Shock magnitude (%)",
        "shock_duration_label": "Shock duration (months)",
        "shock_timing_label": "Shock timing",
        "shock_random": " Random (per simulation)",
        "shock_fixed": " Specific year",
        "shock_year_label": "Shock year",
        "contrib_constant_title": "Constant contribution",
        "contrib_constant_label": "Constant contribution (€/month)",
        "contrib_progressive_title": "Progressive contribution",
        "contrib_initial_label": "Initial contribution (€/month)",
        "contrib_final_label": "Final contribution (€/month)",
        "fee_label": "Annual/additional fees (%)",
        "fee_help": "In real ETF mode, this percentage adds to the TER already embedded in the fund's "
                   "history. In raw index mode, it represents the total estimated fees.",
        "inflation_label": "Annual inflation (%)",
        "display_label": "Display",
        "display_nominal": " Nominal",
        "display_real": " Constant euros (inflation-adjusted)",
        "envelope_label": "Account type",
        "envelope_pea": " PEA",
        "envelope_cto": " Ordinary brokerage account (CTO)",
        "cto_method_label": "Tax method (brokerage account)",
        "cto_flat": " Flat tax (30%)",
        "cto_bareme": " Progressive income tax scale + social contributions",
        "cto_tmi_label": "Marginal tax bracket",
        "compare_checkbox": " Compare PEA vs brokerage account (dedicated chart)",
        "band_width_label": "Confidence band width (%)",
        "n_sims_label": "Number of Monte Carlo simulations",
        "seed_label": "Random seed",
        "objective_title": "🎯 Goal mode",
        "objective_checkbox": " Compute the contribution needed for a goal",
        "objective_amount_label": "Target amount (€)",
        "objective_percentile_label": "Confidence level",
        "objective_p_low": "Conservative (low percentile)",
        "objective_median": "Median",
        "objective_p_high": "Optimistic (high percentile)",
        "objective_result_line": "{label}: {amount:,.0f} €/month needed to reach {target:,.0f} € in {years} years ({percentile})",
        "objective_decumulation_note": "Goal mode is unavailable with decumulation enabled (the calculation assumes a pure accumulation phase).",
        "objective_unavailable": "Goal unreachable with this scenario (reference result is zero or negative).",
        "config_export_btn": "💾 Export (JSON)",
        "config_upload_placeholder": "Drag a JSON file or click to load a configuration",
        "tax_label_pea": " Net of social contributions (17.2% on gains)",
        "tax_help_pea": "PEA: exempt from income tax after 5 years, only the 17.2% social contributions "
                       "on gains remain. Before 5 years, a withdrawal is much more penalized tax-wise "
                       "(exits the plan).",
        "tax_label_cto_flat": " Net of tax (flat tax {rate:.0f}% on gains)",
        "tax_help_cto_flat": "Brokerage account: single flat-rate levy (12.8% tax + 17.2% social "
                             "contributions), no minimum holding period.",
        "tax_label_cto_bareme": " Net of tax (bracket {tmi}% + 17.2% = {rate:.1f}%)",
        "tax_help_cto_bareme": "Brokerage account, progressive scale: applies your marginal tax bracket "
                              "+ 17.2% social contributions on the entire gain. Approximate: does not "
                              "model the 40% dividend allowance specific to this regime.",
        "tab1_warning_select_index": "Select at least one index.",
        "tab1_no_data": "No data available.",
        "trajectories_title": "Simulated trajectories",
        "metrics_title": "Metrics by scenario",
        "metrics_title_portfolio": "Metrics by portfolio and strategy",
        "download_metrics_btn": "Download metrics (CSV)",
        "compare_pea_cto_title": "PEA vs brokerage account",
        "tax_net_note": "Values net of {rate:.1f}% tax on gains.",
        "prob_gain_prefix": "Probability of gain: ",
        "years_axis": "Years",
        "value_axis": "Value (€)",
        "invested_capital_trace": "Invested capital",
        "withdrawal_start_annotation": "Withdrawals begin",
        "schedule_constant": "Constant contribution",
        "schedule_progressive": "Progressive contribution",
        "band_subtitle": "median and P{lower:g}-P{upper:g} band",
        "col_scenario": "Scenario",
        "metric_invested": "Invested capital (€)",
        "metric_median": "Median final value (€)",
        "metric_p_low": "Final value P{pct} (€)",
        "metric_p_high": "Final value P{pct} (€)",
        "metric_prob_gain": "Probability of gain (%)",
        "metric_volatility": "Median annualized volatility (%)",
        "metric_sharpe": "Median Sharpe",
        "metric_max_drawdown": "Median max drawdown (%)",
        "metric_prob_ruin": "Probability of capital depletion (%)",
        "envelope_compare_title": "Median net final value — PEA vs brokerage account",
        "pea_trace_label": "PEA (net, {rate:.1f}%)",
        "cto_trace_label": "Brokerage (net, {rate:.1f}%)",
        "n_portfolios_label": "Number of portfolios to compare",
        "portfolio_default_name": "Portfolio {n}",
        "weight_label": "Weight — {name} (%)",
        "caption_zero": "At least one weight must be greater than 0.",
        "caption_normalized_prefix": "Normalized weights: ",
        "portfolio_warning_zero": "Define at least one portfolio with a weight greater than 0.",
        "no_aligned_data": "No aligned data.",
        "corr_title": "Historical correlations",
        "corr_chart_title": "Historical correlations between indices",
        "suggested_weights_title": "Suggested weights (historical optimization)",
        "sharpe_title": "Maximum Sharpe",
        "vol_title": "Minimum volatility",
        "rp_title": "Risk parity",
        "weights_explain_toggle": "ℹ️ How are these weights computed?",
        "weights_explain_text": (
            "Maximum Sharpe: best historical return/risk trade-off. Since average returns are a noisy "
            "estimator, they are shrunk toward their overall mean to avoid betting everything on the "
            "asset that got lucky over the period.\n"
            "Minimum volatility: the least volatile combination, ignoring return.\n"
            "Risk parity: each asset contributes equally to portfolio risk — diversified by "
            "construction, independent of expected returns.\n"
            "These suggestions are still based on the chosen lookback window: a starting point, "
            "not an absolute truth."
        ),
        "shrinkage_label": "Shrinkage toward the mean (%)",
        "shrinkage_help": (
            "0% = full trust in each asset's historical mean (more unstable). 100% = all assets are "
            "assumed to have the same expected return (Sharpe allocation driven by risk alone). Has no "
            "effect on an asset with a custom expected return set above."
        ),
        "apply_btn": "Apply to Portfolio 1",
        "intro1": "Compares the P/E Ratio (price / earnings) of a selection of French, German, British "
                 "and American stocks to spot the most expensive and cheapest ones. These lists are "
                 "hand-maintained selections in the code (not the exact, full official index "
                 "composition, notably for the FTSE 100 and US stocks where only a sample is included "
                 "to keep loading times reasonable).",
        "intro2": "📌 A PEA only accepts shares of companies domiciled in the EU/EEA (or via certain "
                 "ETFs/trackers for the rest of the world): German stocks and some French ones are "
                 "eligible, but not the British or American stocks listed here — those belong in an "
                 "ordinary brokerage account (CTO).",
        "intro3": "⚠️ A low P/E doesn't mean \"undervalued\" and a high P/E doesn't mean \"overvalued\": "
                 "it depends heavily on the sector (tech vs energy, for instance) and growth prospects. "
                 "The sector comparison below, and the single-sector filter, allow for a fairer "
                 "comparison than a raw ranking across all sectors.",
        "intro4": "The table also includes the P/B (price / book value), dividend yield, trading "
                 "currency, and a 5-year average P/E specific to each stock along with its position "
                 "(percentile) relative to that history — a signal that's often more meaningful than the "
                 "sector comparison. This historical P/E is approximate: computed with the current EPS "
                 "held constant and applied to the historical price, so it's less reliable for a highly "
                 "cyclical stock or one with fast-growing earnings. Select a row in the table to see its "
                 "full 5-year history.",
        "markets_label": "Markets to include",
        "universe_cac40": "CAC 40 (France)",
        "universe_dax40": "DAX 40 (Germany)",
        "universe_ftse100": "FTSE 100 (UK, selection)",
        "universe_us": "US stocks (large-cap selection)",
        "load_btn": "Load / refresh data",
        "select_market_warning": "Select at least one market.",
        "no_data_fetched": "No data retrieved. Check your connection or try again later.",
        "unavailable_tickers": "Data unavailable for: {names} (check the ticker or data not provided by "
                              "Yahoo Finance).",
        "sector_compare_title": "Sector comparison",
        "sector_filter_label": "Filter by sector (optional — fairer comparison)",
        "sector_all": "All sectors",
        "pe_ratio_by_stock_title": "P/E Ratio by stock",
        "detail_title": "Detail",
        "detail_hint": "Click a row to see its 5-year P/E history below.",
        "history_title": "5-year P/E history",
        "history_hint_default": "Click a row in the table above.",
        "history_unavailable": "History unavailable for {name}.",
        "history_unavailable_full": "P/E history unavailable for {name} (EPS not provided by Yahoo "
                                    "Finance).",
        "history_chart_title": "5-year implied P/E — {name}",
        "history_mean_annotation": "5-year average",
        "history_current_annotation": "Current P/E",
        "download_btn": "Download (CSV)",
        "load_hint_placeholder": "Click « Load / refresh data » above.",
        "cheapest_title": "5 lowest P/E (potentially cheapest)",
        "priciest_title": "5 highest P/E (potentially most expensive)",
        "below_history_title": "5 most discounted vs their own 5-year history",
        "above_history_title": "5 most stretched vs their own 5-year history",
        "axis_pe_avg": "Average P/E",
        "sector_avg_pe_title": "Average P/E by sector",
        "sector_dist_pe_title": "P/E distribution by sector",
        "pe_by_stock_chart_title": "P/E Ratio (trailing) — cheapest to most expensive",
        "basket_avg_annotation": "Basket average",
        "col_company": "Company",
        "col_ticker": "Ticker",
        "col_sector": "Sector",
        "col_currency": "Currency",
        "col_price": "Price",
        "col_pe_trailing": "P/E (trailing)",
        "col_pe_forward": "P/E (forward)",
        "col_pb": "P/B",
        "col_div_yield": "Dividend yield (%)",
        "col_pe_5y_mean": "5-year average P/E (approx.)",
        "col_pe_5y_pct": "Position vs 5-year history (percentile)",
        "col_market_cap": "Market cap",
    },
}


def L(lang: str, key: str, **kwargs) -> str:
    """Traduit `key` dans la langue `lang` (repli sur le français puis sur la clé elle-même).
    Les `**kwargs` sont appliqués via .format() pour les chaînes paramétrées."""
    text = TRANSLATIONS.get(lang, TRANSLATIONS["fr"]).get(key, TRANSLATIONS["fr"].get(key, key))
    return text.format(**kwargs) if kwargs else text
