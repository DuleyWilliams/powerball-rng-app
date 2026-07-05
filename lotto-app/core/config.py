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

# Data files live under lotto-app/ regardless of the caller's cwd.
# numbers.json is now an export/backup snapshot; database.db is primary.
DATA_FILE: Path = Path(__file__).resolve().parent.parent / "numbers.json"
DB_FILE: Path = Path(__file__).resolve().parent.parent / "database.db"

# TN Powerball data source (daily latest-draw scraper)
POWERBALL_URL: str = "https://www.powerball.com/draw-result?oc=tn"

# NY State Open Data (Socrata) — official historical Powerball drawings
# since 2010. Rows predating the Oct 2015 format change (white balls
# 1-59, powerball 1-35) are naturally rejected by WHITE_BALL_MAX /
# POWERBALL_MAX above during validation, since they describe a
# different game format than the one this app models.
NY_OPEN_DATA_URL: str = "https://data.ny.gov/resource/d6yy-54nr.json"

# Draw source labels, recorded on every row for provenance/auditing.
SOURCE_LEGACY_JSON: str = "legacy_json"
SOURCE_NY_OPEN_DATA: str = "data.ny.gov"
SOURCE_TN_SCRAPER: str = "powerball.com"
