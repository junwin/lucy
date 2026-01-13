import os
import json
import shlex
import subprocess
import logging
from typing import Any, Dict, Tuple

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2


class CommandExecutionHandler2(HandlerV2):
    """
    New scheme:
      - No absolute paths in tool calls.
      - Callers specify either:
          (A) location="sandbox", working_directory="<relative under code sandbox base>"
          (B) location="external", external_root="<named root>", working_directory="<relative under that root>"
      - STRICT schema: required must include every key in properties.
    """

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
            "description": (
                "Run a command (shell=False) inside a sandboxed working directory under a named location. "
                "Paths are always relative. "
                "location='sandbox' uses code_sandbox_path; location='external' uses external_root."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "enum": ["sandbox", "external"],
                        "description": "Where to run the command.",
                    },
                    "external_root": {
                        "type": "string",
                        "description": "Named external root key when location='external'. Use '' otherwise.",
                    },
                    "command": {
                        "type": "string",
                        "description": (
                            "Command to execute (shell=False). Provide a full command line; "
                            "shell operators like |, >, && will not work unless you explicitly run a shell."
                        ),
                    },
                    "working_directory": {
                        "type": "string",
                        "description": (
                            "Working directory relative to the chosen location (no leading /, no ..)."
                        ),
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Timeout in seconds (limits runtime)",
                        "default": 30,
                    },
                },
                # STRICT RULE: required must include EVERY property key
                "required": ["location", "external_root", "command", "working_directory", "timeout_seconds"],
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
                "location": {"type": "string"},
                "external_root": {"type": "string"},
                "command": {"type": "string"},
                "working_directory": {"type": "string"},
                "normalized_working_directory": {"type": "string"},
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
        location = (args.get("location") or "sandbox").strip().lower()
        external_root = (args.get("external_root") or "").strip()
        command = (args.get("command") or "").strip()
        working_directory_in = (args.get("working_directory") or "").strip()
        timeout_seconds = args.get("timeout_seconds", 30)

        if not command or not working_directory_in:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "command and working_directory are required",
                "location": location,
                "external_root": external_root,
                "command": command,
                "working_directory": working_directory_in,
            }

        # Validate relative working_directory
        norm_wd, err = self._validate_and_normalize_relative_path(working_directory_in)
        if err:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": err,
                "location": location,
                "external_root": external_root,
                "working_directory": working_directory_in,
            }

        # Resolve base dir
        try:
            if location == "sandbox":
                if external_root:
                    return {
                        "ok": False,
                        "tool": self.NAME,
                        "error": "external_root must be '' when location='sandbox'",
                        "location": location,
                        "external_root": external_root,
                        "working_directory": working_directory_in,
                    }
                base_dir = self._sandbox_base_dir(account_name=account_name)
            elif location == "external":
                if not external_root:
                    return {
                        "ok": False,
                        "tool": self.NAME,
                        "error": "external_root is required when location='external'",
                        "location": location,
                        "external_root": external_root,
                        "working_directory": working_directory_in,
                    }
                base_dir = self._external_root_dir(external_root)
            else:
                return {
                    "ok": False,
                    "tool": self.NAME,
                    "error": f"Unknown location '{location}'",
                    "location": location,
                    "external_root": external_root,
                    "working_directory": working_directory_in,
                }
        except Exception as e:
            logging.exception("execute_command: failed to resolve base directory")
            return {
                "ok": False,
                "tool": self.NAME,
                "error": str(e),
                "location": location,
                "external_root": external_root,
                "working_directory": working_directory_in,
            }

        # Resolve + containment-check working directory
        try:
            resolved_dir = self._resolve_dir_safe(base_dir, norm_wd)
        except Exception as e:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": str(e),
                "location": location,
                "external_root": external_root,
                "working_directory": working_directory_in,
                "normalized_working_directory": norm_wd,
                "base_dir": base_dir,
            }

        logging.info(
            "execute_command: account=%s location=%s external_root=%s working_directory=%s command=%s",
            account_name,
            location,
            external_root,
            working_directory_in,
            command,
        )

        try:
            rc, out, err = self._execute_script(command, resolved_dir, timeout=int(timeout_seconds))
        except Exception as e:
            logging.exception("execute_command failed")
            return {
                "ok": False,
                "tool": self.NAME,
                "error": str(e),
                "location": location,
                "external_root": external_root,
                "command": command,
                "working_directory": working_directory_in,
                "normalized_working_directory": norm_wd,
                "resolved_working_directory": resolved_dir,
            }

        if rc == 0:
            result_str = out.strip() or "success"
        else:
            result_str = f"error {rc}\nSTDOUT:\n{out}\nSTDERR:\n{err}"

        return {
            "ok": rc == 0,
            "tool": self.NAME,
            "location": location,
            "external_root": external_root,
            "command": command,
            "working_directory": working_directory_in,
            "normalized_working_directory": norm_wd,
            "resolved_working_directory": resolved_dir,
            "returncode": rc,
            "stdout": out,
            "stderr": err,
            "result": result_str,
        }

    def execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "") -> str:
        """
        Strict schema means new tool calls will supply:
          location/external_root/command/working_directory/timeout_seconds

        If you want a tiny back-compat shim, you can set defaults here.
        """
        try:
            args = json.loads(arguments_raw or "{}")
        except Exception:
            args = {}

        if isinstance(args, dict):
            if "location" not in args:
                args["location"] = "sandbox"
            if "external_root" not in args:
                args["external_root"] = ""
            if "timeout_seconds" not in args:
                args["timeout_seconds"] = 30

        result = self.execute(args if isinstance(args, dict) else {}, account_name=account_name)
        return json.dumps(result, ensure_ascii=False)

    # -----------------------
    # Resolution helpers
    # -----------------------

    def _sandbox_base_dir(self, *, account_name: str) -> str:
        """
        Command sandbox base. Prefer a dedicated sandbox directory, NOT /home.
        If you must keep /home, consider appending the account name to contain blast radius.

        Options:
          - code_sandbox_path=/home/junwin (current)
          - or better: code_sandbox_path=/home/junwin/lucy_sandbox
        """
        base = (self.config.get("code_sandbox_path") or "").strip()
        if not base:
            raise ValueError("Missing config 'code_sandbox_path'")

        # Safer default: fence to a per-account subdir
        base = os.path.join(base, account_name) if os.path.isdir(base) else base
        return os.path.abspath(base)

    def _external_root_dir(self, external_root: str) -> str:
        roots = self.config.get("external_roots") or {}
        if not isinstance(roots, dict):
            raise ValueError("Config 'external_roots' must be an object/map")
        base = roots.get(external_root)
        if not base:
            raise ValueError(f"Unknown external_root '{external_root}'")
        return os.path.abspath(str(base))

    # -----------------------
    # Path validation + safe resolution
    # -----------------------

    @staticmethod
    def _has_drive_letter(path: str) -> bool:
        return len(path) >= 2 and path[1] == ":" and path[0].isalpha()

    def _validate_and_normalize_relative_path(self, path_in: str) -> Tuple[str, str]:
        if self._has_drive_letter(path_in):
            return "", "working_directory must be relative, not include drive letters"
        if os.path.isabs(path_in):
            return "", "working_directory must be relative, not absolute"

        norm_rel = os.path.normpath(path_in)

        if norm_rel in ("", ".", ".."):
            return "", "working_directory must not be empty or point to current/parent directory"

        parts = [p for p in norm_rel.split(os.path.sep) if p]
        if os.path.altsep:
            parts = [p for seg in parts for p in seg.split(os.path.altsep) if p]
        if any(p == ".." for p in parts) or norm_rel.startswith(".."):
            return "", "working_directory must not contain '..' segments"

        return norm_rel, ""

    def _resolve_dir_safe(self, base_dir: str, rel_dir: str) -> str:
        """
        Resolve base_dir + rel_dir and ensure containment (realpath) to prevent symlink escapes.
        """
        base_abs = os.path.abspath(base_dir)
        full_path = os.path.normpath(os.path.join(base_abs, rel_dir))

        base_real = os.path.realpath(base_abs)
        full_real = os.path.realpath(full_path)

        if not (full_real == base_real or full_real.startswith(base_real + os.path.sep)):
            raise ValueError("Working directory outside allowed base path")

        if not os.path.isdir(full_real):
            raise ValueError(f"working dir does not exist: {full_real}")

        return full_real

    # -----------------------
    # Command execution
    # -----------------------

    def _execute_script(self, command: str, cwd: str, timeout: int = 30) -> tuple[int, str, str]:
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
