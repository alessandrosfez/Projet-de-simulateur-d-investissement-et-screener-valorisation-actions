"""
Moteur de calcul pur de l'analyse financière : normalisation des états financiers, classement
sectoriel, conversion des données de marché. Aucune dépendance Dash, réseau ou disque : les
fonctions reçoivent des DataFrames ou des dicts déjà chargés (voir market_data.py), c'est ce que
couvre test_engine.py.

Règle transversale : une donnée manquante n'est jamais remplacée par 0. Un poste introuvable vaut
None, accompagné de la raison, pour que l'interface affiche « n.d. » plutôt qu'un chiffre faux.
"""
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
ANALYSES = ("beneish", "altman", "working_capital", "earnings_quality")


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
