"""Centralized constants for ticket rules, scoring thresholds, and data paths."""

from pathlib import Path

# Powerball number ranges
WHITE_BALL_MIN: int = 1
WHITE_BALL_MAX: int = 69
WHITE_BALL_COUNT: int = 5

POWERBALL_MIN: int = 1
POWERBALL_MAX: int = 26

# A white ball at or below this value is considered "low"; above is "high".
LOW_HIGH_SPLIT: int = 35

# Ticket validity / weak-pattern bounds (used by filters and condensation)
FILTER_SUM_MIN: int = 90
FILTER_SUM_MAX: int = 240
MAX_CONSECUTIVE_PAIRS: int = 3

# Scoring reward bounds (used by the scoring engine — intentionally
# narrower than the filter bounds above, since "score well" is a
# stricter bar than "is valid")
SCORE_SUM_MIN: int = 100
SCORE_SUM_MAX: int = 220
BALANCED_ODD_COUNTS: frozenset[int] = frozenset({2, 3})
BALANCED_LOW_COUNTS: frozenset[int] = frozenset({2, 3})

# Data file lives at lotto-app/numbers.json regardless of the caller's cwd.
DATA_FILE: Path = Path(__file__).resolve().parent.parent / "numbers.json"

# TN Powerball data source
POWERBALL_URL: str = "https://www.powerball.com/draw-result?oc=tn"
