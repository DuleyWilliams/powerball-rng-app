"""ETL transform stage: reshape a raw extracted record into a canonical
TransformedDraw. Never rejects data — parsing failures are recorded as
None fields / flags for validate.py to decide on.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

RawRecord = dict[str, Any]


@dataclass
class TransformedDraw:
    ball1: Optional[int]
    ball2: Optional[int]
    ball3: Optional[int]
    ball4: Optional[int]
    ball5: Optional[int]
    powerball: Optional[int]
    draw_date: Optional[date]
    date_parse_error: bool
    source: str
    raw: RawRecord = field(default_factory=dict)

    def balls(self) -> list[Optional[int]]:
        return [self.ball1, self.ball2, self.ball3, self.ball4, self.ball5]


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Optional[str]) -> tuple[Optional[date], bool]:
    """Returns (parsed_date, had_parse_error)."""
    if value is None:
        return None, False

    try:
        # Handles both plain "2010-02-03" and Socrata's
        # "2010-02-03T00:00:00.000" timestamp strings.
        return date.fromisoformat(value.split("T")[0]), False
    except (ValueError, AttributeError):
        return None, True


def transform_record(raw: RawRecord) -> TransformedDraw:
    white_balls = [_safe_int(n) for n in raw.get("white_balls", [])]

    # Pad/truncate to exactly 5 slots so downstream code always sees 5 balls.
    white_balls = (white_balls + [None] * 5)[:5]

    if all(n is not None for n in white_balls):
        white_balls = sorted(white_balls)

    draw_date, date_parse_error = _parse_date(raw.get("draw_date"))

    return TransformedDraw(
        ball1=white_balls[0],
        ball2=white_balls[1],
        ball3=white_balls[2],
        ball4=white_balls[3],
        ball5=white_balls[4],
        powerball=_safe_int(raw.get("powerball")),
        draw_date=draw_date,
        date_parse_error=date_parse_error,
        source=raw.get("source", "unknown"),
        raw=raw,
    )
