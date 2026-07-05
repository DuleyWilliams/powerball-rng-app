"""Application service: ticket generation and validity filtering.

This is the layer the UI calls to get playable tickets — it combines
the weighted generator with the shared validity policy from core.patterns.
"""

import random
from collections import Counter

from core.config import WHITE_BALL_MIN, WHITE_BALL_MAX, WHITE_BALL_COUNT, POWERBALL_MIN, POWERBALL_MAX
from core.patterns import analyze_pattern, is_weak_pattern, has_duplicate_white_balls
from data.repository import get_all_draws

Ticket = list[int]


def weighted_choice(counter: Counter, min_num: int, max_num: int, exclude: set[int] | None = None) -> int:
    exclude = exclude or set()

    pool = []
    weights = []

    for number in range(min_num, max_num + 1):
        if number in exclude:
            continue

        pool.append(number)
        weights.append(counter.get(number, 1))

    return random.choices(pool, weights=weights, k=1)[0]


def generate_ticket() -> Ticket:
    draws = get_all_draws()

    white_counter: Counter = Counter()
    powerball_counter: Counter = Counter()

    for draw in draws:
        white_numbers = draw[:5]
        powerball = draw[5]

        white_counter.update(white_numbers)
        powerball_counter.update([powerball])

    selected: set[int] = set()

    while len(selected) < WHITE_BALL_COUNT:
        pick = weighted_choice(
            white_counter,
            min_num=WHITE_BALL_MIN,
            max_num=WHITE_BALL_MAX,
            exclude=selected,
        )
        selected.add(pick)

    powerball = weighted_choice(
        powerball_counter,
        min_num=POWERBALL_MIN,
        max_num=POWERBALL_MAX,
    )

    return sorted(selected) + [powerball]


def generate_tickets(count: int = 5) -> list[Ticket]:
    return [generate_ticket() for _ in range(count)]


def is_valid_ticket(ticket: Ticket) -> bool:
    white_balls = sorted(ticket[:5])

    if has_duplicate_white_balls(white_balls):
        return False

    pattern = analyze_pattern(white_balls)

    return not is_weak_pattern(pattern)


def filter_tickets(tickets: list[Ticket]) -> tuple[list[Ticket], list[Ticket]]:
    valid = []
    rejected = []

    for ticket in tickets:
        if is_valid_ticket(ticket):
            valid.append(ticket)
        else:
            rejected.append(ticket)

    return valid, rejected
