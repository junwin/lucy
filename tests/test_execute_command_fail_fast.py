import json
import shlex
from src.config_manager import ConfigManager
from src.handlers.command_execution_handler2 import CommandExecutionHandler2


def test_heredoc_is_detected_and_rejected():
    cfg = ConfigManager("config.json")
    handler = CommandExecutionHandler2(cfg)

    cmd = "python3 - << 'PY'\nprint(\"hello\")\nPY"
    args = {
        "location": "external",
        "external_root": "repo_lucy",
        "command": cmd,
        "working_directory": ".",
        "timeout_seconds": 2,
        "success_exit_codes": [0],
    }

    res = handler.execute(args)

    assert res["ok"] is False
    assert "shell" in (res.get("error") or "").lower()
    # Should return quickly without attempting to run a subprocess
    assert res.get("command") == cmd


def test_heredoc_allowed_when_wrapped_in_bash_lc():
    """
    Regression: a heredoc should be rejected when used directly (above), but
    allowed when the caller intentionally wraps the entire command in a
    `bash -lc '...` invocation. This ensures callers can use shell features
    (including heredocs) when they explicitly request a shell.
    """
    cfg = ConfigManager("config.json")
    handler = CommandExecutionHandler2(cfg)

    # The inner command uses a heredoc to provide stdin to python3; when wrapped
    # in bash -lc the handler should allow it and actually execute.
    inner = "python3 - <<'PY'\nprint(\"hello-from-heredoc\")\nPY"
    # Properly quote the inner command so shlex parsing yields ['bash','-lc', inner]
    cmd = "bash -lc " + shlex.quote(inner)

    args = {
        "location": "external",
        "external_root": "repo_lucy",
        "command": cmd,
        "working_directory": ".",
        "timeout_seconds": 5,
        "success_exit_codes": [0],
    }

    res = handler.execute(args)

    assert res["ok"] is True
    # stdout should contain the printed string from the heredoc-fed python
    assert "hello-from-heredoc" in (res.get("stdout") or "")
    assert res.get("command") == cmd
