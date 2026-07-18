#!/usr/bin/env python3
"""IONOS cron updater.

Fetches the latest TN Powerball drawing and persists it through the same
ETL/validation pipeline the Streamlit app uses (services.update_service),
then exports numbers.json as a backup. Designed to run under cron on
IONOS shared hosting via run_cron_update.sh.

Deliberately dependency-light: only requests/beautifulsoup4 plus the
stdlib. Never imports streamlit, plotly, scipy, pandas, or app.py — see
requirements-cron.txt.

After a successful database update, it also:
  - takes a private, IONOS-only SQLite snapshot (never synced to GitHub)
    when a new drawing was actually inserted, retaining the newest 4
  - regenerates the portable backup files (backups/draws_backup.json,
    backups/backup_manifest.json)
  - synchronizes numbers.json, draws_backup.json, and backup_manifest.json
    to GitHub (services.github_sync_service) via the REST Contents API —
    no git/subprocess/SSH involved, and no commit for a file whose
    content hasn't actually changed.

Exit codes:
    0 - success (new drawing inserted), no new drawing, or --dry-run,
        with no partial failures
    1 - failure (fetch/validation/database error), OR the database
        update succeeded but something in the backup/sync pipeline
        (snapshot rotation, backup export, or any GitHub sync) failed
    2 - another run already holds the lock
"""

import argparse
import fcntl
import json
import logging
import sys
import time
from pathlib import Path

# Absolute, cwd-independent: works no matter where cron invokes this from.
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

LOG_DIR = APP_DIR / "logs"
LOG_FILE = LOG_DIR / "cron_update.log"
LOCK_FILE = LOG_DIR / "cron_update.lock"

from core.config import (  # noqa: E402  (needs sys.path set up first)
    DATA_FILE,
    DRAWS_BACKUP_FILE,
    BACKUP_MANIFEST_FILE,
    NUMBERS_JSON_GITHUB_PATH,
    DRAWS_BACKUP_GITHUB_PATH,
    BACKUP_MANIFEST_GITHUB_PATH,
    COMMIT_MESSAGE_NUMBERS_JSON,
    COMMIT_MESSAGE_DRAWS_BACKUP,
    COMMIT_MESSAGE_BACKUP_MANIFEST,
    SNAPSHOT_RETENTION_COUNT,
)
from data.backup_export import export_backup
from data.snapshot import create_and_rotate_snapshot
from services.update_service import update_numbers  # noqa: E402
from services.github_sync_service import sync_file, GithubSyncError  # noqa: E402


class LockHeldError(Exception):
    pass


class _JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _build_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("cron_update")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Re-running main() in the same process (e.g. tests) would otherwise
    # stack duplicate handlers pointed at whatever LOG_FILE was current
    # at attach-time.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(_JsonLogFormatter())
    logger.addHandler(handler)

    # services.* modules (e.g. github_sync_service) log via their own
    # __name__-based logger, not "cron_update" — attach the same handler
    # so their structured messages land in the same cron log file.
    services_logger = logging.getLogger("services")
    services_logger.setLevel(logging.INFO)
    for handler_ in list(services_logger.handlers):
        services_logger.removeHandler(handler_)
        handler_.close()
    services_logger.addHandler(handler)

    return logger


def _acquire_lock():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    lock_file = open(LOCK_FILE, "a+")

    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        raise LockHeldError(f"Another run already holds the lock: {LOCK_FILE}")

    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(str(time.time()))
    lock_file.flush()

    return lock_file


def _release_lock(lock_file) -> None:
    try:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
    finally:
        lock_file.close()


def run(logger: logging.Logger, dry_run: bool = False) -> int:
    if dry_run:
        logger.info("Dry run: locking, logging, and path resolution verified; no fetch performed.")
        return 0

    try:
        result = update_numbers()
    except Exception as error:
        logger.error("Cron update failed: %s", error, exc_info=True)
        return 1

    if result["updated"]:
        logger.info("New drawing inserted: %s", result["latest"])
    else:
        logger.info("No new drawing: %s", result["message"])

    # Everything below is best-effort: each step is attempted
    # independently so one failure (e.g. GitHub being briefly
    # unreachable) doesn't skip an otherwise-successful private
    # snapshot, or vice versa. Any failure here is a *partial* failure
    # — the database update itself already succeeded — and is
    # aggregated into a single exit-code-1 decision at the end.
    had_partial_failure = False

    # Private SQLite snapshot — IONOS-only, never synced to GitHub, and
    # only taken when a new drawing was actually inserted.
    if result["updated"]:
        try:
            snapshot_path, removed = create_and_rotate_snapshot()
            logger.info(
                "Private snapshot created: %s (retained newest %d, removed %d)",
                snapshot_path.name, SNAPSHOT_RETENTION_COUNT, len(removed),
            )
        except Exception as error:
            logger.error("Private snapshot rotation failed: %s", error, exc_info=True)
            had_partial_failure = True

    # Regenerate the portable backup files. If this fails, numbers.json
    # can still be synced independently below — only the archive/
    # manifest sync gets skipped.
    backup_export_ok = True
    try:
        export_backup()
    except Exception as error:
        logger.error("Backup export failed: %s", error, exc_info=True)
        backup_export_ok = False
        had_partial_failure = True

    sync_targets = [(DATA_FILE, NUMBERS_JSON_GITHUB_PATH, COMMIT_MESSAGE_NUMBERS_JSON, "numbers.json")]
    if backup_export_ok:
        sync_targets.append((DRAWS_BACKUP_FILE, DRAWS_BACKUP_GITHUB_PATH, COMMIT_MESSAGE_DRAWS_BACKUP, "draws_backup.json"))

    draws_backup_changed = False

    for local_path, github_path, commit_message, label in sync_targets:
        try:
            sync_result = sync_file(local_path, github_path, commit_message)
        except GithubSyncError:
            # sync_file() already logged github_sync_failed with a safe
            # (token-free) message.
            had_partial_failure = True
            continue

        if sync_result.changed:
            logger.info("GitHub %s updated: commit %s", label, sync_result.commit_sha)
            if label == "draws_backup.json":
                draws_backup_changed = True

    # The manifest's own bytes always differ run-to-run (it embeds
    # generated_at_utc), so a plain byte comparison against GitHub would
    # create a commit every single day even when the underlying data is
    # unchanged. Instead, only sync it when draws_backup.json itself
    # actually changed — driven by draws_backup.json's real byte
    # comparison against GitHub above, which is the true signal for
    # "did the draw data change."
    if backup_export_ok and draws_backup_changed:
        try:
            manifest_result = sync_file(BACKUP_MANIFEST_FILE, BACKUP_MANIFEST_GITHUB_PATH, COMMIT_MESSAGE_BACKUP_MANIFEST)
            if manifest_result.changed:
                logger.info("GitHub backup manifest updated: commit %s", manifest_result.commit_sha)
        except GithubSyncError:
            had_partial_failure = True

    return 1 if had_partial_failure else 0


def parse_args(argv):
    parser = argparse.ArgumentParser(description="IONOS cron updater for the Powerball dataset.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify locking/logging/path resolution without fetching or writing data.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    logger = _build_logger()

    try:
        lock_file = _acquire_lock()
    except LockHeldError as error:
        logger.warning(str(error))
        return 2

    try:
        return run(logger, dry_run=args.dry_run)
    except Exception:
        logger.error("Unexpected error in cron_update", exc_info=True)
        return 1
    finally:
        _release_lock(lock_file)


if __name__ == "__main__":
    sys.exit(main())
