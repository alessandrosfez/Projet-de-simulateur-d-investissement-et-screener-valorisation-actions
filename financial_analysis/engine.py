"""
Moteur de calcul pur de l'analyse financière : normalisation des états financiers, classement
sectoriel, conversion des données de marché, ratios, scores d'alerte, vision Transaction Services
et loi de Benford. Aucune dépendance Dash, réseau ou disque : les fonctions reçoivent des
DataFrames, des dicts ou du texte déjà chargés (voir market_data.py et callbacks.py), c'est ce que
couvrent les tests.

Règle transversale : une donnée manquante n'est jamais remplacée par 0. Un poste introuvable vaut
None, accompagné de la raison, pour que l'interface affiche « n.d. » plutôt qu'un chiffre faux.
"""
import csv
import io
import math
import re
from dataclasses import dataclass

import pandas as pd

from constants import BANK_INDUSTRY_PREFIXES, CAUTION_INDUSTRIES, INSURER_INDUSTRY_PREFIXES, MINOR_CURRENCY_UNITS

# ============================================================
# NORMALISATION DES ÉTATS FINANCIERS
# ============================================================
# Les libellés yfinance ("Total Revenue", "Net PPE"...) ne sont ni stables d'une société à l'autre
# ni d'une version de yfinance à l'autre : le moteur ne les manipule qu'ici, et tout le reste du
# code travaille sur des clés internes stables (revenue, ebit, receivables...).

STATEMENTS = ("income", "balance", "cashflow")


@dataclass(frozen=True)
class FieldSpec:
    """Définition d'un poste interne.

    published : libellés yfinance qui désignent EXACTEMENT ce poste, par priorité décroissante,
    éventuellement dans un autre état (la dotation aux amortissements figure aussi au tableau de
    flux). derivation : identité comptable de repli, ("sum" | "diff", clés internes) ; ses
    opérandes doivent être définis plus haut dans FIELD_SCHEMA. equivalents : postes voisins mais
    pas strictement identiques (souvent plus larges), utilisés en dernier recours et signalés comme
    tels dans la provenance.

    Ordre de recherche : publié, puis identité comptable, puis poste voisin. Une identité exacte
    (CA - coût des ventes) est plus fidèle qu'un poste seulement proche, d'où cet ordre."""
    key: str
    statement: str
    published: tuple[tuple[str, str], ...]
    derivation: tuple[str, tuple[str, ...]] | None = None
    equivalents: tuple[tuple[str, str], ...] = ()


def _inc(*labels: str) -> tuple[tuple[str, str], ...]:
    return tuple(("income", label) for label in labels)


def _bal(*labels: str) -> tuple[tuple[str, str], ...]:
    return tuple(("balance", label) for label in labels)


def _cf(*labels: str) -> tuple[tuple[str, str], ...]:
    return tuple(("cashflow", label) for label in labels)


FIELD_SCHEMA: tuple[FieldSpec, ...] = (
    # ---------- Compte de résultat ----------
    FieldSpec("revenue", "income", _inc("Total Revenue"), equivalents=_inc("Operating Revenue")),
    FieldSpec("cost_of_revenue", "income", _inc("Cost Of Revenue"), equivalents=_inc("Reconciled Cost Of Revenue")),
    FieldSpec("gross_profit", "income", _inc("Gross Profit"), derivation=("diff", ("revenue", "cost_of_revenue"))),
    FieldSpec("sga", "income", _inc("Selling General And Administration")),
    FieldSpec(
        "d_and_a", "income",
        _inc("Reconciled Depreciation", "Depreciation And Amortization In Income Statement")
        + _cf("Depreciation And Amortization"),
    ),
    # Amortissement des immobilisations corporelles seules : le DEPI de Beneish (1999) l'exige
    # (dépréciation hors amortissement des incorporels). Repli sur les dotations totales, signalé.
    FieldSpec(
        "depreciation", "income", _inc("Depreciation Income Statement") + _cf("Depreciation"),
        equivalents=_inc("Reconciled Depreciation", "Depreciation And Amortization In Income Statement")
        + _cf("Depreciation And Amortization"),
    ),
    FieldSpec("interest_expense", "income", _inc("Interest Expense"), equivalents=_inc("Interest Expense Non Operating")),
    FieldSpec("pretax_income", "income", _inc("Pretax Income")),
    # EBIT : Yahoo le construit comme résultat avant impôt + charges d'intérêts, et l'EBITDA comme
    # EBIT + dotations (vérifié à l'unité près sur Air Liquide, LVMH, Schneider et Carrefour), d'où
    # ces identités de repli. Le résultat opérationnel publié n'est qu'un voisin : il s'écarte de
    # quelques % de l'EBIT de Yahoo sur ces mêmes sociétés.
    FieldSpec(
        "ebit", "income", _inc("EBIT"),
        derivation=("sum", ("pretax_income", "interest_expense")), equivalents=_inc("Operating Income"),
    ),
    FieldSpec("ebitda", "income", _inc("EBITDA"), derivation=("sum", ("ebit", "d_and_a"))),
    FieldSpec("tax_provision", "income", _inc("Tax Provision")),
    FieldSpec("net_income", "income", _inc("Net Income")),
    FieldSpec("net_income_incl_minorities", "income", _inc("Net Income Including Noncontrolling Interests")),
    # ---------- Bilan ----------
    FieldSpec("total_assets", "balance", _bal("Total Assets")),
    FieldSpec("current_assets", "balance", _bal("Current Assets")),
    FieldSpec("current_liabilities", "balance", _bal("Current Liabilities")),
    FieldSpec("equity", "balance", _bal("Stockholders Equity"), equivalents=_bal("Common Stock Equity")),
    FieldSpec("total_equity_incl_minorities", "balance", _bal("Total Equity Gross Minority Interest")),
    FieldSpec("minority_interest", "balance", _bal("Minority Interest")),
    FieldSpec(
        "total_liabilities", "balance", _bal("Total Liabilities Net Minority Interest"),
        derivation=("diff", ("total_assets", "total_equity_incl_minorities")),
    ),
    FieldSpec("retained_earnings", "balance", _bal("Retained Earnings")),
    FieldSpec(
        "working_capital", "balance", _bal("Working Capital"),
        derivation=("diff", ("current_assets", "current_liabilities")),
    ),
    # "Receivables"/"Payables" englobent aussi les créances et dettes hors exploitation (fiscales,
    # sociales...) : simples voisins, qui gonfleraient DSO et DPO s'ils étaient pris pour le poste
    # client ou fournisseur strict.
    FieldSpec("receivables", "balance", _bal("Accounts Receivable"), equivalents=_bal("Receivables")),
    FieldSpec("inventory", "balance", _bal("Inventory")),
    FieldSpec(
        "payables", "balance", _bal("Accounts Payable"),
        equivalents=_bal("Payables", "Payables And Accrued Expenses"),
    ),
    FieldSpec("cash", "balance", _bal("Cash And Cash Equivalents")),
    FieldSpec("cash_and_short_term_investments", "balance", _bal("Cash Cash Equivalents And Short Term Investments")),
    FieldSpec("ppe_net", "balance", _bal("Net PPE")),
    FieldSpec("current_debt", "balance", _bal("Current Debt")),
    FieldSpec("long_term_debt", "balance", _bal("Long Term Debt")),
    FieldSpec("lease_liabilities_current", "balance", _bal("Current Capital Lease Obligation")),
    FieldSpec("lease_liabilities_non_current", "balance", _bal("Long Term Capital Lease Obligation")),
    FieldSpec(
        "lease_liabilities", "balance", _bal("Capital Lease Obligations"),
        derivation=("sum", ("lease_liabilities_current", "lease_liabilities_non_current")),
    ),
    # Dette à long terme y compris dettes locatives non courantes : sous IFRS 16, les dettes locatives
    # courantes sont déjà dans le passif courant, d'où ce périmètre pour le LVGI de Beneish.
    FieldSpec(
        "long_term_debt_incl_leases", "balance", _bal("Long Term Debt And Capital Lease Obligation"),
        derivation=("sum", ("long_term_debt", "lease_liabilities_non_current")),
    ),
    # "Total Debt" de Yahoo inclut les dettes locatives : la dette financière brute hors IFRS 16 se
    # reconstruit à partir de current_debt et long_term_debt (voir phase 4, pont de dette nette).
    FieldSpec("total_debt", "balance", _bal("Total Debt")),
    FieldSpec(
        "pension_liabilities", "balance",
        _bal("Non Current Pension And Other Postretirement Benefit Plans", "Pensionand Other Post Retirement Benefit Plans"),
        equivalents=_bal("Employee Benefits"),
    ),
    FieldSpec("shares_outstanding", "balance", _bal("Ordinary Shares Number"), equivalents=_bal("Share Issued")),
    # ---------- Tableau de flux de trésorerie ----------
    FieldSpec("cfo", "cashflow", _cf("Operating Cash Flow")),
    # Signe conservé tel que publié par yfinance (une dépense d'investissement est négative) : le FCF
    # dérivé est donc bien CFO + capex, pas CFO - capex.
    FieldSpec("capex", "cashflow", _cf("Capital Expenditure"), equivalents=_cf("Purchase Of PPE")),
    FieldSpec("fcf", "cashflow", _cf("Free Cash Flow"), derivation=("sum", ("cfo", "capex"))),
    FieldSpec("change_in_working_capital", "cashflow", _cf("Change In Working Capital")),
    # Émission d'actions ordinaires encaissée dans l'exercice (positive). « Issuance Of Capital Stock »
    # englobe aussi les actions de préférence : simple voisin. Une ligne absente reste None, jamais 0 :
    # Yahoo omet la ligne aussi bien quand rien n'a été émis que quand l'information manque.
    FieldSpec("common_stock_issuance", "cashflow", _cf("Common Stock Issuance"),
              equivalents=_cf("Issuance Of Capital Stock")),
)

