"""
Test de démarrage des écrans : appelle chaque callback Python enregistré avec les valeurs initiales de
ses entrées (lues dans la mise en page de l'application), données de marché simulées, sur une base
vide puis sur une base remplie de lignes fictives. Échoue si un callback lève une erreur ou renvoie
un nombre de valeurs différent de ses sorties déclarées : ces erreurs-là n'apparaissent sinon qu'à
l'écran, après lancement. Aucun appel réseau (Yahoo est remplacé), aucune donnée réelle.
Usage : pip install -r requirements-dev.txt && pytest -v
"""
import dash
from dash._callback_context import context_value
from dash._utils import AttributeDict
from dash.development.base_component import Component
import numpy as np
import pandas as pd
import pytest

import app as app_module  # noqa: F401 - construit la mise en page (sans lancer le serveur)
import callbacks  # noqa: F401 - enregistre les callbacks
import market_data
import portfolio_db
from app_instance import app
from callbacks import par_indice, portefeuille, portefeuille_reel, validation


def _monthly(seed: int, n: int = 360) -> pd.Series:
    rng = np.random.default_rng(seed)
    index = pd.date_range(end=pd.Timestamp.today().normalize(), periods=n, freq="MS")
    return pd.Series(rng.normal(0.006, 0.04, n), index=index)


def _daily(start: str) -> pd.Series:
    index = pd.date_range(start=start, end=pd.Timestamp.today().normalize(), freq="B")
    return pd.Series(np.linspace(10.0, 11.0, len(index)), index=index)


FAKES = {
    "get_monthly_returns": lambda ticker, lookback_years: _monthly(abs(hash(ticker)) % 1000),
    "get_monthly_returns_eur": lambda ticker, lookback_years: _monthly(abs(hash(ticker)) % 1000),
    "get_aligned_returns": lambda names, lookback_years, source_key: pd.DataFrame(
        {name: _monthly(i) for i, name in enumerate(names)}),
    "get_aligned_returns_for_tickers": lambda tickers, lookback_years: pd.DataFrame(
        {t: _monthly(i) for i, t in enumerate(tickers)}),
    "get_current_price": lambda ticker: 10.5,
    "get_daily_price_history": lambda ticker, start_date: _daily(start_date),
    "get_daily_total_return_history": lambda ticker, start_date: _daily(start_date),
    "get_dividends_per_share_eur": lambda ticker: pd.Series(dtype=float),
    "get_instrument_profile": lambda ticker: {"name": f"Amundi fonds {ticker}", "quote_type": "ETF"},
    "get_ticker_name": lambda ticker: f"Fonds {ticker}",
    "resolve_isin_to_ticker": lambda isin: None,
}


@pytest.fixture
def offline(monkeypatch):
    """Remplace les accès Yahoo partout où ils sont importés (module market_data et callbacks)."""
    for module in (market_data, par_indice, portefeuille, portefeuille_reel, validation):
        for name, fake in FAKES.items():
            if hasattr(module, name):
                monkeypatch.setattr(module, name, fake)


def _layout_values(component, values=None) -> dict:
    """{(id, propriété): valeur} de chaque composant de la mise en page initiale."""
    values = {} if values is None else values
    if isinstance(component, (list, tuple)):
        for child in component:
            _layout_values(child, values)
        return values
    if not isinstance(component, Component):
        return values
    component_id = getattr(component, "id", None)
    if isinstance(component_id, str):
        for prop in component._prop_names:
            values[(component_id, prop)] = getattr(component, prop, None)
    for prop in component._prop_names:
        child = getattr(component, prop, None)
        if isinstance(child, (Component, list, tuple)):
            _layout_values(child, values)
    return values


def _output_count(key: str) -> int:
    return len(key[2:-2].split("...")) if key.startswith("..") else 1


def _sweep() -> list[str]:
    """Appelle chaque callback dont toutes les entrées existent dans la mise en page initiale ;
    renvoie la liste des callbacks effectivement appelés."""
    values = _layout_values(app.layout)
    called = []
    for key, entry in app.callback_map.items():
        func = getattr(entry.get("callback"), "__wrapped__", None)
        if func is None:
            continue  # callback côté navigateur
        deps = list(entry["inputs"]) + list(entry.get("state", []))
        if any((dep["id"], dep["property"]) not in values for dep in deps if isinstance(dep["id"], str)):
            continue  # entrée créée plus tard par un autre callback
        args = [values.get((dep["id"], dep["property"])) for dep in deps]
        # Contexte de requête Dash simulé : la première entrée déclenche, comme au chargement de la page.
        first = entry["inputs"][0] if entry["inputs"] else None
        triggered = [{"prop_id": f"{first['id']}.{first['property']}", "value": args[0]}] if first else []
        token = context_value.set(AttributeDict(
            triggered_inputs=triggered, inputs_list=[], states_list=[], outputs_list=[], inputs={}, states={},
        ))
        try:
            result = func(*args)
        except dash.exceptions.PreventUpdate:
            called.append(func.__name__)
            continue
        finally:
            context_value.reset(token)
        expected = _output_count(key)
        if expected > 1:
            assert isinstance(result, (list, tuple)), f"{func.__name__} : une seule valeur pour {expected} sorties"
            assert len(result) == expected, f"{func.__name__} : {len(result)} valeurs pour {expected} sorties"
        called.append(func.__name__)
    return called


def _python_callbacks() -> set[str]:
    return {entry["callback"].__wrapped__.__name__ for entry in app.callback_map.values()
            if getattr(entry.get("callback"), "__wrapped__", None)}


def test_every_callback_runs_on_an_empty_portfolio(offline):
    called = set(_sweep())
    # Tous les callbacks Python doivent être atteints : un nouveau callback dont une entrée manque à
    # la mise en page initiale serait sinon ignoré sans bruit par ce test.
    assert called == _python_callbacks(), f"non couverts : {sorted(_python_callbacks() - called)}"


def test_every_callback_runs_on_a_filled_portfolio(offline):
    # Lignes fictives : aucun rapport avec un portefeuille réel.
    for ticker, date, amount in (("AAA.PA", "2025-01-15", 300.0), ("BBB.PA", "2025-03-03", 200.0),
                                 ("AAA.PA", "2025-06-02", 150.0), ("CCC.PA", "2025-09-01", 100.0)):
        portfolio_db.insert_transaction(ticker, date, amount, 10.0, 1.0)
    portfolio_db.insert_dividend("BBB.PA", "2025-10-01", 4.0)
    portfolio_db.upsert_target_weight("AAA.PA", 50.0)
    portfolio_db.upsert_target_weight("BBB.PA", 30.0)
    portfolio_db.upsert_target_weight("CCC.PA", 20.0)
    called = _sweep()
    assert {"refresh_tab3", "plan_next_contribution", "refresh_line_contributions",
            "refresh_dividend_calendar", "refresh_performance"} <= set(called)
