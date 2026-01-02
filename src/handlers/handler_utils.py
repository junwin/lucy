import os
import shlex
import subprocess
import logging
from subprocess import check_output


def get_base_path(config, account_name: str, relative_path: str = "") -> str:
    """Resolve a path inside the per-account sandbox.

    Rules:
    - `relative_path` is normally relative (no leading slash, no drive letter).
    - Absolute paths are allowed only if they resolve *within* the account root.
    - `..` segments are not allowed to escape the account root.
    - `~` or `~/` are treated as "no extra path" (for convenience), but still
      resolved inside the account sandbox.
    - Both forward and backslashes are normalized to the current OS separator.

    Raises:
        ValueError: If the path is absolute outside the sandbox or attempts
            traversal outside the allowed base path.
    """

    relative_path = (relative_path or "").strip()

    # treat "~" or "~/" as "no extra path" (but still under the sandbox)
    if relative_path == "~" or relative_path.startswith("~/") or relative_path.startswith("~\\"):
        relative_path = relative_path[1:]  # drop the "~"
        relative_path = relative_path.lstrip("/\\")  # drop following slash if present

    # normalize windows-style slashes to current OS style
    relative_path = relative_path.replace("\\", os.path.sep).replace("/", os.path.sep)

    config_base = config.get("code_sandbox_path")
    if not config_base:
        raise ValueError("code_sandbox_path is not configured")

    account_root = os.path.realpath(os.path.join(config_base, account_name))

    # Allow absolute paths only if they are within account_root.
    if os.path.isabs(relative_path):
        resolved = os.path.realpath(relative_path)
        if os.path.commonpath([account_root, resolved]) != account_root:
            raise ValueError("Path traversal outside allowed base path")
        return resolved

    # Normalize and build the final path
    norm_rel = os.path.normpath(relative_path) if relative_path else ""

    # Reject attempts to escape via leading ".."
    if norm_rel.startswith(".."):
        raise ValueError("Path traversal outside allowed base path")

    resolved = os.path.realpath(os.path.join(account_root, norm_rel))

    # Enforce containment: resolved must be inside account_root
    if os.path.commonpath([account_root, resolved]) != account_root:
        raise ValueError("Path traversal outside allowed base path")

    return resolved  # no forced trailing slash


def execute_script(command: str, working_dir: str) -> str:
    if not os.path.isdir(working_dir):
        return f"working dir does not exist: {working_dir}"

    try:
        # Split command in an OS-appropriate way
        args = shlex.split(command, posix=(os.name != "nt"))

        result = subprocess.run(
            args,
            shell=False,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return (
                f"error {result.returncode}\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )

        return result.stdout.strip() or "success"

    except subprocess.TimeoutExpired:
        logging.exception("execute_script timeout")
        return "error: command timed out"
    except Exception as e:
        logging.exception("execute_script failed")
        return f"error: {e}"
