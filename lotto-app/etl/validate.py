"""ETL validate stage: pure business-rule validation of a TransformedDraw.

Does not touch the database — "duplicate row" detection against
existing data happens in load.py, since that requires a repository
lookup. Everything checkable from the record alone lives here.
"""

from dataclasses import dataclass
from datetime import date

from core.config import WHITE_BALL_MIN, WHITE_BALL_MAX, POWERBALL_MIN, POWERBALL_MAX
from core.patterns import has_duplicate_white_balls
from etl.transform import TransformedDraw


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    reasons: list[str]


def validate_draw(draw: TransformedDraw, *, require_date: bool = True) -> ValidationResult:
    reasons: list[str] = []
    balls = draw.balls()

    if any(ball is None for ball in balls) or draw.powerball is None:
        reasons.append("missing numbers")
    else:
        if has_duplicate_white_balls(balls):
            reasons.append("duplicate white balls")

        if not all(WHITE_BALL_MIN <= ball <= WHITE_BALL_MAX for ball in balls):
            reasons.append("invalid white ball range")

        if not (POWERBALL_MIN <= draw.powerball <= POWERBALL_MAX):
            reasons.append("invalid powerball range")

    if draw.date_parse_error:
        reasons.append("invalid date")
    elif draw.draw_date is None:
        if require_date:
            reasons.append("missing date")
    elif draw.draw_date > date.today():
        reasons.append("future date")

    return ValidationResult(is_valid=not reasons, reasons=reasons)
