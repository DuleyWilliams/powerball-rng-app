from data import database
from import_history import run_import


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "test.db")


def test_run_import_counts_imported_skipped_and_failed(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    records = [
        {"white_balls": [1, 2, 3, 4, 5], "powerball": 6, "draw_date": "2020-01-01", "source": "data.ny.gov"},
        {"white_balls": [7, 8, 9, 10, 11], "powerball": 12, "draw_date": "2020-01-04", "source": "data.ny.gov"},
        {"white_balls": [7, 8, 9, 10, 11], "powerball": 12, "draw_date": "2020-01-04", "source": "data.ny.gov"},  # duplicate
        {"white_balls": [1, 2, 3, 4, 5], "powerball": 99, "draw_date": "2020-01-08", "source": "data.ny.gov"},  # invalid powerball
    ]

    summary = run_import(records, require_date=True, progress_every=0)

    assert summary.processed == 4
    assert summary.imported == 2
    assert summary.skipped == 1
    assert summary.failed == 1


def test_run_import_requires_date_for_historical_source(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    records = [
        {"white_balls": [1, 2, 3, 4, 5], "powerball": 6, "draw_date": None, "source": "data.ny.gov"},
    ]

    summary = run_import(records, require_date=True, progress_every=0)

    assert summary.imported == 0
    assert summary.failed == 1
