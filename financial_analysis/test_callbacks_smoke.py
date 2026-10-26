"""
Test de démarrage des écrans : appelle chaque callback Python enregistré avec les valeurs initiales de
ses entrées (lues dans la mise en page), d'abord sans société analysée, puis sur l'exemple Wirecard
importé (examples/, hors ligne), y compris les callbacks des composants que l'analyse crée (pont du
résultat, modèle d'Altman, transaction...). Échoue si un callback lève une erreur ou renvoie un nombre
de valeurs différent de ses sorties déclarées : ces erreurs-là n'apparaissent sinon qu'à l'écran.
Recopié et adapté de portfolio_projection (pas d'import croisé entre outils). Les accès Yahoo sont
remplacés par des fonctions qui échouent : le test ne doit jamais aller sur le réseau.
Usage : pip install -r requirements-dev.txt && pytest -v
"""
from pathlib import Path

import dash
import pytest
from dash._callback_context import context_value
from dash._utils import AttributeDict
from dash.development.base_component import Component

import app as app_module  # noqa: F401 - construit la mise en page (sans lancer le serveur)
import callbacks
import engine
import market_data
from app_instance import app

EXAMPLE = Path(__file__).with_name("examples") / "wirecard_2015_2018.csv"
NETWORK = ("get_annual_statements", "get_company_profile", "get_daily_closes", "get_fx_rate")


@pytest.fixture
def offline(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("appel réseau pendant le test de démarrage")

    for module in (market_data, callbacks):
        for name in NETWORK:
            if hasattr(module, name):
                monkeypatch.setattr(module, name, refuse)


def _layout_values(component, values=None) -> dict:
    """{(id, propriété): valeur} de chaque composant d'un arbre Dash."""
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


def _sweep(values: dict) -> tuple[set[str], dict]:
    """Appelle chaque callback dont toutes les entrées sont connues ; renvoie les callbacks appelés et
    les valeurs des composants créés par leurs sorties (pour un second passage)."""
    called, created = set(), {}
    for key, entry in app.callback_map.items():
        func = getattr(entry.get("callback"), "__wrapped__", None)
        if func is None:
            continue  # callback côté navigateur
        deps = list(entry["inputs"]) + list(entry.get("state", []))
        if any((dep["id"], dep["property"]) not in values for dep in deps if isinstance(dep["id"], str)):
            continue  # entrée créée par un autre callback : voir le second passage
        try:
            result = _call(func, entry, [values.get((dep["id"], dep["property"])) for dep in deps])
        except dash.exceptions.PreventUpdate:
            called.add(func.__name__)
            continue
        expected = _output_count(key)
        if expected > 1:
            assert isinstance(result, (list, tuple)), f"{func.__name__} : une seule valeur pour {expected} sorties"
            assert len(result) == expected, f"{func.__name__} : {len(result)} valeurs pour {expected} sorties"
        _layout_values(result, created)
        called.add(func.__name__)
    return called, created


def test_every_callback_runs_before_any_analysis(offline):
    called, _ = _sweep(_layout_values(app.layout))
    missing = _python_callbacks() - called
    # Les callbacks des composants créés par l'analyse ne sont atteignables qu'après elle (test suivant).
    assert {"render_analysis"} <= called, f"non couverts : {sorted(missing)}"


def test_every_callback_runs_on_an_imported_company(offline):
    dataset = engine.parse_statements_csv(EXAMPLE.read_text(encoding="utf-8"))["dataset"]
    values = _layout_values(app.layout)
    values[("analysis-ticker-store", "data")] = {"source": "import", "filename": EXAMPLE.name, "dataset": dataset}
    called, created = _sweep(values)
    values.update(created)
    called_again, _ = _sweep(values)
    called |= called_again
    assert called == _python_callbacks(), f"non couverts : {sorted(_python_callbacks() - called)}"
