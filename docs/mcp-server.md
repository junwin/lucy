# Lucy MCP server façade (issue #157)

Design: [`docs/design/mcp-handlerregistry.md`](design/mcp-handlerregistry.md)
(approved 2026-09-04). Code: `src/mcp/server.py` (transport/lifecycle) and
`src/mcp/tool_adapter.py` (pure schema/result mapping).

## What it is

An optional, opt-in server process that exposes Lucy's existing
`HandlerRegistry` as Model Context Protocol (MCP) tools, so local MCP clients
(ChatGPT custom apps, Claude Desktop, custom tooling) can list and call
Lucy's tools.

Lucy remains the **single source of truth** for tool definitions,
permissions and execution. The MCP layer is a thin adapter only:

```text
MCP client
    |
    v
src/mcp/server.py        (streamable-HTTP transport, list/dispatch)
    |
    v
HandlerRegistry          (eligibility: registry ∩ agent.allowed_tools ∩ context list)
    |
    v
ToolExecutor (FCP)       (unchanged — handlers see the same context as an /ask run)
    |
    v
existing HandlerV2 implementations
```

No handler is rewritten for MCP, and no second permission system exists.

## Enable and start

1. Install the pinned dependency: `pip install -r requirements.txt`
   (the official MCP Python SDK, `mcp==2.1.1`, is the only new dependency).
2. In `config.json` the block ships **disabled** by default:

   ```json
   "mcp": {
     "enabled": false,
     "agent": "mcp",
     "account": "junwin",
     "context_name": "lucyproject",
     "transport": "streamable-http",
     "host": "127.0.0.1",
     "port": 8765
   }
   ```

   Set `enabled` to `true` to opt in. Scope (agent / account / context) is
   fixed at startup and cannot be changed by a client.
3. Start from the repo root (this honours `config.local.json`):

   ```bash
   .venv/bin/python -m src.mcp.server
   ```

   The server serves streamable HTTP at `http://127.0.0.1:8765/mcp`.

### Fail-closed startup (server refuses to start, exit code 2)

- `mcp.enabled` is missing or `false`;
- the configured agent does not exist in `static/data/agents.json`;
- the agent has a missing/empty `allowed_tools` list;
- the eligibility intersection resolves to zero tools (nothing to expose);
- the host is not loopback (`127.0.0.1` / `localhost` / `::1`);
- the transport is not `streamable-http`, or the port is invalid.

> Note: the default port `8765` can be occupied by unrelated local services
> (on the development Pi it is used by another app). Pick a free port via
> `mcp.port` in the config block.

## How exposed tools are controlled

The exposed set is exactly the registry's permission intersection for the
configured `mcp` agent and context:

```text
eligible = registry.eligible_tool_defs(mcp_agent, context_state)
         = registry ∩ agent.allowed_tools ∩ context.allowed_tools (non-empty only)
```

`tools/list` advertises one MCP tool per eligible handler def; `tools/call`
only dispatches names inside that startup-fixed set — anything else is an
`isError` result and is never passed to the registry (audit-logged as
`mcp_call_rejected`).

The initial `mcp` agent allowlist in `static/data/agents.json` is deliberately
conservative (deterministic, no nested LLM delegation, no state mutation):

```text
get_keywords, web_search_handler, scrape_web_page, file_load,
generate_svg, generate_image
```

Allowlist entries must match `HandlerV2.name()` exactly — WebSearchHandler2
registers as `web_search_handler`, not `web_search`. Widening or narrowing
the exposed surface is a config edit to that one agents.json entry; no code
change. Excluded for now (add later deliberately if ever needed):
`execute_command`, `sandbox_execute`, `remote_execute`, `file_save`,
`chat2_handler`, `curate_chat`, `tasklists_*`, `agents_manage`, and other
state-mutating / LLM-delegating tools.

### `file_load` note (issue #157 review)

`file_load` is kept in the initial set because its path rules were verified
tight under current Lucy resolution:

- read-only; returns file text only;
- no absolute paths, no drive letters, no `..` segments;
- `location='storage'` confines reads to `<storage_root_path>/<storage_namespace>`;
- `location='external'` requires a named root from `external_roots` in config;
- containment is enforced on `realpath` (symlink escapes blocked).

## Tool schema mapping (tool_def → MCP)

| OpenAI/Responses `tool_def()` field | MCP tool field |
|---|---|
| `name` | `name` |
| `description` | `description` |
| `parameters` (JSON Schema) | `inputSchema` (verbatim deep copy) |

The `parameters` block is already JSON Schema, so the translation is
structural, not semantic. Result/error mapping: a handler dict result is
returned as MCP text content with `isError: false` (including a returned
`{"ok": false, ...}` — that is a result, matching FCP semantics); handler
exceptions and executor failures become an `isError: true` text result,
never a transport failure.

## Security notes (v1)

- Loopback binding only — no WAN exposure, no TLS/auth in v1. Remote access
  is a separate design (reverse proxy + auth in front of the same server).
- The exposed surface equals the `mcp` agent's `allowed_tools` (plus any
  explicit context restriction) — review that one agents.json entry.
- Per-call audit logging reuses the existing conventions:
  `tool_execute_start` / `tool_execute_done` / `mcp_call_rejected` with a
  per-call `correlation_id`.
- No chat persistence: chat/curation/delegation tools are excluded and the
  `mcp` agent sets `save_responses: false`.

## Minimal Python MCP client example

```python
import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main() -> None:
    async with streamable_http_client("http://127.0.0.1:8765/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("tools:", ", ".join(sorted(t.name for t in tools.tools)))

            result = await session.call_tool(
                "file_load",
                {"location": "storage", "external_root": "", "path": "contexts/junwin/debo_work.md"},
            )
            print("isError:", result.is_error)
            print(result.content[0].text[:500])


asyncio.run(main())
```

## Tests

Pure/offline (no server process, no network):

- `tests/test_tool_adapter.py` — lossless mapping conformance over the real
  registry; duplicate names cannot surface.
- `tests/test_mcp_server.py` — config parse/defaults (incl. the committed
  block shipping `enabled: false`), fail-closed startup refusals, eligibility
  == `eligible_tool_defs`, context narrowing, argument passing, result/error
  mapping (`isError`).

Run: `.venv/bin/python -m pytest tests/test_mcp_server.py tests/test_tool_adapter.py`
