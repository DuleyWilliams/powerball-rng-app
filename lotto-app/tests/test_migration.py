import json

from data import database, migration


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "test.db")


def _use_temp_json(tmp_path, monkeypatch, payload):
    json_file = tmp_path / "numbers.json"
    json_file.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(migration, "DATA_FILE", json_file)
    return json_file


def test_migrate_reports_no_source_when_json_missing(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    monkeypatch.setattr(migration, "DATA_FILE", tmp_path / "does_not_exist.json")

    summary = migration.migrate_json_to_sqlite()

    assert summary.source_found is False
    assert summary.migrated == 0


def test_migrate_imports_legacy_entries(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    _use_temp_json(tmp_path, monkeypatch, {"numbers": [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]]})

    summary = migration.migrate_json_to_sqlite()

    assert summary.source_found is True
    assert summary.migrated == 2
    assert summary.skipped == 0
    assert summary.failed == 0


def test_migrate_is_idempotent(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    _use_temp_json(tmp_path, monkeypatch, {"numbers": [[1, 2, 3, 4, 5, 6]]})

    first = migration.migrate_json_to_sqlite()
    second = migration.migrate_json_to_sqlite()

    assert first.migrated == 1
    assert second.migrated == 0
    assert second.skipped == 1


def test_migrate_counts_invalid_entries_as_failed(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    _use_temp_json(tmp_path, monkeypatch, {"numbers": [[1, 2, 3, 4, 5, 99]]})  # powerball out of range

    summary = migration.migrate_json_to_sqlite()

    assert summary.migrated == 0
    assert summary.failed == 1
