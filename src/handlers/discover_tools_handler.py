"""Permission-aware discovery over Lucy's provider-neutral tool catalog."""

from __future__ import annotations

from typing import Any, Dict

from src.handlers.handler_v2 import HandlerV2
from src.handlers.tool_catalog import RegistryToolProvider, ToolCatalog


class DiscoverToolsHandler(HandlerV2):
    """Find compact descriptors without exposing ineligible tool schemas."""

    NAME = "discover_tools"

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
                "Find tools that may help with the current task. Searches eligible "
                "tools by purpose, group, and tags without activating or invoking them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Short description of the capability needed, for example "
                            "'publish an image to social media'. Use an empty string "
                            "when filtering only by groups or tags."
                        ),
                    },
                    "groups": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional groups that every match must belong to.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags that every match must carry.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "description": "Maximum number of compact matches to return.",
                    },
                },
                "required": ["query", "groups", "tags", "limit"],
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
                "query": {"type": "string"},
                "count": {"type": "integer"},
                "matches": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "source": {"type": "string"},
                            "groups": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "capabilities": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "score": {"type": "integer"},
                            "matched_on": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            "id",
                            "name",
                            "description",
                            "source",
                            "groups",
                            "tags",
                            "capabilities",
                            "score",
                            "matched_on",
                        ],
                        "additionalProperties": False,
                    },
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
        if registry is None or agent is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "registry and primary_agent are required for safe discovery",
            }

        catalog = getattr(registry, "tool_catalog", None)
        if catalog is None:
            # Compatibility fallback for tests and custom registry construction.
            # It preserves permission filtering, but source identity is generic.
            catalog = ToolCatalog(
                [RegistryToolProvider(registry, source="registry")]
            )

        eligible_names = self._eligible_names(registry, agent, context_state)
        # The discovery tool is already active and is not a useful search result.
        eligible_names.discard(self.NAME)

        query = str(args.get("query") or "").strip()
        groups = args.get("groups") or []
        tags = args.get("tags") or []
        limit = max(1, min(int(args.get("limit") or 10), 20))

        matches = [
            match
            for match in catalog.search_matches(
                query,
                groups=groups,
                tags=tags,
                # Filtering may remove catalog hits, so search the complete
                # catalog before applying the agent/context eligibility ceiling.
                limit=len(catalog.descriptors()),
            )
            if match.descriptor.name in eligible_names
        ][:limit]

        return {
            "ok": True,
            "tool": self.NAME,
            "query": query,
            "count": len(matches),
            "matches": [
                {
                    "id": match.descriptor.id,
                    "name": match.descriptor.name,
                    "description": match.descriptor.description,
                    "source": match.descriptor.source,
                    "groups": list(match.descriptor.groups),
                    "tags": list(match.descriptor.tags),
                    "capabilities": list(match.descriptor.capabilities),
                    "score": match.score,
                    "matched_on": list(match.matched_on),
                }
                for match in matches
            ],
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
