import json
import random
from collections import Counter
from pathlib import Path

DATA_FILE = Path("numbers.json")


def load_draws():
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    return data.get("numbers", [])


def weighted_choice(counter, min_num, max_num, exclude=None):
    exclude = exclude or set()

    pool = []
    weights = []

    for number in range(min_num, max_num + 1):
        if number in exclude:
            continue

        pool.append(number)
        weights.append(counter.get(number, 1))

    return random.choices(pool, weights=weights, k=1)[0]


def generate_ticket():
    draws = load_draws()

    white_counter = Counter()
    powerball_counter = Counter()

    for draw in draws:
        white_numbers = draw[:5]
        powerball = draw[5]

        white_counter.update(white_numbers)
        powerball_counter.update([powerball])

    selected = set()

    while len(selected) < 5:
        pick = weighted_choice(
            white_counter,
            min_num=1,
            max_num=69,
            exclude=selected
        )
        selected.add(pick)

    powerball = weighted_choice(
        powerball_counter,
        min_num=1,
        max_num=26
    )

    return sorted(selected) + [powerball]


def generate_tickets(count=5):
    return [generate_ticket() for _ in range(count)]