FIELD_KEYS = tuple(spec.key for spec in FIELD_SCHEMA)


@dataclass
class NormalizedStatements:
    """États financiers sous le schéma interne : values[clé][exercice] vaut un float ou None, et
    provenance[clé][exercice] décrit d'où vient la valeur (ou pourquoi elle manque), pour que
    l'interface puisse toujours répondre à « d'où sort ce chiffre ? ». Exercices du plus récent au
    plus ancien, comme yfinance."""
    years: list[pd.Timestamp]
    values: dict[str, dict[pd.Timestamp, float | None]]
    provenance: dict[str, dict[pd.Timestamp, dict]]

    def get(self, key: str, year: pd.Timestamp) -> float | None:
        return self.values.get(key, {}).get(year)

    def available_count(self, year: pd.Timestamp) -> int:
        return sum(1 for key in FIELD_KEYS if self.get(key, year) is not None)


def _lookup(frames: dict[str, pd.DataFrame], statement: str, label: str, year: pd.Timestamp) -> float | None:
    """Valeur publiée d'un libellé pour un exercice, None si le libellé, l'exercice ou la valeur
    manque (NaN compris : yfinance remplit de NaN les postes non publiés une année donnée)."""
    frame = frames.get(statement)
    if frame is None or frame.empty or label not in frame.index or year not in frame.columns:
        return None
    raw = frame.at[label, year]
    if pd.isna(raw):
        return None
    return float(raw)


def _clean_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    """Colonnes converties en Timestamp normalisé (date de clôture sans heure) : les trois états
    yfinance ne datent pas toujours leurs colonnes de la même façon, il faut une clé commune pour
    aligner les exercices."""
    if frame is None or frame.empty:
        return pd.DataFrame()
    frame = frame.copy()
    frame.columns = [pd.Timestamp(c).normalize() for c in frame.columns]
    return frame.loc[:, ~frame.columns.duplicated()]


def normalize_statements(income: pd.DataFrame | None, balance: pd.DataFrame | None,
                         cashflow: pd.DataFrame | None) -> NormalizedStatements:
    """Met les trois états annuels yfinance (index = libellés, colonnes = dates de clôture) sous le
    schéma FIELD_SCHEMA.

    Un exercice n'est retenu que si au moins un poste du schéma y a une valeur : yfinance ajoute
    souvent une colonne d'exercice quasi vide (5e année du tableau de flux, par exemple), qui
    afficherait sinon une colonne entière de « n.d. » sans rien apporter."""
    frames = {"income": _clean_frame(income), "balance": _clean_frame(balance), "cashflow": _clean_frame(cashflow)}
    candidate_years = sorted({year for frame in frames.values() for year in frame.columns}, reverse=True)

    values: dict[str, dict[pd.Timestamp, float | None]] = {key: {} for key in FIELD_KEYS}
    provenance: dict[str, dict[pd.Timestamp, dict]] = {key: {} for key in FIELD_KEYS}
    for year in candidate_years:
        for spec in FIELD_SCHEMA:
            value, origin = _resolve_field(spec, frames, year, values)
            values[spec.key][year] = value
            provenance[spec.key][year] = origin

    years = [year for year in candidate_years if any(values[key][year] is not None for key in FIELD_KEYS)]
    for key in FIELD_KEYS:
        values[key] = {year: values[key][year] for year in years}
        provenance[key] = {year: provenance[key][year] for year in years}
    return NormalizedStatements(years=years, values=values, provenance=provenance)


def _resolve_field(spec: FieldSpec, frames: dict[str, pd.DataFrame], year: pd.Timestamp,
                   resolved: dict[str, dict[pd.Timestamp, float | None]]) -> tuple[float | None, dict]:
    for statement, label in spec.published:
        value = _lookup(frames, statement, label, year)
        if value is not None:
            return value, {"source": "published", "statement": statement, "label": label}

    missing_operands: tuple[str, ...] = ()
    if spec.derivation is not None:
        operator, operands = spec.derivation
        operand_values = [resolved[key].get(year) for key in operands]
        missing_operands = tuple(key for key, v in zip(operands, operand_values) if v is None)
        if not missing_operands:
            numbers = [v for v in operand_values if v is not None]
            total = sum(numbers) if operator == "sum" else numbers[0] - sum(numbers[1:])
            return total, {"source": "derived", "operator": operator, "operands": operands}

    for statement, label in spec.equivalents:
        value = _lookup(frames, statement, label, year)
        if value is not None:
            return value, {"source": "equivalent", "statement": statement, "label": label}

    if spec.derivation is not None:
        operator, operands = spec.derivation
        return None, {
            "source": "missing", "reason": "derivation_inputs_missing",
            "operator": operator, "operands": operands, "missing_operands": missing_operands,
        }
    return None, {"source": "missing", "reason": "not_in_yfinance"}


# ============================================================
# CLASSEMENT SECTORIEL
# ============================================================

# earnings_quality : conversion du résultat en cash et accruals. Pour une banque, le CFO est dominé
# par les flux de dépôts et de crédits (des dizaines de milliards d'une année sur l'autre) : CFO /
# résultat net n'y mesure rien de la qualité du résultat.
# piotroski : ses critères de liquidité (ratio de liquidité générale) et de marge brute n'ont pas de
# sens pour une banque ou un assureur, comme les deux autres scores.
# transaction_services : dette nette / EBITDA et VE / EBITDA n'ont pas de sens pour une banque, dont
# l'EBITDA reconstitué est gonflé par les charges d'intérêts (matière première de l'activité).
ANALYSES = ("beneish", "altman", "piotroski", "working_capital", "earnings_quality", "transaction_services")


def detect_sector_regime(sector: str | None, industry: str | None) -> dict:
    """Classe la société selon la nature de son bilan, à partir de l'industrie Yahoo Finance (le
    secteur "Financial Services" est trop large : il couvre aussi les gérants d'actifs ou les
    bourses, dont les comptes se lisent comme ceux d'une entreprise ordinaire).

    Banques et assureurs : le passif (dépôts, provisions techniques) est la matière première de
    l'activité, il n'y a ni stocks ni cycle clients/fournisseurs au sens industriel. Beneish,
    Altman, l'analyse du BFR et la qualité des résultats (conversion en cash, accruals) y
    produiraient des chiffres absurdes, d'où applicable=False pour toutes ces analyses. Renvoie {"regime": "bank" | "insurer" | "general", "caution": None |
    "third_party_funds" | "unknown_industry", "applicable": {analyse: bool}}."""
    industry = (industry or "").strip()
    if industry.startswith(BANK_INDUSTRY_PREFIXES):
        regime = "bank"
    elif industry.startswith(INSURER_INDUSTRY_PREFIXES):
        regime = "insurer"
    else:
        regime = "general"

    caution = None
    if regime == "general":
        if not industry:
            # Pas de quoi classer : on analyse quand même, mais l'utilisateur doit savoir que la
            # vérification « banque ou assureur ? » n'a pas pu être faite.
            caution = "unknown_industry"
        elif industry in CAUTION_INDUSTRIES:
            caution = "third_party_funds"

    applicable = {analysis: regime == "general" for analysis in ANALYSES}
    return {"regime": regime, "caution": caution, "applicable": applicable, "sector": sector, "industry": industry or None}


# ============================================================
# DEVISES : données de marché ramenées dans la devise des comptes
# ============================================================
# Les comptes restent dans leur devise de publication (financialCurrency) : seules les données de
# marché (cours, capitalisation) sont converties, pour ne jamais toucher aux chiffres publiés.

def split_currency_unit(code: str | None) -> tuple[str | None, float]:
    """Devise principale et diviseur d'un code de cotation : ("GBP", 100) pour "GBp" (pence),
    (code, 1) sinon. (None, 1) si le code est inconnu ou absent."""
    if not code:
        return None, 1.0
    if code in MINOR_CURRENCY_UNITS:
        major, divisor = MINOR_CURRENCY_UNITS[code]
        return major, float(divisor)
    return code, 1.0


