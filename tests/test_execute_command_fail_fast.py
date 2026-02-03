import json
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
