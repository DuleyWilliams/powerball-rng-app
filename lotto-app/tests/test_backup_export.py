import json
from datetime import date

import pytest

from data import database
from data.repository import insert_draw
from data.backup_export import (
    BackupValidationError,
    _build_manifest,
    _validate_export,
    export_backup,
)


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "test.db")


def _seed_draws():
    # Two dated rows (out of order on purpose), two undated legacy rows
    # (also inserted out of ball-value order on purpose).
    insert_draw(date(2020, 1, 1), 1, 2, 3, 4, 5, 6, "test")
    insert_draw(date(2022, 6, 15), 10, 20, 30, 40, 50, 12, "test")
    insert_draw(None, 9, 19, 29, 39, 49, 20, "legacy_json")
    insert_draw(None, 1, 11, 21, 31, 41, 5, "legacy_json")


def test_export_orders_dated_newest_first_then_undated_by_ball_values(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    _seed_draws()

    result = export_backup(
        draws_backup_file=tmp_path / "draws_backup.json",
        manifest_file=tmp_path / "backup_manifest.json",
    )

    records = json.loads(result.draws_backup_file.read_text(encoding="utf-8"))

    dates = [r["draw_date"] for r in records]
    assert dates == ["2022-06-15", "2020-01-01", None, None]

    # Undated rows ordered by their own ball values, not insertion order.
    undated = records[2:]
    assert [r["ball1"] for r in undated] == [1, 9]


def test_record_key_order_is_fixed(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    _seed_draws()

    result = export_backup(
        draws_backup_file=tmp_path / "draws_backup.json",
        manifest_file=tmp_path / "backup_manifest.json",
    )

    records = json.loads(result.draws_backup_file.read_text(encoding="utf-8"))
    expected_keys = ["draw_date", "ball1", "ball2", "ball3", "ball4", "ball5", "powerball", "source"]
    for record in records:
        assert list(record.keys()) == expected_keys


def test_draws_backup_has_no_generated_timestamp(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    _seed_draws()

    result = export_backup(
        draws_backup_file=tmp_path / "draws_backup.json",
        manifest_file=tmp_path / "backup_manifest.json",
    )

    raw_text = result.draws_backup_file.read_text(encoding="utf-8")
    assert "generated_at" not in raw_text


def test_draws_backup_uses_utf8_indent2_and_trailing_newline(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    _seed_draws()

    result = export_backup(
        draws_backup_file=tmp_path / "draws_backup.json",
        manifest_file=tmp_path / "backup_manifest.json",
    )

    raw_bytes = result.draws_backup_file.read_bytes()
    assert raw_bytes.endswith(b"\n")
    assert raw_bytes.decode("utf-8")  # doesn't raise
    assert b'"draw_date": ' in raw_bytes  # indent=2 style spacing present


def test_repeated_export_is_byte_identical_when_database_unchanged(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    _seed_draws()

    draws_file = tmp_path / "draws_backup.json"
    manifest_file = tmp_path / "backup_manifest.json"

    first = export_backup(draws_backup_file=draws_file, manifest_file=manifest_file)
    first_bytes = draws_file.read_bytes()

    second = export_backup(draws_backup_file=draws_file, manifest_file=manifest_file)
    second_bytes = draws_file.read_bytes()

    assert first_bytes == second_bytes
    assert first.draws_backup_hash == second.draws_backup_hash


def test_manifest_fields_are_correct(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    _seed_draws()

    result = export_backup(
        draws_backup_file=tmp_path / "draws_backup.json",
        manifest_file=tmp_path / "backup_manifest.json",
    )

    manifest = json.loads(result.manifest_file.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["total_draws"] == 4
    assert manifest["dated_draws"] == 2
    assert manifest["undated_draws"] == 2
    assert manifest["earliest_draw_date"] == "2020-01-01"
    assert manifest["latest_draw_date"] == "2022-06-15"
    assert manifest["latest_drawing"]["draw_date"] == "2022-06-15"
    assert manifest["latest_drawing"]["ball1"] == 10
    assert manifest["sha256_draws_backup"] == result.draws_backup_hash
    assert "generated_at_utc" in manifest


def test_manifest_with_only_undated_rows_has_null_dates(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    insert_draw(None, 1, 2, 3, 4, 5, 6, "legacy_json")

    result = export_backup(
        draws_backup_file=tmp_path / "draws_backup.json",
        manifest_file=tmp_path / "backup_manifest.json",
    )
    manifest = json.loads(result.manifest_file.read_text(encoding="utf-8"))

    assert manifest["earliest_draw_date"] is None
    assert manifest["latest_draw_date"] is None
    assert manifest["latest_drawing"] is None


def test_empty_database_exports_cleanly(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    result = export_backup(
        draws_backup_file=tmp_path / "draws_backup.json",
        manifest_file=tmp_path / "backup_manifest.json",
    )

    assert result.total_draws == 0
    assert json.loads(result.draws_backup_file.read_text(encoding="utf-8")) == []


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------

def _valid_record(draw_date="2020-01-01", balls=(1, 2, 3, 4, 5), powerball=6, source="test"):
    return {
        "draw_date": draw_date,
        "ball1": balls[0], "ball2": balls[1], "ball3": balls[2], "ball4": balls[3], "ball5": balls[4],
        "powerball": powerball, "source": source,
    }


def test_validate_export_passes_for_good_data():
    records = [_valid_record()]
    from data.backup_export import _serialize_draws_backup
    import hashlib

    draws_bytes = _serialize_draws_backup(records)
    manifest = _build_manifest(records, hashlib.sha256(draws_bytes).hexdigest())

    _validate_export(records, manifest, draws_bytes, db_total_count=1)  # must not raise


def test_validate_export_rejects_count_mismatch():
    records = [_valid_record()]
    manifest = _build_manifest(records, "irrelevant")

    with pytest.raises(BackupValidationError, match="does not match database count"):
        _validate_export(records, manifest, b"[]", db_total_count=2)


def test_validate_export_rejects_duplicate_records():
    records = [_valid_record(), _valid_record()]
    manifest = _build_manifest(records, "irrelevant")

    with pytest.raises(BackupValidationError, match="Duplicate draw record"):
        _validate_export(records, manifest, b"[]", db_total_count=2)


def test_validate_export_rejects_unsorted_white_balls():
    records = [_valid_record(balls=(5, 4, 3, 2, 1))]
    manifest = _build_manifest(records, "irrelevant")

    with pytest.raises(BackupValidationError, match="not sorted/unique"):
        _validate_export(records, manifest, b"[]", db_total_count=1)


def test_validate_export_rejects_out_of_range_white_ball():
    records = [_valid_record(balls=(1, 2, 3, 4, 99))]
    manifest = _build_manifest(records, "irrelevant")

    with pytest.raises(BackupValidationError, match="out of range"):
        _validate_export(records, manifest, b"[]", db_total_count=1)


def test_validate_export_rejects_out_of_range_powerball():
    records = [_valid_record(powerball=99)]
    manifest = _build_manifest(records, "irrelevant")

    with pytest.raises(BackupValidationError, match="out of range"):
        _validate_export(records, manifest, b"[]", db_total_count=1)


def test_validate_export_rejects_manifest_hash_mismatch():
    records = [_valid_record()]
    manifest = _build_manifest(records, "wronghash")

    with pytest.raises(BackupValidationError, match="SHA-256 does not match"):
        _validate_export(records, manifest, b"some bytes", db_total_count=1)
