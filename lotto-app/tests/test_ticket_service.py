from services.ticket_service import generate_ticket, generate_tickets, filter_tickets

VALID_TICKET = [2, 6, 26, 39, 68, 6]     # balanced pattern
INVALID_TICKET = [3, 15, 45, 63, 67, 9]  # all-odd whites -> weak pattern


def test_generate_ticket_invariants():
    for _ in range(20):
        ticket = generate_ticket()

        assert len(ticket) == 6
        white_balls, powerball = ticket[:5], ticket[5]

        assert len(set(white_balls)) == 5
        assert all(1 <= n <= 69 for n in white_balls)
        assert white_balls == sorted(white_balls)
        assert 1 <= powerball <= 26


def test_generate_tickets_returns_requested_count():
    tickets = generate_tickets(7)
    assert len(tickets) == 7


def test_filter_tickets_splits_valid_and_rejected():
    valid, rejected = filter_tickets([VALID_TICKET, INVALID_TICKET])

    assert valid == [VALID_TICKET]
    assert rejected == [INVALID_TICKET]
