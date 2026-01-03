import pytest

from src.handlers.command_execution_handler2 import CommandExecutionHandler2


class _DummyConfig:
    def get(self, key, default=None):
        # keep it deterministic and writable
        if key == "code_sandbox_path":
            return "/tmp/lucy_test_sandbox"
        return default


def test_execute_command_tool_def_description_mentions_sandbox_and_shell_false():
    tool_def = CommandExecutionHandler2.tool_def()

    assert tool_def["name"] == "execute_command"

    desc = (tool_def.get("description") or "").lower()
    assert "shell=false" in desc
    assert "allowed base" in desc
    assert "timeout" in desc

    props = tool_def["parameters"]["properties"]

    cmd_desc = (props["command"].get("description") or "").lower()
    assert "shell=false" in cmd_desc
    assert "operators" in cmd_desc or "|" in cmd_desc

    wd_desc = (props["working_directory"].get("description") or "").lower()
    assert "allowed base" in wd_desc
    assert "get_base_path" in wd_desc


@pytest.mark.parametrize(
    "args, expected_error_substr",
    [
        ({"command": "", "working_directory": "x", "timeout_seconds": 1}, "required"),
        ({"command": "echo hi", "working_directory": "", "timeout_seconds": 1}, "required"),
    ],
)
def test_execute_command_requires_command_and_working_directory(args, expected_error_substr):
    # These cases fail before any config/path resolution is needed.
    handler = CommandExecutionHandler2(_DummyConfig())
    result = handler.execute(args)

    assert result["ok"] is False
    assert expected_error_substr in (result.get("error") or "").lower()
