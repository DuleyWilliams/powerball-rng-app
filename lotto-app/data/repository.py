"""Data layer: all numbers.json I/O lives here.

Still a flat JSON file for Milestone 1 — SQLite migration is a later
milestone. Path resolution is cwd-independent (see core.config.DATA_FILE).
"""

import json
from typing import Any

from core.config import DATA_FILE

Draw = list[int]
Dataset = dict[str, Any]


def load_dataset() -> Dataset:
    if not DATA_FILE.exists():
        return {"numbers": []}

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_dataset(data: Dataset) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def load_draws() -> list[Draw]:
    return load_dataset().get("numbers", [])
