"""Application service: fetch and persist the latest TN Powerball drawing.

Also used directly by the IONOS cron updater (cron_update.py) — keep this
module importable on Python 3.9 (no bare `X | None` union syntax) and free
of Streamlit/Plotly/SciPy/Pandas imports.
"""

import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from core.config import POWERBALL_URL, WHITE_BALL_MIN, WHITE_BALL_MAX, POWERBALL_MIN, POWERBALL_MAX, SOURCE_TN_SCRAPER
from data.json_export import export_draws_to_json
from data.repository import Draw
from etl.load import load_draw
from etl.transform import RawRecord, transform_record

DRAW_DATE_PATTERN = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"\d{1,2},\s+\d{4}\b"
)


def fetch_powerball_page() -> str:
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(POWERBALL_URL, headers=headers, timeout=20)
    response.raise_for_status()
    return response.text


def is_valid_powerball_draw(draw: Optional[Draw]) -> bool:
    if not draw or len(draw) != 6:
        return False

    white_balls = draw[:5]
    powerball = draw[5]

    if len(set(white_balls)) != 5:
        return False

    if not all(WHITE_BALL_MIN <= n <= WHITE_BALL_MAX for n in white_balls):
        return False

    if not POWERBALL_MIN <= powerball <= POWERBALL_MAX:
        return False

    return True


def extract_numbers_from_text(text: str) -> Optional[Draw]:
    """
    Attempts to extract only the actual draw numbers from the Powerball page.
    Filters out dates, multipliers, prize numbers, and repeated bad matches.
    """

    # Find small number groups only
    raw_numbers = [int(n) for n in re.findall(r"\b\d{1,2}\b", text)]

    candidates = []

    # Slide through the numbers looking for a valid Powerball pattern:
    # 5 white balls from 1-69, no duplicates, plus 1 Powerball from 1-26.
    for i in range(len(raw_numbers) - 5):
        possible_draw = raw_numbers[i:i + 6]

        white_balls = possible_draw[:5]
        powerball = possible_draw[5]

        sorted_draw = sorted(white_balls) + [powerball]

        if is_valid_powerball_draw(sorted_draw):
            candidates.append(sorted_draw)

    if not candidates:
        return None

    # Return the first valid candidate found
    return candidates[0]


def extract_dated_draw_from_text(text: str) -> Optional[RawRecord]:
    """Extract the official result date and its six winning numbers.

    The official page contains other dates and many prize figures, so
    parsing is scoped to the first ``Winning Numbers`` section and stops
    before ``Power Play``.
    """
    section_start = text.find("Winning Numbers")
    if section_start < 0:
        return None

    result_section = text[section_start:]
    date_match = DRAW_DATE_PATTERN.search(result_section)
    if not date_match:
        return None

    try:
        draw_date = datetime.strptime(date_match.group(0), "%a, %b %d, %Y").date()
    except ValueError:
        return None

    numbers_section = result_section[date_match.end():]
    power_play_start = numbers_section.find("Power Play")
    if power_play_start >= 0:
        numbers_section = numbers_section[:power_play_start]

    draw = extract_numbers_from_text(numbers_section)
    if not is_valid_powerball_draw(draw):
        return None

    return {
        "white_balls": draw[:5],
        "powerball": draw[5],
        "draw_date": draw_date.isoformat(),
        "source": SOURCE_TN_SCRAPER,
    }


def fetch_latest_powerball_record() -> RawRecord:
    html = fetch_powerball_page()
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    record = extract_dated_draw_from_text(text)
    if record is None:
        raise ValueError("Could not extract a dated Powerball drawing from the official results page.")

    return record


def fetch_latest_powerball() -> Draw:
    """Backward-compatible number-only view of the latest official result."""
    record = fetch_latest_powerball_record()
    return record["white_balls"] + [record["powerball"]]


def update_numbers() -> dict:
    record = fetch_latest_powerball_record()
    transformed = transform_record(record)
    latest = transformed.balls() + [transformed.powerball]

    outcome = load_draw(transformed, require_date=True)

    if outcome.status == "failed":
        raise ValueError(f"Scraped drawing failed validation: {', '.join(outcome.reasons)}")

    if outcome.status == "skipped":
        return {
            "updated": False,
            "latest": latest,
            "message": "Drawing already exists.",
        }

    export_draws_to_json()

    return {
        "updated": True,
        "latest": latest,
        "message": "New drawing added.",
    }
