"""Explicit, permission-checked activation of discovered tools."""

from __future__ import annotations

from typing import Any, Dict

from src.handlers.handler_v2 import HandlerV2


class ActivateToolsHandler(HandlerV2):
    """Request run-scoped activation of qualified catalog tool IDs."""

    NAME = "activate_tools"
    MAX_ACTIVATIONS = 5

    def __init__(self, config: Any):
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
                "Activate one or more tools returned by discover_tools for the "
                "remainder of the current request. This does not invoke the tools."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": cls.MAX_ACTIVATIONS,
                        "description": (
                            "Qualified tool IDs returned by discover_tools, such as "
                            "'galet-tools:bsky_publish'."
                        ),
                    }
                },
                "required": ["tool_ids"],
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
                "activated": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "activate_tool_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": False,
        }

    def execute(
        self,
        args: Dict[str, Any],
        *,
        account_name: str = "auto",
        **context: Any,
    ) -> Dict[str, Any]:
        registry = context.get("registry")
        agent = context.get("primary_agent")
        context_state = context.get("context_state")
        catalog = getattr(registry, "tool_catalog", None) if registry is not None else None
        if registry is None or agent is None or catalog is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "registry, catalog, and primary_agent are required",
            }

        requested = list(
            dict.fromkeys(
                str(value).strip()
                for value in (args.get("tool_ids") or [])
                if str(value).strip()
            )
        )
        if not requested:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "tool_ids must contain at least one qualified tool id",
            }
        if len(requested) > self.MAX_ACTIVATIONS:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": f"at most {self.MAX_ACTIVATIONS} tools may be activated at once",
            }

        eligible_names = self._eligible_names(registry, agent, context_state)
        rejected: list[str] = []
        for tool_id in requested:
            descriptor = catalog.get(tool_id)
            definition = catalog.definition(tool_id)
            if (
                descriptor is None
                or definition is None
                or descriptor.name not in eligible_names
                or descriptor.name in {"discover_tools", "activate_tools"}
            ):
                rejected.append(tool_id)

        if rejected:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": (
                    "Unknown or ineligible tool id(s): " + ", ".join(rejected)
                ),
            }

        # LLMLoopRunner recognizes this field only on results from this handler
        # and performs a second eligibility check before changing function_defs.
        return {
            "ok": True,
            "tool": self.NAME,
            "activated": requested,
            "activate_tool_ids": requested,
        }

    @staticmethod
    def _eligible_names(registry: Any, agent: Any, context_state: Any) -> set[str]:
        resolver = getattr(registry, "eligible_tool_defs", None)
        if callable(resolver):
            definitions = resolver(agent, context_state)
        else:
            allowed = set(getattr(agent, "allowed_tools", None) or [])
            definitions = [
                tool_def
                for tool_def in registry.tools()
                if tool_def.get("name") in allowed
            ]
        return {
            str(tool_def.get("name"))
            for tool_def in definitions
            if tool_def.get("name")
        }
