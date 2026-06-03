from itertools import combinations


def normalize_ticket(ticket):
    white_balls = sorted([int(n) for n in ticket[:5]])
    powerball = int(ticket[5])
    return white_balls + [powerball]


def get_pairs(ticket):
    return set(combinations(ticket[:5], 2))


def is_weak_pattern(ticket):
    white_balls = ticket[:5]

    odd_count = sum(1 for n in white_balls if n % 2 != 0)
    low_count = sum(1 for n in white_balls if n <= 35)
    white_sum = sum(white_balls)

    consecutive_count = sum(
        1 for a, b in zip(white_balls, white_balls[1:])
        if b - a == 1
    )

    if odd_count in [0, 5]:
        return True

    if low_count in [0, 5]:
        return True

    if white_sum < 90 or white_sum > 240:
        return True

    if consecutive_count >= 3:
        return True

    return False


def overlap_score(ticket, selected):
    score = 0
    ticket_whites = set(ticket[:5])
    ticket_pairs = get_pairs(ticket)

    for existing in selected:
        existing_whites = set(existing[:5])
        existing_pairs = get_pairs(existing)

        shared_numbers = len(ticket_whites.intersection(existing_whites))
        shared_pairs = len(ticket_pairs.intersection(existing_pairs))

        score += shared_numbers * 3
        score += shared_pairs * 5

        if ticket[5] == existing[5]:
            score += 4

    return score


def coverage_score(ticket, covered_numbers, covered_pairs, covered_powerballs):
    ticket_whites = set(ticket[:5])
    ticket_pairs = get_pairs(ticket)

    new_numbers = len(ticket_whites - covered_numbers)
    new_pairs = len(ticket_pairs - covered_pairs)
    new_powerball = 1 if ticket[5] not in covered_powerballs else 0

    return (new_numbers * 6) + (new_pairs * 2) + (new_powerball * 5)


def condense_tickets(scored_tickets, target_count=10):
    cleaned = []

    for item in scored_tickets:
        ticket = normalize_ticket(item["ticket"])

        if is_weak_pattern(ticket):
            continue

        cleaned.append({
            "ticket": ticket,
            "score": item["score"],
            "odd_even": item["odd_even"],
            "low_high": item["low_high"],
            "sum": item["sum"]
        })

    selected = []
    selected_rows = []

    covered_numbers = set()
    covered_pairs = set()
    covered_powerballs = set()

    while len(selected) < target_count and cleaned:
        best_item = None
        best_total_score = None

        for item in cleaned:
            ticket = item["ticket"]

            total_score = item["score"]
            total_score += coverage_score(
                ticket,
                covered_numbers,
                covered_pairs,
                covered_powerballs
            )
            total_score -= overlap_score(ticket, selected)

            if best_total_score is None or total_score > best_total_score:
                best_total_score = total_score
                best_item = item

        if not best_item:
            break

        selected_ticket = best_item["ticket"]
        selected.append(selected_ticket)

        covered_numbers.update(selected_ticket[:5])
        covered_pairs.update(get_pairs(selected_ticket))
        covered_powerballs.add(selected_ticket[5])

        selected_rows.append({
            "Ball 1": selected_ticket[0],
            "Ball 2": selected_ticket[1],
            "Ball 3": selected_ticket[2],
            "Ball 4": selected_ticket[3],
            "Ball 5": selected_ticket[4],
            "Powerball": selected_ticket[5],
            "Original Score": best_item["score"],
            "Condensed Score": best_total_score,
            "Odd / Even": best_item["odd_even"],
            "Low / High": best_item["low_high"],
            "White Ball Sum": best_item["sum"]
        })

        cleaned.remove(best_item)

    return selected_rows