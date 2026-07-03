def analyze_ticket_pattern(ticket):
    white_balls = sorted(ticket[:5])

    odd_count = sum(1 for n in white_balls if n % 2 != 0)
    even_count = 5 - odd_count

    low_count = sum(1 for n in white_balls if n <= 35)
    high_count = 5 - low_count

    white_sum = sum(white_balls)

    consecutive_pairs = sum(
        1 for a, b in zip(white_balls, white_balls[1:])
        if b - a == 1
    )

    return {
        "odd_count": odd_count,
        "even_count": even_count,
        "low_count": low_count,
        "high_count": high_count,
        "white_sum": white_sum,
        "consecutive_pairs": consecutive_pairs
    }


def is_valid_ticket(ticket):
    white_balls = sorted(ticket[:5])

    if len(set(white_balls)) != 5:
        return False

    pattern = analyze_ticket_pattern(ticket)

    if pattern["odd_count"] in [0, 5]:
        return False

    if pattern["low_count"] in [0, 5]:
        return False

    if pattern["white_sum"] < 90 or pattern["white_sum"] > 240:
        return False

    if pattern["consecutive_pairs"] >= 3:
        return False

    return True


def filter_tickets(tickets):
    valid = []
    rejected = []

    for ticket in tickets:
        if is_valid_ticket(ticket):
            valid.append(ticket)
        else:
            rejected.append(ticket)

    return valid, rejected