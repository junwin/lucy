from __future__ import annotations

from typing import Any, Dict, Optional

from src.handlers.handler_v2 import HandlerV2


class ToolHandlerMetaHandler(HandlerV2):
    """Return tool metadata for a named registered handler.

    Args: {"tool_name": "<name>"}

    Returns: {ok, tool, requested_tool_name, tool_def, result_schema, error}
    """

    NAME = "tool_handler_meta"

    def __init__(self, config: Any):
        # keep signature compatible with registry.create
        self.config = config

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": "Return the tool definition and result JSON schema for a named tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string", "description": "Name of the tool to inspect."},
                },
                "required": ["tool_name"],
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
                "requested_tool_name": {"type": "string"},
                "tool_def": {"type": ["object", "null"]},
                "result_schema": {"type": ["object", "null"]},
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": False,
        }

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:
        tool_name = (args.get("tool_name") or "").strip()
        if not tool_name:
            return {"ok": False, "tool": self.NAME, "error": "tool_name is required"}

        # Lazy import to avoid circular module import at package import time
        from src.handlers.registry_bootstrap import build_registry

        reg = build_registry()

        # Find tool_def by name
        tool_def: Optional[Dict[str, Any]] = None
        for td in reg.tools():
            if td.get("name") == tool_name:
                tool_def = td
                break

        schema = reg.result_schema(tool_name)

        if tool_def is None and schema is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "requested_tool_name": tool_name,
                "error": f"Unknown tool: {tool_name}",
            }

        return {
            "ok": True,
            "tool": self.NAME,
            "requested_tool_name": tool_name,
            "tool_def": tool_def,
            "result_schema": schema,
        }
