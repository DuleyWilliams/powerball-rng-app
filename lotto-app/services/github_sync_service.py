"""Synchronizes lotto-app/numbers.json to GitHub via the REST Contents
API — no git, git CLI, subprocess, SSH keys, or GitPython.

The token is read from a server-only secret file (never committed, see
github_sync.secret.json.example) and must never appear in log messages,
exception messages, or HTTP responses. Every error message constructed
in this module is built from safe values only (HTTP status codes, key
names, exception class names) — never from raw request/response bodies
or exception text that could echo request internals.
"""

import base64
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

from core.config import DATA_FILE

logger = logging.getLogger(__name__)

SECRET_FILE = Path(__file__).resolve().parent.parent / "github_sync.secret.json"
GITHUB_API_BASE = "https://api.github.com"
CONTENTS_PATH = "lotto-app/numbers.json"
COMMIT_MESSAGE = "Update Powerball drawing backup data"
REQUEST_TIMEOUT_SECONDS = 20

_REQUIRED_SECRET_KEYS = ("token", "owner", "repo", "branch")


class GithubSyncError(Exception):
    """Raised for any sync failure. The message is always safe to log —
    it never includes the token or raw HTTP response bodies."""


@dataclass(frozen=True)
class GithubSyncConfig:
    token: str
    owner: str
    repo: str
    branch: str


@dataclass(frozen=True)
class GithubSyncResult:
    changed: bool
    commit_sha: Optional[str] = None


def load_config(secret_file: Path = SECRET_FILE) -> GithubSyncConfig:
    if not secret_file.exists():
        raise GithubSyncError(f"Secret file not found: {secret_file}")

    try:
        raw = json.loads(secret_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GithubSyncError(f"Secret file could not be read/parsed: {type(error).__name__}") from None

    if not isinstance(raw, dict):
        raise GithubSyncError("Secret file must contain a JSON object.")

    missing = [key for key in _REQUIRED_SECRET_KEYS if not isinstance(raw.get(key), str) or not raw.get(key)]
    if missing:
        raise GithubSyncError(f"Secret file missing required keys: {', '.join(missing)}")

    return GithubSyncConfig(
        token=raw["token"],
        owner=raw["owner"],
        repo=raw["repo"],
        branch=raw["branch"],
    )


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _contents_url(config: GithubSyncConfig) -> str:
    return f"{GITHUB_API_BASE}/repos/{config.owner}/{config.repo}/contents/{CONTENTS_PATH}"


def _fetch_remote(config: GithubSyncConfig) -> tuple[bytes, str]:
    """Returns (decoded_content_bytes, sha). Never raises anything that
    could carry the token or a raw response body."""
    try:
        response = requests.get(
            _contents_url(config),
            headers=_headers(config.token),
            params={"ref": config.branch},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        raise GithubSyncError(f"GitHub GET request failed: {type(error).__name__}") from None

    if response.status_code != 200:
        raise GithubSyncError(f"GitHub GET failed with status {response.status_code}")

    try:
        payload = response.json()
        content_b64 = payload["content"]
        sha = payload["sha"]
    except (ValueError, KeyError, TypeError) as error:
        raise GithubSyncError(f"GitHub GET returned an unexpected payload: {type(error).__name__}") from None

    try:
        decoded = base64.b64decode(content_b64)
    except (ValueError, TypeError) as error:
        raise GithubSyncError(f"GitHub content could not be decoded: {type(error).__name__}") from None

    return decoded, sha


def _push_update(config: GithubSyncConfig, new_content: bytes, sha: str) -> str:
    """Returns the new commit SHA. Never raises anything that could
    carry the token or a raw response body."""
    body = {
        "message": COMMIT_MESSAGE,
        "content": base64.b64encode(new_content).decode("ascii"),
        "sha": sha,
        "branch": config.branch,
    }

    try:
        response = requests.put(
            _contents_url(config),
            headers=_headers(config.token),
            json=body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        raise GithubSyncError(f"GitHub PUT request failed: {type(error).__name__}") from None

    if response.status_code not in (200, 201):
        raise GithubSyncError(f"GitHub PUT failed with status {response.status_code}")

    try:
        return response.json()["commit"]["sha"]
    except (ValueError, KeyError, TypeError) as error:
        raise GithubSyncError(f"GitHub PUT returned an unexpected payload: {type(error).__name__}") from None


def sync_numbers_json(secret_file: Path = SECRET_FILE, local_file: Path = DATA_FILE) -> GithubSyncResult:
    """Pushes local_file to GitHub if its content differs from what's
    currently there. Raises GithubSyncError on any failure — every
    failure is also logged as github_sync_failed before the exception
    propagates, so callers don't need to duplicate that logging.
    """
    logger.info("github_sync_started")

    try:
        config = load_config(secret_file)

        if not local_file.exists():
            raise GithubSyncError(f"Local file not found: {local_file}")

        local_content = local_file.read_bytes()
        remote_content, remote_sha = _fetch_remote(config)

        if remote_content == local_content:
            logger.info("github_sync_skipped_no_change")
            return GithubSyncResult(changed=False)

        commit_sha = _push_update(config, local_content, remote_sha)
        logger.info("github_sync_completed commit_sha=%s", commit_sha)
        return GithubSyncResult(changed=True, commit_sha=commit_sha)

    except GithubSyncError as error:
        logger.error("github_sync_failed: %s", error)
        raise
