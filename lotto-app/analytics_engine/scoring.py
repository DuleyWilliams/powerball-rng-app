"""Ticket scoring: rewards historically active numbers and balanced patterns."""

from core.config import SCORE_SUM_MIN, SCORE_SUM_MAX, BALANCED_ODD_COUNTS, BALANCED_LOW_COUNTS
from core.patterns import analyze_pattern, odd_even_label, low_high_label
from data.repository import Draw
from analytics_engine.frequency import get_frequency

Ticket = list[int]


def odd_even_pattern(ticket: Ticket) -> dict:
    pattern = analyze_pattern(ticket[:5])
    return {
        "odd": pattern.odd_count,
        "even": pattern.even_count,
        "label": odd_even_label(pattern),
    }


def low_high_pattern(ticket: Ticket) -> dict:
    pattern = analyze_pattern(ticket[:5])
    return {
        "low": pattern.low_count,
        "high": pattern.high_count,
        "label": low_high_label(pattern),
    }


def ticket_sum(ticket: Ticket) -> int:
    return sum(ticket[:5])


def score_ticket(ticket: Ticket, draws: list[Draw]) -> int:
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
    if oe["odd"] in BALANCED_ODD_COUNTS:
        score += 10

    # Reward balanced low/high
    lh = low_high_pattern(ticket)
    if lh["low"] in BALANCED_LOW_COUNTS:
        score += 10

    # Penalize very low or very high sums
    total = ticket_sum(ticket)
    if SCORE_SUM_MIN <= total <= SCORE_SUM_MAX:
        score += 10
    else:
        score -= 10

    # Penalize duplicate white balls
    if len(set(white)) < 5:
        score -= 50

    return score


def score_tickets(tickets: list[Ticket], draws: list[Draw]) -> list[dict]:
    scored = []

    for ticket in tickets:
        scored.append({
            "ticket": ticket,
            "score": score_ticket(ticket, draws),
            "odd_even": odd_even_pattern(ticket)["label"],
            "low_high": low_high_pattern(ticket)["label"],
            "sum": ticket_sum(ticket),
        })

    return sorted(scored, key=lambda x: x["score"], reverse=True)
