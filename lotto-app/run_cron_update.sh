#!/bin/bash
# IONOS cron entry point. Add this exact path as the cron command:
#   /kunden/homepages/8/d230686207/htdocs/powerball-cron/powerball-rng-app/lotto-app/run_cron_update.sh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/cron_update.log"

mkdir -p "$LOG_DIR"

if [ -x "$SCRIPT_DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"
else
    PYTHON_BIN="python3"
fi

# Run with -e temporarily off so a non-zero exit doesn't abort the script
# before we can capture and propagate the real exit code.
set +e
"$PYTHON_BIN" "$SCRIPT_DIR/cron_update.py" "$@" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
set -e

exit "$EXIT_CODE"
