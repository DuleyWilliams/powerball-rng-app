"""Export the current SQLite dataset for the React frontend and GitHub.

The legacy ``numbers`` array remains intact for backward compatibility.
Schema v2 adds metadata and dated records without changing the SQLite
source of truth or the deterministic backup-export format.
"""

import json
from datetime import datetime, timezone

from core.config import DATA_FILE
from data.repository import get_all_export_draws


SCHEMA_VERSION = 2


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_export_payload() -> dict:
    records = get_all_export_draws()
    dated_records = [record for record in records if record.draw_date is not None]
    latest = dated_records[0] if dated_records else None

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "total_draws": len(records),
        "dated_draws": len(dated_records),
        "undated_draws": len(records) - len(dated_records),
        "latest_draw_date": latest.draw_date.isoformat() if latest else None,
        "latest_drawing": (
            {
                "draw_date": latest.draw_date.isoformat(),
                "numbers": latest.balls,
            }
            if latest
            else None
        ),
        "draws": [
            {
                "draw_date": record.draw_date.isoformat() if record.draw_date else None,
                "numbers": record.balls,
                "source": record.source,
            }
            for record in records
        ],
        "numbers": [record.balls for record in records],
    }


def export_draws_to_json() -> None:
    payload = build_export_payload()
    DATA_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
