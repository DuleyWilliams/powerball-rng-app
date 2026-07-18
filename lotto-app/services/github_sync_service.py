"""Generic GitHub Contents API file synchronization — no git, git CLI,
subprocess, SSH keys, or GitPython.

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

from core.config import DATA_FILE, NUMBERS_JSON_GITHUB_PATH, COMMIT_MESSAGE_NUMBERS_JSON

logger = logging.getLogger(__name__)

SECRET_FILE = Path(__file__).resolve().parent.parent / "github_sync.secret.json"
GITHUB_API_BASE = "https://api.github.com"
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


def _contents_url(config: GithubSyncConfig, github_path: str) -> str:
    return f"{GITHUB_API_BASE}/repos/{config.owner}/{config.repo}/contents/{github_path}"


def _fetch_remote(config: GithubSyncConfig, github_path: str) -> tuple[Optional[bytes], Optional[str]]:
    """Returns (content_bytes, sha). (None, None) means the file
    doesn't exist yet on GitHub — a create, not an update. Never raises
    anything that could carry the token or a raw response body."""
    try:
        response = requests.get(
            _contents_url(config, github_path),
            headers=_headers(config.token),
            params={"ref": config.branch},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        raise GithubSyncError(f"GitHub GET request failed: {type(error).__name__}") from None

    if response.status_code == 404:
        return None, None

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


def _push_update(
    config: GithubSyncConfig,
    github_path: str,
    new_content: bytes,
    sha: Optional[str],
    commit_message: str,
) -> str:
    """Returns the new commit SHA. sha=None creates a new file (GitHub
    rejects a sha field for a file that doesn't exist yet). Never
    raises anything that could carry the token or a raw response body.
    """
    body = {
        "message": commit_message,
        "content": base64.b64encode(new_content).decode("ascii"),
        "branch": config.branch,
    }
    if sha is not None:
        body["sha"] = sha

    try:
        response = requests.put(
            _contents_url(config, github_path),
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


def sync_file(
    local_path: Path,
    github_path: str,
    commit_message: str,
    secret_file: Path = SECRET_FILE,
) -> GithubSyncResult:
    """Pushes local_path to github_path if its content differs from
    what's currently there on GitHub (or creates it if it doesn't exist
    there yet). Raises GithubSyncError on any failure — every failure
    is also logged as github_sync_failed before the exception
    propagates, so callers don't need to duplicate that logging.
    """
    logger.info("github_sync_started path=%s", github_path)

    try:
        config = load_config(secret_file)

        if not local_path.exists():
            raise GithubSyncError(f"Local file not found: {local_path}")

        local_content = local_path.read_bytes()
        remote_content, remote_sha = _fetch_remote(config, github_path)

        if remote_content == local_content:
            logger.info("github_sync_skipped_no_change path=%s", github_path)
            return GithubSyncResult(changed=False)

        commit_sha = _push_update(config, github_path, local_content, remote_sha, commit_message)
        logger.info("github_sync_completed path=%s commit_sha=%s", github_path, commit_sha)
        return GithubSyncResult(changed=True, commit_sha=commit_sha)

    except GithubSyncError as error:
        logger.error("github_sync_failed path=%s: %s", github_path, error)
        raise


def sync_numbers_json(secret_file: Path = SECRET_FILE, local_file: Optional[Path] = None) -> GithubSyncResult:
    """Preserves the original numbers.json sync behavior as a thin
    wrapper around sync_file()."""
    return sync_file(
        local_file if local_file is not None else DATA_FILE,
        NUMBERS_JSON_GITHUB_PATH,
        COMMIT_MESSAGE_NUMBERS_JSON,
        secret_file=secret_file,
    )
