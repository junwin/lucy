# Remote Agent Delegation — Design Doc

**Status:** Draft
**Date:** 2026-07-30
**Author:** Peace

---

## 1. Overview

Allow one Lucy instance to delegate work to another Lucy instance over HTTP.
This turns `POST /ask` into a remote-callable agent endpoint, enabling
multi-instance setups where agents on different machines can cooperate.

### Motivating example

- NUC runs heavy LLM models (gpt-4o, claude-sonnet)
- Pi 5 runs lightweight models (gpt-4o-mini) + long-running tasks
- Pi 5 Lucy wants to offload a complex reasoning task to the NUC Lucy
- NUC Lucy responds with the answer — Pi 5 Lucy surfaces it to the user

---

## 2. Scope

| In scope | Out of scope |
|---|---|
| Fire-and-forget ask → remote → get text back | Streaming (SSE) across instances |
| Single-hop delegation | Multi-hop / chain delegation |
| Static peer list in config | Dynamic discovery / service mesh |
| API key auth | OAuth / mutual TLS |
| New `delegate_to_remote` handler | Modifying existing handlers |

---

## 3. API Design

### Peer Lucy exposes one endpoint we already have

```
POST /ask
Content-Type: application/json

{
  "agentName": "lucy",
  "accountName": "junwin",
  "query": "Summarize this document...",
  "sessionId": null
}
```

Returns the same response as a local `/ask` call — the full text reply.

### Key difference from user-facing /ask

- Caller is another Lucy, not a human
- Session is optional (stateless delegation)
- Response is plain text (no SSE streaming in v1)

---

## 4. Handler Design

### New handler: `delegate_to_remote`

**Signature (conceptual):**
```python
def delegate_to_remote(
    url: str,
    agent_name: str,
    query: str,
    *,
    api_key: str = "",
    timeout_seconds: int = 120
) -> str
```

**Parameters:**

| Param | Required | Description |
|---|---|---|
| `url` | Yes | Base URL of the remote Lucy (e.g., `https://c93f-207-237-255-168.ngrok-free.app`) |
| `agent_name` | Yes | Which agent on the remote to invoke |
| `query` | Yes | The message / instruction to send |
| `api_key` | No | API key for the remote (falls back to config) |
| `timeout_seconds` | No | HTTP timeout (default 120) |

**Behavior:**
1. POST to `{url}/ask` with JSON body `{agentName, accountName, query}`
2. Parse JSON response
3. Return the `reply` field as a string
4. On failure: raise a descriptive error the LLM can surface to the user

**Tool definition (agents.json):**
```json
{
  "name": "delegate_to_remote",
  "description": "Send a query to a remote Lucy instance and return its reply.",
  "parameters": {
    "type": "object",
    "properties": {
      "url": {"type": "string", "description": "Base URL of the remote Lucy"},
      "agent_name": {"type": "string", "description": "Agent name on remote"},
      "query": {"type": "string", "description": "Message to send"},
      "timeout_seconds": {"type": "integer", "description": "Timeout in seconds", "default": 120}
    },
    "required": ["url", "agent_name", "query"]
  }
}
```

---

## 5. Configuration

### New section in `config.json`

```json
{
  "remote_agents": {
    "api_key": "lucy-shared-secret",
    "peers": {
      "nuc-lucy": {
        "url": "https://c93f-207-237-255-168.ngrok-free.app",
        "api_key": "optional-override"
      },
      "pi-lucy": {
        "url": "http://192.168.1.50:5000",
        "api_key": null
      }
    }
  }
}
```

**Peer names** are human-friendly aliases the LLM can use instead of raw URLs:
> "Delegate this to nuc-lucy using the colin agent"

### API key flow

1. Remote Lucy's `POST /ask` already validates API keys (`src/api_key.py`)
2. Caller Lucy reads its `remote_agents.api_key` from config
3. Sends it as `Authorization: Bearer <key>` header
4. Remote validates using existing auth middleware

**No new auth mechanism needed.** Just use what's already there.

---

## 6. Error Handling

| Scenario | Handler behavior |
|---|---|
| Remote unreachable | Return `"Error: Could not reach remote at {url} — connection refused"` |
| Remote timeout | Return `"Error: Remote at {url} timed out after {n}s"` |
| Remote returns non-200 | Return `"Error: Remote returned {status}: {body}"` |
| Remote auth failure | Return `"Error: Authentication failed for {url}"` |
| Malformed response | Return `"Error: Unexpected response from {url}: {truncated_body}"` |

All errors are returned as *strings* (not raised as exceptions that crash the FCP).
The calling LLM can read the error and decide what to tell the user.

---

## 7. Security Considerations

1. **API key required** — remote won't respond without valid auth
2. **No session leaking** — delegation calls use `sessionId: null` by default
3. **Timeout cap** — hard cap at 300s to prevent hanging
4. **No recursive delegation** — handler does NOT call itself (avoids infinite loops)
5. **ngrok URLs** — only use for dev; production should use tailscale/wireguard IPs

---

## 8. Implementation Plan

One step at a time with review checkpoints. No commits until review passes.

### Step 1: Handler skeleton
- Create `src/handlers/delegate_to_remote.py`
- Define the handler function with HTTP POST logic
- Register in `handler_registry.py` and `registry_bootstrap.py`

### Step 2: Config schema
- Add `remote_agents` section to config schema / defaults
- Load it in ConfigManager

### Step 3: Tool definition
- Add `delegate_to_remote` to `static/data/agents.json` for agents that should have it

### Step 4: Integration test
- Manual test: NUC Lucy → Pi 5 Lucy via ngrok
- Verify error handling for unreachable / timeout / bad auth

### Step 5: Documentation
- Update module docs
- Add usage example to design doc

---

## 9. Future Enhancements (not now)

- **Streaming** — proxy SSE from remote to caller's SSE stream
- **Named peer resolution** — `delegate_to_remote(peer="nuc-lucy", ...)` resolves URL from config
- **Multi-hop** — remote can delegate further
- **Response metadata** — timing, model used, token counts
- **Health check** — `/health` endpoint for peer monitoring

---

## 10. Open Questions

1. Should the handler resolve peer names from config, or just accept raw URLs?
   → **v1: raw URLs only.** Peer name resolution is a future convenience.

2. Should remote delegation respect the caller's `accountName`?
   → **v1: always uses the remote's configured default account.** Keeps it simple.

3. What about file context? If the caller has loaded a file, does the remote need it?
   → **v1: caller sends the content inline in the query.** No file transfer protocol yet.
