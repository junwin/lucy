import os
import json
import shlex
import subprocess
import logging
import re
import sys
import shutil
from typing import Any, Dict, Tuple

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2


IS_WINDOWS = sys.platform == "win32"


class CommandExecutionHandler2(HandlerV2):
    """
    New scheme:
      - No absolute paths in tool calls.
      - Callers specify either:
          (A) location="sandbox", working_directory="<relative under code sandbox base>"
          (B) location="external", external_root="<named root>", working_directory="<relative under that root>"
      - Option A (explicit): callers must pass working_directory="." to mean the root of the chosen base.
      - STRICT schema: required must include every key in properties.

    Notes:
      - When a shell is needed, wrap the entire command in a shell invocation appropriate for the platform:
        on Unix-like systems this is commonly `bash -lc "..."`; on Windows prefer PowerShell Core (pwsh) if
        available, otherwise Windows PowerShell (`powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "..."`).
      - The tests and examples in the docs show both styles where relevant so callers on either platform see
      a clear example they can copy.
    """

    NAME = "execute_command"

    # Benign / read-only commands that produce non-zero exit codes in normal use
    # (e.g. grep returns 1 when no match, not a real "error").
    _BENIGN_COMMANDS = {"grep", "egrep", "fgrep", "find", "test", "[", "which", "command"}

    def __init__(self, config: ConfigManager):
        self.config = config

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        if IS_WINDOWS:
            shell_example = "powershell.exe -NoProfile -NonInteractive -Command \"...\" (or 'pwsh -NoProfile -NonInteractive -Command \"...\"' if pwsh is installed)"
            shell_note = "(PowerShell is available in the environment.)"
            example_usage = "powershell.exe -NoProfile -NonInteractive -Command \"grep -R 'pattern' . | Select-String -Pattern 'pattern'\""
            command_wrap_example = "powershell.exe -NoProfile -NonInteractive -Command \"your full command here\""
        else:
            shell_example = "bash -lc '\"...\"'"
            shell_note = "(bash is available in the environment.)"
            example_usage = "bash -lc '\"grep -R \\\'pattern\\\' . | sed -n '1,10p\\\"'"
            command_wrap_example = "bash -lc '\"your full command here\"'"

        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "Run a command inside a sandboxed working directory under a named location. "
                "IMPORTANT: the command is executed with shell=False (subprocess.run(..., shell=False)). "
                "Do NOT use shell operators (for example: &&, ||, |, ;, >, <, >>, 2>, $(), backticks, etc.). "
                f"If you need shell features (pipes, redirection, compound/conditional commands), wrap the entire command in a shell invocation appropriate for your OS, e.g. `{shell_example}`. "
                f"Example: `{example_usage}` will run a shell so pipes and redirects work. "
                f"{shell_note} "
                "Commands MUST be non-interactive and MUST terminate. "
                "Do NOT call `bash` or `python3` with no arguments (they will wait for stdin and time out). "
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
                            "Command to execute (executed with shell=False). "
                            "Do NOT include shell operators like &&, ||, |, >, <, 2>, etc. "
                            f"If you need them, wrap the command in a shell invocation appropriate for your platform, for example: `{command_wrap_example}`."
                        ),
                    },
                    "working_directory": {
                        "type": "string",
                        "description": (
                            "Working directory relative to the chosen location (no leading /, no ..). "
                            "Use '.' to run in the root of the chosen base directory."
                        ),
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Timeout in seconds (limits runtime)",
                        "default": 30,
                    },
                    "success_exit_codes": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": (
                            "Return codes that should be treated as success. "
                            "Default [0]. Useful for commands like grep where 1 means 'no matches'."
                        ),
                        "default": [0],
                    },
                    "wrapper": {
                        "type": "string",
                        "enum": ["none", "bash", "powershell"],
                        "description": (
                            "Shell wrapper to use for this command. "
                            "Default 'none' runs the command directly with shell=False. "
                            "Set to 'bash' to wrap in `bash -lc \"...\"` (Linux/macOS). "
                            "Set to 'powershell' to wrap in PowerShell (pwsh or powershell.exe) using -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command '...'. "
                            "When a wrapper is set, shell operators in the command are allowed."
                        ),
                        "default": "none",
                    },
                },
                # STRICT RULE: required must include EVERY property key
                "required": ["location", "external_root", "command", "working_directory", "timeout_seconds", "success_exit_codes"],
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
                "status": {"type": "string"},
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
        wrapper = (args.get("wrapper") or "none").strip().lower()

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

        # ── Cross-platform wrapper validation ──
        if wrapper == "bash" and IS_WINDOWS:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "bash is not available on Windows. Use wrapper='powershell'.",
                "location": location,
                "external_root": external_root,
                "command": command,
                "working_directory": working_directory_in,
            }
        if wrapper == "powershell" and not IS_WINDOWS:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "PowerShell wrapper requested but the platform is not Windows. If you have pwsh (PowerShell Core) installed, prefer that; otherwise run the command using wrapper='bash' or leave wrapper='none' and avoid shell operators.",
                "location": location,
                "external_root": external_root,
                "command": command,
                "working_directory": working_directory_in,
            }
        
        # Reject interactive shells / REPLs that will hang waiting for stdin.
        if self._is_bare_interactive(command):
            if IS_WINDOWS:
                wrap_example = 'pwsh -NoProfile -NonInteractive -Command "<your command>" or powershell.exe -NoProfile -NonInteractive -Command "<your command>"'
            else:
                wrap_example = "bash -lc \"<your command>\""

            return {
                "ok": False,
                "tool": self.NAME,
                "error": (
                    f"Refusing interactive command that would wait for stdin: {command!r}. "
                    "Provide a terminating command. Examples: "
                    "`python3 path/to/script.py [args]`, "
                    "`python3 -c \"print('hi')\"`, "
                    f"`{wrap_example}`."
                ),
                "location": location,
                "external_root": external_root,
                "command": command,
                "working_directory": working_directory_in,
            }

        # Detect shell-only syntax that requires a shell to interpret (pipes, redirects, heredoc, &&, ||, ;, $(), backticks, etc.)
        # Skip this check when a wrapper is explicitly set — the wrapper handles the shell operators.
        if wrapper == "none" and self._contains_shell_syntax(command):
            if IS_WINDOWS:
                wrap_example = 'pwsh -NoProfile -NonInteractive -Command "your full command here" (or powershell.exe -NoProfile -NonInteractive -Command "...")'
            else:
                wrap_example = "bash -lc '\"your full command here\"'"

            return {
                "ok": False,
                "tool": self.NAME,
                "error": (
                    "Command appears to contain shell-only syntax (pipes, redirects, heredoc/<<, &&, ||, ;, $(), backticks, etc.). "
                    "These require a shell to interpret. "
                    f"Wrap the entire command in a shell invocation appropriate for your OS, e.g. `{wrap_example}`."
                ),
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

        success_exit_codes = args.get("success_exit_codes", [0])
        if not isinstance(success_exit_codes, list) or not all(isinstance(x, int) for x in success_exit_codes):
            success_exit_codes = [0]

        try:
            rc, out_raw, err_raw = self._execute_script(command, resolved_dir, timeout=int(timeout_seconds), wrapper=wrapper)

            out = self._truncate(out_raw)
            err = self._truncate(err_raw)

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

        ok = rc in success_exit_codes

        if ok:
            # If rc!=0 but is "expected success" (e.g., grep=1), don't label it "error".
            if out.strip():
                result_str = out.strip()
            elif err.strip():
                result_str = err.strip()
            else:
                result_str = "success"
        else:
            result_str = f"error {rc}\nSTDOUT:\n{out}\nSTDERR:\n{err}"

        result = {
            "ok": ok,
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

        # ── Status: mark benign/read-only tool failures as "warning" ──
        if not ok and self._is_benign_command(command):
            result["status"] = "warning"

        return result

    def execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "", **context: Any) -> str:
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
            if "wrapper" not in args:
                args["wrapper"] = "none"

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

        # Option A (explicit): allow '.' to mean the base directory itself.
        if norm_rel in ("", ".."):
            return "", "working_directory must not be empty or point to parent directory"
        if norm_rel == ".":
            return ".", ""

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

    def _build_wrapper_argv(self, wrapper: str, command: str, cwd: str):
        """
        Build an argv list for the chosen wrapper. Handles UNC cwd special-casing for PowerShell.
        Returns (argv, cwd_to_pass)
        """
        wrapper = (wrapper or "none").strip().lower()
        if wrapper == "none":
            return None, cwd

        if wrapper == "bash":
            return ["bash", "-lc", command], cwd

        if wrapper == "powershell":
            # UNC handling: PowerShell chokes on UNC as process cwd; prefer Set-Location -LiteralPath and pass cwd=None
            cwd_to_pass = cwd
            cmd = command
            if IS_WINDOWS and cwd and cwd.startswith("\\\\"):
                # Prepend Set-Location to the command and avoid passing cwd to subprocess
                # Use single-quoted literal to avoid interpolation
                cmd = f"Set-Location -LiteralPath '{cwd}'; {command}"
                cwd_to_pass = None

            # Prefer pwsh (PowerShell Core) if available
            pwsh_path = shutil.which("pwsh")
            if pwsh_path:
                return [pwsh_path, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd], cwd_to_pass
            else:
                # Fall back to Windows PowerShell executable name
                return ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd], cwd_to_pass

        # Unknown wrapper
        raise ValueError(f"Unknown wrapper: {wrapper}")

    def _execute_script(self, command: str, cwd: str, timeout: int = 30, wrapper: str = "none") -> tuple[int, str, str]:
        # If wrapper is provided, build argv via wrapper helper and do not use shell=True
        if wrapper and wrapper != "none":
            argv, cwd_to_pass = self._build_wrapper_argv(wrapper, command, cwd)
            completed = subprocess.run(
                argv,
                shell=False,
                cwd=cwd_to_pass,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return completed.returncode, completed.stdout or "", completed.stderr or ""

        # Default direct execution (no wrapper)
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

    MAX_OUTPUT_CHARS = 10_000  # conservative, well under tool limits

    def _truncate(self, text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return (
            text[: limit // 2]
            + "\n\n[... output truncated ...]\n\n"
            + text[-limit // 2 :]
        )

    # -----------------------
    # Benign command detection
    # -----------------------

    def _is_benign_command(self, command: str) -> bool:
        """Return True if *command* is a benign/read-only tool whose non-zero
        exit code should be treated as a warning, not an error.

        Benign commands: grep, egrep, fgrep, find, test, [, which, command.
        Also: diff when passed --brief or -q.

        Handles ``bash -lc "..."`` / ``bash -c "..."`` wrappers by peeking
        inside the quoted string to find the real program name.
        """
        try:
            parts = shlex.split(command, posix=(os.name != "nt"))
        except Exception:
            return False

        if not parts:
            return False

        relevant_parts = parts
        prog = parts[0]

        # Unwrap bash -c / bash -lc
        if os.path.basename(prog) == "bash":
            for i, p in enumerate(parts):
                if p in ("-c", "-lc") and i + 1 < len(parts):
                    try:
                        inner_parts = shlex.split(parts[i + 1], posix=(os.name != "nt"))
                    except Exception:
                        return False
                    if not inner_parts:
                        return False
                    relevant_parts = inner_parts
                    prog = inner_parts[0]
                    break

        # Unwrap PowerShell -Command / pwsh -Command
        base_prog = os.path.basename(prog).lower()
        if base_prog in ("powershell.exe", "pwsh"):
            for i, p in enumerate(parts):
                if p.lower() == "-command" and i + 1 < len(parts):
                    try:
                        inner_parts = shlex.split(parts[i + 1], posix=(os.name != "nt"))
                    except Exception:
                        return False
                    if not inner_parts:
                        return False
                    relevant_parts = inner_parts
                    prog = inner_parts[0]
                    break

        name = os.path.basename(prog)

        if name in self._BENIGN_COMMANDS:
            return True

        if name == "diff":
            if any(a in ("--brief", "-q") for a in relevant_parts):
                return True

        return False

    # -----------------------
    # Interactive / shell-syntax guards
    # -----------------------

    INTERACTIVE_BARE = {"python", "python3", "bash", "sh", "zsh", "powershell.exe", "pwsh", "cmd.exe"}

    def _is_bare_interactive(self, command: str) -> bool:
        try:
            parts = shlex.split(command, posix=(os.name != "nt"))
        except Exception:
            # If it can't be parsed, treat it as unsafe / reject early
            return True

        if not parts:
            return True

        prog = parts[0]

        # `python3` alone / `bash` alone
        if prog in self.INTERACTIVE_BARE and len(parts) == 1:
            return True

        # `bash` without -c/-lc is very likely interactive (waiting on stdin)
        if prog == "bash" and not any(p in ("-c", "-lc") for p in parts[1:]):
            return True

        # `powershell.exe` or `pwsh` without -Command is interactive
        if os.path.basename(prog).lower() in ("powershell.exe", "pwsh") and not any(p.lower() == "-command" for p in parts[1:]):
            return True

        # `cmd.exe` without /c is interactive
        if os.path.basename(prog).lower() == "cmd.exe" and not any(p.lower() == "/c" for p in parts[1:]):
            return True

        return False

    def _contains_shell_syntax(self, command: str) -> bool:
        """
        Detect characters/sequences that are only meaningful to a shell and which will
        not be handled by subprocess.run(shell=False). This is conservative and may
        reject some commands where the characters appear inside quoted literals, but
        that's acceptable: callers should wrap complex commands in a shell invocation
        appropriate for the platform (e.g., `bash -lc "..."` on Unix, or
        PowerShell (pwsh/powershell.exe) with -NoProfile -NonInteractive -Command "..." on Windows).

        However, if the caller already wrapped the entire command in a `bash -c` or
        `bash -lc` invocation, don't treat shell metacharacters as errors — the
        wrapper indicates the user intentionally used the shell.
        """
        # If command is already wrapped with `bash -c` or `bash -lc`, allow it.
        try:
            parts = shlex.split(command, posix=(os.name != "nt"))
        except Exception:
            # If parsing fails, be conservative and report that shell syntax is present
            return True

        if parts:
            prog = os.path.basename(parts[0])
            # allow '/bin/bash' as well as 'bash'
            if prog == "bash":
                # If any of the early args include -c or -lc, assume the rest is a shell command
                # and don't try to detect shell metacharacters ourselves.
                for p in parts[1:3]:
                    if p in ("-c", "-lc"):
                        return False

        # common shell operators
        patterns = [r"\|\|", r"&&", r"\|", r">>", r">", r"<<", r"<", r"\$\(", r"`", r"2>", r"2>>"]
        # On Unix-like systems semicolon is a statement separator interpreted by the shell.
        # On Windows CreateProcess treats semicolons literally in many contexts, so allow them.
        if not IS_WINDOWS:
            patterns.insert(3, r";")

        combined = "|".join(f"({p})" for p in patterns)
        return re.search(combined, command) is not None
