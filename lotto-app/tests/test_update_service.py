from services.update_service import (
    is_valid_powerball_draw,
    extract_numbers_from_text,
    extract_dated_draw_from_text,
)


def test_is_valid_powerball_draw_accepts_good_draw():
    assert is_valid_powerball_draw([1, 2, 3, 4, 5, 6]) is True


def test_is_valid_powerball_draw_rejects_wrong_length():
    assert is_valid_powerball_draw([1, 2, 3]) is False


def test_is_valid_powerball_draw_rejects_duplicate_white_balls():
    assert is_valid_powerball_draw([1, 1, 3, 4, 5, 6]) is False


def test_is_valid_powerball_draw_rejects_out_of_range_white_ball():
    assert is_valid_powerball_draw([0, 2, 3, 4, 5, 6]) is False


def test_is_valid_powerball_draw_rejects_out_of_range_powerball():
    assert is_valid_powerball_draw([1, 2, 3, 4, 5, 30]) is False


def test_extract_numbers_from_text_finds_first_valid_window():
    text = "99 1 2 3 4 5 6 88"
    assert extract_numbers_from_text(text) == [1, 2, 3, 4, 5, 6]


def test_extract_numbers_from_text_returns_none_when_no_valid_window():
    assert extract_numbers_from_text("1 2 3") is None


def test_extract_dated_draw_from_official_results_text():
    text = (
        "Draw Results Search Winning Numbers Wed, Jul 22, 2026 "
        "4 5 22 50 58 1 Power Play 3x Estimated Jackpot $570 Million"
    )

    assert extract_dated_draw_from_text(text) == {
        "white_balls": [4, 5, 22, 50, 58],
        "powerball": 1,
        "draw_date": "2026-07-22",
        "source": "powerball.com",
    }


def test_extract_dated_draw_ignores_dates_and_numbers_before_winning_section():
    text = (
        "Next Draw Sat, Jul 25, 2026 Jackpot 600 Million "
        "Winning Numbers Mon, Jul 20, 2026 2 9 44 53 59 8 "
        "Power Play 2x"
    )

    record = extract_dated_draw_from_text(text)

    assert record["draw_date"] == "2026-07-20"
    assert record["white_balls"] == [2, 9, 44, 53, 59]
    assert record["powerball"] == 8


def test_extract_dated_draw_requires_winning_numbers_heading_and_date():
    assert extract_dated_draw_from_text("Wed, Jul 22, 2026 4 5 22 50 58 1") is None
    assert extract_dated_draw_from_text("Winning Numbers 4 5 22 50 58 1 Power Play 3x") is None
