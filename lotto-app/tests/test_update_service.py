from services.update_service import is_valid_powerball_draw, extract_numbers_from_text


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
