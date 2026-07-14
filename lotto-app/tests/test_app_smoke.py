"""Smoke test: actually executes app.py through Streamlit's script runner.

A plain import or an HTTP-200 check on the server is not enough — Streamlit
only raises errors like duplicate element IDs when the script body runs.
This caught a real bug during Milestone 4 (a chart rendered twice under
two different sections) that no other test in this suite could catch.
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


def test_app_runs_without_exceptions():
    at = AppTest.from_file(str(APP_PATH), default_timeout=60)
    at.run()

    assert at.exception == []
