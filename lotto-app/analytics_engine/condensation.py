"""Combinatorial condensation: reduce a large scored candidate pool down to
a smaller set with strong coverage and low overlap.
"""

from itertools import combinations

from core.patterns import analyze_pattern, is_weak_pattern as _is_weak_pattern

Ticket = list[int]


def normalize_ticket(ticket: Ticket) -> Ticket:
    white_balls = sorted(int(n) for n in ticket[:5])
    powerball = int(ticket[5])
    return white_balls + [powerball]


def get_pairs(ticket: Ticket) -> set[tuple[int, int]]:
    return set(combinations(ticket[:5], 2))


def is_weak_pattern(ticket: Ticket) -> bool:
    return _is_weak_pattern(analyze_pattern(ticket[:5]))


def overlap_score(ticket: Ticket, selected: list[Ticket]) -> int:
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


def coverage_score(
    ticket: Ticket,
    covered_numbers: set[int],
    covered_pairs: set[tuple[int, int]],
    covered_powerballs: set[int],
) -> int:
    ticket_whites = set(ticket[:5])
    ticket_pairs = get_pairs(ticket)

    new_numbers = len(ticket_whites - covered_numbers)
    new_pairs = len(ticket_pairs - covered_pairs)
    new_powerball = 1 if ticket[5] not in covered_powerballs else 0

    return (new_numbers * 6) + (new_pairs * 2) + (new_powerball * 5)


def condense_tickets(scored_tickets: list[dict], target_count: int = 10) -> list[dict]:
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
            "sum": item["sum"],
        })

    selected: list[Ticket] = []
    selected_rows: list[dict] = []

    covered_numbers: set[int] = set()
    covered_pairs: set[tuple[int, int]] = set()
    covered_powerballs: set[int] = set()

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
                covered_powerballs,
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
            "White Ball Sum": best_item["sum"],
        })

        cleaned.remove(best_item)

    return selected_rows
