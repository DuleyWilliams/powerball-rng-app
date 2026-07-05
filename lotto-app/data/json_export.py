"""Exports the current SQLite dataset to numbers.json as a human-readable
backup snapshot. SQLite remains the primary data source; this file is
not read back in by the running application.
"""

import json

from core.config import DATA_FILE
from data.repository import get_all_draws


def export_draws_to_json() -> None:
    draws = get_all_draws()
    DATA_FILE.write_text(json.dumps({"numbers": draws}, indent=2), encoding="utf-8")
