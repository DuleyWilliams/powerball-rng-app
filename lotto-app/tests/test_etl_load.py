from datetime import date

from data import database
from etl.load import load_draw
from etl.transform import TransformedDraw


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "test.db")


def _draw(**overrides) -> TransformedDraw:
    defaults = dict(
        ball1=1, ball2=2, ball3=3, ball4=4, ball5=5,
        powerball=6, draw_date=date(2020, 1, 1),
        date_parse_error=False, source="test", raw={},
    )
    defaults.update(overrides)
    return TransformedDraw(**defaults)


def test_load_draw_imports_new_valid_draw(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    outcome = load_draw(_draw())

    assert outcome.status == "imported"
    assert outcome.reasons == []


def test_load_draw_skips_existing_duplicate(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    load_draw(_draw())
    outcome = load_draw(_draw())

    assert outcome.status == "skipped"


def test_load_draw_fails_invalid_draw(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    outcome = load_draw(_draw(powerball=99))

    assert outcome.status == "failed"
    assert "invalid powerball range" in outcome.reasons
