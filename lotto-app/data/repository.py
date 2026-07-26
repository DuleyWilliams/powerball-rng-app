"""Data layer: the only place the rest of the app talks to SQLite.

SQLite (database.db) is the primary data store. numbers.json is kept
only as an export/backup snapshot — see data.json_export and
data.migration.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from data.database import get_connection

# Backward-compatible shape used throughout analytics_engine/services:
# a draw is [ball1, ball2, ball3, ball4, ball5, powerball].
Draw = list[int]


@dataclass(frozen=True)
class DatabaseStatistics:
    total_rows: int
    latest_draw_date: Optional[date]
    oldest_draw_date: Optional[date]
    last_updated_at: Optional[str]


@dataclass(frozen=True)
class DatedDraw:
    draw_date: date
    balls: Draw


@dataclass(frozen=True)
class ExportDraw:
    draw_date: Optional[date]
    balls: Draw
    source: str


def _parse_date(value: Optional[str]) -> Optional[date]:
    return date.fromisoformat(value) if value else None


def get_all_export_draws() -> list[ExportDraw]:
    """All draws, newest first.

    Dated rows sort by draw_date descending; undated legacy rows (no
    known draw_date) are ordered after all dated rows, newest-inserted
    first, since their real-world recency is unknown.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT draw_date, ball1, ball2, ball3, ball4, ball5, powerball, source
            FROM draws
            ORDER BY (draw_date IS NULL) ASC, draw_date DESC, id DESC
            """
        ).fetchall()

    return [
        ExportDraw(
            draw_date=_parse_date(row["draw_date"]),
            balls=[row["ball1"], row["ball2"], row["ball3"], row["ball4"], row["ball5"], row["powerball"]],
            source=row["source"],
        )
        for row in rows
    ]


def get_all_draws() -> list[Draw]:
    """Backward-compatible number-only view of the full dataset."""
    return [record.balls for record in get_all_export_draws()]


def get_latest_draw() -> Optional[Draw]:
    draws = get_all_draws()
    return draws[0] if draws else None


def get_recent_dated_draws(limit: int = 50) -> list[DatedDraw]:
    """The most recent draws that have a known draw_date, oldest first
    (ready for a left-to-right timeline chart). Undated legacy/scraper
    rows are excluded — a timeline is meaningless without a real date.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT draw_date, ball1, ball2, ball3, ball4, ball5, powerball
            FROM draws
            WHERE draw_date IS NOT NULL
            ORDER BY draw_date DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    dated_draws = [
        DatedDraw(
            draw_date=_parse_date(row["draw_date"]),
            balls=[row["ball1"], row["ball2"], row["ball3"], row["ball4"], row["ball5"], row["powerball"]],
        )
        for row in rows
    ]

    return list(reversed(dated_draws))


def insert_draw(
    draw_date: Optional[date],
    ball1: int,
    ball2: int,
    ball3: int,
    ball4: int,
    ball5: int,
    powerball: int,
    source: str,
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO draws (draw_date, ball1, ball2, ball3, ball4, ball5, powerball, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (draw_date.isoformat() if draw_date else None, ball1, ball2, ball3, ball4, ball5, powerball, source),
        )
        return cursor.lastrowid


def draw_exists(
    ball1: int,
    ball2: int,
    ball3: int,
    ball4: int,
    ball5: int,
    powerball: int,
    draw_date: Optional[date] = None,
) -> bool:
    """A duplicate is either:

    1. An existing row on the exact same known date (the real-world
       unique key for an official drawing), or
    2. An existing row with the exact same 6 numbers where *either*
       side's date is unknown (the only reliable check available for
       undated legacy rows, regardless of which side — legacy row
       already stored vs. newly-dated import, or vice versa).

    A coincidental repeat of the same 6 numbers across two rows that
    both have known, different dates is NOT treated as a duplicate —
    that's a rare but real possibility, not a data-entry collision.
    """
    with get_connection() as conn:
        if draw_date is not None:
            match = conn.execute(
                "SELECT 1 FROM draws WHERE draw_date = ? LIMIT 1",
                (draw_date.isoformat(),),
            ).fetchone()
            if match:
                return True

        numbers_clause = "ball1 = ? AND ball2 = ? AND ball3 = ? AND ball4 = ? AND ball5 = ? AND powerball = ?"
        params = [ball1, ball2, ball3, ball4, ball5, powerball]

        # If the incoming draw's date is unknown, any existing row with
        # the same numbers is a plausible duplicate. If it's known, only
        # an existing *undated* row with the same numbers is ambiguous
        # enough to count.
        if draw_date is None:
            query = f"SELECT 1 FROM draws WHERE {numbers_clause} LIMIT 1"
        else:
            query = f"SELECT 1 FROM draws WHERE {numbers_clause} AND draw_date IS NULL LIMIT 1"

        match = conn.execute(query, params).fetchone()

        return match is not None


def database_statistics() -> DatabaseStatistics:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_rows,
                MAX(draw_date) AS latest_draw_date,
                MIN(draw_date) AS oldest_draw_date,
                MAX(created_at) AS last_updated_at
            FROM draws
            """
        ).fetchone()

    return DatabaseStatistics(
        total_rows=row["total_rows"],
        latest_draw_date=_parse_date(row["latest_draw_date"]),
        oldest_draw_date=_parse_date(row["oldest_draw_date"]),
        last_updated_at=row["last_updated_at"],
    )
