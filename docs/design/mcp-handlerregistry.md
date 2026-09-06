# MCP / ChatGPT façade over HandlerRegistry

## Status
Approved 2026-09-04 — reviewed on issue #157 (junwin). Linked to issue #157,
branch `experiment/mcp-handlerregistry`. Implementation tracked as a persisted
tasklist derived from the checklist on #157.


## Goal
Expose Lucy's existing `HandlerRegistry` as an MCP server so MCP clients (ChatGPT
app façade, Claude Desktop, custom tools) can list and call Lucy's tools.

Lucy remains the single source of truth for tool definitions, permissions and
execution. The MCP layer is a thin adapter only: it must never redefine a tool,
never bypass the permission model, and never require handler changes.

## Background / why this shape
Issue #157 asked for a review comment answering five questions, then a design.
The review comment (on #157) recorded the code-level findings. This doc turns
those findings into decisions and a concrete plan.

Key code facts the design relies on (verified on `develop`):

- `HandlerRegistry` (`src/handlers/handler_registry.py`)
  - `register(cls)` — raises `ValueError` on duplicate names (duplicates are
    impossible by construction).
  - `create(name, *, config)` — instantiates a `HandlerV2`.
  - `tools()` / `tool_names()` — registry-wide defs.
  - `eligible_tool_defs(agent, context_state)` — the permission ceiling:
    registry ∩ `agent.allowed_tools` ∩ context `allowed_tools` (only when the
    context list is non-empty). Fail-closed: `allowed_tools` missing/`None`/`[]`
    ⇒ no tools.
  - `result_schema(name)` / `all_result_schemas()` — optional result schemas,
    cached at registration.
- `HandlerV2` contract (`src/handlers/handler_v2.py`)
  - classmethods `name()` and `tool_def()` (OpenAI/Responses format:
    `{"type": "function", "function": {"name", "description", "parameters"}}`).
  - `execute(args, *, account_name="auto", **context)` returns a structured
    dict; some handlers additionally accept `execute_raw(arguments_raw,
    account_name=..., call_id=..., **context)`.
  - `result_schema()` optional classmethod.
  - All ~23 handlers produce uniform Responses-API style `tool_def()`s — no
    format drift observed.
- Execution engine (`src/message_processors/fcp_tool_executor.py`)
  - `ToolExecutor` already does everything an MCP call needs: builds the shared
    `handler_context` dict (`primary_agent`, `secondary_agent`, `processor_factory`,
    `account`, `conversation_id`, `correlation_id`, `context_name`, `context_state`,
    `agent_name`, `storage`, `registry`, `prompt_builder`, `config`, `chat2_store`,
    `llm_adapter`, `agent_manager`), loads the context state exactly like the FCP,
    handles unknown tools, result-to-text serialisation, `max_tool_result_chars`
    caps, and error mapping.
  - `ProcessorContext.from_agent(primary_agent, account, conversation_id,
    context_name)` (in `fcp_models.py`) resolves `account_id`, `agent_name` and
    the context-name fallback to `agent.default_context`.
- DI (`src/container_config.py`) provides singletons the executor needs:
  `ConfigManager`, `AgentManager`, `Storage`/`ContextStore`, `Chat2Store`,
  `HandlerRegistry`, `PromptBuilder`, `LLMAdapter`, `ProcessorFactory`.
- `static/data/agents.json` currently has no `mcp` agent (agents: lucy, doris,
  colin, nelly, glinda, dorothy, peace, debo, star, belle, lamy, ziggy).
- `Agent` dataclass has no mandatory/required-tool fields; eligibility is
  `allowed_tools` only (plus optional context list).

## Decisions (answers to the five review questions)

### 1. Integration boundary: `HandlerRegistry` — yes
The registry already owns the two capabilities MCP needs:
- `eligible_tool_defs(agent, context_state)` for `tools/list`, and
- `create(name, config)` + handler `execute(...)` for `tools/call`.

No new boundary, no registry fork, no bypass. The MCP server composes existing
registry + executor pieces only.

### 2. Schema: keep `tool_def()` as the single source; translate, don't duplicate
No canonical internal schema refactor. All handlers already emit one uniform
OpenAI/Responses style; a second canonical schema would touch every handler with
zero current benefit. Instead, `tool_adapter.py` mechanically translates:

| OpenAI / Responses def | MCP tool |
|---|---|
| `function.name` | `name` |
| `function.description` | `description` |
| `function.parameters` (JSON Schema object) | `inputSchema` |

The parameters block is already JSON Schema, so the translation is structural,
not semantic. A conformance test iterates every registered handler def and
asserts the MCP translation is lossless (see Tests). If a genuine second
consumer format appears later, revisit the canonical-schema idea then.

### 3. Runtime context: reuse the FCP's executor, don't re-invent
`account_name` alone is not enough — several handlers read `primary_agent`,
`account`, `conversation_id`, `context_state`, `agent_manager`, etc. from the
`handler_context` dict that `ToolExecutor` builds. So:

- The MCP server uses `ToolExecutor.execute_tool_calls(...)` as its execution
  engine, unchanged. Every handler call therefore sees byte-identical context to
  an FCP call.
- Scope is **server-level and fixed at startup**: configured account + dedicated
  `mcp` agent (+ optional default context name). MCP has no notion of Lucy
  accounts, so a client cannot select an arbitrary account/session.
- `ProcessorContext` is built via `ProcessorContext.from_agent(...)` with:
  - `primary_agent` = the configured `mcp` agent,
  - `account` = `{"accountId": <configured account>}`,
  - `context_name` = configured default context (falls back to
    `agent.default_context` when absent),
  - `conversation_id` = derived from the MCP session id (or a per-server uuid on
    transports without sessions) so conversation-scoped tools remain coherent.
- `processor_factory` = `None` initially. Tools that require nested LLM
  delegation (tasklists_run-style flows) are excluded from the `mcp` agent's
  allowlist rather than half-supported.
- Correlation: one `correlation_id` per `tools/call`, logged with the same
  start/done lines as FCP tool execution.

### 4. Permissions: `allowed_tools` is sufficient — as a dedicated, restricted agent
The fail-closed intersection already answers "what is externally reachable":
exactly `eligible_tool_defs(mcp_agent, context_state)`. Operators control the
attack surface by editing one agents.json entry — no code change to add/remove
tools.

- New agent `mcp` in `static/data/agents.json` with an explicit, curated
  `allowed_tools` list. Start conservative (see Config/agent draft below);
  extend deliberately later.
- No context intersection trickery: the server uses the agent's default context;
  `context_state` loads through the same path as the FCP.
- Per-call audit logging (correlation id, tool, account, result preview) reuses
  the existing logger conventions.

### 5. Smallest implementation
Two new files + config + one agent entry. `app.py` and the Flask app untouched;
no handler rewrites; the only new dependency is the official MCP Python SDK.

- `src/mcp/tool_adapter.py` — pure, no I/O:
  - `handler_tool_def_to_mcp(tool_def) -> dict` (mapping in decision 2),
  - `call_tool(registry, name, arguments: dict, ctx, executor_deps) -> text/error`
    or equivalently thin helpers wrapping `ToolExecutor`,
  - result/error mapping (`isError` semantics).
- `src/mcp/server.py` — entry point `python -m src.mcp.server`:
  - builds the DI container (`container_config.configure_container()`),
  - resolves the configured agent/account/deps, registers one MCP tool per
    eligible def (translated), executes through `ToolExecutor`,
  - serves streamable-HTTP on `127.0.0.1` (no WAN exposure).

## Components (SOLID)

| Component | Responsibility |
|---|---|
| `tool_adapter.py` | Pure translation OpenAI def → MCP tool; argument/result/error mapping. Single reason to change: mapping rules. |
| `server.py` | Transport + lifecycle only: resolve scope, list tools from registry, dispatch calls to `ToolExecutor`. |
| `HandlerRegistry` (existing) | Eligibility and handler construction — unchanged. |
| `ToolExecutor` (existing) | Shared execution context + result safety — unchanged, reused. |
| `container_config.py` (existing) | Wiring — unchanged; server consumes it. |

No new abstraction layer is invented; composition over duplication.

## Config

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

- `enabled: false` default — opt-in only, and the branch keeps it off until the
  smoke test passes. The block ships in `config.json` (2026-09-04) with
  `enabled: false`; the `mcp` agent entry is in `static/data/agents.json`.
- `agent` / `account` fix the scope; the server refuses to start if the agent is
  missing or has no `allowed_tools`.

### Agent draft (`static/data/agents.json`)
New entry, deliberately small initial allowlist — deterministic, no nested
delegation, no chat-mutation tools first:

```
mcp: allowed_tools = [
  "get_keywords",
  "web_search_handler",
  "scrape_web_page",
  "file_load",
  "generate_svg",
  "generate_image"
]
```

Implementation note (2026-09-04): `allowed_tools` entries must match `HandlerV2.name()`
exactly; WebSearchHandler2 registers as `web_search_handler`, not `web_search`, so the
agents.json entry uses the real name (`web_search` would be a silent no-op).

file_load verification (2026-09-04): **kept** in the allowlist. Code review plus
live probes under the current Lucy path-resolution rules (merged config on the Pi:
storage base = `storage_root_path`/`storage_namespace` = `/home/junwin/lucy_storage/data`;
external base = the configured `external_roots` map keys only). Enforced and verified:
relative paths only (absolute paths and drive-letter paths rejected); `..` segments
rejected after normpath (any surviving `..` -> error, so in-base collapses like
`data/../contexts/...` stay in-base while `../../etc` is refused); `location` enum
`storage`/`external` only; `external_root` must be an allow-listed config key (empty or
unknown -> error); realpath containment rejects symlink escapes (probe: in-root symlink
to `/etc/hostname` -> "File access outside allowed base path"); open is read-only
(`"r"`). Exposure is therefore bounded to the operator-configured named roots, plus the
loopback-only + `enabled:false` defaults in the Config section. No drop needed, so no
change to the allowlist on #157.

Selection is a proposal for review, not a code constraint: eligibility comes from
`allowed_tools`, so widening later is a config edit. Excluded for now:
`execute_command`, `sandbox_execute`, `remote_execute`, `file_save`,
`chat2`, `curate_chat`, `tasklists_*`, `agents_manage` — anything that mutates
state or delegates to an LLM.

## Non-goals
- No handler rewrites or new `HandlerV2` methods.
- No registry bypass, no second permission system, no message queue.
- No canonical internal tool schema (defer unless a real second format appears).
- No WAN exposure / auth system: loopback binding only; remote access later is a
  separate design (reverse proxy + auth in front of the same server).
- No UI, no changes to FCP/Flask/app.py.
- No live OpenAI/MCP-network dependency in tests.

## Risks
- **New dependency (`mcp` SDK + its HTTP extras)**: pin versions; the adapter is
  pure Python dicts, so SDK churn stays in `server.py`.
- **Tools outside the `/ask` flow**: no chat persistence for MCP sessions —
  handled by excluding chat/curation/delegation tools initially and deriving a
  stable per-session `conversation_id` before ever enabling them.
- **Surface creep**: the exposed set is exactly the `mcp` agent's
  `allowed_tools`; keep the allowlist reviewable in the agents.json entry.
- **Schema drift**: a conformance test over the full registry fails CI if a new
  handler def no longer translates losslessly.

## Tests
All pure/offline; no live connection.

| Test | What it proves |
|---|---|
| `test_tool_adapter_mapping` | Every registered handler `tool_def()` translates to a valid MCP tool with identical name/description/parameters (lossless). |
| `test_tool_adapter_duplicate_defs` | Duplicate names cannot surface (registry `register` raises); adapter is idempotent over the registry list. |
| `test_mcp_eligibility` | `tools/list` content == `eligible_tool_defs(mcp_agent, context)`; missing/empty `allowed_tools` ⇒ empty list. |
| `test_mcp_call_argument_passing` | Arguments dict reaches a fake handler's `execute()` unchanged. |
| `test_mcp_call_result_mapping` | Handler dict result → MCP text content; too-large result → capped error text content (`isError` False — `ToolExecutor` converts `ToolResultTooLargeError` into an error-text result, FCP parity; only execution failures map to `isError`, see `tool_adapter`). |
| `test_mcp_call_error_mapping` | Handler exception → MCP `isError` result, not a transport failure. |
| `test_mcp_config` | Config block parse; missing agent / empty allowlist ⇒ startup refusal. |

## Docs
Short section (Obsidian or `docs/`): enable steps (set `mcp.enabled`, start
server), the mapping table above, security note (loopback only, exposed set ==
agent allowlist, audit log), and a minimal Python MCP client example (connect,
`tools/list`, `tools/call`).

## Implementation order (tasklist after this doc is reviewed)
1. `tool_adapter.py` + mapping tests (pure, no server).
2. `server.py` using `ToolExecutor`; config block + `mcp` agent entry.
3. Smoke test: start server locally, list tools, call one safe tool.
4. Docs + final review; commit on a feature branch from `develop` and open a PR
   back to `develop` (no merge), with permission.


## Smoke test record (2026-09-04, issue #157 checklist item 7)

Test suite (repo root, branch `experiment/mcp-handlerregistry`, worktree state --
nothing committed yet):

- `.venv/bin/python -m pytest tests/test_mcp_server.py tests/test_tool_adapter.py -v`
  -> **22 passed** (20 `test_mcp_*` + 2 `test_tool_adapter_*`).
- Full suite `.venv/bin/python -m pytest tests -q` -> **exit 0, no failures/errors**.

Manual local smoke test (real server + official MCP SDK 2.1.1 client over streamable HTTP):

- The shipped config block stays `enabled: false`; the run opted in via a
  throwaway `mcp` override in the untracked `config.local.json` (deep-merged by
  `ConfigManager`), removed again immediately after the run.
- Port: the default `8765` is occupied on the dev Pi by an unrelated uvicorn (as
  the Config notes warn), so the override bound `127.0.0.1:8877`.
- Start: `.venv/bin/python -m src.mcp.server` logged
  `mcp_server_start agent=mcp account=junwin context=lucyproject tools=6
  transport=streamable-http bind=127.0.0.1:8877`, one `mcp_server_tool` line per
  exposed tool (file_load, generate_image, generate_svg, get_keywords,
  scrape_web_page, web_search_handler), then
  `mcp_server_serving url=http://127.0.0.1:8877/mcp agent=mcp`.
- Client: initialize OK (server `lucy` v0.1.0); `tools/list` returned exactly 6
  tools == the `mcp` agent's `allowed_tools` (no context narrowing: the
  lucyproject context file carries no `allowed_tools`).
