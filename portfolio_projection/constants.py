"""
Constantes partagées : univers d'indices/ETF PEA, taux de fiscalité. Aucune
dépendance sur les autres modules du projet.
"""

TICKERS = {
    "S&P 500": {"indice": "^GSPC", "etf": "PSP5.PA"},
    "Euro Stoxx 600": {"indice": "^STOXX", "etf": "ETZ.PA"},
    # Pas de flux TOPIX gratuit sur Yahoo Finance : le Nikkei 225 sert de proxy pour la source
    # "indice" (même marché, corrélation historique élevée en JPY ; l'ETF PEA ci-dessous, lui,
    # réplique bien le TOPIX et sert de source "etf").
    "Japon (TOPIX)": {"indice": "^N225", "etf": "PTPXE.PA"},
    "MSCI Emerging Markets": {"indice": "EEM", "etf": "PAEEM.PA"},
}

ETF_NAMES = {
    "PSP5.PA": "Amundi PEA S&P 500 UCITS ETF Acc (TER 0.12%)",
    "ETZ.PA": "BNP Paribas Easy Stoxx Europe 600 UCITS ETF (TER 0.19%)",
    "PTPXE.PA": "Amundi PEA Japon (TOPIX) UCITS ETF EUR Acc",
    "PAEEM.PA": "Amundi PEA Emergent (MSCI EM) ESG Transition UCITS ETF",
}

TICKER_KEYS = list(TICKERS.keys())

N_PORTFOLIOS_MAX = 4

# Fiscalité française. PEA : prélèvements sociaux uniquement après 5 ans. CTO (flat) : PFU
# (12,8 % impôt + 17,2 % prélèvements sociaux) ; le barème progressif ajoute la TMI de
# l'utilisateur aux 17,2 % de prélèvements sociaux (voir layout.compute_cto_tax_rate).
PEA_TAX_RATE = 0.172
CTO_FLAT_TAX_RATE = 0.30
