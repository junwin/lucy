"""Deliver an existing account-scoped generated report without passing bytes to the model."""
from __future__ import annotations
from typing import Any, Dict
from src.generated_files import resolve_report
from src.handlers.handler_v2 import HandlerV2


class ServeFileHandler(HandlerV2):
    NAME = "serve_file"

    def __init__(self, config):
        self.config = config

    @classmethod
    def name(cls):
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": "Deliver an existing account-owned generated report file to the browser. Accepts a file UUID only; never an arbitrary path.",
            "parameters": {"type": "object", "properties": {
                "file_id": {"type": "string", "description": "UUID returned by execution_trace."},
            }, "required": ["file_id"], "additionalProperties": False},
            "strict": True,
        }

    @classmethod
    def result_schema(cls):
        return {"type": "object", "properties": {
            "ok": {"type": "boolean"}, "tool": {"type": "string"},
            "file": {"type": "object"}, "error": {"type": "string"},
        }, "required": ["ok", "tool"], "additionalProperties": True}

    def execute(self, args, *, account_name="auto", **context):
        file_id = args.get("file_id") or ""
        try:
            path, mime = resolve_report(self.config, account_name, file_id)
            return {"ok": True, "tool": self.NAME, "file": {
                "file_id": path.stem,
                "mime_type": mime,
                "download_name": path.name,
                "size_bytes": path.stat().st_size,
            }}
        except (ValueError, OSError) as exc:
            return {"ok": False, "tool": self.NAME, "error": str(exc)}
