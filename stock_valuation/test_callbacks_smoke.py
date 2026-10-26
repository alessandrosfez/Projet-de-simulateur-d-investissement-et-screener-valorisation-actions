"""
Test de démarrage des écrans : appelle chaque callback Python enregistré avec les valeurs initiales de
ses entrées (lues dans la mise en page de l'application), données Yahoo simulées : avant chargement,
puis avec un univers fictif chargé, une ligne sélectionnée et une liste de suivi. Échoue si un
callback lève une erreur ou renvoie un nombre de valeurs différent de ses sorties déclarées : ces
erreurs-là n'apparaissent sinon qu'à l'écran. Recopié et adapté de portfolio_projection (pas
d'import croisé entre outils). Aucun appel réseau, aucune donnée réelle.
Usage : pip install -r requirements-dev.txt && pytest -v
"""
import json
import time

import dash
import numpy as np
import pandas as pd
import pytest
from dash._callback_context import context_value
from dash._utils import AttributeDict
from dash.development.base_component import Component

import app as app_module  # noqa: F401 - construit la mise en page (sans lancer le serveur)
import callbacks
import journal_db
import last_load
import market_data
from app_instance import app

FAKE_TICKERS = {"AAA.PA": "Alpha", "BBB.PA": "Beta", "CCC.PA": "Gamma", "DDD.PA": "Delta"}


def _seed(ticker: str) -> int:
    return sum(ord(c) for c in ticker)


def _valuation(ticker: str) -> dict:
    s = _seed(ticker) % 7
    return {"name": FAKE_TICKERS.get(ticker, ticker), "sector": "Industrials" if s % 2 else "Technology",
            "currency": "EUR", "price": 40.0 + s, "trailing_pe": 10.0 + 3 * s, "forward_pe": 9.0 + 2 * s,
            "peg_ratio": 0.8 + 0.3 * s, "ev_to_ebitda": 6.0 + s, "price_to_book": 1.5 + 0.2 * s,
            "dividend_yield": 2.0, "market_cap": 5e9 * (1 + s), "pe_5y_mean": 15.0, "pe_5y_percentile": 10.0 * s}


def _weekly(ticker: str) -> pd.Series:
    rng = np.random.default_rng(_seed(ticker))
    index = pd.date_range(end=pd.Timestamp.today().normalize(), periods=150, freq="W")
    series = pd.Series(15 + rng.normal(0, 1, 150).cumsum() * 0.2, index=index)
    series.attrs["method"] = "annual_eps"
    return series


def _monthly_prices(ticker: str) -> pd.Series:
    rng = np.random.default_rng(_seed(ticker))
    index = pd.date_range(end=pd.Timestamp.today().normalize(), periods=60, freq="MS")
    return pd.Series(50 * np.cumprod(1 + rng.normal(0.008, 0.05, 60)), index=index)


FAKES = {
    "get_stock_valuation": _valuation,
    # Mêmes clés que market_data.get_stock_quality_metrics, une manquante (n.d.) comme chez Yahoo.
    "get_stock_quality_metrics": lambda ticker: {
        "roic": 12.0, "return_on_equity": 15.0, "return_on_assets": 6.0, "gross_margin": 40.0,
        "operating_margin": 14.0, "profit_margin": 9.0, "revenue_growth": 4.0, "debt_to_equity": 80.0,
        "current_ratio": 1.3, "quick_ratio": None},
    "get_stock_price_history": lambda ticker, *args, **kwargs: _monthly_prices(ticker),
    "get_stock_pe_history": _weekly,
    "get_dcf_inputs": lambda ticker: {
        "fcf": 1e9, "fcf_history": [], "total_debt": 2e9, "total_cash": 1e9, "shares_outstanding": 1e8,
        "price": 45.0, "currency": "EUR", "enterprise_value": 6e9, "ev_to_ebitda": 8.0},
}


@pytest.fixture
def offline(monkeypatch):
    """Remplace les accès Yahoo partout où ils sont importés."""
    for module in (market_data, callbacks):
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


