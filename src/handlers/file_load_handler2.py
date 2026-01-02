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
                "Load a file from a directory relative to the allowed base folder "
                "and chunk if needed"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": (
                            "Location of the file relative to the allowed base folder. "
                            "Must be a relative path (no leading / and no .. segments)."
                        ),
                    },
                    "file_name": {
                        "type": "string",
                        "description": "Name of the file to be loaded",
                    },
                },
                "required": ["directory_path", "file_name"],
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
        directory_path = (args.get("directory_path") or "").strip()
        file_name = (args.get("file_name") or "").strip()

        if not directory_path or not file_name:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "directory_path and file_name are required",
                "args": {"directory_path": directory_path, "file_name": file_name},
            }

        if os.path.isabs(directory_path):
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "directory_path must be relative, not absolute",
                "directory_path": directory_path,
            }

        norm_dir = os.path.normpath(directory_path)
        if norm_dir.startswith("..") or os.path.isabs(norm_dir):
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "directory_path must not escape the allowed base folder",
                "directory_path": directory_path,
                "normalized_directory_path": norm_dir,
            }

        logging.info(
            "file_load: account=%s directory_path=%s file_name=%s",
            account_name,
            directory_path,
            file_name,
        )

        base_path = get_base_path(self.config, account_name, norm_dir)
        logging.info("file_load: resolved base_path=%s", base_path)

        try:
            content, full_path = self._read_file_safe(base_path, file_name)
        except Exception as e:
            logging.exception("file_load failed")
            return {
                "ok": False,
                "tool": self.NAME,
                "error": str(e),
                "directory_path": directory_path,
                "normalized_directory_path": norm_dir,
                "file_name": file_name,
                "base_path": base_path,
            }

        return {
            "ok": True,
            "tool": self.NAME,
            "file_name": file_name,
            "directory_path": directory_path,
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

    def _read_file_safe(self, base_path: str, file_name: str) -> Tuple[str, str]:
        base_abs = os.path.abspath(base_path)

        if os.path.sep in file_name or (os.path.altsep and os.path.altsep in file_name):
            raise ValueError("file_name must not contain path separators")

        full_path = os.path.abspath(os.path.join(base_abs, file_name))

        if not (full_path == base_abs or full_path.startswith(base_abs + os.path.sep)):
            raise ValueError("File access outside allowed base path")

        with open(full_path, "r", encoding="utf-8") as f:
            return f.read(), full_path