- `tools/call` of one safe tool: `file_load` with `{"location": "storage",
  "external_root": "", "path": "contexts/junwin/skinny.md"}` ->
  `isError=false`, one text content block (552 chars), result begins
  `{"ok": true, "tool": "file_load", ...}`.
- Per-call audit lines observed (FCP conventions, correlation id per call):
  `tool_execute_start correlation_id=321eaa13-9fd6-4fba-b03a-62239d48bef8
  tool=file_load call_id=3 account=junwin` and the matching `tool_execute_done`
  line with the result preview.
- Server stopped after the run; the `config.local.json` override was removed;
  `config.json` still ships `enabled: false`; no process left listening.

No server-side defects found. (Two early client attempts hit snake_case attribute
names in the throwaway script itself -- `server_info` vs `serverInfo`,
`input_schema` vs `inputSchema` -- fixed in the script; no source change needed.)
Implementation order step 3 and issue checklist item 7 are therefore complete;
step 4 (docs + final review, then the normal git workflow with permission) remains.

## Review checklist
- [x] Registry-as-boundary decision accepted (Q1)
- [x] Single-source `tool_def()` + translator accepted, no canonical schema (Q2)
- [x] Scope model accepted: fixed account/agent/context, session-derived
      conversation_id, reuse `ToolExecutor` (Q3)
- [x] Dedicated `mcp` agent + fail-closed allowlist accepted (Q4)
- [x] Two-file + config scope accepted as smallest implementation (Q5)
- [x] Initial `mcp` agent allowlist agreed — conditional on `file_load`
      path/root restrictions being verified tight under current Lucy
      path-resolution rules (see #157 review)
- [x] `mcp` SDK dependency approved
- [x] Test list agreed
