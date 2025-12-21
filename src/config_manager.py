import json
import os

SANDBOX_RELATIVE_PATH_KEYS = [
    "python_utils_path",
    # add others as you standardize them:
    # "some_tools_workdir",
    # "obsidian_root_relative",
]


def validate_sandbox_relative_paths(config: dict) -> None:
    sandbox_root = (config.get("code_sandbox_path") or "").strip()
    if not sandbox_root:
        raise ValueError("code_sandbox_path is not configured")

    # Optional but helpful: sandbox root should be absolute
    if not os.path.isabs(sandbox_root):
        raise ValueError(f"code_sandbox_path must be an absolute path (got: {sandbox_root})")

    for key in SANDBOX_RELATIVE_PATH_KEYS:
        val = (config.get(key) or "").strip()
        if not val:
            continue  # allow missing if optional

        # Disallow absolute paths for these keys
        if os.path.isabs(val):
            raise ValueError(f"Config '{key}' must be sandbox-relative (got absolute path: {val})")

        # Disallow traversal tokens
        if ".." in val.replace("\\", "/").split("/"):
            raise ValueError(f"Config '{key}' must not contain '..' path traversal (got: {val})")


class ConfigManager:
    def __init__(self, file_name: str):
        self.config = self.load_config(file_name)
        validate_sandbox_relative_paths(self.config)  # fail fast

    def load_config(self, file_name: str) -> dict:
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file '{file_name}' not found.")
        except json.JSONDecodeError as e:
            raise ValueError(f"Config file '{file_name}' is not valid JSON: {e}")

    def get(self, key: str, default=None):
        return self.config.get(key, default)
