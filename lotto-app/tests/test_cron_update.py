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
from services.github_sync_service import GithubSyncError, GithubSyncResult


def _use_temp_paths(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(cron_update, "LOG_DIR", log_dir)
    monkeypatch.setattr(cron_update, "LOG_FILE", log_dir / "cron_update.log")
    monkeypatch.setattr(cron_update, "LOCK_FILE", log_dir / "cron_update.lock")
    return log_dir


def _read_log_lines(log_file: Path) -> list[dict]:
    return [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def _stub_update_numbers(monkeypatch, *, updated: bool, message: str):
    monkeypatch.setattr(cron_update, "update_numbers", lambda: {
        "updated": updated, "latest": [1, 2, 3, 4, 5, 6], "message": message,
    })


def _stub_sync_success(monkeypatch, *, changed: bool = False, commit_sha=None):
    monkeypatch.setattr(cron_update, "sync_numbers_json", lambda: GithubSyncResult(changed=changed, commit_sha=commit_sha))


def test_successful_update_returns_exit_0_and_logs(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    _stub_update_numbers(monkeypatch, updated=True, message="New drawing added.")
    _stub_sync_success(monkeypatch)

    exit_code = cron_update.main([])

    assert exit_code == 0
    lines = _read_log_lines(log_dir / "cron_update.log")
    assert any("New drawing inserted" in line["message"] for line in lines)
    assert all(line["level"] in ("INFO", "WARNING") for line in lines)


def test_no_new_draw_returns_exit_0(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    _stub_update_numbers(monkeypatch, updated=False, message="Drawing already exists.")
    _stub_sync_success(monkeypatch)

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
    _stub_update_numbers(monkeypatch, updated=False, message="Drawing already exists.")
    _stub_sync_success(monkeypatch)

    first = cron_update.main([])
    second = cron_update.main([])

    assert first == 0
    assert second == 0


def test_github_sync_failure_after_successful_update_returns_exit_1(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    _stub_update_numbers(monkeypatch, updated=True, message="New drawing added.")

    def _sync_boom():
        raise GithubSyncError("GitHub PUT failed with status 500")

    monkeypatch.setattr(cron_update, "sync_numbers_json", _sync_boom)

    exit_code = cron_update.main([])

    assert exit_code == 1
    # The database update itself still succeeded and was logged as such —
    # only the sync step failed.
    lines = _read_log_lines(log_dir / "cron_update.log")
    assert any("New drawing inserted" in line["message"] for line in lines)


def test_github_sync_success_with_change_is_logged(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    _stub_update_numbers(monkeypatch, updated=True, message="New drawing added.")
    _stub_sync_success(monkeypatch, changed=True, commit_sha="abc123")

    exit_code = cron_update.main([])

    assert exit_code == 0
    lines = _read_log_lines(log_dir / "cron_update.log")
    assert any("GitHub backup updated" in line["message"] and "abc123" in line["message"] for line in lines)


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
