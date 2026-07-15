import base64
import json
import logging
from unittest.mock import Mock, patch

import pytest

from services import github_sync_service as sync_module
from services.github_sync_service import GithubSyncError, load_config, sync_numbers_json

VALID_SECRET = {
    "token": "github_pat_SUPER_SECRET_VALUE_12345",
    "owner": "DuleyWilliams",
    "repo": "powerball-rng-app",
    "branch": "main",
}


def _write_secret(tmp_path, payload=None):
    path = tmp_path / "github_sync.secret.json"
    path.write_text(json.dumps(payload if payload is not None else VALID_SECRET), encoding="utf-8")
    return path


def _write_local_file(tmp_path, content: bytes):
    path = tmp_path / "numbers.json"
    path.write_bytes(content)
    return path


def _mock_response(status_code, json_data=None):
    response = Mock()
    response.status_code = status_code
    response.json = Mock(return_value=json_data if json_data is not None else {})
    return response


def _github_get_response(content_bytes: bytes, sha: str = "abc123sha"):
    encoded = base64.b64encode(content_bytes).decode("ascii")
    return _mock_response(200, {"content": encoded, "sha": sha, "encoding": "base64"})


def _github_put_response(commit_sha: str = "def456commit"):
    return _mock_response(201, {"commit": {"sha": commit_sha}, "content": {"sha": "newfilesha"}})


# ---------------------------------------------------------------------
# Identical remote and local content
# ---------------------------------------------------------------------

def test_sync_skips_when_content_is_identical(tmp_path):
    content = b'{"numbers": [[1, 2, 3, 4, 5, 6]]}'
    secret = _write_secret(tmp_path)
    local = _write_local_file(tmp_path, content)

    with patch.object(sync_module.requests, "get", return_value=_github_get_response(content)) as mock_get, \
         patch.object(sync_module.requests, "put") as mock_put:
        result = sync_numbers_json(secret_file=secret, local_file=local)

    assert result.changed is False
    assert result.commit_sha is None
    mock_get.assert_called_once()
    mock_put.assert_not_called()


# ---------------------------------------------------------------------
# Successful update
# ---------------------------------------------------------------------

def test_sync_pushes_update_when_content_differs(tmp_path):
    remote_content = b'{"numbers": [[1, 2, 3, 4, 5, 6]]}'
    local_content = b'{"numbers": [[7, 8, 9, 10, 11, 12]]}'
    secret = _write_secret(tmp_path)
    local = _write_local_file(tmp_path, local_content)

    with patch.object(sync_module.requests, "get", return_value=_github_get_response(remote_content, sha="oldsha")), \
         patch.object(sync_module.requests, "put", return_value=_github_put_response("newcommit")) as mock_put:
        result = sync_numbers_json(secret_file=secret, local_file=local)

    assert result.changed is True
    assert result.commit_sha == "newcommit"
    mock_put.assert_called_once()


# ---------------------------------------------------------------------
# Missing secret file
# ---------------------------------------------------------------------

