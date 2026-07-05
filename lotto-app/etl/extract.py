"""ETL extract stage: pull raw records from a source into a common shape
— {"white_balls": [...], "powerball": ..., "draw_date": ..., "source": ...}
— without interpreting or validating the values. That's transform/validate's job.
"""

import json
from pathlib import Path
from typing import Iterator

import requests

from core.config import NY_OPEN_DATA_URL, SOURCE_LEGACY_JSON, SOURCE_NY_OPEN_DATA
from etl.transform import RawRecord


def extract_from_json(path: Path) -> Iterator[RawRecord]:
    """Legacy numbers.json entries have no recorded draw date."""
    if not path.exists():
        return

    data = json.loads(path.read_text(encoding="utf-8"))

    for entry in data.get("numbers", []):
        yield {
            "white_balls": entry[:5],
            "powerball": entry[5] if len(entry) > 5 else None,
            "draw_date": None,
            "source": SOURCE_LEGACY_JSON,
        }


def extract_from_ny_open_data(page_size: int = 1000) -> Iterator[RawRecord]:
    """Paginates through the NY State Open Data Powerball dataset
    (Socrata API), oldest first.
    """
    offset = 0

    while True:
        response = requests.get(
            NY_OPEN_DATA_URL,
            params={"$order": "draw_date ASC", "$limit": page_size, "$offset": offset},
            timeout=30,
        )
        response.raise_for_status()
        page = response.json()

        if not page:
            return

        for row in page:
            numbers = row.get("winning_numbers", "").split()

            yield {
                "white_balls": numbers[:5],
                "powerball": numbers[5] if len(numbers) > 5 else None,
                "draw_date": row.get("draw_date"),
                "source": SOURCE_NY_OPEN_DATA,
            }

        offset += page_size
