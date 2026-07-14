#!/usr/bin/env python3
"""IONOS cron updater.

Fetches the latest TN Powerball drawing and persists it through the same
ETL/validation pipeline the Streamlit app uses (services.update_service),
then exports numbers.json as a backup. Designed to run under cron on
IONOS shared hosting via run_cron_update.sh.

Deliberately dependency-light: only requests/beautifulsoup4 plus the
stdlib. Never imports streamlit, plotly, scipy, pandas, or app.py — see
requirements-cron.txt.

Exit codes:
    0 - success (new drawing inserted), no new drawing, or --dry-run
    1 - failure (fetch/validation/database error)
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

from services.update_service import update_numbers  # noqa: E402  (needs sys.path set up first)


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

    return 0


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
