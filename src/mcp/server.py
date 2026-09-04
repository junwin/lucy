# src/mcp/server.py
"""MCP streamable-HTTP server facade over Lucy's HandlerRegistry (design doc).

Entry point: ``python -m src.mcp.server`` (run from the repo root, same as
``app.py``; config.local.json is honoured via ``ConfigManager``).

Role (design doc ``docs/design/mcp-handlerregistry.md``, Decision 5 and the
Component table): transport + lifecycle only. Everything else is reused, not
re-invented (Decision 3):

- DI container: ``container_config.configure_container()`` (unchanged wiring).
- Scope: the configured ``mcp`` agent + account + default context, resolved at
  startup and fixed for the server process.
- Exposed tool set: ``HandlerRegistry.eligible_tool_defs(agent, context_state)``
  -- the registry / agent ``allowed_tools`` / context ``allowed_tools``
  intersection (fail-closed) -- translated by
  ``tool_adapter.handler_tool_def_to_mcp`` into one MCP tool per eligible def.
  ``inputSchema`` is the handler's own JSON-Schema parameters verbatim.
- Execution: the FCP's ``ToolExecutor.execute_tool_calls(...)`` unchanged, so
  every handler call sees the byte-identical ``handler_context`` to an /ask
  run (Decision 3). ``processor_factory`` is None (no nested LLM delegation).
- Result/error mapping: ``tool_adapter.success_result`` / ``error_result``
  (``isError`` semantics); a handler exception becomes an MCP ``isError``
  result, never a transport failure.

Fail-closed startup guarantees (Decision 4 / Config section):

- refuses to serve unless ``mcp.enabled`` is true (opt-in; the config block
  added in a later task ships with ``enabled: false``),
- the configured agent must exist in agents.json with a non-empty
  ``allowed_tools`` list, and the eligibility intersection must not be empty
  (nothing exposed => nothing to serve),
- loopback binding only: hosts other than 127.0.0.1/localhost/::1 are refused
  (no WAN exposure / auth is a separate design),
- ``tools/call`` only dispatches tool names inside the startup-fixed eligible
  set (what ``tools/list`` advertises is exactly what may be called).

Transport / SDK notes:

- Serves MCP **streamable HTTP** on ``127.0.0.1:8765`` by default (the MCP
  SDK's ``/mcp`` endpoint).
- Written against the official MCP Python SDK **2.x low-level API**
  (``mcp.server.lowlevel.Server`` with ``on_list_tools`` / ``on_call_tool`` +
  ``streamable_http_app()``; verified against mcp 2.1.1). SDK churn is
  confined to this module by design (design doc Risks); if a different SDK
  major/API is pinned, only the SDK section inside ``serve()`` needs changes.
- The SDK import is deferred to ``serve()`` so that importing this module --
  and unit-testing the pure helpers below -- never requires the SDK to be
  installed (design doc Tests are pure/offline).

Conversation id (Decision 3): one stable ``conversation_id`` per MCP session
where the transport exposes its session id (best effort via the HTTP
``mcp-session-id`` header), otherwise a stable per-server uuid. One
``correlation_id`` is minted per ``tools/call`` and logged with the same
start/done lines as FCP tool execution (``ToolExecutor`` emits them).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.agent.agent import Agent
from src.agent.agent_manager import AgentManager
from src.config_manager import ConfigManager
from src.handlers.handler_registry import HandlerRegistry
from src.message_processors.fcp_models import ProcessorContext, ToolHandlerError
from src.message_processors.fcp_tool_executor import ToolExecutor, load_context_state
from src.mcp.tool_adapter import error_result, handler_tool_def_to_mcp, success_result

logger = logging.getLogger(__name__)

#: MCP server identity reported to clients.
SERVER_NAME = "lucy"
SERVER_VERSION = "0.1.0"

#: Config key holding the optional ``mcp`` block (design doc Config section).
MCP_CONFIG_KEY = "mcp"

#: Defaults per the design doc Config section. ``context_name`` intentionally
#: defaults to "" so an absent context falls back to the agent's
#: ``default_context`` (Decision 3), exactly like ``ProcessorContext.from_agent``.
DEFAULT_AGENT_NAME = "mcp"
DEFAULT_ACCOUNT_ID = "junwin"
DEFAULT_TRANSPORT = "streamable-http"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

#: Only loopback binds are allowed (design doc Non-goals: no WAN exposure).
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

#: The only transport this server implements.
_SUPPORTED_TRANSPORTS = frozenset({"streamable-http"})


class McpConfigError(Exception):
    """Raised when the MCP server cannot start from the current configuration.

    Startup is fail-closed: every raised instance means "refuse to serve" with
    an actionable message (design doc Config: missing agent / empty allowlist
    => startup refusal).
    """


@dataclass(frozen=True)
class McpScope:
    """Startup-fixed server scope (Decision 3: server-level, fixed at startup).

    ``eligible_names`` is the snapshot of what ``tools/list`` advertises and
    ``tools/call`` may dispatch: the registry / agent-allowlist / context
    intersection derived from ``eligible_tool_defs`` at startup.
    """

    agent: Agent
    account_id: str
    context_name: str
    eligible_names: frozenset  # of str


def _as_bool(value: Any, default: bool = False) -> bool:
    """Coerce a config boolean the same tolerant way Agent fields are coerced."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _as_text(value: Any, default: str) -> str:
    """Return a stripped string; empty/None falls back to ``default``."""
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def resolve_mcp_config(config_manager: Any) -> Dict[str, Any]:
    """Parse and validate the ``mcp`` config block (design doc Config section).

    Returns a normalized dict with keys: enabled, agent, account, context_name,
    transport, host, port. Missing/empty keys fall back to the design defaults.
    Malformed values (unsupported transport, non-loopback host, invalid port)
    raise ``McpConfigError`` -- configuration errors fail fast even before the
    ``enabled`` gate, so a typo is never silently served.
    """
    raw = config_manager.get(MCP_CONFIG_KEY) or {}
    if not isinstance(raw, dict):
        raise McpConfigError(
            f"config key {MCP_CONFIG_KEY!r} must be an object, got "
            f"{type(raw).__name__}"
        )

    transport = _as_text(raw.get("transport"), DEFAULT_TRANSPORT).lower()
    if transport not in _SUPPORTED_TRANSPORTS:
        raise McpConfigError(
            f"unsupported mcp.transport {transport!r}; supported transports: "
            f"{sorted(_SUPPORTED_TRANSPORTS)}"
        )

    host = _as_text(raw.get("host"), DEFAULT_HOST).lower()
    if host not in _ALLOWED_HOSTS:
        raise McpConfigError(
            f"mcp.host {host!r} is not loopback; this server binds loopback "
            f"only (127.0.0.1/localhost/::1). Remote access needs a separate "
            f"design (reverse proxy + auth)."
        )

    try:
        port = int(raw.get("port", DEFAULT_PORT))
    except (TypeError, ValueError):
        raise McpConfigError(f"mcp.port must be an integer, got {raw.get('port')!r}")
    if not 1 <= port <= 65535:
        raise McpConfigError(f"mcp.port must be in 1..65535, got {port}")

    return {
        "enabled": _as_bool(raw.get("enabled"), False),
        "agent": _as_text(raw.get("agent"), DEFAULT_AGENT_NAME),
        "account": _as_text(raw.get("account"), DEFAULT_ACCOUNT_ID),
        "context_name": _as_text(raw.get("context_name"), ""),
        "transport": transport,
        "host": host,
        "port": port,
    }


