"""
Traductions (FR/EN) et palettes de couleurs. Aucune dépendance sur les autres modules du projet.
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

PALETTE = PALETTES["default"]

TRANSLATIONS = {
    "fr": {
        "app_title": "Analyse financière : qualité et solidité des comptes",
        "app_subtitle": "Lecture des états financiers d'une société dans l'esprit d'une due diligence "
                        "(audit, Transaction Services) : les comptes sont-ils fiables et solides ? Ce "
                        "sont des signaux à creuser, pas des verdicts.",
        "footer_disclaimer": "États financiers et données de marché fournis par Yahoo Finance via la "
                             "librairie yfinance, sans retraitement par un analyste : des écarts avec les "
                             "comptes publiés sont possibles. Outil personnel à but éducatif, ni un avis "
                             "d'audit ni un conseil en investissement.",
        "lang_label": "Langue",
        "dark_mode_label": "Mode sombre",
        "palette_label": "Palette de couleurs",
        "intro": "Saisis un ticker Yahoo Finance (ex. AI.PA, SHEL.L, AAPL) ou choisis une société du "
                 "CAC 40. Chaque poste des comptes est ramené à un schéma interne stable ; survole une "
                 "cellule pour voir d'où vient le chiffre (publié, dérivé d'une identité comptable, ou "
                 "poste voisin), ou pourquoi il manque.",
        "ticker_label": "Ticker",
        "ticker_placeholder": "ex. AI.PA",
        "quick_pick_label": "Sélection rapide (CAC 40)",
        "quick_pick_placeholder": "Choisir une société...",
        "analyze_btn": "Analyser",
        "error_empty_ticker": "Saisis un ticker ou choisis une société dans la liste.",
        "error_no_data": "Aucun état financier annuel disponible pour « {ticker} » sur Yahoo Finance "
                         "(ticker erroné, société non cotée, ou service momentanément indisponible).",
        "results_placeholder": "Les résultats s'afficheront ici après l'analyse.",
        "na": "n.d.",
        "unit_billion": "Md",
        "unit_million": "M",
        "date_format": "%d/%m/%Y",
        # ---------- Société, devises ----------
        "section_company": "Société",
        "label_sector": "Secteur",
        "label_industry": "Industrie",
        "label_reporting_currency": "Devise des comptes",
        "label_quote_currency": "Devise de cotation",
        "label_price": "Cours (devise des comptes)",
        "label_market_cap": "Capitalisation (devise des comptes)",
        "label_fx_rate": "Taux de change utilisé",
        "currency_help": "Les comptes restent dans leur devise de publication ; seules les données de "
                         "marché (cours, capitalisation) sont converties. Formule : cours en devise des "
                         "comptes = cours coté ÷ diviseur de sous-unité (100 pour un cours en pence, GBp) "
                         "× taux de change ; capitalisation = capitalisation Yahoo (déjà en devise "
                         "principale) × taux de change.",
        "fx_detail": "1 {quote} = {rate:.4f} {reporting}",
        "fx_same_currency": "aucune conversion (même devise)",
        "minor_unit_detail": "cours coté en sous-unité ({quote_raw}) : divisé par {divisor:.0f}",
        "warn_fx_unavailable": "Taux de change {quote} → {reporting} indisponible sur Yahoo Finance : cours "
                               "et capitalisation ne sont pas convertis (affichés n.d.). Les ratios qui "
                               "en dépendent ne pourront pas être calculés.",
        "warn_currency_unknown": "Devise de cotation ou des comptes inconnue : cours et capitalisation ne "
                                 "peuvent pas être ramenés dans la devise des comptes (affichés n.d.).",
        "warn_minor_unit_inconsistent": "Contrôle de cohérence : cours ÷ (P/E × BPA) = {ratio:.1f}, alors que "
                                        "le code devise indique un diviseur de {divisor:.0f}. Une donnée de "
                                        "marché de Yahoo semble incohérente : vérifie le cours avant de "
                                        "t'appuyer sur la capitalisation.",
        # ---------- Classement sectoriel ----------
        "regime_bank": "Banque",
        "regime_insurer": "Assureur",
        "regime_general": "Société non financière",
        "regime_not_applicable": "{regime} : analyses non applicables : {analyses}. Le passif d'une banque "
                                 "(dépôts) ou d'un assureur (provisions techniques) est la matière première "
                                 "de son activité, et il n'y a ni stocks ni cycle clients/fournisseurs au "
                                 "sens industriel : ces analyses produiraient des chiffres absurdes plutôt "
                                 "qu'un signal. Les états financiers restent affichés ci-dessous.",
        "caution_third_party_funds": "Société financière (« {industry} ») analysée normalement, mais son "
                                     "bilan peut contenir des fonds de tiers (fonds fiduciaires d'un courtier, "
                                     "positions de compensation d'une bourse...) qui gonflent actif et passif "
                                     "sans refléter son activité propre : lis les ratios de bilan avec prudence.",
        "caution_unknown_industry": "Industrie non renseignée par Yahoo Finance : impossible de vérifier "
                                    "s'il s'agit d'une banque ou d'un assureur. L'analyse est faite comme pour "
                                    "une société non financière.",
        "analysis_beneish": "Beneish M-score",
        "analysis_altman": "Altman Z-score",
        "analysis_working_capital": "analyse du BFR",
        "analysis_earnings_quality": "qualité des résultats (conversion en cash, accruals)",
        # ---------- États financiers ----------
        "section_statements": "États financiers normalisés",
        "coverage_note": "yfinance ne fournit qu'environ {typical} exercices annuels : {n} exercice(s) "
                         "exploitable(s) ici ({years}). Les tendances et les scores qui comparent deux "
                         "exercices reposent donc sur un historique court.",
        "statements_legend": "Italique : poste dérivé d'une identité comptable ou repris d'un poste "
                             "voisin (survole la cellule pour le détail). « n.d. » : donnée non "
                             "disponible, jamais remplacée par 0.",
        "statement_income": "Compte de résultat",
        "statement_balance": "Bilan",
        "statement_cashflow": "Tableau de flux de trésorerie",
        "col_item": "Poste",
        "amounts_unit": "Montants en {currency}",
        "prov_published": "Publié : « {label} » ({statement}).",
        "prov_equivalent": "Poste voisin, faute du poste exact : « {label} » ({statement}). Pas "
                           "strictement identique (souvent plus large) : à garder en tête.",
        "prov_derived": "Dérivé : {formula}.",
        "prov_missing_not_in_yfinance": "n.d. : poste absent des données yfinance pour cet exercice.",
        "prov_missing_derivation": "n.d. : absent des données yfinance, et non dérivable ({formula}) faute "
                                   "de : {missing}.",
        # ---------- Postes ----------
        # ---------- Qualité des résultats ----------
        "section_earnings_quality": "Qualité des résultats",
        "section_bridge": "Du résultat net au cash d'exploitation",
        "section_working_capital": "BFR en jours",
        "section_not_applicable": "{regime} : analyse non applicable (voir l'encadré en haut de page).",
        "col_metric": "Indicateur",
        "col_trend": "Évolution",
        "trend_text": "{delta} ({first} → {last})",
        "trend_na": "n.d. (moins de 2 exercices)",
        "unit_days": "j",
        "ratio_cfo_to_net_income": "CFO / résultat net",
        "ratio_cfo_to_net_income_help": "Mesure la part du résultat effectivement encaissée. Formule : flux de "
                                        "trésorerie d'exploitation ÷ résultat net y compris minoritaires (même "
                                        "périmètre que le CFO consolidé). Lecture : autour de 1 ou plus, le résultat "
                                        "est adossé à du cash ; durablement sous 0,8, il dépasse le cash qu'il génère, "
                                        "signal à creuser (produits constatés avant encaissement, BFR qui gonfle). "
                                        "Sous IFRS 16, les remboursements de dettes locatives sont classés en "
                                        "financement : le CFO des sociétés très locataires (distribution) en est "
                                        "gonflé. Non interprétable si le résultat est nul ou négatif.",
        "ratio_fcf_to_net_income": "FCF / résultat net",
        "ratio_fcf_to_net_income_help": "Mesure le cash restant après investissements, par euro de résultat. Formule "
                                        ": (CFO + capex, le capex étant négatif) ÷ résultat net y compris "
                                        "minoritaires. Lecture : proche de 1, le résultat devient du cash disponible ; "
                                        "durablement bas ou négatif, les investissements absorbent le résultat "
                                        "(normal en phase d'investissement, inquiétant si cela dure). Non "
                                        "interprétable si le résultat est nul ou négatif.",
        "ratio_sloan_accruals": "Accruals (Sloan)",
        "ratio_sloan_accruals_help": "Mesure la part du résultat non encore traduite en cash, rapportée à la taille "
                                     "du bilan. Formule : (résultat net − CFO) ÷ actif total moyen, soit (ouverture "
                                     "+ clôture) / 2. Lecture : proche de 0 ou négatif, le résultat est adossé au "
                                     "cash ; au-delà d'environ +10 % de l'actif, signal d'alerte : Sloan (1996) "
                                     "montre que les sociétés aux accruals les plus élevés voient ensuite leurs "
                                     "résultats se dégrader. Exercice le plus ancien n.d. faute de bilan "
                                     "d'ouverture.",
        "ratio_dso": "DSO (jours de créances clients)",
        "ratio_dso_help": "Mesure le délai moyen d'encaissement des clients. Formule : créances clients de clôture ÷ "
                          "chiffre d'affaires × 365. Lecture : à comparer aux délais du secteur (en France, la loi "
                          "LME plafonne les délais entre entreprises à 60 jours, ou 45 jours fin de mois) ; une hausse "
                          "sans croissance du chiffre d'affaires peut signaler des difficultés d'encaissement ou une "
                          "comptabilisation agressive du chiffre d'affaires.",
        "ratio_dio": "DIO (jours de stocks)",
        "ratio_dio_help": "Mesure combien de jours de coût des ventes les stocks représentent. Formule : stocks de "
                          "clôture ÷ coût des ventes × 365. Lecture : à comparer au secteur et à son propre historique "
                          "; une hausse durable peut signaler des stocks lents ou obsolètes (risque de dépréciation). "
                          "n.d. sans coût des ventes : le calculer sur le chiffre d'affaires en changerait le sens.",
        "ratio_dpo": "DPO (jours de dettes fournisseurs)",
        "ratio_dpo_help": "Mesure le délai moyen de paiement des fournisseurs. Formule : dettes fournisseurs de "
                          "clôture ÷ coût des ventes × 365. Lecture : une hausse fait financer le BFR par les "
                          "fournisseurs ; très au-delà des délais légaux ou du secteur, elle peut traduire une tension "
                          "de trésorerie. n.d. sans coût des ventes.",
        "ratio_ccc": "Cycle de conversion de trésorerie",
        "ratio_ccc_help": "Mesure le nombre de jours pendant lesquels l'exploitation immobilise du cash, entre le "
                          "paiement des fournisseurs et l'encaissement des clients. Formule : DSO + DIO − DPO. Lecture "
                          ": plus il est court, moins l'activité consomme de trésorerie ; négatif, les fournisseurs "
                          "financent l'exploitation (grande distribution par exemple). Une hausse continue signale une "
                          "dégradation du BFR.",
        "formula_cfo_to_net_income": "CFO {cfo} ÷ résultat net {net_income}",
        "formula_fcf_to_net_income": "FCF {fcf} ÷ résultat net {net_income}",
        "formula_sloan_accruals": "(résultat net {net_income} − CFO {cfo}) ÷ actif moyen (({total_assets} + "
                                  "{total_assets_prior}) / 2)",
        "formula_dso": "créances clients {receivables} ÷ CA {revenue} × 365",
        "formula_dio": "stocks {inventory} ÷ coût des ventes {cost_of_revenue} × 365",
        "formula_dpo": "dettes fournisseurs {payables} ÷ coût des ventes {cost_of_revenue} × 365",
        "formula_ccc": "DSO {dso} + DIO {dio} − DPO {dpo}",
        "reason_missing_inputs": "n.d. : donnée manquante ({missing}).",
        "reason_non_positive_denominator": "n.d. : {denominator} nul ou négatif, ratio non interprétable.",
        "reason_no_prior_year": "n.d. : pas de bilan d'ouverture (exercice le plus ancien disponible).",
        "denominator_net_income": "résultat net",
        "denominator_revenue": "chiffre d'affaires",
        "denominator_cost_of_revenue": "coût des ventes",
        "denominator_average_total_assets": "actif total moyen",
        "flag_group_share_fallback": "Résultat net part du groupe utilisé : la version y compris minoritaires "
                                     "n'est pas fournie par Yahoo.",
        "flag_broad_receivables": "Poste « Receivables » plus large utilisé : DSO surestimé (inclut des créances "
                                  "hors clients).",
        "flag_broad_payables": "Poste « Payables » plus large utilisé : DPO surestimé (inclut des dettes hors "
                               "fournisseurs).",
        "bridge_year_label": "Exercice",
        "bridge_title": "Du résultat net au CFO ({year})",
        "bridge_step_net_income": "Résultat net (y c. minoritaires)",
        "bridge_step_d_and_a": "Dotations aux amortissements",
        "bridge_step_change_in_working_capital": "Variation du BFR",
        "bridge_step_other_items": "Autres éléments",
        "bridge_cfo": "CFO publié",
        "bridge_help": "Explique l'écart entre résultat et cash : les dotations sont des charges sans sortie de "
                       "trésorerie, la variation du BFR mesure le cash absorbé (négatif) ou libéré (positif) par les "
                       "stocks, créances et dettes d'exploitation. « Autres éléments » est le résidu qui fait "
                       "retomber le pont exactement sur le CFO publié (impôts différés, rémunérations en actions, "
                       "plus-values de cession...).",
        "bridge_missing_items": "Non fournis par Yahoo pour cet exercice, donc inclus dans « Autres éléments » : "
                                "{items}.",
        "bridge_unavailable": "Pont indisponible pour cet exercice : {missing} manquant.",
        "days_chart_title": "Évolution des jours de BFR",
        "days_axis": "Jours",
        # ---------- Scores d'alerte ----------
        "analysis_piotroski": "Piotroski F-score",
        "section_scores": "Scores d'alerte",
        "scores_caveat": "Ces scores ont été calibrés sur des sociétés américaines, à d'autres époques (1946-1965 "
                         "pour Altman, 1982-1992 pour Beneish, 1976-1996 pour Piotroski), et avec des normes "
                         "comptables différentes des IFRS : ce sont des signaux à creuser, pas des verdicts.",
        "col_pair": "{t} vs {p}",
        "col_reference_manipulators": "Manipulateurs (moy.)",
        "col_reference_non_manipulators": "Non-manipulateurs (moy.)",
        "suffix_t": "(t)",
        "suffix_p": "(t-1)",
        "reason_non_positive_base": "n.d. : base de comparaison nulle ou négative, indice non interprétable.",
        "flag_aqi_neutral_by_definition": "Base de t-1 nulle (actif composé uniquement d'actif courant et "
                                          "d'immobilisations corporelles) : indice fixé à 1, comme le fait Beneish.",
        "flag_depreciation_includes_amortization": "Amortissements des seules immobilisations corporelles non "
                                                   "distingués par Yahoo : dotations totales utilisées (incluent "
                                                   "l'amortissement des incorporels).",
        "flag_group_share_equity_fallback": "Capitaux propres part du groupe utilisés : la version y compris "
                                            "minoritaires n'est pas fournie par Yahoo.",
        # Beneish
        "section_beneish": "Beneish M-score",
        "beneish_help": "Mesure la ressemblance des comptes avec ceux des sociétés ayant manipulé leurs résultats "
                        "(échantillon de Beneish, 1999). Formule : M = −4,84 + 0,920·DSRI + 0,528·GMI + 0,404·AQI + "
                        "0,892·SGI + 0,115·DEPI − 0,172·SGAI + 4,679·TATA − 0,327·LVGI. Seuil : au-dessus de −1,78, "
                        "profil plus proche des manipulateurs. Compare deux exercices consécutifs (t et t-1). "
                        "Colonnes de droite : moyennes de l'échantillon d'estimation (Beneish 1999, tableau 2).",
        "beneish_m_score": "M-score",
        "beneish_m_score_indicative": "M-score indicatif (indices manquants neutralisés à 1)",
        "beneish_verdict_manipulation_risk": "{pair} : M = {value}, au-dessus de −1,78 : profil plus proche des "
                                             "manipulateurs de l'échantillon de Beneish, signal à creuser.",
        "beneish_verdict_no_signal": "{pair} : M = {value}, en dessous de −1,78 : pas de signal de manipulation "
                                     "selon le modèle.",
        "beneish_official_na": "{pair} : M-score n.d., indice(s) manquant(s) : {missing}. Les coefficients sont "
                               "estimés conjointement, on ne peut pas retirer une variable.",
        "beneish_indicative_note": "Variante indicative, indices manquants remplacés par 1 (aucune variation) : "
                                   "{neutralized}. C'est ce que faisait Beneish lui-même pour DEPI et SGAI quand "
                                   "COMPUSTAT ne fournissait pas la donnée ; à lire comme un ordre de grandeur.",
        "beneish_dsri": "DSRI (créances / CA)",
        "beneish_dsri_help": "Indice des jours de créances. Formule : (créances t ÷ CA t) ÷ (créances t-1 ÷ CA t-1). "
                             "Au-dessus de 1, les créances progressent plus vite que les ventes : changement de "
                             "politique de crédit, ou chiffre d'affaires gonflé.",
        "beneish_gmi": "GMI (marge brute)",
        "beneish_gmi_help": "Indice de marge brute. Formule : marge brute t-1 ÷ marge brute t (en % du CA). "
                            "Au-dessus de 1, la marge s'est dégradée : des perspectives moins bonnes incitent "
                            "davantage à embellir les comptes.",
        "beneish_aqi": "AQI (qualité des actifs)",
        "beneish_aqi_help": "Indice de qualité des actifs. Formule : [1 − (actif courant + immobilisations "
                            "corporelles) ÷ actif total] t ÷ même ratio t-1. Au-dessus de 1, la part d'actifs aux "
                            "avantages futurs incertains augmente : coûts possiblement immobilisés plutôt que passés "
                            "en charges.",
        "beneish_sgi": "SGI (croissance du CA)",
        "beneish_sgi_help": "Indice de croissance des ventes. Formule : CA t ÷ CA t-1. La croissance n'est pas une "
                            "manipulation, mais la pression pour la maintenir y incite.",
        "beneish_depi": "DEPI (amortissements)",
        "beneish_depi_help": "Indice d'amortissement. Formule : taux t-1 ÷ taux t, avec taux = amortissements ÷ "
                             "(amortissements + immobilisations corporelles nettes). Au-dessus de 1, le rythme "
                             "d'amortissement ralentit : durées d'utilité allongées, ce qui améliore le résultat.",
        "beneish_sgai": "SGAI (frais généraux)",
        "beneish_sgai_help": "Indice des frais commerciaux et administratifs. Formule : (SG&A t ÷ CA t) ÷ (SG&A "
                             "t-1 ÷ CA t-1). Au-dessus de 1, les frais progressent plus vite que les ventes. Souvent "
                             "n.d. : beaucoup de sociétés européennes ne publient pas de SG&A séparé.",
        "beneish_lvgi": "LVGI (endettement)",
        "beneish_lvgi_help": "Indice d'endettement. Formule : [(passif courant + dette long terme, dettes locatives "
                             "comprises) ÷ actif total] t ÷ même ratio t-1. Au-dessus de 1, l'endettement augmente : "
                             "les covenants bancaires peuvent inciter à embellir les comptes.",
        "beneish_tata": "TATA (accruals / actif)",
        "beneish_tata_help": "Accruals rapportés à l'actif. Formule : (résultat net − CFO) ÷ actif total t. Plus il "
                             "est élevé, moins le résultat est adossé à du cash. Calculé par les flux de trésorerie "
                             "plutôt que par les variations de postes du bilan de l'article (plus fiable, Hribar et "
                             "Collins 2002).",
        "formula_beneish_dsri": "(créances {receivables_t} ÷ CA {revenue_t}) ÷ (créances {receivables_p} ÷ CA {revenue_p})",
        "formula_beneish_gmi": "(marge brute {gross_profit_p} ÷ CA {revenue_p}) ÷ (marge brute {gross_profit_t} ÷ CA "
                               "{revenue_t})",
        "formula_beneish_aqi": "[1 − ({current_assets_t} + {ppe_net_t}) ÷ {total_assets_t}] ÷ [1 − ({current_assets_p} "
                               "+ {ppe_net_p}) ÷ {total_assets_p}]",
        "formula_beneish_sgi": "CA {revenue_t} ÷ CA {revenue_p}",
        "formula_beneish_depi": "[{depreciation_p} ÷ ({depreciation_p} + {ppe_net_p})] ÷ [{depreciation_t} ÷ "
                                "({depreciation_t} + {ppe_net_t})]",
        "formula_beneish_sgai": "(SG&A {sga_t} ÷ CA {revenue_t}) ÷ (SG&A {sga_p} ÷ CA {revenue_p})",
        "formula_beneish_lvgi": "[({current_liabilities_t} + {long_term_debt_incl_leases_t}) ÷ {total_assets_t}] ÷ "
                                "[({current_liabilities_p} + {long_term_debt_incl_leases_p}) ÷ {total_assets_p}]",
        "formula_beneish_tata": "(résultat net {net_income_t} − CFO {cfo_t}) ÷ actif {total_assets_t}",
        "contribution_text": "contribution au score : {coefficient} × {value} = {contribution}",
        # Altman
        "section_altman": "Altman Z-score",
        "altman_help": "Mesure le risque de défaillance à partir de cinq ratios de bilan et de résultat. Z d'origine "
                       "(Altman 1968, industriels cotés) : Z = 1,2·X1 + 1,4·X2 + 3,3·X3 + 0,6·X4 + 0,999·X5, zones "
                       "< 1,81 détresse, 1,81-2,99 grise, > 2,99 sûre. Z'' (Altman 1995, sociétés non "
                       "manufacturières) : Z'' = 6,56·X1 + 3,26·X2 + 6,72·X3 + 1,05·X4 sur fonds propres comptables, "
                       "zones < 1,10 détresse, 1,10-2,60 grise, > 2,60 sûre. Score de niveau : un exercice à la fois.",
        "altman_model_label": "Modèle",
        "altman_model_auto": "Automatique",
        "altman_model_original": "Z d'origine (industriels cotés)",
        "altman_model_z_double_prime": "Z'' (non manufacturiers)",
        "altman_auto_choice": "Choix automatique : {model}, d'après le secteur Yahoo « {sector} ». Le Z d'origine est "
                              "réservé aux secteurs Industrials et Basic Materials, proches de l'échantillon "
                              "d'industriels sur lequel il a été calibré.",
        "altman_x1": "X1 fonds de roulement / actif",
        "altman_x1_help": "Liquidité : (actif courant − passif courant) ÷ actif total. Un fonds de roulement qui fond "
                          "est l'un des premiers signes de difficulté.",
        "altman_x2": "X2 réserves / actif",
        "altman_x2_help": "Profitabilité cumulée : résultats accumulés non distribués ÷ actif total. Pénalise "
                          "naturellement les sociétés jeunes.",
        "altman_x3": "X3 EBIT / actif",
        "altman_x3_help": "Rentabilité économique de l'actif : EBIT ÷ actif total, le ratio le plus pondéré.",
        "altman_x4": "X4 capitaux propres / passif",
        "altman_x4_help": "Coussin avant insolvabilité : capitalisation boursière à la clôture (Z d'origine) ou "
                          "capitaux propres comptables (Z'') ÷ passif total. La capitalisation historique = cours de "
                          "clôture à la date de l'exercice × nombre d'actions du bilan, convertie au taux de change "
                          "de cette date.",
        "altman_x5": "X5 CA / actif",
        "altman_x5_help": "Rotation de l'actif : chiffre d'affaires ÷ actif total (Z d'origine seulement : très "
                          "variable d'un secteur à l'autre, d'où son retrait du Z'').",
        "altman_z": "Z-score",
        "altman_zone": "Zone",
        "zone_safe": "sûre",
        "zone_grey": "grise",
        "zone_distress": "détresse",
        "altman_ratio_formula": "{numerator_label} {numerator} ÷ {denominator_label} {denominator} = {value}",
        "altman_mve_unavailable": "Capitalisation à la clôture indisponible (cours ou change historique manquant) : "
                                  "Z d'origine n.d. pour cet exercice, bascule sur Z'' possible.",
        "field_market_value_of_equity": "capitalisation à la clôture",
        # Piotroski
        "section_piotroski": "Piotroski F-score",
        "piotroski_help": "Mesure l'amélioration de la santé financière sur 9 critères binaires (1 = rempli), "
                          "Piotroski 2000 : rentabilité (4), structure financière (3), efficacité (2). Lecture : 8-9 "
                          "solide, 0-2 fragile. ROA et rotation de l'actif rapportés à l'actif d'ouverture, comme dans "
                          "l'article : il faut trois bilans pour les critères de variation.",
        "piotroski_score": "F-score",
        "piotroski_score_text": "{score} / {n}",
        "piotroski_partial": "Calculé sur {n} critères sur 9 (les autres sont n.d.) : à ne pas comparer tel quel "
                             "aux seuils usuels.",
        "piotroski_roa_positive": "ROA > 0",
        "piotroski_roa_positive_help": "Résultat net ÷ actif d'ouverture positif.",
        "piotroski_cfo_positive": "CFO > 0",
        "piotroski_cfo_positive_help": "Flux de trésorerie d'exploitation positif.",
        "piotroski_roa_improved": "ROA en hausse",
        "piotroski_roa_improved_help": "ROA de t supérieur à celui de t-1.",
        "piotroski_cfo_exceeds_net_income": "CFO > résultat net",
        "piotroski_cfo_exceeds_net_income_help": "Résultat adossé à du cash : CFO supérieur au résultat net "
                                                 "(équivaut à CFO / actif > ROA).",
        "piotroski_leverage_decreased": "Levier en baisse",
        "piotroski_leverage_decreased_help": "Dette financière long terme (hors dettes locatives) ÷ actif moyen en "
                                             "baisse sur un an.",
        "piotroski_current_ratio_improved": "Liquidité en hausse",
        "piotroski_current_ratio_improved_help": "Ratio de liquidité générale (actif courant ÷ passif courant) en "
                                                 "hausse sur un an.",
        "piotroski_no_equity_issuance": "Pas d'augmentation de capital",
        "piotroski_no_equity_issuance_help": "Nombre d'actions du bilan stable ou en baisse : une hausse liée à des "
                                             "plans salariés ou à des attributions d'actions gratuites (pratique "
                                             "régulière chez Air Liquide, par exemple) compte aussi comme une "
                                             "émission, sans qu'aucun capital n'ait été levé.",
        "piotroski_gross_margin_improved": "Marge brute en hausse",
        "piotroski_gross_margin_improved_help": "Marge brute (en % du CA) en hausse sur un an.",
        "piotroski_asset_turnover_improved": "Rotation de l'actif en hausse",
        "piotroski_asset_turnover_improved_help": "CA ÷ actif d'ouverture en hausse sur un an.",
        "piotroski_detail_roa_t": "ROA t",
        "piotroski_detail_roa_p": "ROA t-1",
        "piotroski_detail_cfo_t": "CFO t",
        "piotroski_detail_net_income_t": "résultat net t",
        "piotroski_detail_leverage_t": "levier t",
        "piotroski_detail_leverage_p": "levier t-1",
        "piotroski_detail_current_ratio_t": "liquidité t",
        "piotroski_detail_current_ratio_p": "liquidité t-1",
        "piotroski_detail_shares_t": "actions t",
        "piotroski_detail_shares_p": "actions t-1",
        "piotroski_detail_gross_margin_t": "marge brute t",
        "piotroski_detail_gross_margin_p": "marge brute t-1",
        "piotroski_detail_turnover_t": "rotation t",
        "piotroski_detail_turnover_p": "rotation t-1",
        # ---------- Vision Transaction Services ----------
        "analysis_transaction_services": "vision Transaction Services (dette nette, EBITDA ajusté)",
        "section_transaction": "Vision Transaction Services",
        "transaction_intro": "Exercice de référence : {year} (dernier exercice clos). La valeur d'entreprise "
                             "utilise la capitalisation actuelle et la dette nette de cette clôture : décalage de "
                             "dates habituel, à garder en tête.",
        "pension_tax_rate_label": "Taux d'impôt sur les retraites (%)",
        "pension_tax_rate_help": "Hypothèse : les cotisations futures de retraite sont déductibles, la dette "
                                 "réelle est donc l'engagement × (1 − taux d'impôt). 25 % par défaut (IS français).",
        "net_debt_bridge_title": "Pont de dette nette",
        "col_amount": "Montant ({currency})",
        "col_source": "Source",
        "source_data": "Donnée",
        "source_assumption": "Hypothèse",
        "source_subtotal": "Sous-total",
        "source_memo": "Pour mémoire",
        "bridge_line_current_debt": "Dette financière court terme",
        "bridge_line_long_term_debt": "Dette financière long terme",
        "bridge_line_total_debt": "Dette totale (Yahoo, y c. dettes locatives)",
        "bridge_line_lease_liabilities_deducted": "− Dettes locatives incluses dans la dette totale",
        "bridge_line_gross_financial_debt": "Dette financière brute (hors IFRS 16)",
        "bridge_line_cash": "− Trésorerie et équivalents",
        "bridge_line_net_financial_debt": "Dette financière nette",
        "bridge_line_short_term_investments_memo": "Placements court terme (non déduits)",
        "bridge_line_lease_liabilities": "+ Dettes locatives (IFRS 16)",
        "bridge_line_pension_liabilities": "+ Engagements de retraite (bruts)",
        "bridge_line_pension_tax_effect": "− Effet d'impôt sur les retraites ({rate} %)",
        "bridge_line_net_debt_data": "Dette nette (données)",
        "bridge_line_user_item": "{label}",
        "bridge_line_adjusted_net_debt": "Dette nette ajustée",
        "bridge_excluded": "n.d. : non fourni par Yahoo, exclu du total (à saisir en hypothèse si connu).",
        "bridge_memo_help": "Placements financiers à court terme : non déduits par défaut, faute de pouvoir "
                            "vérifier qu'ils sont immédiatement mobilisables. À saisir en hypothèse (montant "
                            "négatif) si tu les retiens.",
        "flag_gross_debt_from_total_debt": "Dette court terme non fournie : dette brute reconstituée comme dette "
                                           "totale Yahoo − dettes locatives.",
        "flag_minority_interest_missing": "Intérêts minoritaires non fournis par Yahoo : exclus de la valeur "
                                          "d'entreprise (à vérifier dans les comptes publiés).",
        "net_debt_items_title": "Éléments assimilables à de la dette ou à de la trésorerie (hypothèses)",
        "net_debt_items_help": "Saisis tes propres éléments, en millions de {currency} : montant positif pour une "
                               "dette (complément de prix, dividendes à payer, affacturage déconsolidant, litige "
                               "provisionné...), négatif pour de la trésorerie (créance de cession, placements court "
                               "terme retenus...).",
        "ebitda_adjustments_title": "Ajustements de l'EBITDA (éléments non récurrents)",
        "ebitda_adjustments_help": "Saisis tes ajustements, en millions de {currency} : montant positif pour "
                                   "réintégrer une charge non récurrente (restructuration, litige ponctuel...), négatif "
                                   "pour retirer un produit non récurrent (plus-value de cession...).",
        "col_label": "Libellé",
        "col_amount_millions": "Montant (M {currency})",
        "add_row_btn": "Ajouter une ligne",
        "invalid_rows": "Ligne(s) {rows} ignorée(s) : montant manquant ou non numérique.",
        "effects_title": "Effet sur les multiples",
        "col_published": "Publié",
        "col_adjusted": "Ajusté",
        "col_change": "Écart",
        "effects_ebitda": "EBITDA",
        "effects_ebitda_help": "EBITDA publié (exercice de référence), puis après les ajustements saisis.",
        "effects_net_debt": "Dette nette",
        "effects_net_debt_help": "Dette nette issue des seules données, puis après les hypothèses saisies.",
        "effects_enterprise_value": "Valeur d'entreprise",
        "effects_enterprise_value_help": "Capitalisation actuelle (devise des comptes) + dette nette + intérêts "
                                         "minoritaires : l'EBITDA consolidé couvre 100 % des filiales, la valeur "
                                         "d'entreprise doit donc inclure la part des minoritaires.",
        "effects_ev_to_ebitda": "VE / EBITDA",
        "effects_ev_to_ebitda_help": "Multiple de valorisation : valeur d'entreprise ÷ EBITDA. Mesure combien "
                                     "d'années d'EBITDA paie un acquéreur. À comparer aux pairs du secteur ; un EBITDA "
                                     "ajusté plus élevé fait mécaniquement baisser le multiple. n.d. si l'EBITDA est "
                                     "nul ou négatif.",
        "effects_net_debt_to_ebitda": "Dette nette / EBITDA",
        "effects_net_debt_to_ebitda_help": "Levier : nombre d'années d'EBITDA pour rembourser la dette nette. "
                                           "Lecture usuelle : sous 2x confortable, au-delà de 3-4x élevé (zone des "
                                           "covenants bancaires classiques). n.d. si l'EBITDA est nul ou négatif.",
        "ifrs16_note": "Dette nette ajustée hors IFRS 16 : {value} (information seulement : un multiple sur cette "
                       "base exigerait un EBITDA après loyers, que yfinance ne fournit pas).",
        "market_cap_unavailable": "Capitalisation indisponible dans la devise des comptes : valeur d'entreprise et "
                                  "VE / EBITDA n.d.",
        # ---------- Loi de Benford ----------
        "section_benford": "Loi de Benford",
        "benford_intro": "Dans de nombreux jeux de montants « naturels » (écritures, factures), le premier chiffre "
                         "significatif vaut 1 dans 30 % des cas et 9 dans moins de 5 %. Un écart marqué peut signaler "
                         "des montants inventés ou arrondis, mais aussi une population atypique (prix fixes, plafonds "
                         "d'approbation) : c'est un outil de ciblage, pas une preuve. Il faut des centaines, idéalement "
                         "des milliers de montants : importe un grand livre ou une liste d'écritures.",
        "benford_source_label": "Source des montants",
        "benford_source_csv": "Fichier CSV (grand livre, écritures)",
        "benford_source_statements": "États financiers de la société analysée (démonstration)",
        "benford_upload": "Glisse un fichier CSV ici, ou clique pour le choisir",
        "benford_file_loaded": "{filename} : {rows} lignes, {cols} colonnes.",
        "benford_file_unreadable": "Fichier illisible : un CSV avec une ligne d'en-tête est attendu (séparateur « ; », "
                                   "« , », tabulation ou « | », encodage UTF-8 ou Windows).",
        "benford_column_label": "Colonne de montant",
        "benford_sign_label": "Montants analysés",
        "benford_sign_positive": "Positifs",
        "benford_sign_negative": "Négatifs (en valeur absolue)",
        "benford_sign_help": "Positifs et négatifs sont analysés séparément, comme le recommande Nigrini : factures et "
                             "avoirs obéissent à des logiques différentes, les mélanger peut masquer une anomalie.",
        "benford_min_amount_label": "Montant minimal (valeur absolue)",
        "benford_min_amount_help": "Les très petits montants (frais, arrondis) relèvent souvent d'une autre logique et "
                                   "faussent la distribution : exclus sous ce seuil (10 par défaut, pratique de "
                                   "Nigrini).",
        "benford_no_file": "Importe un fichier CSV pour lancer le test.",
        "benford_no_ticker": "Analyse d'abord une société (en haut de page) pour la démonstration sur ses états "
                             "financiers.",
        "benford_counts": "{kept} montant(s) retenu(s) sur {total} : {unreadable} illisible(s), {zero} nul(s), "
                          "{other_sign} de l'autre signe, {below_min} sous le montant minimal.",
        "benford_demo_warning": "Démonstration : les états financiers d'une seule société ne fournissent que quelques "
                                "centaines de montants, en partie agrégés (totaux, sous-totaux) et donc dépendants les "
                                "uns des autres. Ce n'est pas un test fiable : pour une vraie analyse, importe un grand "
                                "livre.",
        "benford_warning_not_interpretable": "{n} montants seulement : résultat non interprétable. Sous conformité "
                                             "parfaite, le MAD attendu par le seul hasard vaut ici {expected_mad}, "
                                             "au-delà de la borne « acceptable » de Nigrini (0,012) : même des données "
                                             "parfaitement conformes paraîtraient non conformes. Il faut au moins 400 "
                                             "montants.",
        "benford_warning_caution": "{n} montants : à interpréter avec prudence. Le MAD attendu par le seul hasard vaut "
                                   "ici {expected_mad}, au-dessus de la borne de « conformité étroite » (0,006) : cette "
                                   "zone n'est pas atteignable par hasard sous 1 500 montants environ.",
        "benford_empty": "Aucun montant exploitable avec ces réglages.",
        "benford_mad_label": "MAD (écart absolu moyen)",
        "benford_mad_help": "Mesure l'écart moyen entre fréquences observées et attendues. Formule : moyenne sur les 9 "
                            "chiffres de |observé − Benford|. Bornes de Nigrini (2012) pour le premier chiffre : "
                            "≤ 0,006 conformité étroite, ≤ 0,012 acceptable, ≤ 0,015 marginale, au-delà non-conformité. "
                            "Indépendant de la taille de l'échantillon, c'est l'indicateur qui fait foi.",
        "benford_conformity_label": "Conformité (Nigrini)",
        "conformity_close": "conformité étroite",
        "conformity_acceptable": "conformité acceptable",
        "conformity_marginal": "conformité marginale",
        "conformity_nonconformity": "non-conformité",
        "benford_chi2_label": "χ² (8 degrés de liberté)",
        "benford_chi2_help": "Test du khi-deux : Σ (effectif observé − attendu)² ÷ attendu, comparé à une loi du χ² à 8 "
                             "degrés de liberté (p-value < 0,05 : écart significatif). Sa puissance croît avec la taille : "
                             "sur des dizaines de milliers de montants, il rejette la conformité pour des écarts "
                             "minimes, d'où la préférence de Nigrini pour le MAD.",
        "benford_p_value_label": "p-value",
        "benford_expected_mad": "MAD attendu par le seul hasard pour {n} montants : {value}.",
        "benford_chart_title": "Premier chiffre : observé vs loi de Benford",
        "benford_observed": "Observé",
        "benford_expected": "Benford",
        "benford_digit": "Premier chiffre",
        "benford_frequency": "Fréquence (%)",
        "col_digit": "Chiffre",
        "col_count": "Effectif",
        "col_observed_pct": "Observé (%)",
        "col_expected_pct": "Benford (%)",
        "col_deviation_pct": "Écart (pts)",
        "field_revenue": "Chiffre d'affaires",
        "field_revenue_help": "Produits de l'activité ordinaire de l'exercice, hors taxes.",
        "field_cost_of_revenue": "Coût des ventes",
        "field_cost_of_revenue_help": "Coûts directement attribuables aux produits vendus (achats "
                                      "consommés, production).",
        "field_gross_profit": "Marge brute",
        "field_gross_profit_help": "Chiffre d'affaires − coût des ventes.",
        "field_sga": "Frais commerciaux et administratifs",
        "field_sga_help": "Frais de vente, de distribution et de structure (SG&A). Souvent non publiés "
                          "séparément par les sociétés européennes qui présentent leurs charges par nature.",
        "field_d_and_a": "Dotations aux amortissements",
        "field_d_and_a_help": "Consommation de la valeur des immobilisations sur l'exercice. Charge sans "
                              "sortie de trésorerie : écart structurel entre résultat et flux de trésorerie.",
        "field_depreciation": "Amortissements des immobilisations corporelles",
        "field_depreciation_help": "Dotations aux amortissements hors amortissement des incorporels : la "
                                   "base du DEPI de Beneish. Repli sur les dotations totales (poste voisin) si "
                                   "Yahoo ne les distingue pas.",
        "field_interest_expense": "Charges d'intérêts",
        "field_interest_expense_help": "Coût de la dette financière sur l'exercice.",
        "field_pretax_income": "Résultat avant impôt",
        "field_pretax_income_help": "Résultat de l'exercice avant l'impôt sur les sociétés.",
        "field_ebit": "EBIT",
        "field_ebit_help": "Résultat avant intérêts et impôts. Yahoo le calcule comme résultat avant impôt "
                           "+ charges d'intérêts ; le résultat opérationnel publié n'en est qu'une "
                           "approximation.",
        "field_ebitda": "EBITDA",
        "field_ebitda_help": "EBIT + dotations aux amortissements : un indicateur de résultat opérationnel "
                             "avant consommation des immobilisations, base des multiples de valorisation.",
        "field_tax_provision": "Impôt sur les sociétés",
        "field_tax_provision_help": "Charge d'impôt de l'exercice (exigible et différé).",
        "field_net_income": "Résultat net (part du groupe)",
        "field_net_income_help": "Résultat net revenant aux actionnaires de la société mère.",
        "field_net_income_incl_minorities": "Résultat net (y compris minoritaires)",
        "field_net_income_incl_minorities_help": "Résultat net de l'ensemble consolidé, y compris la part "
                                                 "des actionnaires minoritaires des filiales.",
        "field_total_assets": "Total actif",
        "field_total_assets_help": "Ensemble des ressources contrôlées par la société à la clôture.",
        "field_current_assets": "Actif courant",
        "field_current_assets_help": "Actifs destinés à être réalisés dans le cycle d'exploitation ou "
                                     "dans les 12 mois (stocks, créances, trésorerie...).",
        "field_current_liabilities": "Passif courant",
        "field_current_liabilities_help": "Dettes exigibles dans les 12 mois.",
        "field_equity": "Capitaux propres (part du groupe)",
        "field_equity_help": "Actif − passif, revenant aux actionnaires de la société mère.",
        "field_total_equity_incl_minorities": "Capitaux propres (y compris minoritaires)",
        "field_total_equity_incl_minorities_help": "Capitaux propres de l'ensemble consolidé, y compris les "
                                                   "intérêts minoritaires.",
        "field_minority_interest": "Intérêts minoritaires",
        "field_minority_interest_help": "Part des capitaux propres des filiales revenant aux actionnaires "
                                        "minoritaires (valeur comptable).",
        "field_total_liabilities": "Total passif (hors capitaux propres)",
        "field_total_liabilities_help": "Ensemble des dettes et provisions. Identité de repli : total actif "
                                        "− capitaux propres y compris minoritaires.",
        "field_retained_earnings": "Réserves (résultats accumulés)",
        "field_retained_earnings_help": "Bénéfices passés non distribués, cumulés.",
        "field_working_capital": "Fonds de roulement",
        "field_working_capital_help": "Actif courant − passif courant.",
        "field_receivables": "Créances clients",
        "field_receivables_help": "Montants facturés et non encore encaissés auprès des clients. Le poste "
                                  "« Receivables » de Yahoo, plus large (créances fiscales, sociales...), "
                                  "n'est utilisé qu'en repli.",
        "field_inventory": "Stocks",
        "field_inventory_help": "Matières, en-cours et produits finis détenus à la clôture.",
        "field_payables": "Dettes fournisseurs",
        "field_payables_help": "Montants dus aux fournisseurs. Le poste « Payables » de Yahoo, plus large, "
                               "n'est utilisé qu'en repli.",
        "field_cash": "Trésorerie et équivalents",
        "field_cash_help": "Disponibilités et placements très liquides à court terme.",
        "field_cash_and_short_term_investments": "Trésorerie et placements court terme",
        "field_cash_and_short_term_investments_help": "Trésorerie et équivalents + placements financiers à "
                                                      "court terme.",
        "field_ppe_net": "Immobilisations corporelles nettes",
        "field_ppe_net_help": "Terrains, constructions et équipements, nets des amortissements cumulés.",
        "field_current_debt": "Dette financière court terme",
        "field_current_debt_help": "Emprunts exigibles dans les 12 mois, hors dettes locatives.",
        "field_long_term_debt": "Dette financière long terme",
        "field_long_term_debt_help": "Emprunts à plus de 12 mois, hors dettes locatives.",
        "field_lease_liabilities_current": "Dettes locatives court terme",
        "field_lease_liabilities_current_help": "Part à moins de 12 mois des loyers futurs actualisés "
                                                "(IFRS 16).",
        "field_lease_liabilities_non_current": "Dettes locatives long terme",
        "field_lease_liabilities_non_current_help": "Part à plus de 12 mois des loyers futurs actualisés "
                                                    "(IFRS 16).",
        "field_lease_liabilities": "Dettes locatives (IFRS 16)",
        "field_lease_liabilities_help": "Loyers futurs actualisés des contrats de location (IFRS 16). "
                                        "Identité de repli : court terme + long terme.",
        "field_long_term_debt_incl_leases": "Dette long terme (dont dettes locatives)",
        "field_long_term_debt_incl_leases_help": "Dette financière à plus de 12 mois + dettes locatives non "
                                                 "courantes (IFRS 16). Identité de repli : somme des deux.",
        "field_total_debt": "Dette totale (Yahoo)",
        "field_total_debt_help": "Dette financière + dettes locatives, telle que calculée par Yahoo. La dette "
                                 "financière hors IFRS 16 se lit sur les lignes court et long terme.",
        "field_pension_liabilities": "Engagements de retraite",
        "field_pension_liabilities_help": "Provisions pour retraites et autres avantages postérieurs à "
                                          "l'emploi, assimilables à de la dette.",
        "field_shares_outstanding": "Nombre d'actions",
        "field_shares_outstanding_help": "Actions ordinaires en circulation à la clôture (hors "
                                         "autocontrôle quand Yahoo le distingue).",
        "field_cfo": "Flux de trésorerie d'exploitation (CFO)",
        "field_cfo_help": "Trésorerie générée par l'activité, après variation du BFR et impôts payés.",
        "field_capex": "Investissements (capex)",
        "field_capex_help": "Acquisitions d'immobilisations. Négatif (sortie de trésorerie), comme publié "
                            "par Yahoo.",
        "field_fcf": "Flux de trésorerie disponible (FCF)",
        "field_fcf_help": "CFO + capex (le capex étant négatif) : la trésorerie disponible après "
                          "investissements.",
        "field_change_in_working_capital": "Variation du BFR",
        "field_change_in_working_capital_help": "Effet sur la trésorerie de la variation des stocks, "
                                                "créances et dettes d'exploitation (négatif quand le BFR "
                                                "augmente).",
    },
    "en": {
        "app_title": "Financial analysis: quality and soundness of the accounts",
        "app_subtitle": "Reading a company's financial statements in the spirit of due diligence (audit, "
                        "Transaction Services): are the accounts reliable and sound? These are signals "
                        "to investigate, not verdicts.",
        "footer_disclaimer": "Financial statements and market data provided by Yahoo Finance via the "
                             "yfinance library, without analyst restatement: differences from the published "
                             "accounts are possible. Personal educational tool, neither an audit opinion nor "
                             "investment advice.",
        "lang_label": "Language",
        "dark_mode_label": "Dark mode",
        "palette_label": "Color palette",
        "intro": "Enter a Yahoo Finance ticker (e.g. AI.PA, SHEL.L, AAPL) or pick a CAC 40 company. Every "
                 "line item is mapped to a stable internal schema; hover a cell to see where the figure "
                 "comes from (published, derived from an accounting identity, or a neighbouring item), "
                 "or why it is missing.",
        "ticker_label": "Ticker",
        "ticker_placeholder": "e.g. AI.PA",
        "quick_pick_label": "Quick pick (CAC 40)",
        "quick_pick_placeholder": "Pick a company...",
        "analyze_btn": "Analyze",
        "error_empty_ticker": "Enter a ticker or pick a company from the list.",
        "error_no_data": "No annual financial statements available for \"{ticker}\" on Yahoo Finance "
                         "(wrong ticker, unlisted company, or service temporarily unavailable).",
        "results_placeholder": "Results will appear here after the analysis.",
        "na": "n/a",
        "unit_billion": "bn",
        "unit_million": "m",
        "date_format": "%Y-%m-%d",
        "section_company": "Company",
        "label_sector": "Sector",
        "label_industry": "Industry",
        "label_reporting_currency": "Reporting currency",
        "label_quote_currency": "Quote currency",
        "label_price": "Price (reporting currency)",
        "label_market_cap": "Market cap (reporting currency)",
        "label_fx_rate": "Exchange rate used",
        "currency_help": "The accounts stay in their reporting currency; only market data (price, market "
                         "cap) is converted. Formula: price in reporting currency = quoted price ÷ minor-unit "
                         "divisor (100 for a price in pence, GBp) × exchange rate; market cap = Yahoo market "
                         "cap (already in the major unit) × exchange rate.",
        "fx_detail": "1 {quote} = {rate:.4f} {reporting}",
        "fx_same_currency": "no conversion (same currency)",
        "minor_unit_detail": "price quoted in a minor unit ({quote_raw}): divided by {divisor:.0f}",
        "warn_fx_unavailable": "Exchange rate {quote} → {reporting} unavailable on Yahoo Finance: price and "
                               "market cap are not converted (shown as n/a). Ratios depending on them "
                               "cannot be computed.",
        "warn_currency_unknown": "Unknown quote or reporting currency: price and market cap cannot be "
                                 "expressed in the reporting currency (shown as n/a).",
        "warn_minor_unit_inconsistent": "Consistency check: price ÷ (P/E × EPS) = {ratio:.1f}, while the "
                                        "currency code implies a divisor of {divisor:.0f}. A Yahoo market "
                                        "data point looks inconsistent: check the price before relying on "
                                        "the market cap.",
        "regime_bank": "Bank",
        "regime_insurer": "Insurer",
        "regime_general": "Non-financial company",
        "regime_not_applicable": "{regime}: analyses not applicable: {analyses}. A bank's liabilities "
                                 "(deposits) or an insurer's (technical provisions) are the raw material of "
                                 "its business, and there are no inventories nor an industrial customer/"
                                 "supplier cycle: these analyses would produce absurd figures rather than a "
                                 "signal. The financial statements are still shown below.",
        "caution_third_party_funds": "Financial company (\"{industry}\") analyzed as usual, but its balance "
                                     "sheet may hold third-party funds (a broker's fiduciary funds, an "
                                     "exchange's clearing positions...) that inflate assets and liabilities "
                                     "without reflecting its own business: read balance-sheet ratios with care.",
        "caution_unknown_industry": "Industry not provided by Yahoo Finance: impossible to check whether this "
                                    "is a bank or an insurer. The analysis is run as for a non-financial "
                                    "company.",
        "analysis_beneish": "Beneish M-score",
        "analysis_altman": "Altman Z-score",
        "analysis_working_capital": "working capital analysis",
        "analysis_earnings_quality": "earnings quality (cash conversion, accruals)",
        "section_statements": "Normalized financial statements",
        "coverage_note": "yfinance only provides about {typical} annual fiscal years: {n} usable year(s) here "
                         "({years}). Trends and scores comparing two fiscal years therefore rest on a short "
                         "history.",
        "statements_legend": "Italics: item derived from an accounting identity or taken from a neighbouring "
                             "item (hover the cell for details). \"n/a\": data not available, never replaced "
                             "by 0.",
        "statement_income": "Income statement",
        "statement_balance": "Balance sheet",
        "statement_cashflow": "Cash flow statement",
        "col_item": "Item",
        "amounts_unit": "Amounts in {currency}",
        "prov_published": "Published: \"{label}\" ({statement}).",
        "prov_equivalent": "Neighbouring item, for lack of the exact one: \"{label}\" ({statement}). Not "
                           "strictly identical (often broader): keep it in mind.",
        "prov_derived": "Derived: {formula}.",
        "prov_missing_not_in_yfinance": "n/a: item missing from yfinance data for this fiscal year.",
        "prov_missing_derivation": "n/a: missing from yfinance data, and not derivable ({formula}) for lack "
                                   "of: {missing}.",
        "section_earnings_quality": "Earnings quality",
        "section_bridge": "From net income to operating cash flow",
        "section_working_capital": "Working capital in days",
        "section_not_applicable": "{regime}: analysis not applicable (see the box at the top of the page).",
        "col_metric": "Metric",
        "col_trend": "Change",
        "trend_text": "{delta} ({first} → {last})",
        "trend_na": "n/a (fewer than 2 fiscal years)",
        "unit_days": "d",
        "ratio_cfo_to_net_income": "CFO / net income",
        "ratio_cfo_to_net_income_help": "Measures the share of earnings actually collected in cash. Formula: cash "
                                        "flow from operations ÷ net income including minorities (same scope as the "
                                        "consolidated CFO). Reading: around 1 or above, earnings are backed by cash; "
                                        "persistently below 0.8, earnings exceed the cash they generate, a signal to "
                                        "investigate (revenue booked before collection, growing working capital). "
                                        "Under IFRS 16, lease principal repayments are classified as financing: the "
                                        "CFO of heavy lessees (retail) is inflated accordingly. Not meaningful if "
                                        "net income is zero or negative.",
        "ratio_fcf_to_net_income": "FCF / net income",
        "ratio_fcf_to_net_income_help": "Measures the cash left after investment, per unit of earnings. Formula: (CFO "
                                        "+ capex, capex being negative) ÷ net income including minorities. Reading: "
                                        "close to 1, earnings turn into free cash; persistently low or negative, "
                                        "investment absorbs earnings (normal during an investment phase, worrying if "
                                        "it lasts). Not meaningful if net income is zero or negative.",
        "ratio_sloan_accruals": "Accruals (Sloan)",
        "ratio_sloan_accruals_help": "Measures the share of earnings not yet turned into cash, scaled by balance "
                                     "sheet size. Formula: (net income − CFO) ÷ average total assets, i.e. (opening "
                                     "+ closing) / 2. Reading: close to 0 or negative, earnings are backed by cash; "
                                     "above roughly +10% of assets, a warning sign: Sloan (1996) shows that firms "
                                     "with the highest accruals subsequently see their earnings deteriorate. The "
                                     "oldest fiscal year is n/a for lack of an opening balance sheet.",
        "ratio_dso": "DSO (days sales outstanding)",
        "ratio_dso_help": "Measures the average customer collection period. Formula: closing trade receivables ÷ "
                          "revenue × 365. Reading: compare with the sector's payment terms (in France, the LME law caps "
                          "business-to-business terms at 60 days, or 45 days end of month); a rise without revenue "
                          "growth may signal collection problems or aggressive revenue recognition.",
        "ratio_dio": "DIO (days inventory outstanding)",
        "ratio_dio_help": "Measures how many days of cost of revenue inventories represent. Formula: closing "
                          "inventories ÷ cost of revenue × 365. Reading: compare with the sector and the company's own "
                          "history; a lasting rise may signal slow-moving or obsolete stock (impairment risk). n/a "
                          "without cost of revenue: computing it on revenue would change its meaning.",
        "ratio_dpo": "DPO (days payables outstanding)",
        "ratio_dpo_help": "Measures the average supplier payment period. Formula: closing trade payables ÷ cost of "
                          "revenue × 365. Reading: a rise makes suppliers finance working capital; far beyond legal or "
                          "sector terms, it may reflect cash strain. n/a without cost of revenue.",
        "ratio_ccc": "Cash conversion cycle",
        "ratio_ccc_help": "Measures the number of days the business ties up cash, between paying suppliers and "
                          "collecting from customers. Formula: DSO + DIO − DPO. Reading: the shorter, the less cash the "
                          "business consumes; negative, suppliers finance operations (retail for example). A steady "
                          "rise signals deteriorating working capital.",
        "formula_cfo_to_net_income": "CFO {cfo} ÷ net income {net_income}",
        "formula_fcf_to_net_income": "FCF {fcf} ÷ net income {net_income}",
        "formula_sloan_accruals": "(net income {net_income} − CFO {cfo}) ÷ average assets (({total_assets} + "
                                  "{total_assets_prior}) / 2)",
        "formula_dso": "trade receivables {receivables} ÷ revenue {revenue} × 365",
        "formula_dio": "inventories {inventory} ÷ cost of revenue {cost_of_revenue} × 365",
        "formula_dpo": "trade payables {payables} ÷ cost of revenue {cost_of_revenue} × 365",
        "formula_ccc": "DSO {dso} + DIO {dio} − DPO {dpo}",
        "reason_missing_inputs": "n/a: missing data ({missing}).",
        "reason_non_positive_denominator": "n/a: {denominator} zero or negative, ratio not meaningful.",
        "reason_no_prior_year": "n/a: no opening balance sheet (oldest fiscal year available).",
        "denominator_net_income": "net income",
        "denominator_revenue": "revenue",
        "denominator_cost_of_revenue": "cost of revenue",
        "denominator_average_total_assets": "average total assets",
        "flag_group_share_fallback": "Group-share net income used: the version including minorities is not "
                                     "provided by Yahoo.",
        "flag_broad_receivables": "Broader \"Receivables\" item used: DSO overstated (includes non-trade "
                                  "receivables).",
        "flag_broad_payables": "Broader \"Payables\" item used: DPO overstated (includes non-trade payables).",
        "bridge_year_label": "Fiscal year",
        "bridge_title": "From net income to CFO ({year})",
        "bridge_step_net_income": "Net income (incl. minorities)",
        "bridge_step_d_and_a": "Depreciation and amortization",
        "bridge_step_change_in_working_capital": "Change in working capital",
        "bridge_step_other_items": "Other items",
        "bridge_cfo": "Published CFO",
        "bridge_help": "Explains the gap between earnings and cash: depreciation is a non-cash charge, the change in "
                       "working capital measures the cash absorbed (negative) or released (positive) by inventories, "
                       "receivables and operating payables. \"Other items\" is the residual that makes the bridge land "
                       "exactly on the published CFO (deferred taxes, share-based pay, disposal gains...).",
        "bridge_missing_items": "Not provided by Yahoo for this fiscal year, hence included in \"Other items\": "
                                "{items}.",
        "bridge_unavailable": "Bridge unavailable for this fiscal year: {missing} missing.",
        "days_chart_title": "Working capital days over time",
        "days_axis": "Days",
        "analysis_piotroski": "Piotroski F-score",
        "section_scores": "Warning scores",
        "scores_caveat": "These scores were calibrated on US companies, in other eras (1946-1965 for Altman, "
                         "1982-1992 for Beneish, 1976-1996 for Piotroski), and under accounting standards other than "
                         "IFRS: they are signals to investigate, not verdicts.",
        "col_pair": "{t} vs {p}",
        "col_reference_manipulators": "Manipulators (mean)",
        "col_reference_non_manipulators": "Non-manipulators (mean)",
        "suffix_t": "(t)",
        "suffix_p": "(t-1)",
        "reason_non_positive_base": "n/a: zero or negative comparison base, index not meaningful.",
        "flag_aqi_neutral_by_definition": "Zero base in t-1 (assets made only of current assets and property, plant "
                                          "and equipment): index set to 1, as Beneish does.",
        "flag_depreciation_includes_amortization": "Depreciation of tangible assets alone not separated by Yahoo: "
                                                   "total D&A used (includes amortization of intangibles).",
        "flag_group_share_equity_fallback": "Group-share equity used: the version including minorities is not "
                                            "provided by Yahoo.",
        "section_beneish": "Beneish M-score",
        "beneish_help": "Measures how closely the accounts resemble those of companies that manipulated earnings "
                        "(Beneish 1999 sample). Formula: M = −4.84 + 0.920·DSRI + 0.528·GMI + 0.404·AQI + 0.892·SGI + "
                        "0.115·DEPI − 0.172·SGAI + 4.679·TATA − 0.327·LVGI. Threshold: above −1.78, profile closer to "
                        "manipulators. Compares two consecutive fiscal years (t and t-1). Right-hand columns: means of "
                        "the estimation sample (Beneish 1999, table 2).",
        "beneish_m_score": "M-score",
        "beneish_m_score_indicative": "Indicative M-score (missing indices neutralized at 1)",
        "beneish_verdict_manipulation_risk": "{pair}: M = {value}, above −1.78: profile closer to the manipulators of "
                                             "Beneish's sample, a signal to investigate.",
        "beneish_verdict_no_signal": "{pair}: M = {value}, below −1.78: no manipulation signal according to the model.",
        "beneish_official_na": "{pair}: M-score n/a, missing index(es): {missing}. The coefficients are estimated "
                               "jointly, a variable cannot be dropped.",
        "beneish_indicative_note": "Indicative variant, missing indices replaced by 1 (no change): {neutralized}. "
                                   "Beneish himself did this for DEPI and SGAI when COMPUSTAT lacked the data; read it "
                                   "as an order of magnitude.",
        "beneish_dsri": "DSRI (receivables / revenue)",
        "beneish_dsri_help": "Days sales in receivables index. Formula: (receivables t ÷ revenue t) ÷ (receivables t-1 ÷ "
                             "revenue t-1). Above 1, receivables grow faster than sales: a change in credit policy, or "
                             "inflated revenue.",
        "beneish_gmi": "GMI (gross margin)",
        "beneish_gmi_help": "Gross margin index. Formula: gross margin t-1 ÷ gross margin t (as % of revenue). Above 1, "
                            "the margin has deteriorated: poorer prospects increase the incentive to dress up the "
                            "accounts.",
        "beneish_aqi": "AQI (asset quality)",
        "beneish_aqi_help": "Asset quality index. Formula: [1 − (current assets + PP&E) ÷ total assets] t ÷ same ratio "
                            "t-1. Above 1, the share of assets with uncertain future benefits grows: costs possibly "
                            "capitalized instead of expensed.",
        "beneish_sgi": "SGI (sales growth)",
        "beneish_sgi_help": "Sales growth index. Formula: revenue t ÷ revenue t-1. Growth is not manipulation, but the "
                            "pressure to sustain it is an incentive.",
        "beneish_depi": "DEPI (depreciation)",
        "beneish_depi_help": "Depreciation index. Formula: rate t-1 ÷ rate t, with rate = depreciation ÷ (depreciation + "
                             "net PP&E). Above 1, depreciation slows down: longer useful lives, which boosts earnings.",
        "beneish_sgai": "SGAI (overheads)",
        "beneish_sgai_help": "SG&A expenses index. Formula: (SG&A t ÷ revenue t) ÷ (SG&A t-1 ÷ revenue t-1). Above 1, "
                             "overheads grow faster than sales. Often n/a: many European companies do not report SG&A "
                             "separately.",
        "beneish_lvgi": "LVGI (leverage)",
        "beneish_lvgi_help": "Leverage index. Formula: [(current liabilities + long-term debt, leases included) ÷ total "
                             "assets] t ÷ same ratio t-1. Above 1, leverage rises: debt covenants may encourage "
                             "dressing up the accounts.",
        "beneish_tata": "TATA (accruals / assets)",
        "beneish_tata_help": "Accruals scaled by assets. Formula: (net income − CFO) ÷ total assets t. The higher, the "
                             "less earnings are backed by cash. Computed from cash flows rather than from the paper's "
                             "balance-sheet changes (more reliable, Hribar and Collins 2002).",
        "formula_beneish_dsri": "(receivables {receivables_t} ÷ revenue {revenue_t}) ÷ (receivables {receivables_p} ÷ "
                                "revenue {revenue_p})",
        "formula_beneish_gmi": "(gross profit {gross_profit_p} ÷ revenue {revenue_p}) ÷ (gross profit {gross_profit_t} ÷ "
                               "revenue {revenue_t})",
        "formula_beneish_aqi": "[1 − ({current_assets_t} + {ppe_net_t}) ÷ {total_assets_t}] ÷ [1 − ({current_assets_p} "
                               "+ {ppe_net_p}) ÷ {total_assets_p}]",
        "formula_beneish_sgi": "revenue {revenue_t} ÷ revenue {revenue_p}",
        "formula_beneish_depi": "[{depreciation_p} ÷ ({depreciation_p} + {ppe_net_p})] ÷ [{depreciation_t} ÷ "
                                "({depreciation_t} + {ppe_net_t})]",
        "formula_beneish_sgai": "(SG&A {sga_t} ÷ revenue {revenue_t}) ÷ (SG&A {sga_p} ÷ revenue {revenue_p})",
        "formula_beneish_lvgi": "[({current_liabilities_t} + {long_term_debt_incl_leases_t}) ÷ {total_assets_t}] ÷ "
                                "[({current_liabilities_p} + {long_term_debt_incl_leases_p}) ÷ {total_assets_p}]",
        "formula_beneish_tata": "(net income {net_income_t} − CFO {cfo_t}) ÷ assets {total_assets_t}",
        "contribution_text": "contribution to the score: {coefficient} × {value} = {contribution}",
        "section_altman": "Altman Z-score",
        "altman_help": "Measures default risk from five balance-sheet and earnings ratios. Original Z (Altman 1968, "
                       "listed manufacturers): Z = 1.2·X1 + 1.4·X2 + 3.3·X3 + 0.6·X4 + 0.999·X5, zones < 1.81 distress, "
                       "1.81-2.99 grey, > 2.99 safe. Z'' (Altman 1995, non-manufacturers): Z'' = 6.56·X1 + 3.26·X2 + "
                       "6.72·X3 + 1.05·X4 on book equity, zones < 1.10 distress, 1.10-2.60 grey, > 2.60 safe. A level "
                       "score: one fiscal year at a time.",
        "altman_model_label": "Model",
        "altman_model_auto": "Automatic",
        "altman_model_original": "Original Z (listed manufacturers)",
        "altman_model_z_double_prime": "Z'' (non-manufacturers)",
        "altman_auto_choice": "Automatic choice: {model}, based on the Yahoo sector \"{sector}\". The original Z is "
                              "reserved for the Industrials and Basic Materials sectors, close to the manufacturing "
                              "sample it was calibrated on.",
        "altman_x1": "X1 working capital / assets",
        "altman_x1_help": "Liquidity: (current assets − current liabilities) ÷ total assets. Shrinking working capital "
                          "is one of the first signs of trouble.",
        "altman_x2": "X2 retained earnings / assets",
        "altman_x2_help": "Cumulative profitability: retained earnings ÷ total assets. Naturally penalizes young "
                          "companies.",
        "altman_x3": "X3 EBIT / assets",
        "altman_x3_help": "Return on assets: EBIT ÷ total assets, the most heavily weighted ratio.",
        "altman_x4": "X4 equity / liabilities",
        "altman_x4_help": "Cushion before insolvency: market capitalization at year end (original Z) or book equity "
                          "(Z'') ÷ total liabilities. Historical market cap = closing price at the fiscal year-end date "
                          "× shares from the balance sheet, converted at that date's exchange rate.",
        "altman_x5": "X5 revenue / assets",
        "altman_x5_help": "Asset turnover: revenue ÷ total assets (original Z only: it varies widely across sectors, "
                          "hence its removal from Z'').",
        "altman_z": "Z-score",
        "altman_zone": "Zone",
        "zone_safe": "safe",
        "zone_grey": "grey",
        "zone_distress": "distress",
        "altman_ratio_formula": "{numerator_label} {numerator} ÷ {denominator_label} {denominator} = {value}",
        "altman_mve_unavailable": "Market cap at year end unavailable (historical price or exchange rate missing): "
                                  "original Z n/a for this fiscal year, switching to Z'' is possible.",
        "field_market_value_of_equity": "market cap at year end",
        "section_piotroski": "Piotroski F-score",
        "piotroski_help": "Measures improving financial health on 9 binary criteria (1 = met), Piotroski 2000: "
                          "profitability (4), financial structure (3), efficiency (2). Reading: 8-9 strong, 0-2 weak. "
                          "ROA and asset turnover scaled by opening assets, as in the paper: change criteria need three "
                          "balance sheets.",
        "piotroski_score": "F-score",
        "piotroski_score_text": "{score} / {n}",
        "piotroski_partial": "Computed on {n} criteria out of 9 (the others are n/a): not directly comparable to the "
                             "usual thresholds.",
        "piotroski_roa_positive": "ROA > 0",
        "piotroski_roa_positive_help": "Net income ÷ opening assets is positive.",
        "piotroski_cfo_positive": "CFO > 0",
        "piotroski_cfo_positive_help": "Cash flow from operations is positive.",
        "piotroski_roa_improved": "ROA up",
        "piotroski_roa_improved_help": "ROA in t higher than in t-1.",
        "piotroski_cfo_exceeds_net_income": "CFO > net income",
        "piotroski_cfo_exceeds_net_income_help": "Earnings backed by cash: CFO above net income (equivalent to CFO / "
                                                 "assets > ROA).",
        "piotroski_leverage_decreased": "Leverage down",
        "piotroski_leverage_decreased_help": "Long-term financial debt (excluding leases) ÷ average assets down over "
                                             "the year.",
        "piotroski_current_ratio_improved": "Liquidity up",
        "piotroski_current_ratio_improved_help": "Current ratio (current assets ÷ current liabilities) up over the "
                                                 "year.",
        "piotroski_no_equity_issuance": "No equity issuance",
        "piotroski_no_equity_issuance_help": "Share count on the balance sheet stable or down: an increase from "
                                             "employee plans or bonus share allotments (a regular practice at Air "
                                             "Liquide, for instance) also counts as an issuance, even though no "
                                             "capital was raised.",
        "piotroski_gross_margin_improved": "Gross margin up",
        "piotroski_gross_margin_improved_help": "Gross margin (as % of revenue) up over the year.",
        "piotroski_asset_turnover_improved": "Asset turnover up",
        "piotroski_asset_turnover_improved_help": "Revenue ÷ opening assets up over the year.",
        "piotroski_detail_roa_t": "ROA t",
        "piotroski_detail_roa_p": "ROA t-1",
        "piotroski_detail_cfo_t": "CFO t",
        "piotroski_detail_net_income_t": "net income t",
        "piotroski_detail_leverage_t": "leverage t",
        "piotroski_detail_leverage_p": "leverage t-1",
        "piotroski_detail_current_ratio_t": "liquidity t",
        "piotroski_detail_current_ratio_p": "liquidity t-1",
        "piotroski_detail_shares_t": "shares t",
        "piotroski_detail_shares_p": "shares t-1",
        "piotroski_detail_gross_margin_t": "gross margin t",
        "piotroski_detail_gross_margin_p": "gross margin t-1",
        "piotroski_detail_turnover_t": "turnover t",
        "piotroski_detail_turnover_p": "turnover t-1",
        "analysis_transaction_services": "Transaction Services view (net debt, adjusted EBITDA)",
        "section_transaction": "Transaction Services view",
        "transaction_intro": "Reference fiscal year: {year} (last closed fiscal year). Enterprise value uses the "
                             "current market cap and the net debt at that year end: a usual date mismatch, to keep "
                             "in mind.",
        "pension_tax_rate_label": "Tax rate on pensions (%)",
        "pension_tax_rate_help": "Assumption: future pension contributions are tax-deductible, so the real debt is "
                                 "the obligation × (1 − tax rate). 25% by default (French corporate tax).",
        "net_debt_bridge_title": "Net debt bridge",
        "col_amount": "Amount ({currency})",
        "col_source": "Source",
        "source_data": "Data",
        "source_assumption": "Assumption",
        "source_subtotal": "Subtotal",
        "source_memo": "Memo",
        "bridge_line_current_debt": "Short-term financial debt",
        "bridge_line_long_term_debt": "Long-term financial debt",
        "bridge_line_total_debt": "Total debt (Yahoo, incl. leases)",
        "bridge_line_lease_liabilities_deducted": "− Lease liabilities included in total debt",
        "bridge_line_gross_financial_debt": "Gross financial debt (excl. IFRS 16)",
        "bridge_line_cash": "− Cash and equivalents",
        "bridge_line_net_financial_debt": "Net financial debt",
        "bridge_line_short_term_investments_memo": "Short-term investments (not deducted)",
        "bridge_line_lease_liabilities": "+ Lease liabilities (IFRS 16)",
        "bridge_line_pension_liabilities": "+ Pension obligations (gross)",
        "bridge_line_pension_tax_effect": "− Tax effect on pensions ({rate}%)",
        "bridge_line_net_debt_data": "Net debt (data)",
        "bridge_line_user_item": "{label}",
        "bridge_line_adjusted_net_debt": "Adjusted net debt",
        "bridge_excluded": "n/a: not provided by Yahoo, excluded from the total (enter it as an assumption if known).",
        "bridge_memo_help": "Short-term financial investments: not deducted by default, since it cannot be checked "
                            "that they are immediately available. Enter them as an assumption (negative amount) if you "
                            "retain them.",
        "flag_gross_debt_from_total_debt": "Short-term debt not provided: gross debt rebuilt as Yahoo total debt − "
                                           "lease liabilities.",
        "flag_minority_interest_missing": "Minority interests not provided by Yahoo: excluded from enterprise value "
                                          "(check the published accounts).",
        "net_debt_items_title": "Debt-like or cash-like items (assumptions)",
        "net_debt_items_help": "Enter your own items, in millions of {currency}: positive for debt (earn-out, "
                               "dividends payable, derecognized factoring, provisioned litigation...), negative for cash "
                               "(disposal receivable, retained short-term investments...).",
        "ebitda_adjustments_title": "EBITDA adjustments (non-recurring items)",
        "ebitda_adjustments_help": "Enter your adjustments, in millions of {currency}: positive to add back a "
                                   "non-recurring charge (restructuring, one-off litigation...), negative to remove a "
                                   "non-recurring gain (disposal gain...).",
        "col_label": "Label",
        "col_amount_millions": "Amount ({currency} m)",
        "add_row_btn": "Add a row",
        "invalid_rows": "Row(s) {rows} ignored: missing or non-numeric amount.",
        "effects_title": "Effect on multiples",
        "col_published": "Reported",
        "col_adjusted": "Adjusted",
        "col_change": "Change",
        "effects_ebitda": "EBITDA",
        "effects_ebitda_help": "Published EBITDA (reference fiscal year), then after the entered adjustments.",
        "effects_net_debt": "Net debt",
        "effects_net_debt_help": "Net debt from the data only, then after the entered assumptions.",
        "effects_enterprise_value": "Enterprise value",
        "effects_enterprise_value_help": "Current market cap (reporting currency) + net debt + minority interests: "
                                         "consolidated EBITDA covers 100% of subsidiaries, so enterprise value must "
                                         "include the minorities' share.",
        "effects_ev_to_ebitda": "EV / EBITDA",
        "effects_ev_to_ebitda_help": "Valuation multiple: enterprise value ÷ EBITDA. Measures how many years of EBITDA "
                                     "a buyer pays. Compare with sector peers; a higher adjusted EBITDA mechanically "
                                     "lowers the multiple. n/a if EBITDA is zero or negative.",
        "effects_net_debt_to_ebitda": "Net debt / EBITDA",
        "effects_net_debt_to_ebitda_help": "Leverage: years of EBITDA needed to repay net debt. Usual reading: below "
                                           "2x comfortable, above 3-4x high (the range of standard bank covenants). n/a "
                                           "if EBITDA is zero or negative.",
        "ifrs16_note": "Adjusted net debt excluding IFRS 16: {value} (information only: a multiple on this basis would "
                       "require EBITDA after rents, which yfinance does not provide).",
        "market_cap_unavailable": "Market cap unavailable in the reporting currency: enterprise value and EV / "
                                  "EBITDA n/a.",
        "section_benford": "Benford's law",
        "benford_intro": "In many sets of \"natural\" amounts (entries, invoices), the first significant digit is 1 "
                         "about 30% of the time and 9 less than 5%. A marked deviation may signal made-up or rounded "
                         "amounts, but also an atypical population (fixed prices, approval limits): it is a targeting "
                         "tool, not proof. Hundreds, ideally thousands, of amounts are needed: import a general ledger "
                         "or a list of entries.",
        "benford_source_label": "Source of the amounts",
        "benford_source_csv": "CSV file (general ledger, entries)",
        "benford_source_statements": "Financial statements of the analyzed company (demonstration)",
        "benford_upload": "Drop a CSV file here, or click to choose one",
        "benford_file_loaded": "{filename}: {rows} rows, {cols} columns.",
        "benford_file_unreadable": "Unreadable file: a CSV with a header row is expected (\";\", \",\", tab or \"|\" "
                                   "separator, UTF-8 or Windows encoding).",
        "benford_column_label": "Amount column",
        "benford_sign_label": "Amounts analyzed",
        "benford_sign_positive": "Positive",
        "benford_sign_negative": "Negative (absolute value)",
        "benford_sign_help": "Positive and negative amounts are analyzed separately, as Nigrini recommends: invoices and "
                             "credit notes follow different logics, mixing them can hide an anomaly.",
        "benford_min_amount_label": "Minimum amount (absolute value)",
        "benford_min_amount_help": "Very small amounts (fees, rounding) often follow another logic and distort the "
                                   "distribution: excluded below this threshold (10 by default, Nigrini's practice).",
        "benford_no_file": "Import a CSV file to run the test.",
        "benford_no_ticker": "Analyze a company first (top of the page) for the demonstration on its financial "
                             "statements.",
        "benford_counts": "{kept} amount(s) kept out of {total}: {unreadable} unreadable, {zero} zero, {other_sign} of "
                          "the other sign, {below_min} below the minimum amount.",
        "benford_demo_warning": "Demonstration: a single company's financial statements only provide a few hundred "
                                "amounts, partly aggregated (totals, subtotals) and therefore dependent on each other. "
                                "This is not a reliable test: for a real analysis, import a general ledger.",
        "benford_warning_not_interpretable": "Only {n} amounts: result not interpretable. Under perfect conformity, the "
                                             "MAD expected from chance alone is {expected_mad} here, beyond Nigrini's "
                                             "\"acceptable\" bound (0.012): even perfectly conforming data would look "
                                             "nonconforming. At least 400 amounts are needed.",
        "benford_warning_caution": "{n} amounts: interpret with caution. The MAD expected from chance alone is "
                                   "{expected_mad} here, above the \"close conformity\" bound (0.006): that zone cannot "
                                   "be reached by chance below roughly 1,500 amounts.",
        "benford_empty": "No usable amount with these settings.",
        "benford_mad_label": "MAD (mean absolute deviation)",
        "benford_mad_help": "Measures the average gap between observed and expected frequencies. Formula: mean over the 9 "
                            "digits of |observed − Benford|. Nigrini (2012) first-digit bounds: ≤ 0.006 close "
                            "conformity, ≤ 0.012 acceptable, ≤ 0.015 marginal, beyond that nonconformity. Independent of "
                            "sample size, it is the indicator that prevails.",
        "benford_conformity_label": "Conformity (Nigrini)",
        "conformity_close": "close conformity",
        "conformity_acceptable": "acceptable conformity",
        "conformity_marginal": "marginal conformity",
        "conformity_nonconformity": "nonconformity",
        "benford_chi2_label": "χ² (8 degrees of freedom)",
        "benford_chi2_help": "Chi-square test: Σ (observed − expected count)² ÷ expected, compared with a χ² distribution "
                             "with 8 degrees of freedom (p-value < 0.05: significant gap). Its power grows with size: on "
                             "tens of thousands of amounts it rejects conformity for tiny gaps, hence Nigrini's "
                             "preference for the MAD.",
        "benford_p_value_label": "p-value",
        "benford_expected_mad": "MAD expected from chance alone for {n} amounts: {value}.",
        "benford_chart_title": "First digit: observed vs Benford's law",
        "benford_observed": "Observed",
        "benford_expected": "Benford",
        "benford_digit": "First digit",
        "benford_frequency": "Frequency (%)",
        "col_digit": "Digit",
        "col_count": "Count",
        "col_observed_pct": "Observed (%)",
        "col_expected_pct": "Benford (%)",
        "col_deviation_pct": "Gap (pts)",
        "field_revenue": "Revenue",
        "field_revenue_help": "Revenue from ordinary activities for the fiscal year, excluding taxes.",
        "field_cost_of_revenue": "Cost of revenue",
        "field_cost_of_revenue_help": "Costs directly attributable to the goods sold (materials consumed, "
                                      "production).",
        "field_gross_profit": "Gross profit",
        "field_gross_profit_help": "Revenue − cost of revenue.",
        "field_sga": "Selling, general and administrative expenses",
        "field_sga_help": "Selling, distribution and overhead costs (SG&A). Often not reported separately by "
                          "European companies presenting expenses by nature.",
        "field_d_and_a": "Depreciation and amortization",
        "field_d_and_a_help": "Consumption of the value of fixed assets over the year. A non-cash charge: a "
                              "structural gap between earnings and cash flow.",
        "field_depreciation": "Depreciation of property, plant and equipment",
        "field_depreciation_help": "Depreciation excluding amortization of intangibles: the basis of Beneish's "
                                   "DEPI. Falls back on total D&A (neighbouring item) if Yahoo does not "
                                   "separate them.",
        "field_interest_expense": "Interest expense",
        "field_interest_expense_help": "Cost of financial debt over the year.",
        "field_pretax_income": "Pre-tax income",
        "field_pretax_income_help": "Earnings for the year before corporate income tax.",
        "field_ebit": "EBIT",
        "field_ebit_help": "Earnings before interest and taxes. Yahoo computes it as pre-tax income + "
                           "interest expense; the published operating income is only an approximation.",
        "field_ebitda": "EBITDA",
        "field_ebitda_help": "EBIT + depreciation and amortization: an operating earnings measure before "
                             "the consumption of fixed assets, the basis of valuation multiples.",
        "field_tax_provision": "Income tax",
        "field_tax_provision_help": "Tax charge for the year (current and deferred).",
        "field_net_income": "Net income (group share)",
        "field_net_income_help": "Net income attributable to the parent company's shareholders.",
        "field_net_income_incl_minorities": "Net income (incl. minorities)",
        "field_net_income_incl_minorities_help": "Net income of the whole consolidated group, including the "
                                                 "share of subsidiaries' minority shareholders.",
        "field_total_assets": "Total assets",
        "field_total_assets_help": "All resources controlled by the company at year end.",
        "field_current_assets": "Current assets",
        "field_current_assets_help": "Assets expected to be realized within the operating cycle or 12 months "
                                     "(inventories, receivables, cash...).",
        "field_current_liabilities": "Current liabilities",
        "field_current_liabilities_help": "Liabilities due within 12 months.",
        "field_equity": "Equity (group share)",
        "field_equity_help": "Assets − liabilities, attributable to the parent company's shareholders.",
        "field_total_equity_incl_minorities": "Equity (incl. minorities)",
        "field_total_equity_incl_minorities_help": "Equity of the whole consolidated group, including "
                                                   "minority interests.",
        "field_minority_interest": "Minority interests",
        "field_minority_interest_help": "Share of subsidiaries' equity belonging to minority shareholders "
                                        "(book value).",
        "field_total_liabilities": "Total liabilities (excl. equity)",
        "field_total_liabilities_help": "All debts and provisions. Fallback identity: total assets − equity "
                                        "including minorities.",
        "field_retained_earnings": "Retained earnings",
        "field_retained_earnings_help": "Cumulative past earnings not distributed.",
        "field_working_capital": "Working capital",
        "field_working_capital_help": "Current assets − current liabilities.",
        "field_receivables": "Trade receivables",
        "field_receivables_help": "Amounts invoiced to customers and not yet collected. Yahoo's broader "
                                  "\"Receivables\" item (tax, social...) is only used as a fallback.",
        "field_inventory": "Inventories",
        "field_inventory_help": "Raw materials, work in progress and finished goods held at year end.",
        "field_payables": "Trade payables",
        "field_payables_help": "Amounts owed to suppliers. Yahoo's broader \"Payables\" item is only used as "
                               "a fallback.",
        "field_cash": "Cash and equivalents",
        "field_cash_help": "Cash and very liquid short-term investments.",
        "field_cash_and_short_term_investments": "Cash and short-term investments",
        "field_cash_and_short_term_investments_help": "Cash and equivalents + short-term financial "
                                                      "investments.",
        "field_ppe_net": "Net property, plant and equipment",
        "field_ppe_net_help": "Land, buildings and equipment, net of accumulated depreciation.",
        "field_current_debt": "Short-term financial debt",
        "field_current_debt_help": "Borrowings due within 12 months, excluding lease liabilities.",
        "field_long_term_debt": "Long-term financial debt",
        "field_long_term_debt_help": "Borrowings due after 12 months, excluding lease liabilities.",
        "field_lease_liabilities_current": "Short-term lease liabilities",
        "field_lease_liabilities_current_help": "Portion due within 12 months of discounted future lease "
                                                "payments (IFRS 16).",
        "field_lease_liabilities_non_current": "Long-term lease liabilities",
        "field_lease_liabilities_non_current_help": "Portion due after 12 months of discounted future lease "
                                                    "payments (IFRS 16).",
        "field_lease_liabilities": "Lease liabilities (IFRS 16)",
        "field_lease_liabilities_help": "Discounted future lease payments (IFRS 16). Fallback identity: "
                                        "short-term + long-term.",
        "field_long_term_debt_incl_leases": "Long-term debt (incl. leases)",
        "field_long_term_debt_incl_leases_help": "Financial debt due after 12 months + non-current lease "
                                                 "liabilities (IFRS 16). Fallback identity: sum of both.",
        "field_total_debt": "Total debt (Yahoo)",
        "field_total_debt_help": "Financial debt + lease liabilities, as computed by Yahoo. Financial debt "
                                 "excluding IFRS 16 is read on the short- and long-term lines.",
        "field_pension_liabilities": "Pension obligations",
        "field_pension_liabilities_help": "Provisions for pensions and other post-employment benefits, "
                                          "debt-like items.",
        "field_shares_outstanding": "Shares outstanding",
        "field_shares_outstanding_help": "Ordinary shares outstanding at year end (excluding treasury shares "
                                         "when Yahoo separates them).",
        "field_cfo": "Cash flow from operations (CFO)",
        "field_cfo_help": "Cash generated by the business, after working capital changes and taxes paid.",
        "field_capex": "Capital expenditure (capex)",
        "field_capex_help": "Purchases of fixed assets. Negative (cash outflow), as published by Yahoo.",
        "field_fcf": "Free cash flow (FCF)",
        "field_fcf_help": "CFO + capex (capex being negative): cash available after investments.",
        "field_change_in_working_capital": "Change in working capital",
        "field_change_in_working_capital_help": "Cash effect of changes in inventories, receivables and "
                                                "operating payables (negative when working capital grows).",
    },
}


def L(lang: str, key: str, **kwargs) -> str:
    """Traduit `key` dans la langue `lang` (repli sur le français puis sur la clé elle-même).
    Les `**kwargs` sont appliqués via .format() pour les chaînes paramétrées."""
    text = TRANSLATIONS.get(lang, TRANSLATIONS["fr"]).get(key, TRANSLATIONS["fr"].get(key, key))
    return text.format(**kwargs) if kwargs else text
