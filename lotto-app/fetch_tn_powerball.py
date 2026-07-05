"""CLI entry point used by the daily GitHub Action workflow.

Kept as a standalone script (invoked as `python fetch_tn_powerball.py`)
so the existing workflow command doesn't need to change. Actual logic
lives in services.update_service.
"""

from services.update_service import update_numbers

if __name__ == "__main__":
    result = update_numbers()
    print(result)
