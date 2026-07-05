from analytics_engine.scoring import (
    odd_even_pattern,
    low_high_pattern,
    ticket_sum,
    score_ticket,
    score_tickets,
)

DRAWS = [
    [1, 2, 3, 4, 5, 10],
    [1, 2, 6, 7, 8, 10],
    [9, 10, 11, 12, 13, 20],
]

TICKET = [1, 2, 3, 4, 5, 10]


def test_odd_even_pattern():
    assert odd_even_pattern(TICKET) == {"odd": 3, "even": 2, "label": "3 odd / 2 even"}


def test_low_high_pattern():
    assert low_high_pattern(TICKET) == {"low": 5, "high": 0, "label": "5 low / 0 high"}


def test_ticket_sum():
    assert ticket_sum(TICKET) == 15


def test_score_ticket_matches_expected_breakdown():
    # white freq (1+2+1+1+1=... see analytics_engine.frequency) + pb freq(10)=2,
    # +10 balanced-odd bonus (3 in {2,3}), no low/high bonus (5 not in {2,3}),
    # -10 sum-out-of-range penalty (15 not in [100,220]), no duplicate penalty.
    assert score_ticket(TICKET, DRAWS) == 9


def test_score_tickets_sorted_descending_and_includes_labels():
    scored = score_tickets([TICKET], DRAWS)

    assert len(scored) == 1
    assert scored[0]["ticket"] == TICKET
    assert scored[0]["score"] == 9
    assert scored[0]["odd_even"] == "3 odd / 2 even"
    assert scored[0]["low_high"] == "5 low / 0 high"
    assert scored[0]["sum"] == 15
