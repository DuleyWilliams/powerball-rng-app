"""Draw frequency analysis: hot/cold numbers and repeated pairs."""

from collections import Counter
from itertools import combinations

from core.config import WHITE_BALL_MIN, WHITE_BALL_MAX
from data.repository import Draw


def split_draws(draws: list[Draw]) -> tuple[list[int], list[int]]:
    white_balls: list[int] = []
    powerballs: list[int] = []

    for draw in draws:
        if len(draw) == 6:
            white_balls.extend(draw[:5])
            powerballs.append(draw[5])

    return white_balls, powerballs


def get_frequency(draws: list[Draw]) -> dict[str, Counter]:
    white_balls, powerballs = split_draws(draws)

    return {
        "white_frequency": Counter(white_balls),
        "powerball_frequency": Counter(powerballs),
    }


def hot_numbers(draws: list[Draw], limit: int = 10) -> list[tuple[int, int]]:
    freq = get_frequency(draws)["white_frequency"]
    return freq.most_common(limit)


def cold_numbers(draws: list[Draw], limit: int = 10) -> list[tuple[int, int]]:
    freq = get_frequency(draws)["white_frequency"]

    all_numbers = range(WHITE_BALL_MIN, WHITE_BALL_MAX + 1)
    full_freq = {n: freq.get(n, 0) for n in all_numbers}

    return sorted(full_freq.items(), key=lambda x: x[1])[:limit]


def hot_powerballs(draws: list[Draw], limit: int = 10) -> list[tuple[int, int]]:
    freq = get_frequency(draws)["powerball_frequency"]
    return freq.most_common(limit)


def repeated_pairs(draws: list[Draw], limit: int = 10) -> list[tuple[tuple[int, int], int]]:
    pair_counter: Counter = Counter()

    for draw in draws:
        white = draw[:5]
        for pair in combinations(white, 2):
            pair_counter[tuple(sorted(pair))] += 1

    return pair_counter.most_common(limit)