def market_values_in_reporting_currency(price: float | None, market_cap: float | None,
                                        quote_currency: str | None, reporting_currency: str | None,
                                        fx_rate: float | None) -> dict:
    """Cours et capitalisation exprimés dans la devise des comptes.

    Le cours est coté dans quote_currency, éventuellement en sous-unité (GBp) ; la capitalisation
    Yahoo est déjà en devise principale (vérifié sur quatre valeurs de Londres : capitalisation /
    (cours x nombre d'actions) = 0,01 exactement). fx_rate convertit 1 unité de la devise
    principale de cotation en devise des comptes ; ignoré si les deux coïncident. Renvoie aussi le
    taux et le diviseur utilisés, pour afficher le calcul. Si la conversion est impossible (devise
    inconnue, taux de change indisponible), les montants valent None avec la raison, jamais une
    valeur non convertie présentée comme convertie."""
    major, divisor = split_currency_unit(quote_currency)
    result = {
        "price": None, "market_cap": None, "fx_rate": None, "divisor": divisor,
        "quote_major_currency": major, "reporting_currency": reporting_currency, "reason": None,
    }
    if major is None or not reporting_currency:
        result["reason"] = "currency_unknown"
        return result
    if major == reporting_currency:
        rate = 1.0
    elif fx_rate is None or fx_rate <= 0:
        result["reason"] = "fx_unavailable"
        return result
    else:
        rate = float(fx_rate)
    result["fx_rate"] = rate
    result["price"] = price / divisor * rate if price is not None else None
    result["market_cap"] = market_cap * rate if market_cap is not None else None
    return result


def minor_unit_consistency(price: float | None, trailing_pe: float | None, trailing_eps: float | None,
                           divisor: float, tolerance: float = 0.10) -> dict:
    """Contrôle croisé du diviseur de sous-unité, repris de l'heuristique de stock_valuation
    (_price_scale_factor) : cours / (P/E x BPA). Yahoo exprime le BPA dans la devise principale
    de COTATION, pas dans celle des comptes (Shell : comptes en USD, BPA en livres, ratio de 100
    exactement) : ce ratio ne mesure donc que la sous-unité, jamais le change. Il doit retomber
    sur le diviseur déduit du code devise ; un écart signale une donnée de marché incohérente.
    consistent vaut None si le ratio n'est pas calculable (P/E ou BPA absent ou non positif)."""
    if not price or not trailing_pe or not trailing_eps or trailing_pe <= 0 or trailing_eps <= 0:
        return {"empirical_ratio": None, "expected_divisor": divisor, "consistent": None}
    empirical = price / (trailing_pe * trailing_eps)
    consistent = abs(empirical - divisor) / divisor <= tolerance
    return {"empirical_ratio": empirical, "expected_divisor": divisor, "consistent": consistent}


# ============================================================
# RATIOS : forme commune
# ============================================================
# Chaque ratio renvoie un dict, pas un simple nombre : la valeur, ses composantes (pour refaire le
# calcul à la main), la clé de formule, les mentions (repli sur un poste voisin...) et, si la
# valeur manque, la raison. L'interface n'a ainsi jamais à deviner pourquoi un ratio est « n.d. ».

DAYS_PER_YEAR = 365

# Mentions et raisons qu'un ratio peut porter (listées ici pour que l'interface puisse toutes les
# traduire : voir test_i18n.py).
RATIO_FLAGS = ("group_share_fallback", "broad_receivables", "broad_payables")
RATIO_REASONS = ("missing_inputs", "non_positive_denominator", "no_prior_year")
RATIO_DENOMINATORS = ("net_income", "revenue", "cost_of_revenue", "average_total_assets")
BRIDGE_STEPS = ("net_income", "d_and_a", "change_in_working_capital", "other_items")
SCORE_FLAGS = ("aqi_neutral_by_definition", "depreciation_includes_amortization", "group_share_equity_fallback",
               "share_count_fallback")


def _ratio(formula: str, numerator: float | None, denominator: float | None, components: dict,
           denominator_key: str, scale: float = 1.0, flags: tuple[str, ...] = ()) -> dict:
    """Ratio numerator / denominator x scale. n.d. si une composante manque, ou si le dénominateur
    est nul ou négatif : un ratio rapporté à une perte ou à un CA négatif inverse son sens, et le
    lire comme les autres serait trompeur."""
    result = {
        "value": None, "formula": formula, "components": components, "reason": None,
        "missing": (), "denominator": denominator_key, "flags": flags,
    }
    missing = tuple(key for key, value in components.items() if value is None)
    if missing or numerator is None:
        result["reason"], result["missing"] = "missing_inputs", missing
        return result
    if denominator is None or denominator <= 0:
        result["reason"] = "non_positive_denominator"
        return result
    result["value"] = numerator / denominator * scale
    return result


def _net_income_for_cash_comparison(ns: NormalizedStatements, year: pd.Timestamp) -> tuple[float | None, tuple[str, ...]]:
    """Résultat net à comparer au CFO : y compris minoritaires, même périmètre que le CFO consolidé
    (qui couvre 100 % des filiales). Repli sur la part du groupe, signalé, si Yahoo ne fournit pas
    la version y compris minoritaires."""
    value = ns.get("net_income_incl_minorities", year)
    if value is not None:
        return value, ()
    fallback = ns.get("net_income", year)
    return fallback, ("group_share_fallback",) if fallback is not None else ()


# ============================================================
# QUALITÉ DES RÉSULTATS : conversion en cash et accruals
# ============================================================

def cash_conversion(ns: NormalizedStatements) -> dict[pd.Timestamp, dict]:
    """Par exercice : CFO / résultat net et FCF / résultat net. Un résultat durablement supérieur au
    cash qu'il génère est le premier signal d'un résultat de faible qualité (produits constatés
    avant d'être encaissés, charges différées...)."""
    out = {}
    for year in ns.years:
        net_income, flags = _net_income_for_cash_comparison(ns, year)
        cfo, fcf = ns.get("cfo", year), ns.get("fcf", year)
        out[year] = {
            "cfo_to_net_income": _ratio(
                "cfo_to_net_income", cfo, net_income, {"cfo": cfo, "net_income": net_income}, "net_income", flags=flags,
            ),
            "fcf_to_net_income": _ratio(
                "fcf_to_net_income", fcf, net_income, {"fcf": fcf, "net_income": net_income}, "net_income", flags=flags,
            ),
        }
    return out


def sloan_accruals(ns: NormalizedStatements) -> dict[pd.Timestamp, dict]:
    """Ratio d'accruals de Sloan (1996) : (résultat net - CFO) / actif total moyen de l'exercice.

    La part du résultat qui ne s'est pas (encore) traduite en cash, rapportée à la taille du bilan
    pour être comparable d'une société à l'autre. Actif moyen = (ouverture + clôture) / 2, d'où un
    exercice le plus ancien toujours n.d. : son bilan d'ouverture n'est pas fourni par yfinance."""
    out = {}
    chronological = sorted(ns.years)
    for i, year in enumerate(chronological):
        net_income, flags = _net_income_for_cash_comparison(ns, year)
        cfo, assets = ns.get("cfo", year), ns.get("total_assets", year)
        if i == 0:
            out[year] = {
                "value": None, "formula": "sloan_accruals", "reason": "no_prior_year", "missing": (),
                "components": {"net_income": net_income, "cfo": cfo, "total_assets": assets, "total_assets_prior": None},
                "denominator": "average_total_assets", "flags": flags,
            }
            continue
        assets_prior = ns.get("total_assets", chronological[i - 1])
        average_assets = (assets + assets_prior) / 2 if assets is not None and assets_prior is not None else None
        numerator = net_income - cfo if net_income is not None and cfo is not None else None
        out[year] = _ratio(
            "sloan_accruals", numerator, average_assets,
            {"net_income": net_income, "cfo": cfo, "total_assets": assets, "total_assets_prior": assets_prior},
            "average_total_assets", flags=flags,
        )
    return out


def net_income_to_cfo_bridge(ns: NormalizedStatements, year: pd.Timestamp) -> dict:
    """Pont du résultat net au CFO d'un exercice : résultat net, + dotations aux amortissements (charge
    sans sortie de cash), + variation du BFR (signe du tableau de flux : négative quand le BFR
    augmente), puis « autres éléments » en résidu.

    Le résidu fait retomber le pont exactement sur le CFO publié. Il regroupe les postes que yfinance
    ne détaille pas de façon homogène (impôts différés, rémunérations en actions, plus-values de
    cession...). Un élément identifié mais absent une année donnée n'est pas pris pour 0 : il est
    signalé comme inclus dans le résidu (missing_items). Renvoie available=False si le résultat net ou
    le CFO manque : sans ses deux extrémités, le pont n'a pas de sens."""
    net_income, flags = _net_income_for_cash_comparison(ns, year)
    cfo = ns.get("cfo", year)
    if net_income is None or cfo is None:
        missing = tuple(key for key, value in (("net_income", net_income), ("cfo", cfo)) if value is None)
        return {"available": False, "missing": missing, "steps": [], "cfo": cfo, "flags": flags, "missing_items": ()}
    steps = [{"key": "net_income", "value": net_income}]
    missing_items = []
    for key in ("d_and_a", "change_in_working_capital"):
        value = ns.get(key, year)
        if value is None:
            missing_items.append(key)
        else:
            steps.append({"key": key, "value": value})
    identified = sum(step["value"] for step in steps)
    steps.append({"key": "other_items", "value": cfo - identified})
    return {"available": True, "missing": (), "steps": steps, "cfo": cfo, "flags": flags,
            "missing_items": tuple(missing_items)}


