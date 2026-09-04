"""Conformance tests for ``src.mcp.tool_adapter`` (design doc Tests table).

Pure/offline: no MCP SDK, no network, no server process. The tests run
against the *real* HandlerRegistry (``registry_bootstrap.build_registry()``)
so any future handler whose ``tool_def()`` stops translating losslessly to an
MCP tool fails CI (design doc, Risks: schema drift).

Covered here:

- ``test_tool_adapter_mapping`` — every registered handler ``tool_def()``
  translates to a valid MCP tool with identical name/description/parameters
  (lossless).
- ``test_tool_adapter_duplicate_defs`` — duplicate names cannot surface
  (``HandlerRegistry.register`` raises ``ValueError``) and the adapter is
  idempotent over the registry list (deterministic translation, one MCP tool
  per registered def, unique names, no state).
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from src.handlers.handler_registry import HandlerRegistry
from src.handlers.handler_v2 import HandlerV2
from src.mcp.tool_adapter import handler_tool_def_to_mcp

#: Keys of a translated MCP tool. ``inputSchema`` replaces ``parameters``;
#: extra ``tool_def()`` keys (``type``, ``strict``, ...) are dropped by design
#: (design doc, Decision 2).
_MCP_TOOL_KEYS = frozenset({"name", "description", "inputSchema"})

#: Source fields that must survive translation losslessly.
_SOURCE_FIELDS = ("name", "description", "parameters")


@pytest.fixture(scope="module")
def real_registry() -> HandlerRegistry:
    """The registry exactly as the application boots it."""
    from src.handlers.registry_bootstrap import build_registry

    return build_registry()


def _source_def(tool_def: Dict[str, Any]) -> Dict[str, Any]:
    """Return the dict carrying the OpenAI/Responses fields.

    Mirrors the Decision 2 mapping: a Chat-Completions style ``function``
    wrapper wins when present, otherwise the def is read flat (the current
    code reality for every registered handler).
    """
    function = tool_def.get("function")
    return function if isinstance(function, dict) else tool_def


def test_tool_adapter_mapping(real_registry: HandlerRegistry) -> None:
    """Every registered handler tool_def() translates losslessly to an MCP tool."""
    tool_defs = real_registry.tools()
    assert tool_defs, "conformance over an empty registry would be vacuous"

    mcp_names = []
    for tool_def in tool_defs:
        source = _source_def(tool_def)

        # Uniformity invariant: every registry def must carry all three source
        # fields, otherwise the translation would silently fall back to an
        # adapter default ("", {}) and no longer be lossless. Failing here is
        # the intended schema-drift tripwire for a human decision.
        missing = [k for k in _SOURCE_FIELDS if k not in source]
        assert not missing, (
            f"registered tool_def {source.get('name')!r} missing source "
            f"field(s) {missing}; translation would not be lossless"
        )

        mcp_tool = handler_tool_def_to_mcp(tool_def)

        # Valid MCP tool shape: exactly {name, description, inputSchema}.
        assert set(mcp_tool) == _MCP_TOOL_KEYS
        assert isinstance(mcp_tool["name"], str) and mcp_tool["name"]
        assert isinstance(mcp_tool["description"], str)
        assert isinstance(mcp_tool["inputSchema"], dict)

        # Lossless: identical name/description/parameters.
        assert mcp_tool["name"] == source["name"]
        assert mcp_tool["description"] == source["description"]
        assert mcp_tool["inputSchema"] == source["parameters"]

        # inputSchema is a deep copy: MCP-side mutation cannot alias back into
        # the registry-owned def.
        assert mcp_tool["inputSchema"] is not source["parameters"]

        mcp_names.append(mcp_tool["name"])

    # One MCP tool per registered handler: nothing invented, nothing dropped.
    assert len(mcp_names) == len(tool_defs)
    assert sorted(mcp_names) == real_registry.tool_names()


class _StubToolHandler(HandlerV2):
    """Registry/translation stub with a fixed tool name."""

    _NAME = "stub_dup_tool"

    @classmethod
    def name(cls) -> str:
        return cls._NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls._NAME,
            "description": "stub handler for duplicate-name tests",
            "parameters": {"type": "object", "properties": {}},
        }

    def execute(
        self, args: Dict[str, Any], *, account_name: str = "auto", **context
    ) -> Dict[str, Any]:
        return {"ok": True}


class _StubToolHandlerLookalike(_StubToolHandler):
    """Second handler class that deliberately collides on ``name()``."""


def test_tool_adapter_duplicate_defs(real_registry: HandlerRegistry) -> None:
    """Duplicate names cannot surface; the adapter is idempotent over the list."""
    # --- The registry is the uniqueness gate --------------------------------
    # register() raises ValueError on any second handler under an existing
    # name, so duplicate tool names can never reach the adapter from a
    # registry-built list (registry.register is the only insertion path).
    registry = HandlerRegistry()
    registry.register(_StubToolHandler)
    with pytest.raises(ValueError, match="Duplicate handler name registered"):
        registry.register(_StubToolHandler)  # same class registered twice
    with pytest.raises(ValueError, match="Duplicate handler name registered"):
        registry.register(_StubToolHandlerLookalike)  # same name(), other class
    assert registry.tool_names() == [_StubToolHandler._NAME]

    # --- The adapter is idempotent over the registry list ------------------
    tool_defs = real_registry.tools()
    assert tool_defs

    translated_once = [handler_tool_def_to_mcp(d) for d in tool_defs]

    # Deterministic: translating the registry list again yields the same tools.
    translated_twice = [handler_tool_def_to_mcp(d) for d in real_registry.tools()]
    assert translated_once == translated_twice

    # Unique MCP names, one per registered handler: the adapter never invents,
    # drops or renames, so duplicates cannot surface through the registry path.
    mcp_names = [tool["name"] for tool in translated_once]
    assert len(mcp_names) == len(set(mcp_names)) == len(real_registry.tool_names())
    assert sorted(mcp_names) == real_registry.tool_names()

    # Stateless: repeated translation of the same def is stable, and mutating
    # one translated output cannot bleed into a later translation.
    first = handler_tool_def_to_mcp(tool_defs[0])
    second = handler_tool_def_to_mcp(tool_defs[0])
    assert first == second
    first["inputSchema"]["_probe"] = True
    assert handler_tool_def_to_mcp(tool_defs[0]) == second
