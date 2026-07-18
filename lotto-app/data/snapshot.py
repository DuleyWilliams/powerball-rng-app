"""Private, IONOS-only SQLite snapshot rotation.

These snapshots are a disaster-recovery convenience for the server
operator only — never synchronized to GitHub (see .gitignore) and
never referenced by the Streamlit app or any GitHub-facing code path.

Uses sqlite3.Connection.backup() (the SQLite Online Backup API), not a
raw file copy, so a snapshot is never taken mid-write.
"""

import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional

from core.config import PRIVATE_BACKUPS_DIR, SNAPSHOT_RETENTION_COUNT
from data import database as database_module

_SNAPSHOT_PREFIX = "database-"
_SNAPSHOT_SUFFIX = ".sqlite3"


def _snapshot_filename(snapshot_date: date) -> str:
    return f"{_SNAPSHOT_PREFIX}{snapshot_date.strftime('%Y%m%d')}{_SNAPSHOT_SUFFIX}"


def create_snapshot(
    source_db_file: Optional[Path] = None,
    private_backups_dir: Path = PRIVATE_BACKUPS_DIR,
    snapshot_date: Optional[date] = None,
) -> Path:
    """Copies the live database via SQLite's own backup API into
    private_backups_dir, named database-YYYYMMDD.sqlite3. A second call
    on the same calendar date overwrites that date's snapshot."""
    if source_db_file is None:
        source_db_file = database_module.DB_FILE
    if snapshot_date is None:
        snapshot_date = date.today()

    private_backups_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = private_backups_dir / _snapshot_filename(snapshot_date)

    source_conn = sqlite3.connect(source_db_file)
    try:
        dest_conn = sqlite3.connect(snapshot_path)
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        source_conn.close()

    return snapshot_path


def rotate_snapshots(
    private_backups_dir: Path = PRIVATE_BACKUPS_DIR,
    retention_count: int = SNAPSHOT_RETENTION_COUNT,
) -> list:
    """Keeps only the newest retention_count snapshots (by filename,
    which sorts chronologically since it embeds YYYYMMDD); deletes the
    rest. Returns the list of removed paths."""
    if not private_backups_dir.exists():
        return []

    snapshots = sorted(private_backups_dir.glob(f"{_SNAPSHOT_PREFIX}*{_SNAPSHOT_SUFFIX}"))
    removed = []

    while len(snapshots) > retention_count:
        oldest = snapshots.pop(0)
        oldest.unlink()
        removed.append(oldest)

    return removed


def create_and_rotate_snapshot(
    source_db_file: Optional[Path] = None,
    private_backups_dir: Path = PRIVATE_BACKUPS_DIR,
    retention_count: int = SNAPSHOT_RETENTION_COUNT,
) -> tuple:
    """Returns (new_snapshot_path, removed_paths)."""
    snapshot_path = create_snapshot(source_db_file=source_db_file, private_backups_dir=private_backups_dir)
    removed = rotate_snapshots(private_backups_dir=private_backups_dir, retention_count=retention_count)
    return snapshot_path, removed
