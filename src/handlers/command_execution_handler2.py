import os
import json
import shlex
import subprocess
import logging
from typing import Any, Dict

from src.config_manager import ConfigManager
from src.handlers.handler_utils import get_base_path
from src.handlers.handler_v2 import HandlerV2


class CommandExecutionHandler2(HandlerV2):
    NAME = "execute_command"

    def __init__(self, config: ConfigManager):
        self.config = config

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": "Execute an OS command in a given working directory under the allowed base folder",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute (shell=False). Provide full args/quotes as needed.",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory relative to the allowed base folder",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Timeout in seconds",
                        "default": 30,
                    },
                },
                "required": ["command", "working_directory", "timeout_seconds"],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "command": {"type": "string"},
                "working_directory": {"type": "string"},
                "resolved_working_directory": {"type": "string"},
                "returncode": {"type": "integer"},
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
                "result": {"type": "string"},
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:
        command = (args.get("command") or "").strip()
        working_directory = (args.get("working_directory") or "").strip()
        timeout_seconds = args.get("timeout_seconds", 30)

        if not command or not working_directory:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "command and working_directory are required",
                "args": {"command": command, "working_directory": working_directory},
            }

        try:
            resolved_dir = get_base_path(self.config, account_name, working_directory)
        except Exception as e:
            logging.exception("execute_command: failed to resolve base path")
            return {
                "ok": False,
                "tool": self.NAME,
                "error": f"Invalid working_directory: {e}",
                "working_directory": working_directory,
            }

        try:
            rc, out, err = self._execute_script(command, resolved_dir, timeout=int(timeout_seconds))
        except Exception as e:
            logging.exception("execute_command failed")
            return {
                "ok": False,
                "tool": self.NAME,
                "error": str(e),
                "command": command,
                "working_directory": working_directory,
                "resolved_working_directory": resolved_dir,
            }

        if rc == 0:
            result_str = out.strip() or "success"
        else:
            result_str = f"error {rc}\nSTDOUT:\n{out}\nSTDERR:\n{err}"

        return {
            "ok": rc == 0,
            "tool": self.NAME,
            "command": command,
            "working_directory": working_directory,
            "resolved_working_directory": resolved_dir,
            "returncode": rc,
            "stdout": out,
            "stderr": err,
            "result": result_str,
        }

    def execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "") -> str:
        try:
            args = json.loads(arguments_raw or "{}")
        except Exception:
            args = {}
        result = self.execute(args if isinstance(args, dict) else {}, account_name=account_name)
        return json.dumps(result, ensure_ascii=False)

    def _execute_script(self, command: str, cwd: str, timeout: int = 30) -> tuple[int, str, str]:
        if not os.path.isdir(cwd):
            raise ValueError(f"working dir does not exist: {cwd}")

        argv = shlex.split(command, posix=(os.name != "nt"))

        completed = subprocess.run(
            argv,
            shell=False,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return completed.returncode, completed.stdout or "", completed.stderr or ""