# ============================================================
# BFR EN JOURS : DSO, DIO, DPO et cycle de conversion de trésorerie
# ============================================================

def working_capital_days(ns: NormalizedStatements) -> dict[pd.Timestamp, dict]:
    """Par exercice, sur les soldes de CLÔTURE (pratique courante en Transaction Services, et
    disponible sur les 4 exercices plutôt que 3 avec des soldes moyens) :

    - DSO = créances clients / chiffre d'affaires x 365 ;
    - DIO = stocks / coût des ventes x 365 ;
    - DPO = dettes fournisseurs / coût des ventes x 365 ;
    - cycle de conversion de trésorerie = DSO + DIO - DPO.

    Sans coût des ventes (fréquent chez les sociétés européennes qui présentent leurs charges par
    nature), DIO et DPO sont n.d. plutôt que calculés sur le CA : ils changeraient de sens et ne
    seraient plus comparables. Les postes « Receivables »/« Payables » de Yahoo, plus larges que les
    seuls clients/fournisseurs, restent utilisés en repli mais signalés (DSO ou DPO surestimé)."""
    out = {}
    for year in ns.years:
        receivables, revenue = ns.get("receivables", year), ns.get("revenue", year)
        inventory, cogs, payables = ns.get("inventory", year), ns.get("cost_of_revenue", year), ns.get("payables", year)
        receivables_flags = ("broad_receivables",) if ns.provenance["receivables"][year]["source"] == "equivalent" else ()
        payables_flags = ("broad_payables",) if ns.provenance["payables"][year]["source"] == "equivalent" else ()
        dso = _ratio("dso", receivables, revenue, {"receivables": receivables, "revenue": revenue}, "revenue",
                     scale=DAYS_PER_YEAR, flags=receivables_flags)
        dio = _ratio("dio", inventory, cogs, {"inventory": inventory, "cost_of_revenue": cogs}, "cost_of_revenue",
                     scale=DAYS_PER_YEAR)
        dpo = _ratio("dpo", payables, cogs, {"payables": payables, "cost_of_revenue": cogs}, "cost_of_revenue",
                     scale=DAYS_PER_YEAR, flags=payables_flags)
        parts = {"dso": dso["value"], "dio": dio["value"], "dpo": dpo["value"]}
        missing = tuple(key for key, value in parts.items() if value is None)
        ccc = {
            "value": None if missing else parts["dso"] + parts["dio"] - parts["dpo"],
            "formula": "ccc", "components": parts, "reason": "missing_inputs" if missing else None,
            "missing": missing, "denominator": None, "flags": receivables_flags + payables_flags,
        }
        out[year] = {"dso": dso, "dio": dio, "dpo": dpo, "ccc": ccc}
    return out


def metric_trend(series_by_year: dict[pd.Timestamp, dict], metric: str) -> dict | None:
    """Évolution d'un indicateur entre le plus ancien et le plus récent exercice où il est
    disponible : {"first_year", "last_year", "first", "last", "delta"}. None s'il est disponible sur
    moins de deux exercices (pas d'évolution à mesurer)."""
    points = [(year, values[metric]["value"]) for year, values in sorted(series_by_year.items())
              if values[metric]["value"] is not None]
    if len(points) < 2:
        return None
    (first_year, first), (last_year, last) = points[0], points[-1]
    return {"first_year": first_year, "last_year": last_year, "first": first, "last": last, "delta": last - first}


# ============================================================
# SCORES D'ALERTE : Beneish, Altman, Piotroski
# ============================================================
# Ces scores ont été calibrés sur des sociétés américaines, à d'autres époques (1946-1965 pour
# Altman, 1982-1992 pour Beneish, 1976-1996 pour Piotroski) : ce sont des signaux à creuser, pas des
# verdicts. Beneish et Piotroski comparent deux exercices consécutifs (t contre t-1) ; chaque
# résultat indique le couple utilisé.