def resolve_scope(agent_manager: AgentManager, cfg: Dict[str, Any]) -> Tuple[Agent, str]:
    """Resolve and validate the configured agent/account against agents.json.

    Refuses to start (raises ``McpConfigError``) when the configured agent is
    missing or carries an empty/missing ``allowed_tools`` (fail closed,
    Decision 4). Returns ``(agent, account_id)``.
    """
    agent_name = cfg["agent"]
    agent = agent_manager.get_agent(agent_name)
    if agent is None:
        raise McpConfigError(
            f"configured mcp agent {agent_name!r} not found in agents.json. "
            f"Add an {agent_name!r} entry with an explicit allowed_tools list "
            f"(design doc Config / agent draft)."
        )
    if not getattr(agent, "allowed_tools", None):
        raise McpConfigError(
            f"mcp agent {agent_name!r} has an empty/missing allowed_tools list; "
            f"refusing to start (fail closed, design doc Decision 4)."
        )
    return agent, cfg["account"]


def effective_context_name(agent: Agent, cfg: Dict[str, Any]) -> str:
    """Resolve the context name: configured value, else the agent default.

    Mirrors ``ProcessorContext.from_agent``: an empty result means "no active
    context tool restriction applies".
    """
    context_name = _as_text(cfg.get("context_name"), "")
    if not context_name and getattr(agent, "default_context", None):
        context_name = str(agent.default_context).strip()
    return context_name


def eligible_tools(
    registry: HandlerRegistry,
    agent: Agent,
    prompt_builder: Any,
    account_id: str,
    context_name: str,
) -> List[Dict[str, Any]]:
    """MCP tools for ``tools/list``: one translated tool per eligible def.

    Eligibility is ``registry.eligible_tool_defs(agent, context_state)`` with
    ``context_state`` loaded through the same FCP path
    (``fcp_tool_executor.load_context_state``), so the exposed set matches an
    /ask run for the same agent/account/context (Decision 4).
    """
    context_state = None
    if prompt_builder is not None:
        context_state = load_context_state(prompt_builder, account_id, context_name)
    tool_defs = registry.eligible_tool_defs(agent, context_state)
    return [handler_tool_def_to_mcp(tool_def) for tool_def in tool_defs]


