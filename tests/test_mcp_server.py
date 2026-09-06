"""Offline tests for ``src.mcp.server`` (design doc Tests table: test_mcp_*).

Pure/offline: no server process, no network, no MCP SDK import (the SDK
section is deferred to ``serve()``). Fakes stand in for the DI container /
AgentManager where the unit under test only needs ``get_agent`` /
``get``. Execution-path tests use the *real* ``ToolExecutor`` with a real
``HandlerRegistry`` + real ``Agent`` so argument passing / result / error
mapping are exercised exactly as the server dispatches (design doc
Decision 3: byte-identical context to an /ask run).

Covered here (design doc Tests table):

- ``test_mcp_config*`` — config block parse/defaults (incl. the repo
  ``config.json`` block shipping ``enabled: false``); missing agent /
  empty ``allowed_tools`` / zero eligible tools => startup refusal
  (fail closed, Decision 4).
- ``test_mcp_eligibility*`` — ``tools/list`` content ==
  ``eligible_tool_defs(mcp_agent, context)``; agent exclusion and context
  narrowing via the same FCP context-loading path.
- ``test_mcp_call_*`` — arguments reach a fake handler's ``execute()``
  unchanged; handler dict result -> MCP text content; too-large result ->
  capped error text content (FCP parity, ``isError`` False); handler
  exceptions and unknown tools -> MCP ``isError`` result.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from src.agent.agent import Agent
from src.handlers.handler_registry import HandlerRegistry
from src.handlers.handler_v2 import HandlerV2
from src.mcp.server import (
    McpConfigError,
    McpScope,
    dispatch_tool_call,
    effective_context_name,
    eligible_tools,
    resolve_mcp_config,
    resolve_scope,
    resolve_startup_scope,
)

#: Repo root = parents[1] of this test file (tests/).
_REPO_ROOT = Path(__file__).resolve().parents[1]

_DESIGN_MCP_BLOCK = {
    "enabled": False,
    "agent": "mcp",
    "account": "junwin",
    "context_name": "lucyproject",
    "transport": "streamable-http",
    "host": "127.0.0.1",
    "port": 8765,
}


class _Cfg:
    """Minimal ConfigManager stand-in: ``get(key, default)`` over a dict."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class _StubAgentManager:
    """AgentManager stand-in for resolve_scope / resolve_startup_scope."""

    def __init__(self, agent: Optional[Agent]) -> None:
        self._agent = agent

    def get_agent(self, name: str) -> Optional[Agent]:
        return self._agent


class _AlphaHandler(HandlerV2):
    """Registry handler whose name() is the allowlist key."""

    _NAME = "alpha_tool"

    @classmethod
    def name(cls) -> str:
        return cls._NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls._NAME,
            "description": "alpha handler for eligibility tests",
            "parameters": {
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            },
        }

    def execute(
        self, args: Dict[str, Any], *, account_name: str = "auto", **context
    ) -> Dict[str, Any]:
        return {"ok": True, "tool": self._NAME, "echo": args}


class _BetaHandler(_AlphaHandler):
    _NAME = "beta_tool"


class _GammaHandler(_AlphaHandler):
    _NAME = "gamma_tool"


class _RecordingHandler(_AlphaHandler):
    """Records (args, account_name) per execute() call."""

    _NAME = "mcp_rec_tool"
    SEEN: List[Dict[str, Any]] = []

    def __init__(self, config: Any) -> None:
        self.config = config

    def execute(
        self, args: Dict[str, Any], *, account_name: str = "auto", **context
    ) -> Dict[str, Any]:
        type(self).SEEN.append({"args": args, "account_name": account_name})
        return {"ok": True, "tool": self._NAME, "echo": args}


class _BoomHandler(_RecordingHandler):
    _NAME = "mcp_boom_tool"

    def execute(
        self, args: Dict[str, Any], *, account_name: str = "auto", **context
    ) -> Dict[str, Any]:
        raise ValueError("boom")


class _BigResultHandler(_RecordingHandler):
    """Returns a result over the configured max_tool_result_chars cap."""

    _NAME = "mcp_big_tool"

    def execute(
        self, args: Dict[str, Any], *, account_name: str = "auto", **context
    ) -> Dict[str, Any]:
        return {"blob": "x" * 4000}


