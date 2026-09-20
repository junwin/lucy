import shutil
import sys

import pytest

from src.config_manager import ConfigManager
from src.handlers.command_execution_handler2 import CommandExecutionHandler2


def _base_args(**overrides):
    args = {
        "mode": "process",
        "executable": "bash",
        "arguments": ["-lc", "echo should-not-run"],
        "script": "",
        "shell": "none",
        "location": "external",
        "external_root": "repo_lucy",
        "working_directory": ".",
        "timeout_seconds": 2,
        "success_exit_codes": [0],
    }
    args.update(overrides)
    return args


def test_embedded_shell_is_rejected_before_subprocess_execution():
    handler = CommandExecutionHandler2(ConfigManager("config.json"))

    result = handler.execute(_base_args())

    assert result["ok"] is False
    assert result["error_code"] == "embedded_shell_refused"


@pytest.mark.skipif(sys.platform == "win32" or shutil.which("bash") is None, reason="bash unavailable")
def test_heredoc_allowed_with_explicit_bash_shell():
    handler = CommandExecutionHandler2(ConfigManager("config.json"))
    script = "python3 - <<'PY'\nprint('hello-from-heredoc')\nPY"

    result = handler.execute(
        _base_args(
            mode="shell",
            executable="",
            arguments=[],
            script=script,
            shell="bash",
            timeout_seconds=5,
        )
    )

    assert result["ok"] is True
    assert "hello-from-heredoc" in result["stdout"]
    assert result["script"] == script
