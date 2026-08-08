import os
import shlex
import subprocess
import logging


def get_base_path(config, account_name: str, relative_path: str = "") -> str:
    """Resolve a path inside the per-account sandbox.

    Resolution strategy (hybrid):
      1. If environment variable LUCY_USER_ROOT is set -> use LUCY_USER_ROOT/<account>
      2. Else if config.code_sandbox_path is set -> use config.code_sandbox_path/<account>
      3. Else if $HOME is set and its basename matches the account -> use $HOME
      4. Else if $HOME/<account> exists -> use $HOME/<account>
      5. Else if /home/<account> exists -> use /home/<account>
      6. Else if /<account> exists -> use /<account>
      7. Otherwise raise a clear ValueError.

    Security rules:
      - `relative_path` must be relative (no leading slash) unless it's an
        absolute path that resolves *inside* the account root.
      - `..` segments are rejected if they attempt to escape the account root.
      - `~` or `~/` are treated as "no extra path" (convenience) and resolved
        inside the account sandbox.
    """

    relative_path = (relative_path or "").strip()

    # treat "~" or "~/" as "no extra path" (but still under the sandbox)
    if relative_path == "~" or relative_path.startswith("~/") or relative_path.startswith("~\\"):
        relative_path = relative_path[1:]  # drop the "~"
        relative_path = relative_path.lstrip("/\\")  # drop following slash if present

    # normalize windows-style slashes to current OS style
    relative_path = relative_path.replace("\\", os.path.sep).replace("/", os.path.sep)

    # Determine account root using hybrid strategy
    env_root = os.environ.get("LUCY_USER_ROOT")
    config_base = None
    if hasattr(config, "get"):
        config_base = config.get("code_sandbox_path")
    else:
        # allow raw dict-like config
        config_base = config.get("code_sandbox_path") if isinstance(config, dict) else None

    account_root = None

    if env_root:
        account_root = os.path.realpath(os.path.join(env_root, account_name))
    elif config_base:
        account_root = os.path.realpath(os.path.join(config_base, account_name))
    else:
        home = os.environ.get("HOME")
        if home:
            # If HOME basename matches account, use HOME directly
            if os.path.basename(os.path.normpath(home)) == account_name:
                account_root = os.path.realpath(home)
            else:
                candidate = os.path.realpath(os.path.join(home, account_name))
                if os.path.isdir(candidate):
                    account_root = candidate
        if account_root is None:
            # check /home/<account>
            candidate2 = os.path.realpath(os.path.join(os.path.sep, "home", account_name))
            if os.path.isdir(candidate2):
                account_root = candidate2
        if account_root is None:
            # check /<account>
            candidate3 = os.path.realpath(os.path.join(os.path.sep, account_name))
            if os.path.isdir(candidate3):
                account_root = candidate3

    if not account_root:
        raise ValueError(
            "Unable to resolve account root for account '%s'. Set LUCY_USER_ROOT or config['code_sandbox_path'], or ensure $HOME or /home/<user> exists." % account_name
        )

    # Allow absolute paths only if they are within account_root.
    if relative_path and os.path.isabs(relative_path):
        resolved_abs = os.path.realpath(relative_path)
        if os.path.commonpath([account_root, resolved_abs]) != account_root:
            raise ValueError("Path traversal outside allowed base path")
        return resolved_abs

    # Normalize and build the final path
    norm_rel = os.path.normpath(relative_path) if relative_path else ""

    # Reject attempts to escape via leading ".."
    if norm_rel.startswith(".."):
        raise ValueError("Path traversal outside allowed base path")

    resolved = os.path.realpath(os.path.join(account_root, norm_rel)) if norm_rel else os.path.realpath(account_root)

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
