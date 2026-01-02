import os
import json
import logging
from typing import Any, Dict

from src.config_manager import ConfigManager
from src.handlers.handler_utils import get_base_path
from src.handlers.handler_v2 import HandlerV2


class FileSaveHandler2(HandlerV2):
    NAME = "file_save"

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
            "description": "Save code or text into a file under the allowed base folder",
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
                        "description": "Name of the file to be saved",
                    },
                    "file_content": {
                        "type": "string",
                        "description": "Content to write to the file",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "If false, fail when the target file already exists",
                        "default": True,
                    },
                },
                # STRICT MODE: ALL PROPERTIES MUST BE REQUIRED
                "required": [
                    "directory_path",
                    "file_name",
                    "file_content",
                    "overwrite",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        # Mirrors FileLoadHandler2: require ok + tool; allow additionalProperties
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
        file_content = args.get("file_content")
        overwrite = args.get("overwrite", True)

        # Basic presence check
        if not directory_path or not file_name or file_content is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "directory_path, file_name and file_content are required",
                "args": {"directory_path": directory_path, "file_name": file_name},
            }

        if not isinstance(file_content, str):
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "file_content must be a string",
                "directory_path": directory_path,
                "file_name": file_name,
            }

        # Enforce that directory_path is relative and safe
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
            "file_save: account=%s directory_path=%s file_name=%s overwrite=%s",
            account_name,
            directory_path,
            file_name,
            overwrite,
        )

        # Resolve to allowed base path
        base_path = get_base_path(self.config, account_name, norm_dir)
        logging.info("file_save: resolved base_path=%s", base_path)

        try:
            full_path = self._write_file_safe(
                base_path,
                file_name,
                file_content,
                overwrite=bool(overwrite),
            )
        except Exception as e:
            logging.exception("file_save failed")
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
            "result": f"success file saved at {full_path}",
        }

    def execute_as_tool_content(self, args: Dict[str, Any], *, account_name: str = "auto") -> str:
        return json.dumps(self.execute(args, account_name=account_name), ensure_ascii=False)

    def _write_file_safe(self, base_path: str, file_name: str, content: str, overwrite: bool = True) -> str:
        """Writes file_name inside base_path safely. Mirrors FileLoadHandler2 path rules."""
        base_abs = os.path.abspath(base_path)

        # file_name must be a bare filename (no path separators)
        if os.path.sep in file_name or (os.path.altsep and os.path.altsep in file_name):
            raise ValueError("file_name must not contain path separators")

        full_path = os.path.abspath(os.path.join(base_abs, file_name))

        # Ensure full path is within base path
        if not (full_path == base_abs or full_path.startswith(base_abs + os.path.sep)):
            raise ValueError("File access outside allowed base path")

        # Ensure directory exists
        os.makedirs(base_abs, exist_ok=True)

        # Overwrite protection
        if not overwrite and os.path.exists(full_path):
            raise FileExistsError("Target file already exists and overwrite=false")

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        return full_path
