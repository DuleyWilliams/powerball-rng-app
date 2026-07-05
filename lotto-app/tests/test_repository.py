from datetime import date

from data import database, repository


def _use_temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_FILE", db_file)
    return db_file


def test_init_db_creates_table_and_indexes(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    database.init_db()

    with database.get_connection() as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='draws'"
        ).fetchone()
        indexes = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }

    assert table is not None
    for column in ["draw_date", "ball1", "ball2", "ball3", "ball4", "ball5", "powerball"]:
        assert f"idx_draws_{column}" in indexes


def test_insert_and_get_all_draws_orders_newest_first(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    repository.insert_draw(date(2020, 1, 1), 1, 2, 3, 4, 5, 6, "test")
    repository.insert_draw(date(2022, 1, 1), 7, 8, 9, 10, 11, 12, "test")

    draws = repository.get_all_draws()

    assert draws == [
        [7, 8, 9, 10, 11, 12],
        [1, 2, 3, 4, 5, 6],
    ]


def test_get_latest_draw_returns_none_when_empty(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    assert repository.get_latest_draw() is None


def test_get_latest_draw_returns_most_recent(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    repository.insert_draw(date(2020, 1, 1), 1, 2, 3, 4, 5, 6, "test")
    repository.insert_draw(date(2022, 1, 1), 7, 8, 9, 10, 11, 12, "test")

    assert repository.get_latest_draw() == [7, 8, 9, 10, 11, 12]


def test_draw_exists_matches_by_date(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    repository.insert_draw(date(2020, 1, 1), 1, 2, 3, 4, 5, 6, "test")

    assert repository.draw_exists(1, 2, 3, 4, 5, 6, date(2020, 1, 1)) is True
    # Same date, different numbers still counts as a clash on that date's slot.
    assert repository.draw_exists(9, 10, 11, 12, 13, 14, date(2020, 1, 1)) is True
    assert repository.draw_exists(1, 2, 3, 4, 5, 6, date(2021, 1, 1)) is False


def test_draw_exists_catches_dated_import_of_already_migrated_legacy_row(tmp_path, monkeypatch):
    # Regression: a legacy (undated) row migrated first, then the same
    # real-world draw arriving later with a known date, must still be
    # recognized as a duplicate — not inserted as a second row.
    _use_temp_db(tmp_path, monkeypatch)
    repository.insert_draw(None, 1, 2, 3, 4, 5, 6, "legacy_json")

    assert repository.draw_exists(1, 2, 3, 4, 5, 6, date(2020, 1, 1)) is True


def test_draw_exists_matches_by_numbers_when_date_unknown(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    repository.insert_draw(None, 1, 2, 3, 4, 5, 6, "legacy_json")

    assert repository.draw_exists(1, 2, 3, 4, 5, 6) is True
    assert repository.draw_exists(1, 2, 3, 4, 5, 7) is False


def test_database_statistics(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    stats_empty = repository.database_statistics()
    assert stats_empty.total_rows == 0
    assert stats_empty.latest_draw_date is None
    assert stats_empty.oldest_draw_date is None

    repository.insert_draw(date(2020, 1, 1), 1, 2, 3, 4, 5, 6, "test")
    repository.insert_draw(date(2022, 1, 1), 7, 8, 9, 10, 11, 12, "test")

    stats = repository.database_statistics()
    assert stats.total_rows == 2
    assert stats.latest_draw_date == date(2022, 1, 1)
    assert stats.oldest_draw_date == date(2020, 1, 1)
    assert stats.last_updated_at is not None
