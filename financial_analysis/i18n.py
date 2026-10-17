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
