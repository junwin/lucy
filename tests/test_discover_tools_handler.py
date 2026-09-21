from __future__ import annotations

from types import SimpleNamespace

from src.handlers.discover_tools_handler import DiscoverToolsHandler
from src.handlers.tool_catalog import RegistryToolProvider, ToolCatalog


class DiscoveryRegistry:
    def __init__(self) -> None:
        self._defs = [
            {
                "type": "function",
                "name": "discover_tools",
                "description": "Discover eligible tools",
            },
            {
                "type": "function",
                "name": "bsky_publish",
                "description": "Publish text and images to Bluesky",
            },
            {
                "type": "function",
                "name": "tumblr_publish",
                "description": "Publish text and images to Tumblr",
            },
            {
                "type": "function",
                "name": "admin_delete",
                "description": "Delete an administrator account",
            },
        ]
        self.tool_catalog = ToolCatalog(
            [
                RegistryToolProvider(
                    self,
                    source="galet-tools",
                    metadata={
                        "bsky_publish": {
                            "groups": ["social-media-tools"],
                            "tags": ["social-media", "image-tools", "bluesky"],
                            "capabilities": ["network", "external-publish"],
                        },
                        "tumblr_publish": {
                            "groups": ["social-media-tools"],
                            "tags": ["social-media", "image-tools", "tumblr"],
                            "capabilities": ["network", "external-publish"],
                        },
                        "admin_delete": {
                            "groups": ["administration-tools"],
                            "tags": ["dangerous"],
                        },
                    },
                )
            ]
        )

    def tools(self):
        return list(self._defs)

    def eligible_tool_defs(self, agent, context_state):
        allowed = set(agent.allowed_tools)
        if context_state is not None:
            allowed &= set(context_state.allowed_tools)
        return [item for item in self._defs if item["name"] in allowed]

    def create(self, name, **kwargs):
        return name


def _execute(registry, *, allowed_tools, context_tools=None, **args):
    agent = SimpleNamespace(allowed_tools=allowed_tools)
    context_state = (
        SimpleNamespace(allowed_tools=context_tools)
        if context_tools is not None
        else None
    )
    return DiscoverToolsHandler(config=None).execute(
        {
            "query": args.get("query", ""),
            "groups": args.get("groups", []),
            "tags": args.get("tags", []),
            "limit": args.get("limit", 10),
        },
        registry=registry,
        primary_agent=agent,
        context_state=context_state,
    )


def test_discovery_returns_compact_group_and_tag_matches() -> None:
    result = _execute(
        DiscoveryRegistry(),
        allowed_tools=["discover_tools", "bsky_publish", "tumblr_publish"],
        query="publish image",
        groups=["social-media-tools"],
        tags=["image-tools"],
    )

    assert result["ok"] is True
    assert [item["name"] for item in result["matches"]] == [
        "bsky_publish",
        "tumblr_publish",
    ]
    assert result["matches"][0] == {
        "id": "galet-tools:bsky_publish",
        "name": "bsky_publish",
        "description": "Publish text and images to Bluesky",
        "source": "galet-tools",
        "groups": ["social-media-tools"],
        "tags": ["bluesky", "image-tools", "social-media"],
        "capabilities": ["external-publish", "network"],
        "score": 46,
        "matched_on": [
            "tag:image",
            "description:image",
            "name:publish",
            "capability:publish",
            "description:publish",
        ],
    }


def test_discovery_ignores_stop_words_and_does_not_pad_results() -> None:
    result = _execute(
        DiscoveryRegistry(),
        allowed_tools=[
            "discover_tools",
            "bsky_publish",
            "tumblr_publish",
            "admin_delete",
        ],
        query="tools related to generating or publishing an image",
        limit=10,
    )

    assert [item["name"] for item in result["matches"]] == [
        "bsky_publish",
        "tumblr_publish",
    ]
    assert all(item["score"] > 0 for item in result["matches"])
    assert all(item["matched_on"] for item in result["matches"])


def test_discovery_never_discloses_agent_prohibited_tools() -> None:
    result = _execute(
        DiscoveryRegistry(),
        allowed_tools=["discover_tools", "bsky_publish"],
        query="delete administrator account",
    )

    assert result["ok"] is True
    assert result["matches"] == []
    assert "admin_delete" not in repr(result)


def test_context_allowlist_further_narrows_discovery() -> None:
    result = _execute(
        DiscoveryRegistry(),
        allowed_tools=["discover_tools", "bsky_publish", "tumblr_publish"],
        context_tools=["discover_tools", "tumblr_publish"],
        groups=["social-media-tools"],
        tags=["image-tools"],
    )

    assert [item["name"] for item in result["matches"]] == ["tumblr_publish"]


def test_discovery_does_not_return_itself() -> None:
    result = _execute(
        DiscoveryRegistry(),
        allowed_tools=["discover_tools"],
        query="discover eligible tools",
    )

    assert result["matches"] == []


def test_discovery_requires_permission_context() -> None:
    result = DiscoverToolsHandler(config=None).execute(
        {"query": "", "groups": [], "tags": [], "limit": 10}
    )

    assert result == {
        "ok": False,
        "tool": "discover_tools",
        "error": "registry and primary_agent are required for safe discovery",
    }
