"""Single source of truth for ticket pattern analysis.

Previously this counting logic (odd/even, low/high, sum, consecutive
pairs) was duplicated with identical behavior across analytics.py,
filters.py, and condensation.py. It now lives here once.
"""

from dataclasses import dataclass

from core.config import LOW_HIGH_SPLIT, FILTER_SUM_MIN, FILTER_SUM_MAX, MAX_CONSECUTIVE_PAIRS


@dataclass(frozen=True)
class TicketPattern:
    odd_count: int
    even_count: int
    low_count: int
    high_count: int
    white_sum: int
    consecutive_pairs: int


def analyze_pattern(white_balls: list[int]) -> TicketPattern:
    sorted_whites = sorted(white_balls)

    odd_count = sum(1 for n in sorted_whites if n % 2 != 0)
    low_count = sum(1 for n in sorted_whites if n <= LOW_HIGH_SPLIT)

    consecutive_pairs = sum(
        1 for a, b in zip(sorted_whites, sorted_whites[1:])
        if b - a == 1
    )

    return TicketPattern(
        odd_count=odd_count,
        even_count=len(sorted_whites) - odd_count,
        low_count=low_count,
        high_count=len(sorted_whites) - low_count,
        white_sum=sum(sorted_whites),
        consecutive_pairs=consecutive_pairs,
    )


def odd_even_label(pattern: TicketPattern) -> str:
    return f"{pattern.odd_count} odd / {pattern.even_count} even"


def low_high_label(pattern: TicketPattern) -> str:
    return f"{pattern.low_count} low / {pattern.high_count} high"


def has_duplicate_white_balls(white_balls: list[int]) -> bool:
    return len(set(white_balls)) != len(white_balls)


def is_weak_pattern(pattern: TicketPattern) -> bool:
    """True if the ticket's white balls fail the shared validity rules."""

    if pattern.odd_count in (0, 5):
        return True

    if pattern.low_count in (0, 5):
        return True

    if pattern.white_sum < FILTER_SUM_MIN or pattern.white_sum > FILTER_SUM_MAX:
        return True

    if pattern.consecutive_pairs >= MAX_CONSECUTIVE_PAIRS:
        return True

    return False
