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

# Plafond légal des versements sur un PEA (hors gains, hors PEA-PME) : au-delà, plus aucun
# versement n'est possible, mais le capital déjà investi continue de fructifier normalement.
PEA_CONTRIBUTION_CAP = 150_000

# Points de départ réels proposés pour la trajectoire du mode historique (voir
# results._backtest_trajectory) : au lieu de toujours prendre tout l'historique de calibration
# téléchargé ("recent"), on peut ancrer la trajectoire au début d'une crise connue pour voir "qu'a
# fait le marché depuis ce point précis ?". None = comportement par défaut (tout l'historique
# téléchargé, se termine aujourd'hui).
BACKTEST_ANCHORS = {
    "recent": None,
    "2008": "2008-01-01",
    "2020": "2020-02-01",
    "2022": "2022-01-01",
}
BACKTEST_ANCHOR_KEYS = list(BACKTEST_ANCHORS.keys())
