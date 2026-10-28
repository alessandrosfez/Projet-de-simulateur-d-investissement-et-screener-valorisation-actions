"""
Constantes partagées : sélection rapide de sociétés, classement sectoriel, unités monétaires.
Aucune dépendance sur les autres modules du projet.
"""

# CAC 40 (tickers Yahoo Finance), recopié de stock_valuation plutôt qu'importé : chaque outil du dépôt
# reste autonome (voir le README racine). Maintenu à la main.
# Composition depuis le 22/12/2025, inchangée aux révisions de mars, juin et septembre 2026 (communiqués
# d'Euronext). Derniers changements : Euronext remplace Teleperformance (22/09/2025), Eiffage remplace
# Edenred (22/12/2025) ; auparavant Bureau Veritas remplace Vivendi (23/12/2024) et Accor remplace
# Alstom (18/03/2024). À revoir à chaque révision trimestrielle (mars, juin, septembre, décembre).
CAC40_TICKERS = {
    "Accor": "AC.PA",
    "Air Liquide": "AI.PA",
    "Airbus": "AIR.PA",
    "ArcelorMittal": "MT.AS",
    "Axa": "CS.PA",
    "BNP Paribas": "BNP.PA",
    "Bouygues": "EN.PA",
    "Bureau Veritas": "BVI.PA",
    "Capgemini": "CAP.PA",
    "Carrefour": "CA.PA",
    "Crédit Agricole": "ACA.PA",
    "Danone": "BN.PA",
    "Dassault Systèmes": "DSY.PA",
    "Eiffage": "FGR.PA",
    "Engie": "ENGI.PA",
    "EssilorLuxottica": "EL.PA",
    "Eurofins Scientific": "ERF.PA",
    "Euronext": "ENX.PA",
    "Hermès": "RMS.PA",
    "Kering": "KER.PA",
    "L'Oréal": "OR.PA",
    "Legrand": "LR.PA",
    "LVMH": "MC.PA",
    "Michelin": "ML.PA",
    "Orange": "ORA.PA",
    "Pernod Ricard": "RI.PA",
    "Publicis": "PUB.PA",
    "Renault": "RNO.PA",
    "Safran": "SAF.PA",
    "Saint-Gobain": "SGO.PA",
    "Sanofi": "SAN.PA",
    "Schneider Electric": "SU.PA",
    "Société Générale": "GLE.PA",
    "Stellantis": "STLAP.PA",
    "STMicroelectronics": "STMPA.PA",
    "Thales": "HO.PA",
    "TotalEnergies": "TTE.PA",
    "Unibail-Rodamco-Westfield": "URW.PA",
    "Veolia": "VIE.PA",
    "Vinci": "DG.PA",
}

# Industries Yahoo Finance des sociétés dont le bilan est de nature différente (le passif est la
# matière première de l'activité : dépôts, provisions techniques) : Beneish, Altman et l'analyse
# du BFR y produiraient des chiffres absurdes. Comparaison par préfixe, Yahoo déclinant chaque
# famille en sous-industries ("Banks - Regional", "Insurance - Life"...). Les courtiers en
# assurance ("Insurance Brokers") ne portent pas le risque : ils restent analysés (voir
# CAUTION_INDUSTRIES).
BANK_INDUSTRY_PREFIXES = ("Banks",)
INSURER_INDUSTRY_PREFIXES = ("Insurance - ",)

# Sociétés financières analysées normalement, mais dont le bilan peut contenir des fonds de tiers
# (fonds fiduciaires d'un courtier, positions de compensation d'une bourse...) qui gonflent actif
# et passif sans refléter l'activité propre : un avertissement suffit, les ratios restent
# calculables.
CAUTION_INDUSTRIES = (
    "Insurance Brokers",
    "Asset Management",
    "Capital Markets",
    "Financial Data & Stock Exchanges",
    "Financial Conglomerates",
    "Credit Services",
    "Mortgage Finance",
    "Shell Companies",
)

# Sous-unités monétaires utilisées par Yahoo Finance pour certains cours : (devise principale,
# diviseur). Exemple vérifié sur Shell, AstraZeneca, Tesco et Unilever (Londres) : cours en pence
# (GBp), alors que la capitalisation et le BPA sont déjà exprimés en livres.
MINOR_CURRENCY_UNITS = {
    "GBp": ("GBP", 100),
    "GBX": ("GBP", 100),
    "ZAc": ("ZAR", 100),
    "ILA": ("ILS", 100),
}

# Nombre d'exercices annuels que yfinance fournit en pratique (souvent un 5e partiellement vide) :
# sert au message d'avertissement de l'interface, pas à tronquer les données.
TYPICAL_YFINANCE_YEARS = 4


# Secteur et industrie de secours quand Yahoo ne les fournit pas du tout (fiche sans « sector » ni
# « industry », sur toutes les cotations du titre) : sans eux, la société tombe dans « Secteur non
# renseigné » et perd ses comparables sectoriels. Valeurs prises dans la taxonomie de Yahoo elle-même,
# celle qu'il applique aux sociétés du même métier, jamais devinées. Complétée au fil des trous constatés.
# - ML.PA (Michelin) : fabricant de pneumatiques, classé comme Goodyear, Continental, Bridgestone et
#   Pirelli (vérifié sur Yahoo le 26/10/2026).
SECTOR_FALLBACK = {
    "ML.PA": {"sector": "Consumer Cyclical", "industry": "Auto Parts"},
}
