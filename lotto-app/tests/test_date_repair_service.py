from datetime import date

from services.date_repair_service import _parse_history_row


def test_parse_history_row_returns_date_and_sorted_numbers():
    row = {
        "draw_date": "2026-07-22T00:00:00.000",
        "winning_numbers": "58 04 22 50 05 01",
    }

    assert _parse_history_row(row) == (
        date(2026, 7, 22),
        [4, 5, 22, 50, 58, 1],
    )


def test_parse_history_row_rejects_missing_or_malformed_data():
    assert _parse_history_row({}) is None
    assert _parse_history_row({"draw_date": "bad", "winning_numbers": "1 2 3 4 5 6"}) is None
    assert _parse_history_row({"draw_date": "2026-07-22", "winning_numbers": "1 2 3"}) is None
