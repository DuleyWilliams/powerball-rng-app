import json
from datetime import date

from data import database, json_export
from data.repository import insert_draw


def _use_temp_files(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "test.db")
    monkeypatch.setattr(json_export, "DATA_FILE", tmp_path / "numbers.json")


def test_export_schema_v2_preserves_numbers_and_adds_metadata(tmp_path, monkeypatch):
    _use_temp_files(tmp_path, monkeypatch)
    insert_draw(None, 1, 11, 21, 31, 41, 5, "legacy_json")
    insert_draw(date(2024, 2, 3), 10, 20, 30, 40, 50, 12, "official")
    insert_draw(date(2025, 4, 5), 2, 12, 22, 32, 42, 8, "official")

    json_export.export_draws_to_json()
    payload = json.loads(json_export.DATA_FILE.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 2
    assert payload["generated_at_utc"].endswith("Z")
    assert payload["total_draws"] == 3
    assert payload["dated_draws"] == 2
    assert payload["undated_draws"] == 1
    assert payload["latest_draw_date"] == "2025-04-05"
    assert payload["latest_drawing"] == {
        "draw_date": "2025-04-05",
        "numbers": [2, 12, 22, 32, 42, 8],
    }
    assert payload["numbers"] == [
        [2, 12, 22, 32, 42, 8],
        [10, 20, 30, 40, 50, 12],
        [1, 11, 21, 31, 41, 5],
    ]
    assert payload["draws"][0] == {
        "draw_date": "2025-04-05",
        "numbers": [2, 12, 22, 32, 42, 8],
        "source": "official",
    }


def test_export_without_dated_draws_uses_null_latest_metadata(tmp_path, monkeypatch):
    _use_temp_files(tmp_path, monkeypatch)
    insert_draw(None, 1, 2, 3, 4, 5, 6, "legacy_json")

    payload = json_export.build_export_payload()

    assert payload["latest_draw_date"] is None
    assert payload["latest_drawing"] is None
    assert payload["dated_draws"] == 0
    assert payload["undated_draws"] == 1