class _LlamaStub:
    """LLMAdapter stand-in: ToolExecutor only calls format_tool_output."""

    def format_tool_output(
        self, *, call_id: str, output: str, name: str, provider: Optional[str]
    ) -> Dict[str, Any]:
        return {"call_id": call_id, "output": output, "name": name}


class _ExplodingExecutor:
    """ToolExecutor stand-in whose execute_tool_calls raises unexpectedly."""

    def __init__(self) -> None:
        self.wrapped: List[Dict[str, Any]] = []

    def wrap_tool_calls(self, tool_calls: Any) -> List[Any]:
        self.wrapped = list(tool_calls or [])
        return self.wrapped

    def execute_tool_calls(self, **kwargs: Any) -> Any:
        raise RuntimeError("kaboom")


class _FakePromptBuilder:
    """PromptBuilder stand-in serving a fixed context state."""

    def __init__(self, context_state: Any) -> None:
        self._context_state = context_state

    def _get_context_state(self, account_name: str, context_name: str) -> Any:
        return self._context_state


def _context_with_allowed_tools(tools: List[str]) -> Any:
    """A Context-like object carrying an explicit extra.allowed_tools list."""
    return type("_Ctx", (), {"extra": {"allowed_tools": tools}, "data": None})()


def _registry_with(*handler_classes: type) -> HandlerRegistry:
    registry = HandlerRegistry()
    for cls in handler_classes:
        registry.register(cls)
    return registry


def _mcp_agent(allowed_tools: Optional[List[str]]) -> Agent:
    return Agent(name="mcp", allowed_tools=allowed_tools)


def _scope_for(agent: Agent, eligible: List[str]) -> McpScope:
    return McpScope(
        agent=agent,
        account_id="junwin",
        context_name="",
        eligible_names=frozenset(eligible),
    )


# ---------------------------------------------------------------------------
# test_mcp_config
# ---------------------------------------------------------------------------


def test_mcp_config_defaults_when_block_absent() -> None:
    cfg = resolve_mcp_config(_Cfg({}))
    assert cfg == {
        "enabled": False,
        "agent": "mcp",
        "account": "junwin",
        "context_name": "",
        "transport": "streamable-http",
        "host": "127.0.0.1",
        "port": 8765,
    }


def test_mcp_config_parses_explicit_block() -> None:
    cfg = resolve_mcp_config(_Cfg({"mcp": _DESIGN_MCP_BLOCK}))
    assert cfg == {
        "enabled": False,
        "agent": "mcp",
        "account": "junwin",
        "context_name": "lucyproject",
        "transport": "streamable-http",
        "host": "127.0.0.1",
        "port": 8765,
    }


def test_mcp_config_rejects_unsupported_transport() -> None:
    with pytest.raises(McpConfigError, match="unsupported mcp.transport"):
        resolve_mcp_config(_Cfg({"mcp": {"transport": "sse"}}))


def test_mcp_config_rejects_non_loopback_host() -> None:
    with pytest.raises(McpConfigError, match="loopback"):
        resolve_mcp_config(_Cfg({"mcp": {"host": "0.0.0.0"}}))


def test_mcp_config_rejects_invalid_port() -> None:
    with pytest.raises(McpConfigError, match="mcp.port"):
        resolve_mcp_config(_Cfg({"mcp": {"port": 0}}))
    with pytest.raises(McpConfigError, match="mcp.port"):
        resolve_mcp_config(_Cfg({"mcp": {"port": "not-a-number"}}))


def test_mcp_config_block_ships_disabled_in_repo_config_json() -> None:
    """The committed config.json mcp block must match the design doc exactly."""
    config_path = _REPO_ROOT / "config.json"
    assert config_path.exists(), f"repo config.json not found at {config_path}"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config.get("mcp") == _DESIGN_MCP_BLOCK


def test_mcp_config_refuses_missing_agent() -> None:
    cfg = resolve_mcp_config(_Cfg({"mcp": {"enabled": True}}))
    with pytest.raises(McpConfigError, match="not found"):
        resolve_scope(_StubAgentManager(None), cfg)


def test_mcp_config_refuses_empty_allowlist() -> None:
    cfg = resolve_mcp_config(_Cfg({"mcp": {"enabled": True}}))
    for allowed in ([], None):
        with pytest.raises(McpConfigError, match="empty/missing allowed_tools"):
            resolve_scope(_StubAgentManager(_mcp_agent(allowed)), cfg)


