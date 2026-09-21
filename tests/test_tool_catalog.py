from __future__ import annotations

import pytest

from src.handlers.tool_catalog import (
    RegistryToolProvider,
    ToolCatalog,
    ToolDescriptor,
)


class FakeRegistry:
    def __init__(self) -> None:
        self.created: list[tuple[str, dict]] = []

    def tools(self):
        return [
            {
                "type": "function",
                "name": "bsky_publish",
                "description": "Publish text and images to Bluesky",
                "parameters": {"type": "object"},
            },
            {
                "type": "function",
                "name": "tumblr_publish",
                "description": "Publish text and images to Tumblr",
                "parameters": {"type": "object"},
            },
        ]

    def create(self, name: str, **kwargs):
        self.created.append((name, kwargs))
        return {"name": name, **kwargs}


def test_descriptor_metadata_is_optional() -> None:
    descriptor = ToolDescriptor.from_tool_def(
        {"name": "plain_tool", "description": "No classification"},
        source="lucy",
    )

    assert descriptor.id == "lucy:plain_tool"
    assert descriptor.groups == ()
    assert descriptor.tags == ()
    assert descriptor.aliases == ()
    assert descriptor.capabilities == ()


def test_singular_group_is_accepted_and_normalised() -> None:
    descriptor = ToolDescriptor.from_tool_def(
        {"name": "bsky_publish", "description": "Publish to Bluesky"},
        source="galet-tools",
        metadata={
            "group": "Social-Media-Tools",
            "tags": ["social-media", "image-tools", "Social-Media"],
        },
    )

    assert descriptor.groups == ("social-media-tools",)
    assert descriptor.tags == ("image-tools", "social-media")


def test_catalog_combines_sources_using_qualified_ids() -> None:
    registry = FakeRegistry()
    catalog = ToolCatalog(
        [
            RegistryToolProvider(
                registry,
                source="galet-tools",
                tool_names=frozenset({"bsky_publish"}),
            ),
            RegistryToolProvider(
                registry,
                source="lucy",
                tool_names=frozenset({"tumblr_publish"}),
            ),
        ]
    )

    assert [item.id for item in catalog.descriptors()] == [
        "galet-tools:bsky_publish",
        "lucy:tumblr_publish",
    ]
    assert catalog.create("galet-tools:bsky_publish", config="config") == {
        "name": "bsky_publish",
        "config": "config",
    }


def test_catalog_searches_optional_groups_and_tags() -> None:
    registry = FakeRegistry()
    metadata = {
        "bsky_publish": {
            "groups": ["social-media-tools", "publishing-tools"],
            "tags": ["social-media", "image-tools", "bluesky"],
        },
        "tumblr_publish": {
            "groups": ["social-media-tools", "publishing-tools"],
            "tags": ["social-media", "image-tools", "tumblr"],
        },
    }
    catalog = ToolCatalog(
        [RegistryToolProvider(registry, source="galet-tools", metadata=metadata)]
    )

    image_publishers = catalog.search(
        groups=["social-media-tools"],
        tags=["image-tools"],
    )
    bluesky = catalog.search("bluesky", groups=["social-media-tools"])

    assert [item.name for item in image_publishers] == [
        "bsky_publish",
        "tumblr_publish",
    ]
    assert [item.name for item in bluesky] == ["bsky_publish"]


def test_provider_names_are_unique() -> None:
    registry = FakeRegistry()
    provider = RegistryToolProvider(registry, source="lucy")

    with pytest.raises(ValueError, match="duplicate tool provider source"):
        ToolCatalog([provider, provider])
