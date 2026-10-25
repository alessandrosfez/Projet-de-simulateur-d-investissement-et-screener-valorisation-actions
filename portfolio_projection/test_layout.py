"""
Tests du convertisseur de colonnes DataTable -> AG Grid (layout.grid_columns) : infobulle d'en-tête
reprise, première colonne figée, largeur minimale assez grande pour ne pas tronquer le plus long
contenu.
Usage : pip install -r requirements-dev.txt && pytest -v
"""
import layout


def test_grid_columns_keep_tooltips_pin_first_column_and_fit_longest_cell():
    columns = [{"name": "Scénario", "id": "Scénario"}, {"name": "Valeur finale P90 (€)", "id": "Valeur finale P90 (€)"}]
    rows = [{"Scénario": "MSCI Emerging Markets : Apport progressif", "Valeur finale P90 (€)": "2 138 787 €"}]
    defs = layout.grid_columns(columns, {"Valeur finale P90 (€)": {"type": "text", "value": "aide P90"}}, rows)
    first, second = defs
    assert first["pinned"] == "left" and "type" not in first
    assert second["type"] == "rightAligned" and second["headerTooltip"] == "aide P90"
    assert first["minWidth"] >= len(rows[0]["Scénario"]) * layout.GRID_CHAR_PX
    assert second["minWidth"] >= len("2 138 787 €") * layout.GRID_CHAR_PX


def test_grid_columns_without_rows_still_fit_the_longest_header_word():
    defs = layout.grid_columns([{"name": "Probabilité de gain (%)", "id": "p"}])
    assert defs[0]["minWidth"] >= len("Probabilité") * layout.GRID_CHAR_PX


def test_correlation_bands_follow_the_agreed_thresholds():
    from charts import corr_band
    assert corr_band(1.0) == "duplicate" and corr_band(0.90) == "duplicate"
    assert corr_band(0.89) == "strong" and corr_band(0.70) == "strong"
    assert corr_band(0.69) == "linked" and corr_band(0.40) == "linked"
    assert corr_band(0.39) == "diversifying" and corr_band(-0.5) == "diversifying"
