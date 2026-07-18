import sqlite3
from datetime import date

from data.repository import insert_draw
from data.snapshot import create_snapshot, rotate_snapshots


def _make_source_db(tmp_path):
    db_file = tmp_path / "source.db"
    conn = sqlite3.connect(db_file)
    conn.execute(
        "CREATE TABLE draws (id INTEGER PRIMARY KEY, ball1 INTEGER, draw_date TEXT)"
    )
    conn.execute("INSERT INTO draws (ball1, draw_date) VALUES (7, '2020-01-01')")
    conn.commit()
    conn.close()
    return db_file


def test_create_snapshot_copies_data_via_sqlite_backup_api(tmp_path):
    source_db = _make_source_db(tmp_path)
    private_dir = tmp_path / "private_backups"

    snapshot_path = create_snapshot(
        source_db_file=source_db,
        private_backups_dir=private_dir,
        snapshot_date=date(2026, 7, 15),
    )

    assert snapshot_path.name == "database-20260715.sqlite3"
    assert snapshot_path.exists()

    conn = sqlite3.connect(snapshot_path)
    row = conn.execute("SELECT ball1, draw_date FROM draws").fetchone()
    conn.close()

    assert row == (7, "2020-01-01")


def test_create_snapshot_on_same_date_overwrites_that_days_file(tmp_path):
    source_db = _make_source_db(tmp_path)
    private_dir = tmp_path / "private_backups"

    first = create_snapshot(source_db_file=source_db, private_backups_dir=private_dir, snapshot_date=date(2026, 7, 15))

    conn = sqlite3.connect(source_db)
    conn.execute("INSERT INTO draws (ball1, draw_date) VALUES (99, '2020-02-02')")
    conn.commit()
    conn.close()

    second = create_snapshot(source_db_file=source_db, private_backups_dir=private_dir, snapshot_date=date(2026, 7, 15))

    assert first == second
    conn = sqlite3.connect(second)
    count = conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
    conn.close()
    assert count == 2  # reflects the updated source, not the first snapshot


def test_rotate_snapshots_keeps_only_newest_four(tmp_path):
    private_dir = tmp_path / "private_backups"
    private_dir.mkdir()

    filenames = [
        "database-20260101.sqlite3",
        "database-20260102.sqlite3",
        "database-20260103.sqlite3",
        "database-20260104.sqlite3",
        "database-20260105.sqlite3",
        "database-20260106.sqlite3",
    ]
    for name in filenames:
        (private_dir / name).write_bytes(b"fake sqlite content")

    removed = rotate_snapshots(private_backups_dir=private_dir, retention_count=4)

    remaining = sorted(p.name for p in private_dir.glob("database-*.sqlite3"))
    assert remaining == [
        "database-20260103.sqlite3",
        "database-20260104.sqlite3",
        "database-20260105.sqlite3",
        "database-20260106.sqlite3",
    ]
    assert sorted(p.name for p in removed) == ["database-20260101.sqlite3", "database-20260102.sqlite3"]


def test_rotate_snapshots_no_op_when_under_retention_limit(tmp_path):
    private_dir = tmp_path / "private_backups"
    private_dir.mkdir()
    (private_dir / "database-20260101.sqlite3").write_bytes(b"x")

    removed = rotate_snapshots(private_backups_dir=private_dir, retention_count=4)

    assert removed == []
    assert (private_dir / "database-20260101.sqlite3").exists()


def test_rotate_snapshots_handles_missing_directory(tmp_path):
    missing_dir = tmp_path / "does_not_exist"
    assert rotate_snapshots(private_backups_dir=missing_dir, retention_count=4) == []
