import pytest

from src.handlers.command_execution_handler2 import CommandExecutionHandler2


def test_execute_command_tool_def_description_mentions_safety_constraints():
    tool_def = CommandExecutionHandler2.tool_def()

    desc = (tool_def.get("description") or "").lower()
    assert "shell=false" in desc
    assert "allowed base" in desc or "allowed base folder" in desc
    assert "timeout" in desc

    props = tool_def["parameters"]["properties"]

    cmd_desc = (props["command"].get("description") or "").lower()
    assert "shell=false" in cmd_desc

    wd_desc = (props["working_directory"].get("description") or "").lower()
    assert "relative" in wd_desc
    assert "allowed base" in wd_desc

    timeout_desc = (props["timeout_seconds"].get("description") or "").lower()
    assert "timeout" in timeout_desc