def test_mcp_config_accepts_agent_with_allowlist() -> None:
    cfg = resolve_mcp_config(_Cfg({"mcp": {"enabled": True}}))
    agent = _mcp_agent(["alpha_tool"])
    resolved_agent, account_id = resolve_scope(_StubAgentManager(agent), cfg)
    assert resolved_agent is agent
    assert account_id == "junwin"


def test_mcp_config_refuses_zero_eligible_tools() -> None:
    """Eligibility intersection empty => startup refusal (nothing exposed)."""
    cfg = resolve_mcp_config(_Cfg({"mcp": {"enabled": True, "context_name": ""}}))
    agent = _mcp_agent(["alpha_tool"])
    registry = _registry_with(_BetaHandler)  # alpha_tool NOT registered
    with pytest.raises(McpConfigError, match="zero eligible tools"):
        resolve_startup_scope(_StubAgentManager(agent), registry, None, cfg)


def test_effective_context_name_config_wins_then_agent_default() -> None:
    agent = _mcp_agent(["alpha_tool"])
    agent.default_context = "skinny"
    cfg = resolve_mcp_config(
        _Cfg({"mcp": {"enabled": True, "context_name": "lucyproject"}})
    )
    assert effective_context_name(agent, cfg) == "lucyproject"
    cfg_no_context = resolve_mcp_config(_Cfg({"mcp": {"enabled": True}}))
    assert effective_context_name(agent, cfg_no_context) == "skinny"


# ---------------------------------------------------------------------------
# test_mcp_eligibility
# ---------------------------------------------------------------------------


def test_mcp_eligibility_tools_list_equals_eligible_defs() -> None:
    """tools/list content == eligible_tool_defs(mcp_agent, context)."""
    registry = _registry_with(_AlphaHandler, _BetaHandler, _GammaHandler)
    agent = _mcp_agent(["alpha_tool", "beta_tool"])

    mcp_tools = eligible_tools(registry, agent, None, "junwin", "")

    names = [tool["name"] for tool in mcp_tools]
    assert names == registry.eligible_tool_names(agent, None) == [
        "alpha_tool",
        "beta_tool",
    ]
    # Handlers excluded by agent.allowed_tools do not appear.
    assert "gamma_tool" not in names
    # Each tool is a lossless translation (name/description/inputSchema).
    for tool in mcp_tools:
        assert set(tool) == {"name", "description", "inputSchema"}
        assert isinstance(tool["inputSchema"], dict)


def test_mcp_eligibility_missing_allowlist_exposes_nothing() -> None:
    registry = _registry_with(_AlphaHandler, _BetaHandler)
    for allowed in (None, []):
        agent = _mcp_agent(allowed)
        assert eligible_tools(registry, agent, None, "junwin", "") == []
        assert registry.eligible_tool_defs(agent, None) == []


def test_mcp_eligibility_context_restriction_narrows_tools() -> None:
    """An explicit non-empty context allowed_tools list narrows the surface."""
    registry = _registry_with(_AlphaHandler, _BetaHandler, _GammaHandler)
    agent = _mcp_agent(["alpha_tool", "beta_tool", "gamma_tool"])
    prompt_builder = _FakePromptBuilder(
        _context_with_allowed_tools(["beta_tool"])
    )

    mcp_tools = eligible_tools(
        registry, agent, prompt_builder, "junwin", "lucyproject"
    )

    assert [tool["name"] for tool in mcp_tools] == ["beta_tool"]

    # Without an active context the full agent allowlist applies unchanged.
    no_context = eligible_tools(registry, agent, None, "junwin", "")
    assert sorted(t["name"] for t in no_context) == [
        "alpha_tool",
        "beta_tool",
        "gamma_tool",
    ]


# ---------------------------------------------------------------------------
# test_mcp_call_* (execution through the real ToolExecutor)
# ---------------------------------------------------------------------------


def _dispatch(
    registry: HandlerRegistry,
    agent: Agent,
    *,
    name: str,
    arguments: Dict[str, Any],
    config: Optional[_Cfg] = None,
) -> Dict[str, Any]:
    executor = _ToolExecutorStub(
        registry,
        config or _Cfg({"max_tool_result_chars": 100000}),
    )
    scope = _scope_for(agent, [name])
    return dispatch_tool_call(
        executor,
        scope=scope,
        name=name,
        arguments=arguments,
        call_id="call-1",
        correlation_id="corr-1",
        conversation_id="mcp-session-1",
    )