def consecutive_pairs(ns: NormalizedStatements) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Couples (exercice t, exercice t-1) disponibles, du plus récent au plus ancien."""
    chronological = sorted(ns.years)
    return [(chronological[i], chronological[i - 1]) for i in range(len(chronological) - 1, 0, -1)]


def _div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _flag_if_equivalent(ns: NormalizedStatements, key: str, years: tuple[pd.Timestamp, ...], flag: str) -> tuple[str, ...]:
    return (flag,) if any(ns.provenance[key][year]["source"] == "equivalent" for year in years) else ()


# ---------- Beneish M-score ----------

# Beneish (1999), « The Detection of Earnings Manipulation », Financial Analysts Journal 55(5), 24-36 ;
# tableau 3, probit non pondéré (version de travail de juin 1999, p. 24).
BENEISH_INTERCEPT = -4.84
BENEISH_COEFFICIENTS = {
    "dsri": 0.920, "gmi": 0.528, "aqi": 0.404, "sgi": 0.892, "depi": 0.115, "sgai": -0.172, "lvgi": -0.327,
    "tata": 4.679,
}
BENEISH_INDICES = tuple(BENEISH_COEFFICIENTS)
BENEISH_THRESHOLD = -1.78
# Beneish (1999), tableau 2 : moyennes de l'échantillon d'estimation (50 manipulateurs, 1 708
# non-manipulateurs du même secteur), affichées comme repères à côté des indices de la société.
BENEISH_REFERENCE_MEANS = {
    "manipulators": {"dsri": 1.465, "gmi": 1.193, "aqi": 1.254, "sgi": 1.607, "depi": 1.077, "sgai": 1.041,
                     "lvgi": 1.111, "tata": 0.031},
    "non_manipulators": {"dsri": 1.031, "gmi": 1.014, "aqi": 1.039, "sgi": 1.134, "depi": 1.001, "sgai": 1.054,
                         "lvgi": 1.037, "tata": 0.018},
}
# Valeur neutre d'un indice : 1, soit « aucune variation entre t-1 et t ». TATA est un niveau (accruals
# / actif), pas un indice de variation : il n'a pas de valeur neutre et n'est jamais neutralisé.
BENEISH_NEUTRALIZABLE = tuple(index for index in BENEISH_INDICES if index != "tata")


def beneish_m_score_from_indices(indices: dict[str, float]) -> float:
    """M = -4,84 + 0,920 DSRI + 0,528 GMI + 0,404 AQI + 0,892 SGI + 0,115 DEPI - 0,172 SGAI
    + 4,679 TATA - 0,327 LVGI. Les 8 indices sont requis : les coefficients ont été estimés
    conjointement, en retirer un fausserait les autres."""
    return BENEISH_INTERCEPT + sum(coefficient * indices[index] for index, coefficient in BENEISH_COEFFICIENTS.items())


def _beneish_index(current: float | None, prior: float | None, components: dict, formula: str,
                   flags: tuple[str, ...] = (), inverse: bool = False) -> dict:
    """Indice de variation entre t et t-1 : ratio_t / ratio_t-1 (ou l'inverse pour GMI et DEPI, où
    Beneish met l'exercice précédent au numérateur pour qu'un indice > 1 signale toujours une
    dégradation)."""
    result = {"value": None, "current": current, "prior": prior, "components": components, "formula": formula,
              "reason": None, "missing": tuple(k for k, v in components.items() if v is None), "flags": flags}
    if result["missing"]:
        result["reason"] = "missing_inputs"
        return result
    numerator, denominator = (prior, current) if inverse else (current, prior)
    if numerator is None or denominator is None or denominator <= 0:
        result["reason"] = "non_positive_base"
        return result
    result["value"] = numerator / denominator
    return result


def beneish_m_score(ns: NormalizedStatements, year: pd.Timestamp, prior_year: pd.Timestamp) -> dict:
    """Les 8 indices de Beneish pour le couple (year, prior_year), selon les définitions du tableau 2 de
    Beneish (1999), puis le M-score.

    Écarts assumés avec l'article, faute de données COMPUSTAT : TATA est calculé par les flux de
    trésorerie, (résultat net - CFO) / actif total, plutôt que par les variations de postes du bilan
    (méthode moins sujette aux erreurs de mesure, Hribar et Collins 2002), avec le résultat net y
    compris minoritaires comme partout ailleurs ; la dette à long terme du LVGI inclut les dettes
    locatives non courantes (IFRS 16).

    M-score officiel n.d. dès qu'un indice manque. Variante indicative : les indices manquants (hors
    TATA) sont remplacés par 1, leur valeur neutre. C'est d'ailleurs ce que faisait Beneish lui-même
    pour DEPI et SGAI quand COMPUSTAT ne fournissait pas la donnée (p. 12 de l'article). Elle est
    toujours présentée comme telle, avec la liste des indices neutralisés."""
    t, p = year, prior_year
    g = ns.get
    revenue_t, revenue_p = g("revenue", t), g("revenue", p)
    assets_t, assets_p = g("total_assets", t), g("total_assets", p)
    net_income, ni_flags = _net_income_for_cash_comparison(ns, t)

    indices = {}
    indices["dsri"] = _beneish_index(
        _div(g("receivables", t), revenue_t), _div(g("receivables", p), revenue_p),
        {"receivables_t": g("receivables", t), "revenue_t": revenue_t,
         "receivables_p": g("receivables", p), "revenue_p": revenue_p},
        "dsri", _flag_if_equivalent(ns, "receivables", (t, p), "broad_receivables"),
    )
    indices["gmi"] = _beneish_index(
        _div(g("gross_profit", t), revenue_t), _div(g("gross_profit", p), revenue_p),
        {"gross_profit_t": g("gross_profit", t), "revenue_t": revenue_t,
         "gross_profit_p": g("gross_profit", p), "revenue_p": revenue_p},
        "gmi", inverse=True,
    )

    def asset_quality(y):
        ca, ppe, ta = g("current_assets", y), g("ppe_net", y), g("total_assets", y)
        return None if None in (ca, ppe, ta) or ta == 0 else 1 - (ca + ppe) / ta

    aqi_components = {"current_assets_t": g("current_assets", t), "ppe_net_t": g("ppe_net", t), "total_assets_t": assets_t,
                      "current_assets_p": g("current_assets", p), "ppe_net_p": g("ppe_net", p), "total_assets_p": assets_p}
    aq_t, aq_p = asset_quality(t), asset_quality(p)
    if aq_p == 0 and aq_t is not None:
        # Beneish (1999, p. 12) : actif de t-1 composé uniquement d'actif courant et
        # d'immobilisations corporelles, indice non défini, fixé à sa valeur neutre 1.
        indices["aqi"] = {"value": 1.0, "current": aq_t, "prior": aq_p, "components": aqi_components, "formula": "aqi",
                          "reason": None, "missing": (), "flags": ("aqi_neutral_by_definition",)}
    else:
        indices["aqi"] = _beneish_index(aq_t, aq_p, aqi_components, "aqi")
    indices["sgi"] = _beneish_index(revenue_t, revenue_p, {"revenue_t": revenue_t, "revenue_p": revenue_p}, "sgi")

    def depreciation_rate(y):
        dep, ppe = g("depreciation", y), g("ppe_net", y)
        return _div(dep, dep + ppe) if dep is not None and ppe is not None else None

    indices["depi"] = _beneish_index(
        depreciation_rate(t), depreciation_rate(p),
        {"depreciation_t": g("depreciation", t), "ppe_net_t": g("ppe_net", t),
         "depreciation_p": g("depreciation", p), "ppe_net_p": g("ppe_net", p)},
        "depi", _flag_if_equivalent(ns, "depreciation", (t, p), "depreciation_includes_amortization"), inverse=True,
    )
    indices["sgai"] = _beneish_index(
        _div(g("sga", t), revenue_t), _div(g("sga", p), revenue_p),
        {"sga_t": g("sga", t), "revenue_t": revenue_t, "sga_p": g("sga", p), "revenue_p": revenue_p}, "sgai",
    )

    def leverage(y):
        cl, ltd, ta = g("current_liabilities", y), g("long_term_debt_incl_leases", y), g("total_assets", y)
        return _div(cl + ltd, ta) if cl is not None and ltd is not None else None

    indices["lvgi"] = _beneish_index(
        leverage(t), leverage(p),
        {"current_liabilities_t": g("current_liabilities", t), "long_term_debt_incl_leases_t": g("long_term_debt_incl_leases", t),
         "total_assets_t": assets_t, "current_liabilities_p": g("current_liabilities", p),
         "long_term_debt_incl_leases_p": g("long_term_debt_incl_leases", p), "total_assets_p": assets_p},
        "lvgi",
    )
    cfo = g("cfo", t)
    tata_components = {"net_income_t": net_income, "cfo_t": cfo, "total_assets_t": assets_t}
    tata_missing = tuple(k for k, v in tata_components.items() if v is None)
    indices["tata"] = {
        "value": None if tata_missing or not assets_t else (net_income - cfo) / assets_t,
        "current": None, "prior": None, "components": tata_components, "formula": "tata",
        "reason": "missing_inputs" if tata_missing else (None if assets_t else "non_positive_base"),
        "missing": tata_missing, "flags": ni_flags,
    }

    values = {index: indices[index]["value"] for index in BENEISH_INDICES}
    missing_indices = tuple(index for index, value in values.items() if value is None)
    official = None
    if not missing_indices:
        official = beneish_m_score_from_indices(values)
    indicative = None
    if missing_indices and values["tata"] is not None:
        neutralized = {index: (1.0 if value is None else value) for index, value in values.items()}
        indicative = {"value": beneish_m_score_from_indices(neutralized), "neutralized": missing_indices}
        indicative["verdict"] = beneish_verdict(indicative["value"])
    return {
        "pair": (t, p),
        "indices": indices,
        "contributions": {index: (BENEISH_COEFFICIENTS[index] * value if value is not None else None)
                          for index, value in values.items()},
        "m_score": {"value": official, "missing": missing_indices,
                    "verdict": beneish_verdict(official) if official is not None else None},
        "m_score_indicative": indicative,
    }


def beneish_verdict(m_score: float) -> str:
    """Au-dessus de -1,78 : profil plus proche des manipulateurs de l'échantillon de Beneish."""
    return "manipulation_risk" if m_score > BENEISH_THRESHOLD else "no_signal"


# ---------- Altman Z-score ----------

# Sources vérifiées dans le texte d'Altman (2000), « Predicting Financial Distress of Companies:
# Revisiting the Z-Score and ZETA Models », NYU Stern (pages du PDF de travail) :
# - Z d'origine (Altman 1968, Journal of Finance 23(4), 589-609) : Z = 0,012 X1 + 0,014 X2 + 0,033 X3
#   + 0,006 X4 + 0,999 X5, X1 à X4 en pourcentages (p. 9-13) ; la forme 1,2 / 1,4 / 3,3 / 0,6 sur des
#   ratios décimaux donne des scores « identiques » (p. 13). On garde 0,999 pour X5, que la forme
#   usuelle arrondit à 1,0. Borne basse de la zone grise à 1,81 (p. 18).
# - Z'' (fonds propres comptables en X4, sans X5) : Z'' = 6,56 X1 + 3,26 X2 + 6,72 X3 + 1,05 X4 (p. 26-27),
#   sans la constante de +3,25 réservée au score des marchés émergents.
# Non vérifiés à la source : la borne haute 2,99 du Z d'origine (Altman 1968, non consulté ; Altman
# 2000 n'emploie que 1,81 et le seuil optimal 2,675) et les zones 1,10 / 2,60 de Z'', absentes
# d'Altman (2000) et d'Altman (2018, International Journal of Financial Studies 6(3), 70) et
# reprises par les sources secondaires d'après Altman et Hotchkiss (2006), ouvrage non consulté.
ALTMAN_MODELS = {
    "original": {"coefficients": {"x1": 1.2, "x2": 1.4, "x3": 3.3, "x4": 0.6, "x5": 0.999}, "zones": (1.81, 2.99)},
    "z_double_prime": {"coefficients": {"x1": 6.56, "x2": 3.26, "x3": 6.72, "x4": 1.05}, "zones": (1.10, 2.60)},
}
# Le Z d'origine a été calibré sur des industriels cotés : réservé par défaut aux secteurs Yahoo les
# plus proches de ce profil, Z'' (la version conseillée par Altman hors industrie) pour les autres.
ALTMAN_ORIGINAL_SECTORS = ("Industrials", "Basic Materials")


def altman_default_model(sector: str | None) -> str:
    return "original" if sector in ALTMAN_ORIGINAL_SECTORS else "z_double_prime"


def altman_zone(z_score: float, model: str) -> str:
    """Zone de détresse, grise ou sûre ; les seuils eux-mêmes sont rangés en zone grise."""
    distress, safe = ALTMAN_MODELS[model]["zones"]
    if z_score < distress:
        return "distress"
    return "safe" if z_score > safe else "grey"


def altman_z_from_ratios(ratios: dict[str, float], model: str) -> float:
    return sum(coefficient * ratios[x] for x, coefficient in ALTMAN_MODELS[model]["coefficients"].items())


def price_on_or_before(closes: pd.Series, date: pd.Timestamp, max_gap_days: int = 10) -> float | None:
    """Dernier cours de clôture connu à `date` ou avant (une clôture d'exercice tombe souvent un jour
    sans cotation, 31 décembre compris). None si le dernier cours connu date de plus de max_gap_days :
    au-delà, ce ne serait plus « le cours à la clôture de l'exercice »."""
    if closes is None or closes.empty:
        return None
    eligible = closes[closes.index <= date]
    if eligible.empty or (date - eligible.index[-1]).days > max_gap_days:
        return None
    return float(eligible.iloc[-1])


def market_value_of_equity(close_price: float | None, shares: float | None, divisor: float,
                           fx_rate: float | None) -> float | None:
    """Capitalisation à une date, dans la devise des comptes : cours de clôture (éventuellement en
    sous-unité, ex. pence) / diviseur x nombre d'actions x taux de change de cette date. None si une
    donnée manque, jamais une capitalisation non convertie."""
    if close_price is None or shares is None or fx_rate is None or divisor <= 0:
        return None
    return close_price / divisor * shares * fx_rate


def altman_z_score(ns: NormalizedStatements, year: pd.Timestamp, model: str,
                   market_value: float | None = None) -> dict:
    """Z-score d'Altman d'un exercice (score de niveau, un seul exercice : pas de couple).

    X1 = fonds de roulement / actif total, X2 = réserves / actif total, X3 = EBIT / actif total,
    X4 = capitalisation boursière (Z d'origine) ou capitaux propres comptables (Z'') / passif total,
    X5 = chiffre d'affaires / actif total (Z d'origine seulement). Les capitaux propres comptables
    incluent les minoritaires, cohérents avec le passif total (actif - capitaux propres consolidés) ;
    repli signalé sur la part du groupe. market_value : capitalisation à la date de clôture, dans la
    devise des comptes (voir market_value_of_equity). Pas de valeur neutre pour un ratio de niveau :
    Z est n.d. dès qu'un ratio manque."""
    g = ns.get
    assets = g("total_assets", year)
    liabilities = g("total_liabilities", year)
    flags: tuple[str, ...] = ()
    if model == "original":
        x4_numerator, x4_key = market_value, "market_value_of_equity"
    else:
        x4_numerator, x4_key = g("total_equity_incl_minorities", year), "total_equity_incl_minorities"
        if x4_numerator is None and g("equity", year) is not None:
            x4_numerator, x4_key, flags = g("equity", year), "equity", ("group_share_equity_fallback",)

    definitions = {
        "x1": ("working_capital", g("working_capital", year), "total_assets", assets),
        "x2": ("retained_earnings", g("retained_earnings", year), "total_assets", assets),
        "x3": ("ebit", g("ebit", year), "total_assets", assets),
        "x4": (x4_key, x4_numerator, "total_liabilities", liabilities),
    }
    if model == "original":
        definitions["x5"] = ("revenue", g("revenue", year), "total_assets", assets)

    components, ratios, missing = {}, {}, []
    for x, (num_key, num, den_key, den) in definitions.items():
        ratio = _div(num, den) if den is not None and den > 0 else None
        components[x] = {"numerator_key": num_key, "numerator": num, "denominator_key": den_key,
                         "denominator": den, "value": ratio}
        if ratio is None:
            missing.extend(k for k, v in ((num_key, num), (den_key, den)) if v is None or (k == den_key and v <= 0))
        ratios[x] = ratio
    missing_keys = tuple(dict.fromkeys(missing))
    value = None if any(r is None for r in ratios.values()) else altman_z_from_ratios(ratios, model)
    coefficients = ALTMAN_MODELS[model]["coefficients"]
    return {
        "model": model, "year": year, "value": value, "zone": altman_zone(value, model) if value is not None else None,
        "components": components,
        "contributions": {x: (coefficients[x] * r if r is not None else None) for x, r in ratios.items()},
        "missing": missing_keys, "flags": flags,
    }


# ---------- Piotroski F-score ----------

# Piotroski (2000), « Value Investing: The Use of Historical Financial Statement Information to
# Separate Winners from Losers », Journal of Accounting Research 38, 1-41.
PIOTROSKI_CRITERIA = (
    "roa_positive", "cfo_positive", "roa_improved", "cfo_exceeds_net_income",
    "leverage_decreased", "current_ratio_improved", "no_equity_issuance",
    "gross_margin_improved", "asset_turnover_improved",
)


def piotroski_f_score(ns: NormalizedStatements, year: pd.Timestamp, asset_base: str = "beginning") -> dict:
    """F-score de Piotroski (9 critères binaires) pour l'exercice `year`, comparé à l'exercice précédent.

    asset_base="beginning" (définition de Piotroski, utilisée par l'interface) : ROA, CFO et rotation
    de l'actif rapportés à l'actif d'OUVERTURE, levier rapporté à l'actif moyen ; il faut donc trois
    bilans (t, t-1, t-2) pour les critères de variation. asset_base="end" : variante courante des
    praticiens, tout rapporté à l'actif de clôture (deux bilans suffisent).

    Dette à long terme hors dettes locatives (poste COMPUSTAT n° 9 de l'article). Émission d'actions
    (EQ_OFFER de l'article : « did not issue common equity ») jugée sur l'émission brute du tableau de
    flux : les augmentations de capital réservées aux salariés comptent, les rachats ne compensent pas,
    et une division ou une attribution gratuite, qui n'apporte aucun cash, n'y figure pas. Repli signalé
    (share_count_fallback) sur le nombre d'actions du bilan quand la ligne manque. Un critère non
    calculable vaut None avec sa raison, et le score est la somme des seuls critères calculables
    (n_available l'indique) : à ne pas comparer tel quel aux seuils usuels sur 9."""
    chronological = sorted(ns.years)
    index = chronological.index(year)
    prior = chronological[index - 1] if index >= 1 else None
    prior2 = chronological[index - 2] if index >= 2 else None
    g = ns.get

    def scaling_assets(y, y_before):
        if asset_base == "end":
            return g("total_assets", y)
        return g("total_assets", y_before) if y_before is not None else None

    def roa(y, y_before):
        net_income, _flags = _net_income_for_cash_comparison(ns, y)
        return _div(net_income, scaling_assets(y, y_before))

    def leverage(y, y_before):
        ltd = g("long_term_debt", y)
        if asset_base == "end":
            return _div(ltd, g("total_assets", y))
        if y_before is None or g("total_assets", y) is None or g("total_assets", y_before) is None:
            return None
        return _div(ltd, (g("total_assets", y) + g("total_assets", y_before)) / 2)

    def turnover(y, y_before):
        return _div(g("revenue", y), scaling_assets(y, y_before))

    def margin(y):
        return _div(g("gross_profit", y), g("revenue", y))

    def current_ratio(y):
        return _div(g("current_assets", y), g("current_liabilities", y))

    net_income, ni_flags = _net_income_for_cash_comparison(ns, year)
    cfo = g("cfo", year)
    prior_scale = prior2 if asset_base == "beginning" else prior
    shares_t = g("shares_outstanding", year)
    shares_p = g("shares_outstanding", prior) if prior is not None else None

    def binary(current, threshold, details, strictly_greater=True, flags=()):
        missing = tuple(key for key, value in details.items() if value is None)
        if current is None or threshold is None:
            return {"value": None, "details": details, "reason": "missing_inputs", "missing": missing, "flags": flags}
        passed = current > threshold if strictly_greater else current >= threshold
        return {"value": 1 if passed else 0, "details": details, "reason": None, "missing": (), "flags": flags}

    def no_equity_issuance():
        issuance = g("common_stock_issuance", year)
        if issuance is not None:
            # 0 émis (publié tel quel par Yahoo) >= montant émis : critère rempli.
            return binary(0.0, issuance, {"equity_issuance_t": issuance}, strictly_greater=False)
        # Yahoo retraite rétroactivement le nombre d'actions des divisions et attributions gratuites
        # (vérifié sur NVDA et Air Liquide) : la comparaison reste homogène d'un exercice à l'autre.
        return binary(shares_p, shares_t, {"shares_t": shares_t, "shares_p": shares_p}, strictly_greater=False,
                      flags=("share_count_fallback",))

    roa_t = roa(year, prior)
    roa_p = roa(prior, prior_scale) if prior is not None else None
    lev_t = leverage(year, prior)
    lev_p = leverage(prior, prior_scale) if prior is not None else None
    cr_t, cr_p = current_ratio(year), current_ratio(prior) if prior is not None else None
    gm_t, gm_p = margin(year), margin(prior) if prior is not None else None
    turn_t = turnover(year, prior)
    turn_p = turnover(prior, prior_scale) if prior is not None else None

    criteria = {
        "roa_positive": binary(roa_t, 0.0, {"roa_t": roa_t}),
        "cfo_positive": binary(cfo, 0.0, {"cfo_t": cfo}),
        "roa_improved": binary(roa_t, roa_p, {"roa_t": roa_t, "roa_p": roa_p}),
        # CFO / actif > ROA revient à CFO > résultat net (même dénominateur).
        "cfo_exceeds_net_income": binary(cfo, net_income, {"cfo_t": cfo, "net_income_t": net_income}),
        # Levier en baisse : le critère est rempli si le levier de t est STRICTEMENT inférieur.
        "leverage_decreased": binary(lev_p, lev_t, {"leverage_t": lev_t, "leverage_p": lev_p}),
        "current_ratio_improved": binary(cr_t, cr_p, {"current_ratio_t": cr_t, "current_ratio_p": cr_p}),
        "no_equity_issuance": no_equity_issuance(),
        "gross_margin_improved": binary(gm_t, gm_p, {"gross_margin_t": gm_t, "gross_margin_p": gm_p}),
        "asset_turnover_improved": binary(turn_t, turn_p, {"turnover_t": turn_t, "turnover_p": turn_p}),
    }
    available = [c["value"] for c in criteria.values() if c["value"] is not None]
    return {
        "year": year, "prior_year": prior, "asset_base": asset_base, "criteria": criteria,
        "score": sum(available) if available else None, "n_available": len(available),
        "n_criteria": len(PIOTROSKI_CRITERIA), "flags": ni_flags,
    }


# ============================================================
# VISION TRANSACTION SERVICES : dette nette, EBITDA ajusté, multiples
# ============================================================
# Chaque ligne du pont porte sa source : "data" (donnée Yahoo), "assumption" (hypothèse : taux
# d'impôt, élément saisi par l'utilisateur), "subtotal" (calculé) ou "memo" (pour information, non
# compté). Une donnée absente n'est jamais prise pour 0 : sa ligne est n.d. et signalée comme exclue.

# Taux d'impôt par défaut pour l'effet fiscal sur les engagements de retraite : IS français (25 %).
DEFAULT_PENSION_TAX_RATE = 0.25
# Les montants saisis dans l'interface sont en millions de la devise des comptes.
USER_AMOUNT_UNIT = 1e6
# Lignes possibles du pont, sources et mentions (listées pour que l'interface puisse toutes les
# traduire : voir test_i18n.py).
NET_DEBT_LINE_KEYS = (
    "current_debt", "long_term_debt", "total_debt", "lease_liabilities_deducted", "gross_financial_debt", "cash",
    "net_financial_debt", "short_term_investments_memo", "lease_liabilities", "pension_liabilities",
    "pension_tax_effect", "net_debt_data", "user_item", "adjusted_net_debt",
)
NET_DEBT_SOURCES = ("data", "assumption", "subtotal", "memo")
TRANSACTION_FLAGS = ("gross_debt_from_total_debt", "minority_interest_missing")


def parse_user_items(rows: list[dict] | None, unit: float = USER_AMOUNT_UNIT) -> tuple[list[dict], list[int]]:
    """Lignes saisies par l'utilisateur ({"label", "amount"} en millions) -> (éléments valides en unités,
    numéros de lignes invalides). Une ligne entièrement vide est ignorée (ligne ajoutée puis jamais
    remplie) ; une ligne avec un montant non numérique est signalée plutôt qu'ignorée en silence. Un
    libellé manquant est remplacé par le numéro de ligne, pour que l'élément reste identifiable."""
    items, invalid = [], []
    for i, row in enumerate(rows or [], start=1):
        label = str(row.get("label") or "").strip()
        raw = row.get("amount")
        if raw is None or str(raw).strip() == "":
            if label:
                invalid.append(i)
            continue
        try:
            amount = float(str(raw).replace(",", ".").replace(" ", ""))
        except ValueError:
            invalid.append(i)
            continue
        items.append({"label": label or f"#{i}", "amount": amount * unit})
    return items, invalid


def net_debt_bridge(ns: NormalizedStatements, year: pd.Timestamp, pension_tax_rate: float = DEFAULT_PENSION_TAX_RATE,
                    user_items: list[dict] | None = None) -> dict:
    """Pont de dette nette d'un exercice, de la dette financière brute à la dette nette ajustée.

    1. Dette financière brute = dette court terme + dette long terme, hors dettes locatives. Repli
       signalé : dette totale Yahoo - dettes locatives (Yahoo inclut les dettes locatives dans sa dette
       totale).
    2. - trésorerie et équivalents (définition stricte) = dette financière nette. Les placements court
       terme sont affichés pour mémoire, non déduits : yfinance ne permet pas de vérifier qu'ils sont
       immédiatement mobilisables ; l'utilisateur peut les retenir en hypothèse.
    3. + dettes locatives IFRS 16 (cohérent avec l'EBITDA publié, qui est post-IFRS 16) et + engagements
       de retraite nets d'impôt (cotisations futures déductibles) = dette nette (données).
    4. + éléments assimilables saisis par l'utilisateur (signe + pour une dette, - pour de la
       trésorerie) = dette nette ajustée.

    Renvoie aussi la dette nette hors IFRS 16, affichée à titre d'information : un multiple sur cette
    base exigerait un EBITDA après loyers, que yfinance ne fournit pas."""
    g = ns.get
    lines = []
    flags = []

    def line(key, value, source, **extra):
        lines.append({"key": key, "value": value, "source": source, **extra})

    current_debt, long_term_debt = g("current_debt", year), g("long_term_debt", year)
    if current_debt is not None and long_term_debt is not None:
        gross_debt = current_debt + long_term_debt
        line("current_debt", current_debt, "data")
        line("long_term_debt", long_term_debt, "data")
    else:
        total_debt, leases = g("total_debt", year), g("lease_liabilities", year)
        gross_debt = total_debt - leases if total_debt is not None and leases is not None else None
        if gross_debt is not None:
            flags.append("gross_debt_from_total_debt")
            line("total_debt", total_debt, "data")
            line("lease_liabilities_deducted", -leases, "data")
        else:
            line("current_debt", current_debt, "data")
            line("long_term_debt", long_term_debt, "data")
    line("gross_financial_debt", gross_debt, "subtotal")

    cash = g("cash", year)
    line("cash", -cash if cash is not None else None, "data")
    net_financial_debt = gross_debt - cash if gross_debt is not None and cash is not None else None
    line("net_financial_debt", net_financial_debt, "subtotal")
    short_term_investments = None
    cash_and_sti = g("cash_and_short_term_investments", year)
    if cash_and_sti is not None and cash is not None and cash_and_sti > cash:
        short_term_investments = cash_and_sti - cash
        line("short_term_investments_memo", -short_term_investments, "memo")

    leases = g("lease_liabilities", year)
    line("lease_liabilities", leases, "data", excluded=leases is None)
    pensions = g("pension_liabilities", year)
    line("pension_liabilities", pensions, "data", excluded=pensions is None)
    pension_tax = -pensions * pension_tax_rate if pensions is not None else None
    if pensions is not None:
        line("pension_tax_effect", pension_tax, "assumption", rate=pension_tax_rate)

    net_debt_data = None
    if net_financial_debt is not None:
        net_debt_data = net_financial_debt + (leases or 0.0) + (pensions or 0.0) + (pension_tax or 0.0)
    line("net_debt_data", net_debt_data, "subtotal")

    user_total = 0.0
    for item in user_items or []:
        line("user_item", item["amount"], "assumption", label=item["label"])
        user_total += item["amount"]
    adjusted = net_debt_data + user_total if net_debt_data is not None else None
    line("adjusted_net_debt", adjusted, "subtotal")

    return {
        "year": year, "lines": lines, "flags": tuple(flags),
        "net_financial_debt": net_financial_debt, "net_debt_data": net_debt_data, "adjusted_net_debt": adjusted,
        "adjusted_net_debt_excl_ifrs16": adjusted - leases if adjusted is not None and leases is not None else None,
        "excluded": tuple(key for key, value in (("lease_liabilities", leases), ("pension_liabilities", pensions))
                          if value is None),
        "short_term_investments": short_term_investments,
    }


def adjusted_ebitda(ebitda_published: float | None, adjustments: list[dict] | None) -> dict:
    """EBITDA publié + ajustements saisis (signe + : réintègre une charge non récurrente, - : retire un
    produit non récurrent). n.d. si l'EBITDA publié manque : un « EBITDA ajusté » construit sur rien
    ne serait que la somme des ajustements."""
    adjustments = adjustments or []
    total = sum(item["amount"] for item in adjustments)
    return {
        "published": ebitda_published, "adjustments": adjustments, "total_adjustments": total,
        "adjusted": ebitda_published + total if ebitda_published is not None else None,
    }


def transaction_multiples(market_cap: float | None, minority_interest: float | None, net_debt: float | None,
                          ebitda: float | None) -> dict:
    """Valeur d'entreprise = capitalisation + dette nette + intérêts minoritaires (l'EBITDA consolidé
    inclut 100 % des filiales, la VE doit donc inclure la part des minoritaires), puis VE / EBITDA et
    dette nette / EBITDA. Minoritaires absents chez Yahoo : exclus de la VE et signalés, jamais pris
    pour 0 en silence. Multiples n.d. si l'EBITDA est nul ou négatif (non interprétables)."""
    flags = ("minority_interest_missing",) if minority_interest is None else ()
    ev = market_cap + net_debt + (minority_interest or 0.0) if market_cap is not None and net_debt is not None else None
    positive_ebitda = ebitda is not None and ebitda > 0
    return {
        "enterprise_value": ev,
        "ev_to_ebitda": ev / ebitda if ev is not None and positive_ebitda else None,
        "net_debt_to_ebitda": net_debt / ebitda if net_debt is not None and positive_ebitda else None,
        "flags": flags,
        "reason": None if positive_ebitda else ("missing_inputs" if ebitda is None else "non_positive_denominator"),
    }


# ============================================================
# LOI DE BENFORD (premier chiffre significatif)
# ============================================================
# Dans de nombreux jeux de montants « naturels » (écritures comptables, factures), le premier chiffre
# significatif d vaut 1 dans 30 % des cas et 9 dans moins de 5 % : P(d) = log10(1 + 1/d). Un écart
# marqué peut signaler des montants inventés ou arrondis, mais aussi une population atypique (prix
# fixes, plafonds d'approbation) : c'est un outil de ciblage, pas une preuve.

DIGITS = tuple(range(1, 10))
BENFORD_PROBABILITIES = {d: math.log10(1 + 1 / d) for d in DIGITS}
# Bornes du MAD pour le premier chiffre (Nigrini 2012, Benford's Law, p. 160) : conformité étroite,
# acceptable, marginale, puis non-conformité au-delà. Bornes empiriques, pas des valeurs critiques.
NIGRINI_FIRST_DIGIT_MAD = (("close", 0.006), ("acceptable", 0.012), ("marginal", 0.015))
# Taille d'échantillon. Sous conformité parfaite, le MAD attendu vaut ≈ 0,235 / √N (bruit
# d'échantillonnage seul, voir expected_mad_under_conformity) : il dépasse la borne « acceptable »
# (0,012) tant que N < ~380, et la borne « étroite » (0,006) tant que N < ~1 530. Sous 400
# observations, même des données parfaitement conformes sortiraient donc en moyenne de la zone
# acceptable : résultat non interprétable. Sous 1 500, la conformité étroite n'est pas atteignable
# par hasard : prudence.
BENFORD_MIN_INTERPRETABLE = 400
BENFORD_MIN_FULL_RESOLUTION = 1500
# Les très petits montants (frais, arrondis) relèvent souvent d'une autre logique (pratique de Nigrini).
DEFAULT_BENFORD_MIN_AMOUNT = 10.0


def expected_mad_under_conformity(n: int) -> float:
    """MAD attendu pour un échantillon de taille n tiré EXACTEMENT selon la loi de Benford : chaque
    proportion observée s'écarte de sa probabilité d'un |N(0, p(1-p)/n)|, d'espérance σ√(2/π) ; le MAD
    en est la moyenne sur les 9 chiffres, soit ≈ 0,235 / √n."""
    if n <= 0:
        return math.inf
    return math.sqrt(2 / math.pi) / len(DIGITS) * sum(math.sqrt(p * (1 - p) / n) for p in BENFORD_PROBABILITIES.values())


def first_significant_digit(value: float) -> int | None:
    """Premier chiffre non nul de |value| (0,0042 -> 4, 1 234 -> 1). None pour 0 ou une valeur non
    finie. Passe par la notation scientifique plutôt que par log10, qui se trompe aux puissances de 10
    exactes à cause des arrondis flottants (log10(1000) = 2,9999...)."""
    if value is None or not math.isfinite(value) or value == 0:
        return None
    return int(f"{abs(value):e}"[0])


_AMOUNT_CLEANUP = re.compile(r"[^\d,.\-+()eE]")


def parse_amount(raw) -> float | None:
    """Montant saisi ou exporté sous un format quelconque -> float, None si illisible. Reconnaît les
    formats européens (« 1 234,56 », « 1.234,56 »), anglo-saxons (« 1,234.56 »), les symboles
    monétaires, et les parenthèses comptables pour un négatif (« (123,45) »). Avec un seul séparateur,
    une virgule suivie de 1 ou 2 chiffres (ou de plus de 3) est décimale, sinon un séparateur de
    milliers."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if math.isfinite(raw) else None
    text = str(raw).strip().replace(" ", "").replace(" ", "").replace(" ", "")
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = _AMOUNT_CLEANUP.sub("", text).strip("()")
    if not text or not re.search(r"\d", text):
        return None
    if "," in text and "." in text:
        decimal = "," if text.rfind(",") > text.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        text = text.replace(thousands, "").replace(decimal, ".")
    elif "," in text:
        head, _, tail = text.rpartition(",")
        is_decimal = text.count(",") == 1 and len(tail) != 3
        text = f"{head.replace(',', '')}.{tail}" if is_decimal else text.replace(",", "")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        value = float(text)
    except ValueError:
        return None
    return -abs(value) if negative else value


def read_ledger_csv(text: str) -> pd.DataFrame | None:
    """Grand livre ou liste d'écritures en CSV -> DataFrame de chaînes brutes (aucune conversion
    automatique : un « 1.234 » européen serait sinon lu comme 1,234). Séparateur détecté parmi
    « ; », « , », tabulation et « | » (les exports Excel français utilisent « ; »). None si le texte
    n'a pas de structure de tableau exploitable."""
    sample = text[:20000]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=";,\t|").delimiter
    except csv.Error:
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
    try:
        frame = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False)
    except Exception:
        return None
    return frame if not frame.empty and len(frame.columns) >= 1 else None


