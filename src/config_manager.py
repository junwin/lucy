import json
import os
import copy
import logging
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

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
        self.file_name = file_name
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

    def reload(self) -> Dict[str, Any]:
        """Re-read config from disk and update self.config in-place.

        Returns a summary dict: {
            'config_reloaded': True,
            'keys_added': [...],
            'keys_removed': [...],
            'keys_changed': [...],
        }

        If the file is missing, invalid JSON, or fails validation, the old
        config is kept and the summary includes an 'error' key.
        """
        old_config = copy.deepcopy(self.config)

        try:
            new_config = self.load_config(self.file_name)
            validate_sandbox_relative_paths(new_config)
        except Exception as e:
            logger.exception("Config reload failed for %s: %s", self.file_name, e)
            return {
                "config_reloaded": False,
                "error": str(e),
            }

        # Compute diff
        old_keys = set(old_config.keys())
        new_keys = set(new_config.keys())

        keys_added = sorted(new_keys - old_keys)
        keys_removed = sorted(old_keys - new_keys)
        keys_changed = sorted(
            k for k in (old_keys & new_keys) if old_config[k] != new_config[k]
        )

        # Apply in-place (mutate dict, don't replace reference)
        self.config.clear()
        self.config.update(new_config)

        logger.info(
            "Config reloaded from %s: added=%s, removed=%s, changed=%s",
            self.file_name, keys_added, keys_removed, keys_changed,
        )

        return {
            "config_reloaded": True,
            "keys_added": keys_added,
            "keys_removed": keys_removed,
            "keys_changed": keys_changed,
        }
