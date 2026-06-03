from collections import Counter
from itertools import combinations


def split_draws(draws):
    white_balls = []
    powerballs = []

    for draw in draws:
        if len(draw) == 6:
            white_balls.extend(draw[:5])
            powerballs.append(draw[5])

    return white_balls, powerballs


def get_frequency(draws):
    white_balls, powerballs = split_draws(draws)

    return {
        "white_frequency": Counter(white_balls),
        "powerball_frequency": Counter(powerballs)
    }


def hot_numbers(draws, limit=10):
    freq = get_frequency(draws)["white_frequency"]
    return freq.most_common(limit)


def cold_numbers(draws, limit=10):
    freq = get_frequency(draws)["white_frequency"]

    all_numbers = range(1, 70)
    full_freq = {n: freq.get(n, 0) for n in all_numbers}

    return sorted(full_freq.items(), key=lambda x: x[1])[:limit]


def hot_powerballs(draws, limit=10):
    freq = get_frequency(draws)["powerball_frequency"]
    return freq.most_common(limit)


def odd_even_pattern(ticket):
    white = ticket[:5]
    odd = sum(1 for n in white if n % 2 != 0)
    even = 5 - odd

    return {
        "odd": odd,
        "even": even,
        "label": f"{odd} odd / {even} even"
    }


def low_high_pattern(ticket):
    white = ticket[:5]
    low = sum(1 for n in white if n <= 35)
    high = 5 - low

    return {
        "low": low,
        "high": high,
        "label": f"{low} low / {high} high"
    }


def ticket_sum(ticket):
    return sum(ticket[:5])


def repeated_pairs(draws, limit=10):
    pair_counter = Counter()

    for draw in draws:
        white = draw[:5]
        for pair in combinations(white, 2):
            pair_counter[tuple(sorted(pair))] += 1

    return pair_counter.most_common(limit)


def score_ticket(ticket, draws):
    freq = get_frequency(draws)
    white_freq = freq["white_frequency"]
    pb_freq = freq["powerball_frequency"]

    white = ticket[:5]
    pb = ticket[5]

    score = 0

    # Reward historically active numbers
    for n in white:
        score += white_freq.get(n, 0)

    score += pb_freq.get(pb, 0)

    # Reward balanced odd/even
    oe = odd_even_pattern(ticket)
    if oe["odd"] in [2, 3]:
        score += 10

    # Reward balanced low/high
    lh = low_high_pattern(ticket)
    if lh["low"] in [2, 3]:
        score += 10

    # Penalize very low or very high sums
    total = ticket_sum(ticket)
    if 100 <= total <= 220:
        score += 10
    else:
        score -= 10

    # Penalize duplicate white balls
    if len(set(white)) < 5:
        score -= 50

    return score


def score_tickets(tickets, draws):
    scored = []

    for ticket in tickets:
        scored.append({
            "ticket": ticket,
            "score": score_ticket(ticket, draws),
            "odd_even": odd_even_pattern(ticket)["label"],
            "low_high": low_high_pattern(ticket)["label"],
            "sum": ticket_sum(ticket)
        })

    return sorted(scored, key=lambda x: x["score"], reverse=True)