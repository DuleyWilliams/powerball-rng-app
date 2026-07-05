from datetime import date, timedelta

from etl.transform import TransformedDraw
from etl.validate import validate_draw


def _draw(**overrides) -> TransformedDraw:
    defaults = dict(
        ball1=1, ball2=2, ball3=3, ball4=4, ball5=5,
        powerball=6, draw_date=date(2020, 1, 1),
        date_parse_error=False, source="test", raw={},
    )
    defaults.update(overrides)
    return TransformedDraw(**defaults)


def test_valid_draw_passes():
    result = validate_draw(_draw())
    assert result.is_valid is True
    assert result.reasons == []


def test_rejects_missing_numbers():
    result = validate_draw(_draw(ball3=None))
    assert result.is_valid is False
    assert "missing numbers" in result.reasons


def test_rejects_duplicate_white_balls():
    result = validate_draw(_draw(ball1=2, ball2=2, ball3=3, ball4=4, ball5=5))
    assert "duplicate white balls" in result.reasons


def test_rejects_invalid_white_ball_range():
    result = validate_draw(_draw(ball5=70))
    assert "invalid white ball range" in result.reasons


def test_rejects_invalid_powerball_range():
    result = validate_draw(_draw(powerball=27))
    assert "invalid powerball range" in result.reasons


def test_rejects_invalid_date():
    result = validate_draw(_draw(date_parse_error=True, draw_date=None))
    assert "invalid date" in result.reasons


def test_rejects_missing_date_when_required():
    result = validate_draw(_draw(draw_date=None), require_date=True)
    assert "missing date" in result.reasons


def test_allows_missing_date_when_not_required():
    result = validate_draw(_draw(draw_date=None), require_date=False)
    assert result.is_valid is True


def test_rejects_future_date():
    result = validate_draw(_draw(draw_date=date.today() + timedelta(days=1)))
    assert "future date" in result.reasons
