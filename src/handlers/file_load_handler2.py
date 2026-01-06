import os
import json
import logging
from typing import Any, Dict, Tuple

from src.config_manager import ConfigManager
from src.handlers.handler_utils import get_base_path
from src.handlers.handler_v2 import HandlerV2


class FileLoadHandler2(HandlerV2):
    NAME = "file_load"

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
                "Load a file from a path relative to the allowed base folder and chunk if needed. "
                "By default, relative paths are resolved under the account home directory (e.g. /home/<account>/...)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": (
                            "File path relative to the allowed base folder (by default: the account home directory). "
                            "Must be a relative path (no leading /, no drive letters, no .. segments)."
                        ),
                    },
                },
                "required": ["relative_path"],
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
                "file_name": {"type": "string"},
                "directory_path": {"type": "string"},
                "relative_path": {"type": "string"},
                "resolved_path": {"type": "string"},
                "content_type": {"type": "string"},
                "encoding": {"type": "string"},
                "result": {"type": "string"},
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:
        relative_path = (args.get("relative_path") or "").strip()

        if not relative_path:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "relative_path is required",
                "args": {"relative_path": relative_path},
            }

        if self._has_drive_letter(relative_path):
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "relative_path must be relative, not include drive letters",
                "relative_path": relative_path,
            }

        if os.path.isabs(relative_path):
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "relative_path must be relative, not absolute",
                "relative_path": relative_path,
            }

        norm_rel = os.path.normpath(relative_path)

        # Reject empty/special paths and any parent traversal after normalization.
        if norm_rel in ("", ".", ".."):
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "relative_path must not be empty or point to current/parent directory",
                "relative_path": relative_path,
                "normalized_relative_path": norm_rel,
            }

        # Also reject any '..' segment anywhere in the normalized path.
        parts = [p for p in norm_rel.split(os.path.sep) if p]
        if os.path.altsep:
            parts = [p for seg in parts for p in seg.split(os.path.altsep) if p]
        if any(p == ".." for p in parts) or norm_rel.startswith(".."):
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "relative_path must not contain '..' segments",
                "relative_path": relative_path,
                "normalized_relative_path": norm_rel,
            }

        logging.info(
            "file_load: account=%s relative_path=%s",
            account_name,
            relative_path,
        )

        # Keep behavior consistent with previous implementation: base path is derived from
        # the directory portion, and file name is read within that base.
        directory_part = os.path.dirname(norm_rel)
        file_name = os.path.basename(norm_rel)

        base_path = get_base_path(self.config, account_name, directory_part)
        logging.info("file_load: resolved base_path=%s", base_path)

        try:
            content, full_path = self._read_file_safe(base_path, file_name)
        except Exception as e:
            logging.exception("file_load failed")
            return {
                "ok": False,
                "tool": self.NAME,
                "error": str(e),
                "relative_path": relative_path,
                "normalized_relative_path": norm_rel,
                "file_name": file_name,
                "base_path": base_path,
            }

        return {
            "ok": True,
            "tool": self.NAME,
            "file_name": file_name,
            "relative_path": relative_path,
            "resolved_path": full_path,
            "content_type": "text/plain",
            "encoding": "utf-8",
            "result": content,
        }

    # New contract: tool processors call execute_raw
    def execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "") -> str:
        try:
            args = json.loads(arguments_raw or "{}")
        except Exception:
            args = {}
        result = self.execute(args if isinstance(args, dict) else {}, account_name=account_name)
        return json.dumps(result, ensure_ascii=False)

    @staticmethod
    def _has_drive_letter(path: str) -> bool:
        # Disallow Windows drive letters like C:\ or C:/ even if running on non-Windows.
        if len(path) >= 2 and path[1] == ":" and path[0].isalpha():
            return True
        return False

    def _read_file_safe(self, base_path: str, file_name: str) -> Tuple[str, str]:
        base_abs = os.path.abspath(base_path)

        if os.path.sep in file_name or (os.path.altsep and os.path.altsep in file_name):
            raise ValueError("file_name must not contain path separators")

        joined = os.path.join(base_abs, file_name)
        full_path = os.path.normpath(joined)

        # Realpath containment check to prevent symlink escapes.
        base_real = os.path.realpath(base_abs)
        full_real = os.path.realpath(full_path)
        if not (full_real == base_real or full_real.startswith(base_real + os.path.sep)):
            raise ValueError("File access outside allowed base path")

        with open(full_real, "r", encoding="utf-8") as f:
            return f.read(), full_real
