"""Gap analysis: how many drawings have passed since each number last appeared."""

from core.config import WHITE_BALL_MIN, WHITE_BALL_MAX, POWERBALL_MIN, POWERBALL_MAX
from data.repository import Draw

_NEVER_SEEN_SORT_KEY = 9999


def white_ball_gap_analysis(draws: list[Draw]) -> list[dict]:
    gaps = []

    for number in range(WHITE_BALL_MIN, WHITE_BALL_MAX + 1):
        last_seen = None

        for index, draw in enumerate(draws):
            white_balls = draw[:5]

            if number in white_balls:
                last_seen = index
                break

        gaps.append({
            "Number": number,
            "Drawings Since Last Seen": last_seen if last_seen is not None else "Never Seen",
        })

    return sorted(
        gaps,
        key=lambda item: item["Drawings Since Last Seen"]
        if isinstance(item["Drawings Since Last Seen"], int)
        else _NEVER_SEEN_SORT_KEY,
        reverse=True,
    )


def powerball_gap_analysis(draws: list[Draw]) -> list[dict]:
    gaps = []

    for number in range(POWERBALL_MIN, POWERBALL_MAX + 1):
        last_seen = None

        for index, draw in enumerate(draws):
            powerball = draw[5]

            if number == powerball:
                last_seen = index
                break

        gaps.append({
            "Powerball": number,
            "Drawings Since Last Seen": last_seen if last_seen is not None else "Never Seen",
        })

    return sorted(
        gaps,
        key=lambda item: item["Drawings Since Last Seen"]
        if isinstance(item["Drawings Since Last Seen"], int)
        else _NEVER_SEEN_SORT_KEY,
        reverse=True,
    )