def resolve_startup_scope(
    agent_manager: AgentManager,
    registry: HandlerRegistry,
    prompt_builder: Any,
    cfg: Dict[str, Any],
) -> Tuple[McpScope, List[Dict[str, Any]]]:
    """Resolve the startup scope: agent/account/context plus eligible tools.

    This is the fail-closed startup gate (design doc Decision 4 / Config
    section): raises ``McpConfigError`` when the configured agent is missing,
    has an empty/missing ``allowed_tools``, or resolves to zero eligible
    tools for the account/context (nothing exposed => nothing to serve).

    Returns ``(scope, mcp_tools)`` where ``mcp_tools`` is the translated
    snapshot ``tools/list`` advertises (one MCP tool per eligible def).
    """
    agent, account_id = resolve_scope(agent_manager, cfg)
    context_name = effective_context_name(agent, cfg)
    mcp_tools = eligible_tools(
        registry, agent, prompt_builder, account_id, context_name
    )
    if not mcp_tools:
        raise McpConfigError(
            f"mcp agent {agent.name!r} resolves to zero eligible tools for "
            f"account {account_id!r} context {context_name!r}; refusing to "
            f"start (nothing exposed)."
        )
    scope = McpScope(
        agent=agent,
        account_id=account_id,
        context_name=context_name,
        eligible_names=frozenset(tool["name"] for tool in mcp_tools),
    )
    return scope, mcp_tools


def dispatch_tool_call(
    executor: ToolExecutor,
    *,
    scope: McpScope,
    name: str,
    arguments: Dict[str, Any],
    call_id: str,
    correlation_id: str,
    conversation_id: str,
) -> Dict[str, Any]:
    """Dispatch one MCP ``tools/call`` through the FCP's ``ToolExecutor``.

    Returns an MCP ``CallToolResult``-shaped dict produced by
    ``tool_adapter`` (``success_result`` / ``error_result``), so callers never
    see transport-level failures for handler errors (design doc isError
    semantics).

    The tool name must be in the startup-fixed eligible set -- the advertised
    set is exactly the callable set (fail closed). Anything else is an
    ``isError`` result, never a registry/handler lookup.
    """
    if name not in scope.eligible_names:
        valid = ", ".join(sorted(scope.eligible_names))
        logging.error(
            "mcp_call_rejected correlation_id=%s tool=%r agent=%s valid_tools=%s",
            correlation_id,
            name,
            scope.agent.name,
            valid,
        )
        return error_result(f"Unknown tool '{name}'. Valid tools: {valid}")

    account = {"accountId": scope.account_id}
    ctx = ProcessorContext.from_agent(
        primary_agent=scope.agent,
        account=account,
        conversation_id=conversation_id,
        context_name=scope.context_name,
    )
    metrics: Dict[str, Any] = {"tool_calls": 0, "failures": 0}
    tool_calls = executor.wrap_tool_calls(
        [
            {
                "name": name,
                "id": call_id,
                "arguments": json.dumps(arguments or {}, ensure_ascii=False),
            }
        ]
    )

    try:
        # secondary_agent/processor_factory are None: the mcp agent's allowlist
        # excludes delegation tools (Decision 3), so nothing nested is needed.
        _, raw_results = executor.execute_tool_calls(
            tool_calls=tool_calls,
            primary_agent=scope.agent,
            secondary_agent=None,
            processor_factory=None,
            account=account,
            ctx=ctx,
            metrics=metrics,
            correlation_id=correlation_id,
        )
    except ToolHandlerError as exc:
        logging.error(
            "mcp_call_failed correlation_id=%s tool=%s error=%s",
            correlation_id,
            name,
            exc,
        )
        return error_result(str(exc))
    except Exception as exc:  # defensive: a handler error is an isError result
        logging.exception(
            "mcp_call_unexpected_error correlation_id=%s tool=%s", correlation_id, name
        )
        return error_result(f"{type(exc).__name__}: {exc}")

    if not raw_results:
        return error_result(f"Tool '{name}' produced no result.")
    return success_result(raw_results[0][1])


def _resolve_conversation_id(ctx: Any, fallback: str) -> str:
    """Per-session conversation id when the transport exposes its session id.

    Streamable HTTP sessions are identified by the ``mcp-session-id`` header;
    when the SDK request context carries the underlying HTTP request we reuse
    it so conversation-scoped tools stay coherent within one MCP session.
    Otherwise (transports without sessions) fall back to the per-server uuid
    (Decision 3). Best effort: any failure falls back silently.
    """
    try:
        request = getattr(ctx, "request", None)
        headers = getattr(request, "headers", None)
        if headers is not None and hasattr(headers, "get"):
            session_id = headers.get("mcp-session-id")
            if session_id:
                return f"mcp-{session_id}"
    except Exception:
        pass
    return fallback


