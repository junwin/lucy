"""
Live integration test: starts the Flask app on port 5001, hits /prompt_builder,
and verifies the response includes chat2 history.

This test:
  - Generates a self-signed SSL cert for testing
  - Creates a temporary config with port 5001
  - Starts the app in a subprocess
  - Seeds chat2 data directly into the storage directory
  - Calls /prompt_builder via curl
  - Kills the app
  - Asserts the response contains expected history

Usage:
  pytest tests/test_live_prompt_builder.py -v

Requires:
  - curl
  - openssl (for cert generation)
  - The app's dependencies installed in the venv
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_self_signed_cert(cert_dir: Path) -> tuple[Path, Path]:
    """Generate a self-signed cert and key using openssl.

    Returns (cert_path, key_path).
    """
    cert_path = cert_dir / "test.crt"
    key_path = cert_dir / "test.key"

    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key_path),
            "-out", str(cert_path),
            "-days", "1",
            "-nodes",
            "-subj", "/C=US/ST=Test/L=Test/O=Test/CN=127.0.0.1",
        ],
        capture_output=True,
        check=True,
    )

    return cert_path, key_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def live_config(tmp_path: Path) -> Path:
    """Create a temporary config.json with port 5001 and a self-signed cert."""
    # Generate self-signed cert
    cert_path, key_path = _generate_self_signed_cert(tmp_path)

    config = {
        "storage_root_path": str(tmp_path / "lucy_storage"),
        "storage_namespace": "data",
        "external_roots": {
            "repo_lucy": REPO_ROOT,
            "repos": str(Path(REPO_ROOT).parent),
            "obsidian": str(tmp_path / "obsidian"),
            "sandbox_cmd": str(tmp_path / "sandbox"),
            "lucy_data_files": str(tmp_path / "lucy_storage"),
        },
        "agents_path": "static/data/agents.json",
        "code_sandbox_path": str(tmp_path / "sandbox"),
        "python_utils_path": "src/utils",
        "swagger_url": "/api/docs",
        "api_url": "/static/swagger.json",
        "app_name": "Lucy API Test",
        "ssl_cert": str(cert_path),
        "ssl_key": str(key_path),
        "host": "127.0.0.1",
        "port": 5001,
        "debug": False,
        "credential_path": str(tmp_path / "credentials"),
        "elapsed_new_session_seconds": 600,
        "max_tool_result_chars": 64000,
        "environment_prompt_block": "ENVIRONMENT\n- Test mode",
    }
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    return config_path


@pytest.fixture
def seeded_chat2_data(tmp_path: Path, live_config: Path) -> str:
    """Seed chat2 data directly into the storage directory.

    Returns the session_id so the test can use it in the curl call.
    """
    storage_root = tmp_path / "lucy_storage" / "data"
    storage_root.mkdir(parents=True, exist_ok=True)

    session_id = str(uuid.uuid4())
    session_dir = storage_root / "chat2" / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Write meta.json
    meta = {
        "session_id": session_id,
        "user_id": "test_user",
        "account_name": "junwin",
        "agent_name": "peace",
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
        "tags": [],
        "friendly_name": None,
    }
    with open(session_dir / "meta.json", "w") as f:
        json.dump(meta, f)

    # Write events.jsonl — include user/assistant messages that should appear in history
    events = [
        {"role": "user", "actor": "test_user", "kind": "user_message", "payload": "Hello from chat2 history", "timestamp": "2025-01-01T00:00:01+00:00", "event_id": str(uuid.uuid4())},
        {"role": "assistant", "actor": "peace", "kind": "assistant_message", "payload": "Hi! I see your chat2 data.", "timestamp": "2025-01-01T00:00:02+00:00", "event_id": str(uuid.uuid4())},
        {"role": "user", "actor": "test_user", "kind": "user_message", "payload": "What do you remember?", "timestamp": "2025-01-01T00:00:03+00:00", "event_id": str(uuid.uuid4())},
        {"role": "assistant", "actor": "peace", "kind": "assistant_tool_call", "payload": "{}", "timestamp": "2025-01-01T00:00:04+00:00", "event_id": str(uuid.uuid4())},
        {"role": "assistant", "actor": "peace", "kind": "tool_result", "payload": "{}", "timestamp": "2025-01-01T00:00:05+00:00", "event_id": str(uuid.uuid4())},
        {"role": "assistant", "actor": "peace", "kind": "assistant_message", "payload": "I remember everything from chat2.", "timestamp": "2025-01-01T00:00:06+00:00", "event_id": str(uuid.uuid4())},
    ]
    with open(session_dir / "events.jsonl", "w") as f:
        for evt in events:
            f.write(json.dumps(evt) + "\n")

    return session_id


@pytest.fixture
def app_process(live_config: Path, seeded_chat2_data: str, tmp_path: Path):
    """Start the Flask app in a subprocess with the temp config.

    Uses 'python app.py' directly. Must unset FLASK_RUN_FROM_CLI to prevent
    flask CLI from intercepting the call.
    Yields the process object. Cleans up on teardown.
    """
    env = os.environ.copy()
    # Unset flask CLI env vars so 'python app.py' runs the __main__ block
    env.pop("FLASK_APP", None)
    env.pop("FLASK_RUN_FROM_CLI", None)
    env.pop("FLASK_DEBUG", None)
    env.pop("FLASK_ENV", None)
    env["PYTHONPATH"] = REPO_ROOT

    # Temporarily replace config.json in the repo root with our test config
    config_dest = Path(REPO_ROOT) / "config.json"
    backup = None
    if config_dest.exists():
        backup = config_dest.with_suffix(".json.bak")
        config_dest.rename(backup)

    # Also temporarily move aside config.local.json so local overrides do not interfere with test config
    local_config_dest = Path(REPO_ROOT) / "config.local.json"
    local_backup = None
    if local_config_dest.exists():
        local_backup = local_config_dest.with_suffix(".local.json.bak")
        local_config_dest.rename(local_backup)

    # Copy temp config to repo root
    import shutil
    shutil.copy(str(live_config), str(config_dest))

    # Ensure the agents file exists
    agents_src = Path(REPO_ROOT) / "static" / "data" / "agents.json"
    if not agents_src.exists():
        agents_src.parent.mkdir(parents=True, exist_ok=True)
        with open(agents_src, "w") as f:
            json.dump({"agents": [{"name": "peace", "model": "test-model"}]}, f)

    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for the app to start
    time.sleep(4)

    # Check if process is still running
    poll = proc.poll()
    if poll is not None:
        stdout, stderr = proc.communicate()
        # Restore config before raising
        if backup and backup.exists():
            backup.rename(config_dest)
        if local_backup and local_backup.exists():
            local_backup.rename(local_config_dest)
        pytest.fail(
            f"App failed to start (exit code {poll}).\n"
            f"stdout: {stdout.decode()}\n"
            f"stderr: {stderr.decode()}"
        )

    yield proc

    # Cleanup
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)

    # Restore original config
    if backup and backup.exists():
        backup.rename(config_dest)
    elif config_dest.exists() and backup is None:
        config_dest.unlink()

    # Restore original local config
    if local_backup and local_backup.exists():
        local_backup.rename(local_config_dest)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_live_prompt_builder_returns_chat2_history(app_process, seeded_chat2_data):
    """Start the app, hit /prompt_builder, verify chat2 history appears."""
    payload = {
        "query": "What do you remember?",
        "agentName": "peace",
        "accountName": "junwin",
        "contextName": "lucyproject",
        "conversationId": seeded_chat2_data,
    }

    # Use curl with -k (insecure) since we have a self-signed cert
    cmd = [
        "curl", "-s", "-X", "POST",
        "http://127.0.0.1:5001/prompt_builder",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(payload),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

    # Check curl succeeded
    assert result.returncode == 0, (
        f"curl failed (exit {result.returncode}): {result.stderr}\n"
        f"stdout: {result.stdout}"
    )

    # Parse response
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Response is not valid JSON: {result.stdout}\nStderr: {result.stderr}")

    # The response should be a list of messages (the prompt)
    assert isinstance(response, list), f"Expected list, got: {type(response)}: {response}"

    # Check that chat2 history is present
    contents = [m.get("content", "") for m in response if isinstance(m, dict)]

    assert any("Hello from chat2 history" in c for c in contents), (
        f"Expected chat2 history in response. Contents: {contents}"
    )
    assert any("I remember everything from chat2" in c for c in contents), (
        f"Expected chat2 assistant response in contents. Contents: {contents}"
    )

    # The current query should be the last user message
    user_msgs = [m for m in response if isinstance(m, dict) and m.get("role") == "user"]
    assert user_msgs[-1]["content"] == "What do you remember?", (
        f"Expected current query as last user message. User messages: {user_msgs}"
    )


def test_live_prompt_builder_fallback_to_v1(app_process, tmp_path):
    """When session doesn't exist in chat2, falls back to v1."""
    payload = {
        "query": "Hello",
        "agentName": "peace",
        "accountName": "junwin",
        "contextName": "lucyproject",
        "conversationId": "nonexistent-session-id",
    }

    cmd = [
        "curl", "-s", "-X", "POST",
        "http://127.0.0.1:5001/prompt_builder",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(payload),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, (
        f"curl failed (exit {result.returncode}): {result.stderr}\n"
        f"stdout: {result.stdout}"
    )

    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Response is not valid JSON: {result.stdout}\nStderr: {result.stderr}")

    # Should still return a valid prompt (list of messages) even without history
    assert isinstance(response, list), f"Expected list, got: {type(response)}: {response}"

    # Should at least contain the current query
    contents = [m.get("content", "") for m in response if isinstance(m, dict)]
    assert any("Hello" in c for c in contents), f"Expected query in response. Contents: {contents}"
