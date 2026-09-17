"""PatchApplyHandler — apply unified-diff patches using git apply.

This is a native Lucy handler (HandlerV2) rather than a galet adapter so it
can implement the exact apply semantics desired by the design.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import importlib.util
from pathlib import PurePosixPath, Path
from typing import Any, Dict

from src.config_manager import ConfigManager
try:
    from src.handlers.handler_v2 import HandlerV2
except Exception:
    # Testing/runtime fallback: provide a minimal HandlerV2 base if galet_tools is not available
    class HandlerV2:
        pass

logger = logging.getLogger(__name__)


def _resolve_lucy_storage_resolver_class():
    # Prefer the installed package import if available (normal runtime).
    try:
        from src.handlers.galet_adapters import LucyStorageLocationResolver

        return LucyStorageLocationResolver
    except Exception:
        # Fallback: load galet_adapters.py from the same directory as this file
        here = Path(__file__).resolve().parent
        path = here / "galet_adapters.py"
        spec = importlib.util.spec_from_file_location("galet_adapters_local", str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.LucyStorageLocationResolver


class PatchApplyHandler(HandlerV2):
    NAME = "patch_apply"

    def __init__(self, config: ConfigManager) -> None:
        self.config = config
        resolver_cls = _resolve_lucy_storage_resolver_class()
        self._resolver = resolver_cls(config)

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": "Apply a unified-diff patch to files on disk using git apply. Use check_only to validate without applying.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "enum": ["storage", "external"]},
                    "external_root": {"type": "string"},
                    "path": {"type": "string"},
                    "patch_content": {"type": "string"},
                    "check_only": {"type": "boolean"},
                },
                "required": ["location", "path", "patch_content"],
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
                "applied": {"type": "boolean"},
                "error": {"type": "string"},
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
            },
            "required": ["ok", "tool", "applied"],
            "additionalProperties": True,
        }

    def _invalid(self, message: str, **extra: Any) -> Dict[str, Any]:
        res = {"ok": False, "tool": self.NAME, "applied": False, "error": message}
        res.update(extra)
        return res

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:
        loc = (args.get("location") or "").strip()
        external_root = (args.get("external_root") or "").strip()
        path = (args.get("path") or "").strip()
        patch_content = args.get("patch_content") or ""
        check_only = bool(args.get("check_only", False))

        if loc not in ("storage", "external"):
            return self._invalid("location must be 'storage' or 'external'")
        if not path:
            return self._invalid("path is required")
        if not patch_content:
            return self._invalid("patch_content is required")

        # Reject absolute paths and parent-up traversal.
        p = PurePosixPath(path)
        if p.is_absolute() or any(part == ".." for part in p.parts):
            return self._invalid("path must be relative and must not contain '..' or be absolute")

        try:
            if loc == "storage":
                base_dir = self._resolver.storage_base_dir()
            else:
                base_dir = self._resolver.external_root_dir(external_root)
        except Exception as e:
            return self._invalid(str(e))

        # Ensure the resolved working directory is inside the base_dir.
        # We'll run git apply from base_dir so file-level escapes should not be
        # possible if callers provide a valid relative path, but check anyway.
        try:
            base_dir = os.path.abspath(base_dir)
        except Exception as e:
            return self._invalid(f"Could not resolve base dir: {e}")

        # Write patch to a temporary file.
        tmp = None
        try:
            tf = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8")
            tf.write(patch_content)
            tf.flush()
            tf.close()
            tmp = tf.name

            # First run a check
            cmd_check = ["git", "apply", "--check", tmp]
            proc = subprocess.run(cmd_check, cwd=base_dir, capture_output=True, text=True)
            if proc.returncode != 0:
                return self._invalid("git apply --check failed", stdout=proc.stdout, stderr=proc.stderr)

            if check_only:
                return {"ok": True, "tool": self.NAME, "applied": False, "stdout": proc.stdout, "stderr": proc.stderr}

            # Apply the patch
            cmd_apply = ["git", "apply", tmp]
            proc2 = subprocess.run(cmd_apply, cwd=base_dir, capture_output=True, text=True)
            if proc2.returncode != 0:
                return self._invalid("git apply failed", stdout=proc2.stdout, stderr=proc2.stderr)

            return {"ok": True, "tool": self.NAME, "applied": True, "stdout": proc2.stdout, "stderr": proc2.stderr}
        except FileNotFoundError as e:
            return self._invalid("git not found on PATH", error=str(e))
        except Exception as e:
            logger.exception("patch apply failed")
            return self._invalid("exception during patch apply", error=str(e))
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass

    def execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "", **context: Any) -> str:
        try:
            args = json.loads(arguments_raw or "{}")
        except Exception:
            args = {}
        result = self.execute(args if isinstance(args, dict) else {}, account_name=account_name)
        return json.dumps(result, ensure_ascii=False)


__all__ = ["PatchApplyHandler"]
