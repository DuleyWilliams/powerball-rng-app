"""Generates a complete, portable, dated backup of the SQLite draws
table:

- draws_backup.json — every draw, deterministically ordered and
  formatted, with NO generated timestamp — so re-exporting an
  unchanged database produces byte-identical output. This is what
  makes "skip the GitHub commit when nothing changed" possible.
- backup_manifest.json — summary/integrity metadata, including the
  SHA-256 of draws_backup.json and a generated_at_utc timestamp (the
  only place a timestamp appears in this backup).

Both files are written locally on every call; whether either gets
pushed to GitHub is decided by the caller (cron_update.py) based on
whether their content actually changed.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from core.config import (
    BACKUP_MANIFEST_FILE,
    DRAWS_BACKUP_FILE,
    POWERBALL_MAX,
    POWERBALL_MIN,
    WHITE_BALL_MAX,
    WHITE_BALL_MIN,
)
from data.database import get_connection

SCHEMA_VERSION = 1


class BackupValidationError(Exception):
    """Raised when a freshly generated backup fails a post-export
    integrity check. Never written to disk in that state."""


@dataclass(frozen=True)
class BackupExportResult:
    draws_backup_file: Path
    manifest_file: Path
    total_draws: int
    draws_backup_hash: str


def _count_draws() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM draws").fetchone()
    return row["c"]


def _fetch_all_draw_rows() -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT draw_date, ball1, ball2, ball3, ball4, ball5, powerball, source FROM draws"
        ).fetchall()
    return [dict(row) for row in rows]


def _sort_rows(rows: list) -> list:
    """Known draw dates newest first; undated legacy rows last, ordered
    deterministically by their own ball values (not DB insertion
    order) so a from-scratch rebuild produces identical output."""
    dated = [row for row in rows if row["draw_date"] is not None]
    undated = [row for row in rows if row["draw_date"] is None]

    dated.sort(key=lambda row: row["draw_date"], reverse=True)
    undated.sort(key=lambda row: (
        row["ball1"], row["ball2"], row["ball3"], row["ball4"], row["ball5"], row["powerball"],
    ))

    return dated + undated


def _build_record(row: dict) -> dict:
    return {
        "draw_date": row["draw_date"],
        "ball1": row["ball1"],
        "ball2": row["ball2"],
        "ball3": row["ball3"],
        "ball4": row["ball4"],
        "ball5": row["ball5"],
        "powerball": row["powerball"],
        "source": row["source"],
    }


def _serialize_draws_backup(records: list) -> bytes:
    text = json.dumps(records, indent=2) + "\n"
    return text.encode("utf-8")


def _build_manifest(records: list, draws_backup_hash: str) -> dict:
    dated_records = [r for r in records if r["draw_date"] is not None]
    undated_records = [r for r in records if r["draw_date"] is None]

    earliest = min((r["draw_date"] for r in dated_records), default=None)
    latest = max((r["draw_date"] for r in dated_records), default=None)

    latest_drawing = None
    if dated_records:
        # dated_records is already sorted newest-first by _sort_rows().
        top = dated_records[0]
        latest_drawing = {
            "draw_date": top["draw_date"],
            "ball1": top["ball1"],
            "ball2": top["ball2"],
            "ball3": top["ball3"],
            "ball4": top["ball4"],
            "ball5": top["ball5"],
            "powerball": top["powerball"],
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "total_draws": len(records),
        "dated_draws": len(dated_records),
        "undated_draws": len(undated_records),
        "earliest_draw_date": earliest,
        "latest_draw_date": latest,
        "latest_drawing": latest_drawing,
        "sha256_draws_backup": draws_backup_hash,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _serialize_manifest(manifest: dict) -> bytes:
    text = json.dumps(manifest, indent=2) + "\n"
    return text.encode("utf-8")


def _validate_export(records: list, manifest: dict, draws_backup_bytes: bytes, db_total_count: int) -> None:
    if len(records) != db_total_count:
        raise BackupValidationError(
            f"Exported record count {len(records)} does not match database count {db_total_count}."
        )

    seen = set()
    for record in records:
        whites = (record["ball1"], record["ball2"], record["ball3"], record["ball4"], record["ball5"])
        powerball = record["powerball"]

        key = (record["draw_date"], whites, powerball)
        if key in seen:
            raise BackupValidationError(f"Duplicate draw record found: {key}")
        seen.add(key)

        if list(whites) != sorted(whites) or len(set(whites)) != len(whites):
            raise BackupValidationError(f"White balls not sorted/unique: {whites}")

        if not all(WHITE_BALL_MIN <= n <= WHITE_BALL_MAX for n in whites):
            raise BackupValidationError(f"White ball out of range: {whites}")

        if not (POWERBALL_MIN <= powerball <= POWERBALL_MAX):
            raise BackupValidationError(f"Powerball out of range: {powerball}")

    recomputed_hash = hashlib.sha256(draws_backup_bytes).hexdigest()
    if recomputed_hash != manifest["sha256_draws_backup"]:
        raise BackupValidationError("Manifest SHA-256 does not match the archive content.")


def export_backup(
    draws_backup_file: Path = DRAWS_BACKUP_FILE,
    manifest_file: Path = BACKUP_MANIFEST_FILE,
) -> BackupExportResult:
    draws_backup_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.parent.mkdir(parents=True, exist_ok=True)

    db_total_count = _count_draws()
    rows = _fetch_all_draw_rows()
    records = [_build_record(row) for row in _sort_rows(rows)]

    draws_backup_bytes = _serialize_draws_backup(records)
    draws_backup_hash = hashlib.sha256(draws_backup_bytes).hexdigest()

    manifest = _build_manifest(records, draws_backup_hash)

    _validate_export(records, manifest, draws_backup_bytes, db_total_count)

    manifest_bytes = _serialize_manifest(manifest)

    draws_backup_file.write_bytes(draws_backup_bytes)
    manifest_file.write_bytes(manifest_bytes)

    return BackupExportResult(
        draws_backup_file=draws_backup_file,
        manifest_file=manifest_file,
        total_draws=db_total_count,
        draws_backup_hash=draws_backup_hash,
    )


if __name__ == "__main__":
    result = export_backup()
    print(f"Exported {result.total_draws} draws to {result.draws_backup_file}")
    print(f"Manifest written to {result.manifest_file}")
    print(f"draws_backup.json SHA-256: {result.draws_backup_hash}")
