from analytics_engine.condensation import condense_tickets

TICKET_A = [3, 10, 18, 26, 40, 5]   # balanced, score 50
TICKET_B = [7, 14, 22, 31, 45, 8]   # balanced, score 40
TICKET_C = [3, 15, 45, 63, 67, 9]   # all-odd whites -> weak pattern, highest score but must be excluded

SCORED_TICKETS = [
    {"ticket": TICKET_A, "score": 50, "odd_even": "1 odd / 4 even", "low_high": "4 low / 1 high", "sum": 97},
    {"ticket": TICKET_B, "score": 40, "odd_even": "3 odd / 2 even", "low_high": "4 low / 1 high", "sum": 119},
    {"ticket": TICKET_C, "score": 100, "odd_even": "5 odd / 0 even", "low_high": "2 low / 3 high", "sum": 193},
]


def test_condense_tickets_excludes_weak_patterns():
    result = condense_tickets(SCORED_TICKETS, target_count=2)

    selected = {
        (r["Ball 1"], r["Ball 2"], r["Ball 3"], r["Ball 4"], r["Ball 5"], r["Powerball"])
        for r in result
    }

    assert len(result) == 2
    assert selected == {tuple(TICKET_A), tuple(TICKET_B)}


def test_condense_tickets_picks_highest_total_score_first():
    result = condense_tickets(SCORED_TICKETS, target_count=1)

    assert len(result) == 1
    row = result[0]
    assert (row["Ball 1"], row["Ball 2"], row["Ball 3"], row["Ball 4"], row["Ball 5"], row["Powerball"]) == tuple(TICKET_A)
    assert row["Original Score"] == 50
    assert row["Condensed Score"] == 105
