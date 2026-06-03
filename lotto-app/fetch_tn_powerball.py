import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_FILE = Path("numbers.json")
POWERBALL_URL = "https://www.powerball.com/draw-result?oc=tn"


def load_numbers():
    if not DATA_FILE.exists():
        return {"numbers": []}

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_numbers(data):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def fetch_powerball_page():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(POWERBALL_URL, headers=headers, timeout=20)
    response.raise_for_status()
    return response.text


def is_valid_powerball_draw(draw):
    if not draw or len(draw) != 6:
        return False

    white_balls = draw[:5]
    powerball = draw[5]

    if len(set(white_balls)) != 5:
        return False

    if not all(1 <= n <= 69 for n in white_balls):
        return False

    if not 1 <= powerball <= 26:
        return False

    return True


def extract_numbers_from_text(text):
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


def fetch_latest_powerball():
    html = fetch_powerball_page()
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    draw = extract_numbers_from_text(text)

    if not is_valid_powerball_draw(draw):
        raise ValueError(f"Could not extract a valid Powerball drawing. Found: {draw}")

    return draw


def update_numbers():
    data = load_numbers()
    existing = data.get("numbers", [])

    latest = fetch_latest_powerball()

    if latest not in existing:
        existing.insert(0, latest)
        data["numbers"] = existing
        save_numbers(data)
        return {
            "updated": True,
            "latest": latest,
            "message": "New drawing added."
        }

    return {
        "updated": False,
        "latest": latest,
        "message": "Drawing already exists."
    }


if __name__ == "__main__":
    result = update_numbers()
    print(result)