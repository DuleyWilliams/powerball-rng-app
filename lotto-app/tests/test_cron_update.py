import json
import subprocess
import sys
from pathlib import Path

import pytest

# cron_update.py (and this test module) use fcntl.flock, which only exists
# on POSIX. The IONOS deployment target is Debian Linux; local Windows dev
# environments should skip this module cleanly rather than break collection
# of the rest of the suite.
fcntl = pytest.importorskip("fcntl")

import cron_update


def _use_temp_paths(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(cron_update, "LOG_DIR", log_dir)
    monkeypatch.setattr(cron_update, "LOG_FILE", log_dir / "cron_update.log")
    monkeypatch.setattr(cron_update, "LOCK_FILE", log_dir / "cron_update.lock")
    return log_dir


def _read_log_lines(log_file: Path) -> list[dict]:
    return [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_successful_update_returns_exit_0_and_logs(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(cron_update, "update_numbers", lambda: {
        "updated": True, "latest": [1, 2, 3, 4, 5, 6], "message": "New drawing added.",
    })

    exit_code = cron_update.main([])

    assert exit_code == 0
    lines = _read_log_lines(log_dir / "cron_update.log")
    assert any("New drawing inserted" in line["message"] for line in lines)
    assert all(line["level"] in ("INFO", "WARNING") for line in lines)


def test_no_new_draw_returns_exit_0(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(cron_update, "update_numbers", lambda: {
        "updated": False, "latest": [1, 2, 3, 4, 5, 6], "message": "Drawing already exists.",
    })

    exit_code = cron_update.main([])

    assert exit_code == 0
    lines = _read_log_lines(log_dir / "cron_update.log")
    assert any("No new drawing" in line["message"] for line in lines)


def test_fetch_failure_returns_exit_1(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)

    def _boom():
        raise ValueError("network unreachable")

    monkeypatch.setattr(cron_update, "update_numbers", _boom)

    exit_code = cron_update.main([])

    assert exit_code == 1
    lines = _read_log_lines(log_dir / "cron_update.log")
    assert any(line["level"] == "ERROR" and "Cron update failed" in line["message"] for line in lines)


def test_dry_run_returns_exit_0_without_calling_update_numbers(tmp_path, monkeypatch):
    _use_temp_paths(tmp_path, monkeypatch)

    def _should_not_be_called():
        raise AssertionError("update_numbers must not be called in --dry-run")

    monkeypatch.setattr(cron_update, "update_numbers", _should_not_be_called)

    exit_code = cron_update.main(["--dry-run"])

    assert exit_code == 0


def test_lock_contention_returns_exit_2(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    log_dir.mkdir(parents=True, exist_ok=True)
    lock_path = log_dir / "cron_update.lock"

    held_lock_file = open(lock_path, "a+")
    fcntl.flock(held_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)

    try:
        exit_code = cron_update.main(["--dry-run"])
        assert exit_code == 2
    finally:
        fcntl.flock(held_lock_file, fcntl.LOCK_UN)
        held_lock_file.close()


def test_lock_is_released_after_a_run_so_a_later_run_can_proceed(tmp_path, monkeypatch):
    _use_temp_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(cron_update, "update_numbers", lambda: {
        "updated": False, "latest": [1, 2, 3, 4, 5, 6], "message": "Drawing already exists.",
    })

    first = cron_update.main([])
    second = cron_update.main([])

    assert first == 0
    assert second == 0


def test_runs_from_unrelated_working_directory(tmp_path):
    """End-to-end proof that paths resolve from __file__, not cwd.

    Runs the real script as a subprocess with cwd set to an unrelated
    tmp directory. Uses --dry-run so this stays network-free while still
    proving the script locates its own logs/ directory correctly.
    """
    script_path = Path(cron_update.__file__).resolve()

    result = subprocess.run(
        [sys.executable, str(script_path), "--dry-run"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"

    real_log_file = script_path.parent / "logs" / "cron_update.log"
    assert real_log_file.exists()

    lines = _read_log_lines(real_log_file)
    assert lines
    assert lines[-1]["message"].startswith("Dry run")