def serve() -> None:
    """Resolve scope from the DI container and serve streamable HTTP.

    Blocking: runs until the server is stopped. Raises ``McpConfigError``
    (fail-closed startup refusal) instead of binding when configuration or
    scope is invalid.
    """
    from src import container_config  # heavy DI build; serve-time only

    config_manager = container_config.config  # ConfigManager("config.json")
    cfg = resolve_mcp_config(config_manager)
    if not cfg["enabled"]:
        raise McpConfigError(
            'refusing to start: "mcp.enabled" is false/missing. Opt in by '
            f'setting {MCP_CONFIG_KEY!r} block "enabled": true in config.json.'
        )

    container = container_config.configure_container()
    agent_manager = container.get(container_config.AgentManager)
    registry = container.get(container_config.HandlerRegistry)
    prompt_builder = container.get(container_config.PromptBuilderInterface)
    llm_adapter = container.get(container_config.LLMAdapter)
    chat2_store = container.get(container_config.Chat2Store)

    scope, mcp_tools = resolve_startup_scope(
        agent_manager, registry, prompt_builder, cfg
    )
    agent = scope.agent
    account_id = scope.account_id
    context_name = scope.context_name
    executor = ToolExecutor(
        registry=registry,
        config=config_manager,
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
        agent_manager=agent_manager,
        chat2_store=chat2_store,
    )


    logging.info(
        "mcp_server_start agent=%s account=%s context=%s tools=%d transport=%s "
        "bind=%s:%d",
        agent.name,
        account_id,
        context_name or agent.default_context or "-",
        len(scope.eligible_names),
        cfg["transport"],
        cfg["host"],
        cfg["port"],
    )
    for tool in sorted(mcp_tools, key=lambda t: t["name"]):
        logging.info("mcp_server_tool name=%s", tool["name"])

    # -- SDK section (design doc risk: SDK churn stays in server.py) ----------
    try:
        from mcp.server.lowlevel import Server

        import mcp.types as mcp_types

        import uvicorn  # HTTP server; mcp SDK dependency
    except ImportError as exc:  # pragma: no cover - depends on the runtime env
        raise McpConfigError(
            "the official MCP Python SDK (mcp 2.x with its HTTP extras) is not "
            "installed. Install the pinned mcp dependency before enabling the "
            "mcp server."
        ) from exc

    # One stable conversation_id per server process when the transport exposes
    # no session id (Decision 3); see _resolve_conversation_id for the
    # per-session upgrade path.
    conversation_base = f"mcp-{uuid.uuid4().hex}"

    async def _handle_list_tools(ctx: Any, params: Any) -> Any:
        return mcp_types.ListToolsResult(
            tools=[
                mcp_types.Tool(
                    name=tool["name"],
                    description=tool["description"],
                    inputSchema=tool["inputSchema"],
                )
                for tool in mcp_tools
            ]
        )

    async def _handle_call_tool(ctx: Any, params: Any) -> Any:
        correlation_id = str(uuid.uuid4())
        request_id = getattr(ctx, "request_id", None)
        call_id = str(request_id) if request_id is not None else correlation_id
        conversation_id = _resolve_conversation_id(ctx, fallback=conversation_base)
        result = await asyncio.to_thread(
            dispatch_tool_call,
            executor,
            scope=scope,
            name=params.name,
            arguments=dict(params.arguments or {}),
            call_id=call_id,
            correlation_id=correlation_id,
            conversation_id=conversation_id,
        )
        return mcp_types.CallToolResult(
            content=[mcp_types.TextContent(text=result["content"][0]["text"])],
            isError=result["isError"],
        )

    sdk_server = Server(
        SERVER_NAME,
        version=SERVER_VERSION,
        instructions=(
            "Lucy MCP facade: exposes the configured agent's eligible "
            "HandlerRegistry tools. Scope is fixed at startup (agent/account/"
            "context); loopback only; exposed set == agent allowlist."
        ),
        on_list_tools=_handle_list_tools,
        on_call_tool=_handle_call_tool,
    )
    app = sdk_server.streamable_http_app()

    logging.info(
        "mcp_server_serving url=http://%s:%d/mcp agent=%s",
        cfg["host"],
        cfg["port"],
        agent.name,
    )
    uvicorn.run(app, host=cfg["host"], port=cfg["port"], log_level="info")


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for ``python -m src.mcp.server``."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        serve()
    except McpConfigError as exc:
        print(f"mcp server: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