class _ToolExecutorStub:
    """Real ToolExecutor wrapper (same construction as ``serve()``)."""

    def __init__(self, registry: HandlerRegistry, config: _Cfg) -> None:
        from src.message_processors.fcp_tool_executor import ToolExecutor

        self._inner = ToolExecutor(
            registry=registry,
            config=config,
            prompt_builder=None,
            llm_adapter=_LlamaStub(),
            agent_manager=None,
            chat2_store=None,
        )

    def wrap_tool_calls(self, tool_calls: Any) -> Any:
        return self._inner.wrap_tool_calls(tool_calls)

    def execute_tool_calls(self, **kwargs: Any) -> Any:
        return self._inner.execute_tool_calls(**kwargs)


def test_mcp_call_argument_passing_reaches_execute_unchanged() -> None:
    _RecordingHandler.SEEN = []
    registry = _registry_with(_RecordingHandler)
    agent = _mcp_agent(["mcp_rec_tool"])

    arguments = {"q": "hello world", "n": 7, "nested": {"a": [1, 2]}}
    result = _dispatch(registry, agent, name="mcp_rec_tool", arguments=arguments)

    assert result["isError"] is False
    assert _RecordingHandler.SEEN == [
        {"args": arguments, "account_name": "junwin"}
    ]
    body = json.loads(result["content"][0]["text"])
    assert body["ok"] is True
    assert body["echo"] == arguments


def test_mcp_call_result_mapping_structured_result_to_text() -> None:
    registry = _registry_with(_RecordingHandler)
    agent = _mcp_agent(["mcp_rec_tool"])

    result = _dispatch(
        registry, agent, name="mcp_rec_tool", arguments={"q": "x"}
    )

    assert result["isError"] is False
    body = json.loads(result["content"][0]["text"])
    assert body["ok"] is True
    assert body["tool"] == "mcp_rec_tool"


def test_mcp_call_result_mapping_too_large_is_capped_error_text() -> None:
    """Too-large results surface as capped error text content (FCP parity).

    ToolExecutor converts ToolResultTooLargeError into a compact error-text
    result (the same recovery an /ask run sees), so the MCP client receives
    an error message as text content with ``isError`` False -- never a
    transport failure.
    """
    registry = _registry_with(_BigResultHandler)
    agent = _mcp_agent(["mcp_big_tool"])
    tiny_cap = _Cfg({"max_tool_result_chars": 80})

    result = _dispatch(
        registry,
        agent,
        name="mcp_big_tool",
        arguments={},
        config=tiny_cap,
    )

    assert result["isError"] is False
    text = result["content"][0]["text"]
    assert "too large" in text
    assert "80" in text  # the cap is reported


def test_mcp_call_error_mapping_handler_exception_is_iserror() -> None:
    registry = _registry_with(_BoomHandler)
    agent = _mcp_agent(["mcp_boom_tool"])

    result = _dispatch(registry, agent, name="mcp_boom_tool", arguments={})

    assert result["isError"] is True
    assert result["content"][0]["text"] == "ValueError: boom"


def test_mcp_call_error_mapping_unknown_tool_is_iserror() -> None:
    registry = _registry_with(_AlphaHandler)
    agent = _mcp_agent(["alpha_tool"])
    scope = _scope_for(agent, ["alpha_tool"])
    executor = _ToolExecutorStub(registry, _Cfg({"max_tool_result_chars": 1000}))

    result = dispatch_tool_call(
        executor,
        scope=scope,
        name="not_eligible_tool",
        arguments={},
        call_id="call-1",
        correlation_id="corr-1",
        conversation_id="mcp-session-1",
    )

    assert result["isError"] is True
    assert "Unknown tool 'not_eligible_tool'" in result["content"][0]["text"]


def test_mcp_call_error_mapping_unexpected_executor_error_is_iserror() -> None:
    agent = _mcp_agent(["alpha_tool"])
    scope = _scope_for(agent, ["alpha_tool"])

    result = dispatch_tool_call(
        _ExplodingExecutor(),
        scope=scope,
        name="alpha_tool",
        arguments={},
        call_id="call-1",
        correlation_id="corr-1",
        conversation_id="mcp-session-1",
    )

    assert result["isError"] is True
    assert result["content"][0]["text"] == "RuntimeError: kaboom"
