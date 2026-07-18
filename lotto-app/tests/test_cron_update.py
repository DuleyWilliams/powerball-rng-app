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
from core.config import NUMBERS_JSON_GITHUB_PATH, DRAWS_BACKUP_GITHUB_PATH, BACKUP_MANIFEST_GITHUB_PATH
from services.github_sync_service import GithubSyncError, GithubSyncResult


def _use_temp_paths(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(cron_update, "LOG_DIR", log_dir)
    monkeypatch.setattr(cron_update, "LOG_FILE", log_dir / "cron_update.log")
    monkeypatch.setattr(cron_update, "LOCK_FILE", log_dir / "cron_update.lock")
    return log_dir


def _read_log_lines(log_file: Path) -> list[dict]:
    return [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def _stub_update_numbers(monkeypatch, *, updated: bool, message: str = "ok"):
    monkeypatch.setattr(cron_update, "update_numbers", lambda: {
        "updated": updated, "latest": [1, 2, 3, 4, 5, 6], "message": message,
    })


def _stub_export_backup(monkeypatch, *, fails: bool = False):
    if fails:
        def _boom():
            raise RuntimeError("export failed")
        monkeypatch.setattr(cron_update, "export_backup", _boom)
    else:
        monkeypatch.setattr(cron_update, "export_backup", lambda: None)


def _stub_snapshot(monkeypatch, *, fails: bool = False):
    if fails:
        def _boom():
            raise RuntimeError("snapshot failed")
        monkeypatch.setattr(cron_update, "create_and_rotate_snapshot", _boom)
    else:
        monkeypatch.setattr(cron_update, "create_and_rotate_snapshot", lambda: (Path("database-20260101.sqlite3"), []))


def _stub_sync_file(monkeypatch, *, changed_paths=(), failing_paths=()):
    """changed_paths: github paths that should report changed=True.
    failing_paths: github paths that should raise GithubSyncError.
    Anything else reports changed=False (already current).
    """
    def _fake_sync_file(local_path, github_path, commit_message):
        if github_path in failing_paths:
            raise GithubSyncError(f"GitHub PUT failed with status 500 for {github_path}")
        if github_path in changed_paths:
            return GithubSyncResult(changed=True, commit_sha=f"commit-{github_path}")
        return GithubSyncResult(changed=False)

    monkeypatch.setattr(cron_update, "sync_file", _fake_sync_file)


def _default_stubs(monkeypatch, *, updated=True, changed_paths=(), failing_paths=(), export_fails=False, snapshot_fails=False):
    _stub_update_numbers(monkeypatch, updated=updated, message="New drawing added." if updated else "Drawing already exists.")
    _stub_snapshot(monkeypatch, fails=snapshot_fails)
    _stub_export_backup(monkeypatch, fails=export_fails)
    _stub_sync_file(monkeypatch, changed_paths=changed_paths, failing_paths=failing_paths)


def test_successful_update_returns_exit_0_and_logs(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    _default_stubs(monkeypatch, updated=True)

    exit_code = cron_update.main([])

    assert exit_code == 0
    lines = _read_log_lines(log_dir / "cron_update.log")
    assert any("New drawing inserted" in line["message"] for line in lines)
    assert all(line["level"] in ("INFO", "WARNING") for line in lines)


def test_no_new_draw_returns_exit_0(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    _default_stubs(monkeypatch, updated=False)

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
    _default_stubs(monkeypatch, updated=False)

    first = cron_update.main([])
    second = cron_update.main([])

    assert first == 0
    assert second == 0


# ---------------------------------------------------------------------
# All three files already current -> zero commits, exit 0
# ---------------------------------------------------------------------

def test_all_three_files_already_current_creates_no_commits(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    _default_stubs(monkeypatch, updated=True, changed_paths=())  # nothing changed anywhere

    exit_code = cron_update.main([])

    assert exit_code == 0
    lines = _read_log_lines(log_dir / "cron_update.log")
    assert not any("updated: commit" in line["message"] for line in lines)


# ---------------------------------------------------------------------
# Manifest only synced when draws_backup.json actually changed
# ---------------------------------------------------------------------

def test_manifest_synced_when_draws_backup_changes(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    _default_stubs(monkeypatch, updated=True, changed_paths={DRAWS_BACKUP_GITHUB_PATH, BACKUP_MANIFEST_GITHUB_PATH})

    exit_code = cron_update.main([])

    assert exit_code == 0
    lines = _read_log_lines(log_dir / "cron_update.log")
    assert any("draws_backup.json updated" in line["message"] for line in lines)
    assert any("backup manifest updated" in line["message"] for line in lines)


def test_manifest_not_synced_when_draws_backup_unchanged(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    # numbers.json changed, but draws_backup.json did not -> manifest sync
    # must never even be attempted.
    _default_stubs(monkeypatch, updated=True, changed_paths={NUMBERS_JSON_GITHUB_PATH})

    def _fake_sync_file(local_path, github_path, commit_message):
        if github_path == BACKUP_MANIFEST_GITHUB_PATH:
            raise AssertionError("manifest must not be synced when draws_backup.json is unchanged")
        if github_path == NUMBERS_JSON_GITHUB_PATH:
            return GithubSyncResult(changed=True, commit_sha="commit-numbers")
        return GithubSyncResult(changed=False)

    monkeypatch.setattr(cron_update, "sync_file", _fake_sync_file)

    exit_code = cron_update.main([])

    assert exit_code == 0


# ---------------------------------------------------------------------
# Partial sync failure
# ---------------------------------------------------------------------

def test_partial_sync_failure_returns_exit_1_but_other_files_still_synced(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    # numbers.json succeeds; draws_backup.json fails.
    _default_stubs(
        monkeypatch, updated=True,
        changed_paths={NUMBERS_JSON_GITHUB_PATH},
        failing_paths={DRAWS_BACKUP_GITHUB_PATH},
    )

    exit_code = cron_update.main([])

    assert exit_code == 1
    lines = _read_log_lines(log_dir / "cron_update.log")
    # numbers.json's success is still logged despite the other failure.
    assert any("numbers.json updated" in line["message"] for line in lines)


def test_snapshot_rotation_failure_is_partial_failure_but_sync_still_attempted(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    _default_stubs(monkeypatch, updated=True, snapshot_fails=True, changed_paths={NUMBERS_JSON_GITHUB_PATH})

    exit_code = cron_update.main([])

    assert exit_code == 1
    lines = _read_log_lines(log_dir / "cron_update.log")
    assert any("Private snapshot rotation failed" in line["message"] for line in lines)
    # Sync still ran and succeeded despite the snapshot failure.
    assert any("numbers.json updated" in line["message"] for line in lines)


def test_backup_export_failure_skips_archive_sync_but_still_syncs_numbers_json(tmp_path, monkeypatch):
    log_dir = _use_temp_paths(tmp_path, monkeypatch)
    _default_stubs(monkeypatch, updated=True, export_fails=True, changed_paths={NUMBERS_JSON_GITHUB_PATH})

    def _fake_sync_file(local_path, github_path, commit_message):
        if github_path in (DRAWS_BACKUP_GITHUB_PATH, BACKUP_MANIFEST_GITHUB_PATH):
            raise AssertionError("must not attempt to sync a backup that failed to export")
        return GithubSyncResult(changed=True, commit_sha="commit-numbers")

    monkeypatch.setattr(cron_update, "sync_file", _fake_sync_file)

    exit_code = cron_update.main([])

    assert exit_code == 1
    lines = _read_log_lines(log_dir / "cron_update.log")
    assert any("Backup export failed" in line["message"] for line in lines)
    assert any("numbers.json updated" in line["message"] for line in lines)


# ---------------------------------------------------------------------
# Snapshot rotation only runs when a new drawing was inserted
# ---------------------------------------------------------------------

def test_snapshot_rotation_skipped_when_no_new_drawing(tmp_path, monkeypatch):
    _use_temp_paths(tmp_path, monkeypatch)
    _stub_update_numbers(monkeypatch, updated=False)
    _stub_export_backup(monkeypatch)
    _stub_sync_file(monkeypatch)

    def _should_not_be_called():
        raise AssertionError("snapshot rotation must not run when no new drawing was inserted")

    monkeypatch.setattr(cron_update, "create_and_rotate_snapshot", _should_not_be_called)

    exit_code = cron_update.main([])

    assert exit_code == 0


def test_snapshot_rotation_runs_when_new_drawing_inserted(tmp_path, monkeypatch):
    _use_temp_paths(tmp_path, monkeypatch)
    _stub_update_numbers(monkeypatch, updated=True)
    _stub_export_backup(monkeypatch)
    _stub_sync_file(monkeypatch)

    calls = []
    monkeypatch.setattr(cron_update, "create_and_rotate_snapshot", lambda: calls.append(1) or (Path("x.sqlite3"), []))

    cron_update.main([])

    assert len(calls) == 1


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