def _is_pattern(component_id) -> bool:
    """Identifiant à motif (dict), que callback_map conserve sous forme de chaîne JSON."""
    return isinstance(component_id, dict) or (isinstance(component_id, str) and component_id.startswith("{"))


def _output_count(key: str) -> int:
    return len(key[2:-2].split("...")) if key.startswith("..") else 1


def _python_callbacks() -> set[str]:
    return {entry["callback"].__wrapped__.__name__ for entry in app.callback_map.values()
            if getattr(entry.get("callback"), "__wrapped__", None)}


def _call(func, entry, args):
    """Appelle un callback dans un contexte de requête Dash simulé (première entrée déclencheuse)."""
    first = entry["inputs"][0] if entry["inputs"] else None
    triggered = [{"prop_id": f"{first['id']}.{first['property']}", "value": args[0]}] if first else []
    token = context_value.set(AttributeDict(
        triggered_inputs=triggered, inputs_list=[], states_list=[], outputs_list=[], inputs={}, states={},
    ))
    try:
        return func(*args)
    finally:
        context_value.reset(token)


def _sweep(overrides: dict | None = None) -> set[str]:
    """Appelle chaque callback dont toutes les entrées existent dans la mise en page initiale ;
    renvoie les callbacks effectivement appelés. overrides : valeurs (id, propriété) imposées."""
    values = _layout_values(app.layout)
    values.update(overrides or {})
    called = set()
    for key, entry in app.callback_map.items():
        func = getattr(entry.get("callback"), "__wrapped__", None)
        if func is None:
            continue  # callback côté navigateur
        deps = list(entry["inputs"]) + list(entry.get("state", []))
        if any((dep["id"], dep["property"]) not in values for dep in deps if not _is_pattern(dep["id"])):
            continue  # entrée créée plus tard par un autre callback
        # Entrée à motif (boutons des fiches du journal, ALL) : liste vide, comme avant tout affichage.
        args = [[] if _is_pattern(dep["id"]) else values.get((dep["id"], dep["property"])) for dep in deps]
        try:
            result = _call(func, entry, args)
        except dash.exceptions.PreventUpdate:
            called.add(func.__name__)
            continue
        expected = _output_count(key)
        if expected > 1:
            assert isinstance(result, (list, tuple)), f"{func.__name__} : une seule valeur pour {expected} sorties"
            assert len(result) == expected, f"{func.__name__} : {len(result)} valeurs pour {expected} sorties"
        called.add(func.__name__)
    return called


def test_every_callback_runs_before_any_data_is_loaded(offline):
    called = _sweep()
    assert called == _python_callbacks(), f"non couverts : {sorted(_python_callbacks() - called)}"


def test_every_callback_runs_with_a_loaded_universe_and_a_selected_row(offline):
    rows = []
    for ticker, name in FAKE_TICKERS.items():
        data = callbacks._load_full_stock_data(ticker)
        data["Entreprise"], data["Ticker"] = name, ticker
        rows.append(data)
    grid_rows = _sweep_render(rows)
    # Journal (fichier temporaire, voir conftest) : une revue due avec cible, une sans cible ni date,
    # un titre absent des données chargées.
    journal_db.upsert_entry("AAA.PA", "Thèse de test", 1000.0, "2020-01-01")
    journal_db.upsert_entry("BBB.PA", "", None, None)
    journal_db.upsert_entry("ZZZ.PA", "Hors univers", 12.0, "2099-01-01")
    # Dernier chargement enregistré il y a deux heures : restauré, avec une demande de rafraîchissement.
    last_load.save_last_load(rows, ["cac40"], saved_at=time.time() - 7200)
    called = _sweep({
        ("stocks-loaded-at", "data"): {"at": time.time() - 7200, "universes": ["cac40"]},
        ("stocks-auto-refresh", "data"): {"universes": ["cac40"], "requested_at": time.time()},
        ("stocks-raw-store", "data"): rows,
        ("stocks-table", "rowData"): grid_rows,
        ("stocks-table", "selectedRows"): [grid_rows[0]],
        ("watchlist-dropdown", "value"): ["AAA.PA", "CCC.PA"],
    })
    assert {"render_stock_views", "update_dcf", "update_pe_history_chart", "update_watchlist_alerts",
            "render_journal", "restore_last_load", "update_freshness"} <= called