def test_missing_secret_file_raises(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    local = _write_local_file(tmp_path, b"{}")

    with pytest.raises(GithubSyncError, match="not found"):
        sync_numbers_json(secret_file=missing, local_file=local)


# ---------------------------------------------------------------------
# Invalid secret format
# ---------------------------------------------------------------------

@pytest.mark.parametrize("payload", [
    {"token": "x", "owner": "DuleyWilliams", "repo": "powerball-rng-app"},  # missing branch
    {"token": "", "owner": "DuleyWilliams", "repo": "powerball-rng-app", "branch": "main"},  # empty token
    {},
])
def test_invalid_secret_format_raises(tmp_path, payload):
    secret = _write_secret(tmp_path, payload)

    with pytest.raises(GithubSyncError, match="missing required keys"):
        load_config(secret)


def test_malformed_json_secret_raises(tmp_path):
    secret = tmp_path / "github_sync.secret.json"
    secret.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(GithubSyncError):
        load_config(secret)


def test_secret_file_that_is_not_a_json_object_raises(tmp_path):
    secret = tmp_path / "github_sync.secret.json"
    secret.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(GithubSyncError, match="JSON object"):
        load_config(secret)


# ---------------------------------------------------------------------
# GitHub GET failure
# ---------------------------------------------------------------------

def test_github_get_failure_raises(tmp_path):
    secret = _write_secret(tmp_path)
    local = _write_local_file(tmp_path, b"{}")

    with patch.object(sync_module.requests, "get", return_value=_mock_response(404)):
        with pytest.raises(GithubSyncError, match="GET failed with status 404"):
            sync_numbers_json(secret_file=secret, local_file=local)


def test_github_get_network_error_raises(tmp_path):
    secret = _write_secret(tmp_path)
    local = _write_local_file(tmp_path, b"{}")

    with patch.object(sync_module.requests, "get", side_effect=sync_module.requests.ConnectionError("boom")):
        with pytest.raises(GithubSyncError, match="GET request failed"):
            sync_numbers_json(secret_file=secret, local_file=local)


# ---------------------------------------------------------------------
# GitHub PUT failure
# ---------------------------------------------------------------------

def test_github_put_failure_raises(tmp_path):
    remote_content = b"old"
    secret = _write_secret(tmp_path)
    local = _write_local_file(tmp_path, b"new")

    with patch.object(sync_module.requests, "get", return_value=_github_get_response(remote_content)), \
         patch.object(sync_module.requests, "put", return_value=_mock_response(422)):
        with pytest.raises(GithubSyncError, match="PUT failed with status 422"):
            sync_numbers_json(secret_file=secret, local_file=local)


def test_github_put_network_error_raises(tmp_path):
    remote_content = b"old"
    secret = _write_secret(tmp_path)
    local = _write_local_file(tmp_path, b"new")

    with patch.object(sync_module.requests, "get", return_value=_github_get_response(remote_content)), \
         patch.object(sync_module.requests, "put", side_effect=sync_module.requests.Timeout("boom")):
        with pytest.raises(GithubSyncError, match="PUT request failed"):
            sync_numbers_json(secret_file=secret, local_file=local)


# ---------------------------------------------------------------------
# Token never appears in errors or logs
# ---------------------------------------------------------------------

def test_token_never_appears_in_errors_or_logs(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)

    secret_payload = dict(VALID_SECRET)
    secret_payload["token"] = "github_pat_UNIQUE_SECRET_MARKER_XYZ"
    secret = _write_secret(tmp_path, secret_payload)
    local = _write_local_file(tmp_path, b"new")

    with patch.object(
        sync_module.requests, "get",
        side_effect=sync_module.requests.ConnectionError("connection failed, token=whatever-leaked"),
    ):
        with pytest.raises(GithubSyncError) as exc_info:
            sync_numbers_json(secret_file=secret, local_file=local)

    assert "UNIQUE_SECRET_MARKER" not in str(exc_info.value)
    for record in caplog.records:
        assert "UNIQUE_SECRET_MARKER" not in record.getMessage()


def test_token_never_appears_in_successful_run_logs(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)

    secret_payload = dict(VALID_SECRET)
    secret_payload["token"] = "github_pat_UNIQUE_SECRET_MARKER_XYZ"
    secret = _write_secret(tmp_path, secret_payload)
    content = b"same-on-both-sides"
    local = _write_local_file(tmp_path, content)

    with patch.object(sync_module.requests, "get", return_value=_github_get_response(content)):
        sync_numbers_json(secret_file=secret, local_file=local)

    for record in caplog.records:
        assert "UNIQUE_SECRET_MARKER" not in record.getMessage()


# ---------------------------------------------------------------------
# Correct SHA, branch, and commit message in the PUT request
# ---------------------------------------------------------------------

def test_put_request_includes_correct_sha_branch_and_message(tmp_path):
    remote_content = b"old-content"
    local_content = b"new-content"
    secret = _write_secret(tmp_path)
    local = _write_local_file(tmp_path, local_content)

    with patch.object(sync_module.requests, "get", return_value=_github_get_response(remote_content, sha="the-remote-sha")), \
         patch.object(sync_module.requests, "put", return_value=_github_put_response()) as mock_put:
        sync_numbers_json(secret_file=secret, local_file=local)

    _, kwargs = mock_put.call_args
    body = kwargs["json"]

    assert body["sha"] == "the-remote-sha"
    assert body["branch"] == "main"
    assert body["message"] == "Update Powerball drawing backup data"
    assert base64.b64decode(body["content"]) == local_content


def test_get_request_uses_correct_url_and_ref(tmp_path):
    content = b"content"
    secret = _write_secret(tmp_path)
    local = _write_local_file(tmp_path, content)

    with patch.object(sync_module.requests, "get", return_value=_github_get_response(content)) as mock_get:
        sync_numbers_json(secret_file=secret, local_file=local)

    _, kwargs = mock_get.call_args
    called_url = mock_get.call_args[0][0]

    assert called_url == "https://api.github.com/repos/DuleyWilliams/powerball-rng-app/contents/lotto-app/numbers.json"
    assert kwargs["params"] == {"ref": "main"}
    assert kwargs["headers"]["Authorization"] == f"Bearer {VALID_SECRET['token']}"
