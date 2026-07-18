from datetime import date

import pytest

from data import database
from data.backup_export import export_backup
from data.repository import get_all_draws, insert_draw
from restore_database import RestoreError, restore_from_backup


def _use_temp_db(tmp_path, monkeypatch, name="test.db"):
    db_file = tmp_path / name
    monkeypatch.setattr(database, "DB_FILE", db_file)
    return db_file


def test_restore_round_trip_reproduces_original_data(tmp_path, monkeypatch):
    # Build an original database and export it.
    _use_temp_db(tmp_path, monkeypatch, name="original.db")
    insert_draw(date(2020, 1, 1), 1, 2, 3, 4, 5, 6, "data.ny.gov")
    insert_draw(date(2022, 6, 15), 10, 20, 30, 40, 50, 12, "powerball.com")
    insert_draw(None, 7, 17, 27, 37, 47, 9, "legacy_json")

    backup_file = tmp_path / "draws_backup.json"
    export_backup(draws_backup_file=backup_file, manifest_file=tmp_path / "manifest.json")
    original_draws = get_all_draws()

    # Restore into a fresh database and compare.
    _use_temp_db(tmp_path, monkeypatch, name="restored.db")

    summary = restore_from_backup(backup_file, force=False)

    assert summary.imported == 3
    assert summary.failed == 0
    assert summary.total_rows == 3

    restored_draws = get_all_draws()
    assert sorted(map(tuple, restored_draws)) == sorted(map(tuple, original_draws))


def test_restore_preserves_original_source_labels(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch, name="original.db")
    insert_draw(date(2020, 1, 1), 1, 2, 3, 4, 5, 6, "data.ny.gov")

    backup_file = tmp_path / "draws_backup.json"
    export_backup(draws_backup_file=backup_file, manifest_file=tmp_path / "manifest.json")

    _use_temp_db(tmp_path, monkeypatch, name="restored.db")
    restore_from_backup(backup_file, force=False)

    with database.get_connection() as conn:
        row = conn.execute("SELECT source FROM draws").fetchone()
    assert row["source"] == "data.ny.gov"


def test_restore_refuses_to_overwrite_without_force(tmp_path, monkeypatch):
    db_file = _use_temp_db(tmp_path, monkeypatch)
    insert_draw(date(2020, 1, 1), 1, 2, 3, 4, 5, 6, "test")  # creates db_file on disk

    backup_file = tmp_path / "draws_backup.json"
    export_backup(draws_backup_file=backup_file, manifest_file=tmp_path / "manifest.json")

    assert db_file.exists()

    with pytest.raises(RestoreError, match="Use --force"):
        restore_from_backup(backup_file, force=False)


def test_restore_overwrites_when_force_given(tmp_path, monkeypatch):
    db_file = _use_temp_db(tmp_path, monkeypatch)
    insert_draw(date(2020, 1, 1), 99, 98, 97, 96, 95, 20, "stale")  # will be wiped

    backup_file = tmp_path / "draws_backup.json"
    fresh_records = [{
        "draw_date": "2025-05-05", "ball1": 1, "ball2": 2, "ball3": 3, "ball4": 4, "ball5": 5,
        "powerball": 6, "source": "data.ny.gov",
    }]
    import json
    backup_file.write_text(json.dumps(fresh_records), encoding="utf-8")

    summary = restore_from_backup(backup_file, force=True)

    assert summary.imported == 1
    draws = get_all_draws()
    assert draws == [[1, 2, 3, 4, 5, 6]]


def test_restore_reports_invalid_records_as_failed(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    backup_file = tmp_path / "draws_backup.json"
    import json
    bad_records = [{
        "draw_date": "2025-05-05", "ball1": 1, "ball2": 2, "ball3": 3, "ball4": 4, "ball5": 99,  # out of range
        "powerball": 6, "source": "data.ny.gov",
    }]
    backup_file.write_text(json.dumps(bad_records), encoding="utf-8")

    summary = restore_from_backup(backup_file, force=False)

    assert summary.imported == 0
    assert summary.failed == 1
