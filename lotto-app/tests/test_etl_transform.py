from datetime import date

from etl.transform import transform_record


def test_transform_record_sorts_white_balls_and_parses_ints():
    raw = {"white_balls": ["17", "22", "36", "5", "9"], "powerball": "24", "draw_date": None, "source": "test"}
    draw = transform_record(raw)

    assert draw.balls() == [5, 9, 17, 22, 36]
    assert draw.powerball == 24
    assert draw.draw_date is None
    assert draw.date_parse_error is False


def test_transform_record_parses_socrata_timestamp():
    raw = {"white_balls": [1, 2, 3, 4, 5], "powerball": 6, "draw_date": "2010-02-03T00:00:00.000", "source": "data.ny.gov"}
    draw = transform_record(raw)

    assert draw.draw_date == date(2010, 2, 3)
    assert draw.date_parse_error is False


def test_transform_record_parses_plain_iso_date():
    raw = {"white_balls": [1, 2, 3, 4, 5], "powerball": 6, "draw_date": "2020-05-01", "source": "test"}
    draw = transform_record(raw)

    assert draw.draw_date == date(2020, 5, 1)


def test_transform_record_flags_unparseable_date():
    raw = {"white_balls": [1, 2, 3, 4, 5], "powerball": 6, "draw_date": "not-a-date", "source": "test"}
    draw = transform_record(raw)

    assert draw.draw_date is None
    assert draw.date_parse_error is True


def test_transform_record_handles_missing_and_non_numeric_values():
    raw = {"white_balls": [1, 2, "oops", 4], "powerball": None, "draw_date": None, "source": "test"}
    draw = transform_record(raw)

    assert draw.balls() == [1, 2, None, 4, None]
    assert draw.powerball is None
