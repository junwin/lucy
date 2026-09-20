import sys

from galet_tools.tools.execute_command2 import ExecuteCommand2 as GaletExecuteCommand2

from src.handlers.command_execution_handler2 import CommandExecutionHandler2


class DummyConfig:
    def __init__(self, **kwargs):
        self._d = dict(kwargs)

    def get(self, key: str, default=None):
        return self._d.get(key, default)


def _mk_handler(tmp_path):
    # Lucy fences an existing sandbox root by account name. The handler's
    # default account is 'auto', so create that resolved directory explicitly.
    (tmp_path / "auto").mkdir(exist_ok=True)
    return CommandExecutionHandler2(DummyConfig(code_sandbox_path=str(tmp_path)))


def _process_args(**overrides):
    args = {
        "mode": "process",
        "executable": sys.executable,
        "arguments": ["-c", "print('hello')"],
        "script": "",
        "shell": "none",
        "location": "sandbox",
        "external_root": "",
        "working_directory": ".",
        "timeout_seconds": 10,
        "success_exit_codes": [0],
    }
    args.update(overrides)
    return args


def test_adapter_uses_structured_galet_handler_and_preserves_public_name():
    assert issubclass(CommandExecutionHandler2, GaletExecuteCommand2)
    assert CommandExecutionHandler2.name() == "execute_command"
    assert CommandExecutionHandler2.tool_def()["name"] == "execute_command"


def test_schema_exposes_structured_execution_arguments():
    properties = CommandExecutionHandler2.tool_def()["parameters"]["properties"]

    assert {"mode", "executable", "arguments", "script", "shell"} <= set(properties)
    assert "command" not in properties
    assert "wrapper" not in properties


def test_validate_relative_path_allows_dot(tmp_path):
    h = _mk_handler(tmp_path)

    norm, err = h._validate_relative_path(".")

    assert err == ""
    assert norm == "."


def test_validate_relative_path_blocks_parent(tmp_path):
    h = _mk_handler(tmp_path)

    norm, err = h._validate_relative_path("..")

    assert norm == ""
    assert "configured root" in err


def test_process_execution_uses_exact_arguments(tmp_path):
    h = _mk_handler(tmp_path)

    result = h.execute(
        _process_args(
            arguments=[
                "-c",
                "import sys; print(sys.argv[1])",
                "value with spaces | and shell text",
            ]
        )
    )

    assert result["ok"] is True
    assert result["stdout"].strip() == "value with spaces | and shell text"


def test_embedded_shell_is_rejected_with_structured_error(tmp_path):
    h = _mk_handler(tmp_path)

    result = h.execute(
        _process_args(executable="bash", arguments=["-lc", "echo bad"])
    )

    assert result["ok"] is False
    assert result["error_code"] == "embedded_shell_refused"
    assert "mode='shell'" in result["error"]
