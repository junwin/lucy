
import os
import shlex
import subprocess
import logging
from subprocess import check_output


import os

def get_base_path(config, account_name: str, relative_path: str = "") -> str:
    relative_path = (relative_path or "").strip()

    # treat "~" or "~/" as "no extra path"
    if relative_path == "~" or relative_path.startswith("~/") or relative_path.startswith("~\\"):
        relative_path = relative_path[1:]  # drop the "~"
        relative_path = relative_path.lstrip("/\\")  # drop following slash if present

    # normalize windows-style slashes to current OS style
    relative_path = relative_path.replace("\\", os.path.sep).replace("/", os.path.sep)

    config_base = config.get("code_sandbox_path")
    if not config_base:
        raise ValueError("code_sandbox_path is not configured")

    account_root = os.path.realpath(os.path.join(config_base, account_name))

    # Disallow absolute paths in the *user supplied* part.
    # (If callers pass an absolute path under account_root, we can optionally support it below.)
    if os.path.isabs(relative_path):
        # If you want to allow absolute paths only when already under account_root, do:
        abs_candidate = os.path.realpath(relative_path)
        if os.path.commonpath([account_root, abs_candidate]) != account_root:
            raise ValueError("relative_path must be relative to the account sandbox")
        resolved = abs_candidate
    else:
        resolved = os.path.realpath(os.path.join(account_root, relative_path))

    # Enforce containment
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