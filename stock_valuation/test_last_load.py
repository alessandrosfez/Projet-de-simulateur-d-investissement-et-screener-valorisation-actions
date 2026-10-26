"""
Dernier chargement enregistré (last_load.py), sur un fichier temporaire (voir
conftest.isolate_last_load).
"""
import last_load


def test_round_trip_keeps_rows_universes_and_time():
    rows = [{"Ticker": "AAA.PA", "price": 10.0, "trailing_pe": None}]
    saved_at = last_load.save_last_load(rows, ["dax", "cac40"], saved_at=1_000.0)
    assert saved_at == 1_000.0
    assert last_load.read_last_load() == {"saved_at": 1_000.0, "universes": ["cac40", "dax"], "rows": rows}


def test_missing_corrupt_or_empty_file_reads_as_none():
    assert last_load.read_last_load() is None
    last_load.LAST_LOAD_FILE.write_bytes(b"pas un pickle")
    assert last_load.read_last_load() is None
    last_load.save_last_load([], ["cac40"])
    assert last_load.read_last_load() is None
