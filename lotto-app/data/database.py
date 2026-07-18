"""SQLite schema and connection handling — the only module that knows SQL."""

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from core.config import DB_FILE

SCHEMA = """
CREATE TABLE IF NOT EXISTS draws (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draw_date DATE,
    ball1 INTEGER NOT NULL,
    ball2 INTEGER NOT NULL,
    ball3 INTEGER NOT NULL,
    ball4 INTEGER NOT NULL,
    ball5 INTEGER NOT NULL,
    powerball INTEGER NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_draws_draw_date ON draws (draw_date);
CREATE INDEX IF NOT EXISTS idx_draws_ball1 ON draws (ball1);
CREATE INDEX IF NOT EXISTS idx_draws_ball2 ON draws (ball2);
CREATE INDEX IF NOT EXISTS idx_draws_ball3 ON draws (ball3);
CREATE INDEX IF NOT EXISTS idx_draws_ball4 ON draws (ball4);
CREATE INDEX IF NOT EXISTS idx_draws_ball5 ON draws (ball5);
CREATE INDEX IF NOT EXISTS idx_draws_powerball ON draws (powerball);
"""


def init_db() -> None:
    """Create the draws table and its indexes if they don't already exist.

    Safe to call on every startup / every connection — pure DDL, idempotent.
    """
    # sqlite3.Connection's context manager only handles commit/rollback,
    # not closing the connection — an explicit close() is required, or
    # this leaks a connection (and its file handle) on every call.
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    init_db()

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row

    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