def guess_amount_column(columns: dict[str, list]) -> str | None:
    """Colonne la plus probablement « montant » : celle où la plus grande part des cellules se lit
    comme un nombre non nul. Simple proposition par défaut, l'utilisateur choisit la colonne."""
    best, best_share = None, 0.0
    for name, values in columns.items():
        if not values:
            continue
        parsed = [parse_amount(v) for v in values]
        share = sum(1 for v in parsed if v not in (None, 0.0)) / len(values)
        if share > best_share:
            best, best_share = name, share
    return best if best_share > 0 else None


def select_benford_amounts(raw_values: list, sign: str = "positive",
                           min_amount: float = DEFAULT_BENFORD_MIN_AMOUNT) -> tuple[list[float], dict]:
    """Montants retenus pour le test et décompte de ce qui est écarté, pour que l'utilisateur sache
    sur quoi porte le résultat. Positifs et négatifs sont analysés séparément (recommandation de
    Nigrini : factures et avoirs obéissent à des logiques différentes) : sign = "positive" ou
    "negative". Les montants dont la valeur absolue est sous min_amount sont exclus."""
    counts = {"total": len(raw_values), "unreadable": 0, "zero": 0, "other_sign": 0, "below_min": 0, "kept": 0}
    kept = []
    for raw in raw_values:
        value = parse_amount(raw)
        if value is None:
            counts["unreadable"] += 1
        elif value == 0:
            counts["zero"] += 1
        elif (value > 0) != (sign == "positive"):
            counts["other_sign"] += 1
        elif abs(value) < min_amount:
            counts["below_min"] += 1
        else:
            kept.append(abs(value))
    counts["kept"] = len(kept)
    return kept, counts


