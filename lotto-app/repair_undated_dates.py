#!/usr/bin/env python3
"""Preview or apply authoritative dates to legacy undated draw rows."""

import argparse
import json
from dataclasses import asdict

from services.date_repair_service import repair_undated_draw_dates


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair undated Powerball rows from NY Open Data.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write uniquely matched dates to SQLite. Without this flag, only report the repair plan.",
    )
    args = parser.parse_args()

    result = repair_undated_draw_dates(apply=args.apply)
    payload = {"mode": "apply" if args.apply else "dry-run", **asdict(result)}
    print(json.dumps(payload, indent=2))

    if args.apply and result.repaired_count != result.unique_matches:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
