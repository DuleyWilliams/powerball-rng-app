"""Historical Powerball importer.

Pulls every drawing from the NY State Open Data Powerball dataset
(the official public archive, 2010-present) and loads it into SQLite
through the same extract -> transform -> validate -> load pipeline used
by the daily updater and the numbers.json migration.

Drawings before the Oct 2015 game-format change (white balls 1-59,
powerball 1-35) are intentionally rejected during validation, since
they describe a different game than the 5/69 + 1/26 format this app
models — see core.config.NY_OPEN_DATA_URL.

Usage:
    python import_history.py
"""

import logging
from dataclasses import dataclass
from typing import Iterable

from data.database import init_db
from data.repository import database_statistics
from etl.extract import extract_from_ny_open_data
from etl.load import load_draw
from etl.transform import RawRecord, transform_record

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImportSummary:
    processed: int
    imported: int
    skipped: int
    failed: int


def run_import(records: Iterable[RawRecord], *, require_date: bool = True, progress_every: int = 200) -> ImportSummary:
    """Runs every record through transform -> load, reporting progress."""

    processed = imported = skipped = failed = 0

    for raw in records:
        processed += 1
        transformed = transform_record(raw)
        outcome = load_draw(transformed, require_date=require_date)

        if outcome.status == "imported":
            imported += 1
        elif outcome.status == "skipped":
            skipped += 1
        else:
            failed += 1

        if progress_every and processed % progress_every == 0:
            print(f"Processed {processed} records (imported={imported}, skipped={skipped}, failed={failed})...")

    return ImportSummary(processed=processed, imported=imported, skipped=skipped, failed=failed)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    init_db()

    summary = run_import(extract_from_ny_open_data(), require_date=True)
    stats = database_statistics()

    print()
    print("=== Historical Import Summary ===")
    print(f"Imported: {summary.imported}")
    print(f"Skipped:  {summary.skipped}")
    print(f"Failed:   {summary.failed}")
    print(f"Newest draw: {stats.latest_draw_date}")
    print(f"Oldest draw: {stats.oldest_draw_date}")
    print(f"Total database rows: {stats.total_rows}")


if __name__ == "__main__":
    main()
