import pytest

from galet_tools.tools.command_execution_handler2 import (
    CommandExecutionHandler2 as GaletCommandExecutionHandler2,
)

from src.handlers.command_execution_handler2 import CommandExecutionHandler2


class DummyConfig:
    def __init__(self, **kwargs):
        self._d = dict(kwargs)

    def get(self, key: str, default=None):
        return self._d.get(key, default)


def _mk_handler(tmp_path):
    # minimal config; we only test path validation helper here
    return CommandExecutionHandler2(DummyConfig(code_sandbox_path=str(tmp_path)))


def test_validate_and_normalize_relative_path_allows_dot(tmp_path):
    h = _mk_handler(tmp_path)

    norm, err = h._validate_and_normalize_relative_path(".")

    assert err == ""
    assert norm == "."


def test_validate_and_normalize_relative_path_empty_normalizes_to_dot(tmp_path):
    """os.path.normpath('') becomes '.', so the helper treats it as base dir."""
    h = _mk_handler(tmp_path)

    norm, err = h._validate_and_normalize_relative_path("")

    assert err == ""
    assert norm == "."


def test_validate_and_normalize_relative_path_blocks_parent(tmp_path):
    h = _mk_handler(tmp_path)

    norm, err = h._validate_and_normalize_relative_path("..")

    assert norm == ""
    assert "parent" in err or ".." in err


def test_validate_and_normalize_relative_path_allows_internal_dotdot_normalization(tmp_path):
    """Current behavior: 'a/../b' normalizes to 'b' and is allowed."""
    h = _mk_handler(tmp_path)

    norm, err = h._validate_and_normalize_relative_path("a/../b")

    assert err == ""
    assert norm == "b"


def test_execute_replaces_generic_security_refusal_with_actionable_message(
    tmp_path, monkeypatch
):
    """The bare Galet refusal must be replaced by an actionable Lucy message."""
    h = _mk_handler(tmp_path)

    def fake_galet_execute(self, args, *, account_name="auto"):
        # Exactly what galet-tools returns when the policy refuses a command.
        return {
            "ok": False,
            "tool": "execute_command",
            "error": "Command refused by security policy",
            "location": "external",
            "external_root": "repo_lucy",
            "command": "pwd && true",
            "working_directory": ".",
        }

    monkeypatch.setattr(
        GaletCommandExecutionHandler2, "execute", fake_galet_execute
    )

    result = h.execute({"command": "pwd && true", "wrapper": "none"})

    # ok:false is preserved.
    assert result["ok"] is False
    # The generic Galet refusal text is gone.
    assert result["error"] != "Command refused by security policy"
    # ... replaced by the actionable Lucy message.
    assert "interactive commands are not allowed" in result["error"]
    assert "bash -lc 'pwd'" in result["error"]
    assert "Do not repeat the rejected command unchanged" in result["error"]