def _sweep_render(rows) -> list[dict]:
    """Lignes du tableau de criblage telles que render_stock_views les produit pour ces données."""
    values = _layout_values(app.layout)
    values[("stocks-raw-store", "data")] = rows
    for key, entry in app.callback_map.items():
        func = getattr(entry.get("callback"), "__wrapped__", None)
        if func is not None and func.__name__ == "render_stock_views":
            deps = list(entry["inputs"]) + list(entry.get("state", []))
            result = _call(func, entry, [values.get((dep["id"], dep["property"])) for dep in deps])
            outputs = key[2:-2].split("...")
            return result[outputs.index("stocks-table.rowData")]
    raise AssertionError("render_stock_views introuvable")


def test_journal_icon_buttons_act_on_the_clicked_entry_only():
    """Corbeille et crayon d'une fiche : seul un clic réel agit, et sur la bonne entrée."""
    journal_db.upsert_entry("AAA.PA", "", None, None)
    journal_db.upsert_entry("BBB.PA", "", None, None)

    def click(func, kind, ticker, n_clicks, *extra):
        prop = json.dumps({"ticker": ticker, "type": f"journal-{kind}"}, separators=(",", ":")) + ".n_clicks"
        token = context_value.set(AttributeDict(triggered_inputs=[{"prop_id": prop, "value": n_clicks}],
                                                inputs_list=[], states_list=[], outputs_list=[], inputs={}, states={}))
        try:
            return func(n_clicks, *extra)
        finally:
            context_value.reset(token)

    # Fiches qui viennent d'apparaître (aucun clic) : rien ne se passe.
    with pytest.raises(dash.exceptions.PreventUpdate):
        click(callbacks.delete_journal_entry, "delete", "AAA.PA", [0, 0], 3)
    assert click(callbacks.edit_journal_entry, "edit", "BBB.PA", [0, 1]) == "BBB.PA"
    assert click(callbacks.delete_journal_entry, "delete", "AAA.PA", [1, 0], 3) == 4
    assert [e["ticker"] for e in journal_db.get_entries()] == ["BBB.PA"]


def test_restore_shows_saved_rows_and_asks_a_refresh_only_when_stale(offline):
    rows = [{"Ticker": "AAA.PA", "Entreprise": "Alpha", "price": 10.0}]
    with pytest.raises(dash.exceptions.PreventUpdate):
        callbacks.restore_last_load(0)  # rien d'enregistré : écran vide comme avant
    last_load.save_last_load(rows, ["cac40"])
    restored, loaded_at, universes, refresh = callbacks.restore_last_load(0)
    assert restored == rows and universes == ["cac40"] and loaded_at["universes"] == ["cac40"]
    assert refresh is dash.no_update  # moins d'une heure : le cache renverrait les mêmes données
    last_load.save_last_load(rows, ["cac40"], saved_at=time.time() - 2 * last_load.STALE_AFTER_SECONDS)
    assert callbacks.restore_last_load(0)[3]["universes"] == ["cac40"]


def test_failed_automatic_refresh_keeps_the_rows_on_screen(offline, monkeypatch):
    def unavailable(ticker):
        raise ConnectionError("Yahoo injoignable")

    monkeypatch.setattr(callbacks, "get_stock_valuation", unavailable)
    token = context_value.set(AttributeDict(
        triggered_inputs=[{"prop_id": "stocks-auto-refresh.data", "value": {}}],
        inputs_list=[], states_list=[], outputs_list=[], inputs={}, states={}))
    try:
        rows, warning, loaded_at = callbacks.load_stock_valuations(None, {"universes": ["cac40"]}, ["cac40"], "fr")
    finally:
        context_value.reset(token)
    assert rows is dash.no_update and loaded_at is dash.no_update and warning
