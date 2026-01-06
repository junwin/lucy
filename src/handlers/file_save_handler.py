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
            "description": (
                "Save code or text into a file under the allowed base folder. "
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
                "required": [
                    "relative_path",
                    "file_content",
                    "overwrite",
                ],
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
        file_content = args.get("file_content")
        overwrite = args.get("overwrite", True)

        if not relative_path or file_content is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "relative_path and file_content are required",
                "args": {"relative_path": relative_path},
            }

        if not isinstance(file_content, str):
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "file_content must be a string",
                "relative_path": relative_path,
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
            "file_save: account=%s relative_path=%s overwrite=%s",
            account_name,
            relative_path,
            overwrite,
        )

        directory_part = os.path.dirname(norm_rel)
        file_name = os.path.basename(norm_rel)

        base_path = get_base_path(self.config, account_name, directory_part)
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
            "result": f"success file saved at {full_path}",
        }

    def execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "") -> str:
        try:
            args = json.loads(arguments_raw or "{}")
        except Exception:
            args = {}
        result = self.execute(args if isinstance(args, dict) else {}, account_name=account_name)
        return json.dumps(result, ensure_ascii=False)

    @staticmethod
    def _has_drive_letter(path: str) -> bool:
        # Disallow Windows drive letters like C:\\ or C:/ even if running on non-Windows.
        if len(path) >= 2 and path[1] == ":" and path[0].isalpha():
            return True
        return False

    def _write_file_safe(self, base_path: str, file_name: str, content: str, overwrite: bool = True) -> str:
        """Writes file_name inside base_path safely. Mirrors FileLoadHandler2 path rules."""
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

        os.makedirs(base_real, exist_ok=True)

        if not overwrite and os.path.exists(full_real):
            raise FileExistsError("Target file already exists and overwrite=false")

        with open(full_real, "w", encoding="utf-8") as f:
            f.write(content)

        return full_real
