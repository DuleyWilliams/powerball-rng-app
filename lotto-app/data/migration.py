"""One-time (but idempotent) migration of the legacy numbers.json file
into SQLite. Safe to call on every app startup.
"""

from dataclasses import dataclass

from core.config import DATA_FILE
from data.database import init_db
from etl.extract import extract_from_json
from etl.load import load_draw
from etl.transform import transform_record


@dataclass(frozen=True)
class MigrationSummary:
    source_found: bool
    migrated: int
    skipped: int
    failed: int


def migrate_json_to_sqlite() -> MigrationSummary:
    init_db()

    if not DATA_FILE.exists():
        return MigrationSummary(source_found=False, migrated=0, skipped=0, failed=0)

    migrated = skipped = failed = 0

    for raw in extract_from_json(DATA_FILE):
        transformed = transform_record(raw)
        # Legacy numbers.json entries predate date tracking entirely,
        # so a missing draw_date is expected here, not a rejection.
        outcome = load_draw(transformed, require_date=False)

        if outcome.status == "imported":
            migrated += 1
        elif outcome.status == "skipped":
            skipped += 1
        else:
            failed += 1

    return MigrationSummary(source_found=True, migrated=migrated, skipped=skipped, failed=failed)
