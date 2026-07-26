"""Dry-run-first repair of undated draws using NY Open Data history."""

from dataclasses import dataclass
from datetime import date
import re
from typing import Optional

import requests

from core.config import NY_OPEN_DATA_URL, SOURCE_NY_OPEN_DATA
from data.json_export import export_draws_to_json
from data.repository import Draw, assign_date_to_undated_draw, get_undated_export_draws


@dataclass(frozen=True)
class DateRepairResult:
    undated_count: int
    unique_matches: int
    repaired_count: int
    ambiguous_count: int
    unmatched_count: int


def _parse_history_row(row: dict) -> Optional[tuple[date, Draw]]:
    raw_date = row.get("draw_date")
    raw_numbers = row.get("winning_numbers")
    if not raw_date or not raw_numbers:
        return None

    try:
        draw_date = date.fromisoformat(str(raw_date).split("T")[0])
    except ValueError:
        return None

    numbers = [int(value) for value in re.findall(r"\d+", str(raw_numbers))]
    if len(numbers) != 6:
        return None

    return draw_date, sorted(numbers[:5]) + [numbers[5]]


def fetch_official_history() -> list[tuple[date, Draw]]:
    response = requests.get(
        NY_OPEN_DATA_URL,
        params={
            "$select": "draw_date,winning_numbers",
            "$order": "draw_date DESC",
            "$limit": 5000,
        },
        headers={"User-Agent": "PowerballRngDataRepair/1.0"},
        timeout=30,
    )
    response.raise_for_status()

    parsed = [_parse_history_row(row) for row in response.json()]
    return [record for record in parsed if record is not None]


def repair_undated_draw_dates(*, apply: bool = False) -> DateRepairResult:
    undated = get_undated_export_draws()
    history = fetch_official_history()

    dates_by_numbers: dict[tuple[int, ...], set[date]] = {}
    for draw_date, balls in history:
        dates_by_numbers.setdefault(tuple(balls), set()).add(draw_date)

    unique_matches: list[tuple[date, Draw]] = []
    ambiguous_count = 0
    unmatched_count = 0

    for record in undated:
        matches = dates_by_numbers.get(tuple(record.balls), set())
        if len(matches) == 1:
            unique_matches.append((next(iter(matches)), record.balls))
        elif len(matches) > 1:
            ambiguous_count += 1
        else:
            unmatched_count += 1

    repaired_count = 0
    if apply:
        for draw_date, balls in unique_matches:
            if assign_date_to_undated_draw(draw_date, balls, SOURCE_NY_OPEN_DATA):
                repaired_count += 1
        if repaired_count:
            export_draws_to_json()

    return DateRepairResult(
        undated_count=len(undated),
        unique_matches=len(unique_matches),
        repaired_count=repaired_count,
        ambiguous_count=ambiguous_count,
        unmatched_count=unmatched_count,
    )
