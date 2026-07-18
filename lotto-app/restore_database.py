"""Rebuilds lotto-app/database.db from backups/draws_backup.json, using
the same extract -> transform -> validate -> load pipeline as the
historical importer and the numbers.json migration.

Refuses to overwrite an existing database unless --force is given —
this is a destructive rebuild-from-backup, not a merge.

Usage:
    python restore_database.py [--force] [--backup-file PATH]
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from core.config import DRAWS_BACKUP_FILE
from data import database as database_module
from data.database import init_db
from data.repository import database_statistics
from etl.extract import extract_from_draws_backup
from etl.load import load_draw
from etl.transform import transform_record


class RestoreError(Exception):
    pass


@dataclass(frozen=True)
class RestoreSummary:
    imported: int
    skipped: int
    failed: int
    total_rows: int


def restore_from_backup(backup_file: Path, force: bool = False) -> RestoreSummary:
    db_file = database_module.DB_FILE

    if db_file.exists():
        if not force:
            raise RestoreError(f"Database already exists at {db_file}. Use --force to overwrite.")
        db_file.unlink()

    init_db()

    imported = skipped = failed = 0

    for raw in extract_from_draws_backup(backup_file):
        transformed = transform_record(raw)
        outcome = load_draw(transformed, require_date=False)

        if outcome.status == "imported":
            imported += 1
        elif outcome.status == "skipped":
            skipped += 1
        else:
            failed += 1

    stats = database_statistics()

    return RestoreSummary(imported=imported, skipped=skipped, failed=failed, total_rows=stats.total_rows)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Rebuild database.db from backups/draws_backup.json.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing database.db.")
    parser.add_argument(
        "--backup-file", type=Path, default=None,
        help="Path to draws_backup.json (default: lotto-app/backups/draws_backup.json).",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    backup_file = args.backup_file if args.backup_file is not None else DRAWS_BACKUP_FILE

    if not backup_file.exists():
        print(f"Backup file not found: {backup_file}", file=sys.stderr)
        return 1

    try:
        summary = restore_from_backup(backup_file, force=args.force)
    except RestoreError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(f"Restore complete: imported={summary.imported} skipped={summary.skipped} failed={summary.failed}")
    print(f"Total rows in database: {summary.total_rows}")

    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