def chi2_survival_even_df(statistic: float, df: int) -> float:
    """P(χ² > statistic) pour un nombre pair de degrés de liberté, en forme exacte :
    exp(-x/2) Σ_{i<df/2} (x/2)^i / i!. Évite une dépendance à scipy pour le seul test de Benford
    (8 degrés de liberté)."""
    if df % 2:
        raise ValueError("forme fermée valable pour un nombre pair de degrés de liberté")
    half = statistic / 2
    return math.exp(-half) * sum(half ** i / math.factorial(i) for i in range(df // 2))


def benford_first_digit_test(amounts: list[float]) -> dict:
    """Test du premier chiffre : fréquences observées contre la loi de Benford, MAD et zone de
    conformité de Nigrini, test du χ² (8 degrés de liberté) et avertissement de taille.

    Le χ² rejette la conformité pour des écarts minimes dès que N est grand (sa puissance croît avec N)
    : Nigrini lui préfère le MAD, qui ne dépend pas de la taille. Les deux sont affichés, le MAD fait
    foi pour la zone de conformité. Renvoie n = 0 et des valeurs None si aucun montant n'est fourni."""
    digits = [d for d in (first_significant_digit(v) for v in amounts) if d is not None]
    n = len(digits)
    counts = {d: digits.count(d) for d in DIGITS}
    if n == 0:
        return {"n": 0, "counts": counts, "observed": {d: None for d in DIGITS}, "expected": BENFORD_PROBABILITIES,
                "mad": None, "conformity": None, "chi2": None, "p_value": None, "sample_warning": "empty",
                "expected_mad": None}
    observed = {d: counts[d] / n for d in DIGITS}
    mad = sum(abs(observed[d] - BENFORD_PROBABILITIES[d]) for d in DIGITS) / len(DIGITS)
    conformity = next((label for label, bound in NIGRINI_FIRST_DIGIT_MAD if mad <= bound), "nonconformity")
    chi2 = sum((counts[d] - n * BENFORD_PROBABILITIES[d]) ** 2 / (n * BENFORD_PROBABILITIES[d]) for d in DIGITS)
    if n < BENFORD_MIN_INTERPRETABLE:
        warning = "not_interpretable"
    elif n < BENFORD_MIN_FULL_RESOLUTION:
        warning = "caution"
    else:
        warning = None
    return {
        "n": n, "counts": counts, "observed": observed, "expected": BENFORD_PROBABILITIES, "mad": mad,
        "conformity": conformity, "chi2": chi2, "p_value": chi2_survival_even_df(chi2, len(DIGITS) - 1),
        "sample_warning": warning, "expected_mad": expected_mad_under_conformity(n),
    }


def financial_statement_amounts(frames: dict[str, pd.DataFrame]) -> list[float]:
    """Démonstration sur les états financiers : tous les montants bruts publiés (trois états, tous les
    exercices), en retirant pour chaque exercice les valeurs strictement identiques présentes dans
    plusieurs états (le résultat net figure au compte de résultat ET au tableau de flux) pour ne pas
    compter deux fois le même chiffre. Quelques centaines de montants au mieux : trop peu pour un test
    fiable, d'où le statut de simple démonstration."""
    by_year: dict[pd.Timestamp, set[float]] = {}
    for frame in frames.values():
        clean = _clean_frame(frame)
        for year in clean.columns:
            values = pd.to_numeric(clean[year], errors="coerce").dropna()
            by_year.setdefault(year, set()).update(float(v) for v in values if v != 0)
    return [value for year in sorted(by_year) for value in sorted(by_year[year])]
