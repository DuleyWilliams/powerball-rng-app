"""ETL load stage: validate, dedupe against the repository, and persist.

The only ETL module that touches the database — extract/transform/validate
are all pure functions operating on plain data.
"""

import logging
from dataclasses import dataclass, field
from typing import Literal

from data.repository import draw_exists, insert_draw
from etl.transform import TransformedDraw
from etl.validate import validate_draw

logger = logging.getLogger(__name__)

LoadStatus = Literal["imported", "skipped", "failed"]


@dataclass(frozen=True)
class LoadOutcome:
    status: LoadStatus
    reasons: list[str] = field(default_factory=list)


def load_draw(draw: TransformedDraw, *, require_date: bool = True) -> LoadOutcome:
    result = validate_draw(draw, require_date=require_date)

    if not result.is_valid:
        logger.warning(
            "Rejected draw from %s (%s): %s",
            draw.source, draw.raw, ", ".join(result.reasons),
        )
        return LoadOutcome(status="failed", reasons=result.reasons)

    if draw_exists(draw.ball1, draw.ball2, draw.ball3, draw.ball4, draw.ball5, draw.powerball, draw.draw_date):
        logger.info("Skipped duplicate draw from %s: %s", draw.source, draw.raw)
        return LoadOutcome(status="skipped")

    insert_draw(draw.draw_date, draw.ball1, draw.ball2, draw.ball3, draw.ball4, draw.ball5, draw.powerball, draw.source)
    return LoadOutcome(status="imported")
