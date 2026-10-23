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
    "CAC 40": {"indice": "^FCHI", "etf": "CAC.PA"},
    "MSCI World": {"indice": "URTH", "etf": "CW8.PA"},
    "Nasdaq 100": {"indice": "^NDX", "etf": "PUST.PA"},
}

ETF_NAMES = {
    "PSP5.PA": "Amundi PEA S&P 500 UCITS ETF Acc (TER 0.12%)",
    "ETZ.PA": "BNP Paribas Easy Stoxx Europe 600 UCITS ETF (TER 0.19%)",
    "PTPXE.PA": "Amundi PEA Japon (TOPIX) UCITS ETF EUR Acc",
    "PAEEM.PA": "Amundi PEA Emergent (MSCI EM) ESG Transition UCITS ETF",
    # Seul ETF "Dist" (distribuant) de cet univers, les autres sont tous "Acc" (capitalisants) :
    # pas d'équivalent Acc PEA-éligible trouvé pour le CAC 40 pur (hors variante ESG, qui suit un
    # indice différent). Reste éligible PEA, les dividendes sont juste versés en cash plutôt que
    # réinvestis automatiquement.
    "CAC.PA": "Amundi CAC 40 UCITS ETF Dist (TER 0.25%)",
    "CW8.PA": "Amundi MSCI World Swap UCITS ETF EUR Acc (TER 0.38%)",
    "PUST.PA": "Amundi PEA Nasdaq-100 UCITS ETF Acc (TER 0.30%)",
}

TICKER_KEYS = list(TICKERS.keys())

# ---------- Indice suivi par chaque ligne du portefeuille réel (exposition par indice) ----------
# Deux lignes qui suivent le même indice (deux ETF S&P 500 d'émetteurs différents) n'apportent aucune
# diversification l'une à l'autre : regrouper par indice suivi le fait voir. Catégories hors indice :
STOCK_INDEX_KEY = "__stock__"      # action individuelle
UNKNOWN_INDEX_KEY = "__unknown__"  # indice non identifié
# Indices proposés (détection automatique et correction manuelle), noms usuels.
UNDERLYING_INDICES = (
    "S&P 500", "Nasdaq-100", "MSCI World", "FTSE All-World", "MSCI ACWI", "Stoxx Europe 600", "Euro Stoxx 50",
    "MSCI Europe", "CAC 40", "MSCI Emerging Markets", "MSCI EM Asie", "TOPIX", "MSCI Japan",
)
# Univers de simulation (TICKERS) -> indice suivi. « Euro Stoxx 600 » est le libellé historique de
# l'onglet de simulation ; l'indice répliqué par ETZ.PA est le Stoxx Europe 600.
TICKERS_UNDERLYING = {
    "S&P 500": "S&P 500", "Euro Stoxx 600": "Stoxx Europe 600", "Japon (TOPIX)": "TOPIX",
    "MSCI Emerging Markets": "MSCI Emerging Markets", "CAC 40": "CAC 40", "MSCI World": "MSCI World",
    "Nasdaq 100": "Nasdaq-100",
}
# Mots-clés du nom du fonds (en majuscules), du plus spécifique au plus général : « All-World » avant
# « World », « Asie émergente » avant « Emerging ». Première règle trouvée retenue ; une variante
# (S&P 500 Equal Weight, ESG...) tombe dans l'indice de base, corrigeable à la main.
INDEX_NAME_KEYWORDS = (
    ("Nasdaq-100", ("NASDAQ",)),
    ("S&P 500", ("S&P 500", "S&P500", "SP500", "S&P 500")),
    ("FTSE All-World", ("ALL-WORLD", "ALL WORLD")),
    ("MSCI ACWI", ("ACWI",)),
    ("MSCI EM Asie", ("EMERGING ASIA", "EM ASIA", "ASIE EMERGENTE", "ASIA EMERGING", "EMERGENTE ASIE")),
    ("MSCI Emerging Markets", ("EMERGING", "EMERGENT", "MSCI EM ")),
    ("MSCI World", ("WORLD", "MONDE")),
    ("Stoxx Europe 600", ("STOXX EUROPE 600", "STOXX 600", "EUROPE 600")),
    ("Euro Stoxx 50", ("EURO STOXX 50", "EUROSTOXX 50", "STOXX 50")),
    ("CAC 40", ("CAC 40", "CAC40")),
    ("MSCI Europe", ("MSCI EUROPE",)),
    ("TOPIX", ("TOPIX",)),
    ("MSCI Japan", ("JAPAN", "JAPON")),
)

N_PORTFOLIOS_MAX = 4

# Fiscalité française. PEA : prélèvements sociaux uniquement après 5 ans. CTO (flat) : PFU
# (12,8 % impôt + 17,2 % prélèvements sociaux) ; le barème progressif ajoute la TMI de
# l'utilisateur aux 17,2 % de prélèvements sociaux (voir layout.compute_cto_tax_rate).
PEA_TAX_RATE = 0.172
CTO_FLAT_TAX_RATE = 0.30
# Retrait d'un PEA avant 5 ans (cas général, hors exceptions légales) : clôture du plan et gains
# imposés au PFU, 12,8 % d'impôt + 17,2 % de prélèvements sociaux -- le même taux global que le
# CTO "flat", d'où l'alias plutôt qu'un second chiffre à tenir à jour. Après 5 ans : seulement
# PEA_TAX_RATE.
PEA_EARLY_WITHDRAWAL_TAX_RATE = CTO_FLAT_TAX_RATE
PEA_MATURITY_YEARS = 5

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
