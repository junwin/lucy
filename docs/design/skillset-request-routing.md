# Opt-in skillset request routing (Lucy #143 / #241)

`POST /ask` supports `routing: "auto"`. The default remains `"explicit"`;
existing clients continue to select an agent without an additional model call.
This first implementation selects one local specialist before prompt construction.
It does not invoke remote delegation or change tool permissions.

```json
{
  "accountName": "junwin",
  "agentName": "lucy",
  "routing": "auto",
  "question": "Create a boutique image from this photograph",
  "image_ids": ["uploaded-image-id"]
}
```

In automatic mode, `agentName` specifies the general/fallback agent and may be
omitted (default `lucy`). Opting into automatic mode permits a specialist to
replace that fallback for the current request. Selecting an agent normally,
without `routing: "auto"`, always bypasses routing. A nonblank explicit
`contextName`, including the `none` sentinel, also bypasses routing. To test
automatic selection, omit `contextName` or send null/empty string: `none`
explicitly disables project context and is not an automatic-selection request.

The router publishes a compact catalog of locally configured chat agents'
`name` and `skillset`. Agents without advertised capabilities, the MCP facade,
and automation processors are excluded. Lumia currently advertises
`image-processing` and `image-creation`. Add other agents' capability labels in
`agents.json` before expecting those specialties to participate. Labels describe
expertise; they are distinct from execution `skills` and machine capabilities.

A tool-free LLM call classifies the request as general work, a required set of
capabilities, a continuation/end, a clarification, or a direct answer. It receives only the catalog, the request
(requests exceeding 12,000 characters ask for guidance without classification), attachment counts, and up to four recent active
user/assistant messages (800 characters each). It does not retrieve embeddings,
archived digests, tool results, or procedural skill text, and does not inspect
attachment contents. Session ownership is checked before reading history.
General requests remain with the fallback agent unless eligible for a direct answer. A specialist is selected only
if exactly one advertised agent covers all required labels and the classifier
confidence meets the configured threshold. Unknown labels, ties, insufficient
confidence and unknown matches ask the user for guidance; ties name the eligible agents.
Direct capability/agent selections and replies to routing clarification can resolve
a unique specialist without another model call. Malformed output and provider
failures report that automatic routing is unavailable instead of repeating an
unanswerable clarification;
no worker executes in that case. Model-reported confidence is a heuristic,
not a calibrated probability. Routing quality needs evaluation on real requests.

Automatic routing keeps a session's selected specialist for an active dialogue.
After a successful specialist reply, session metadata `routing_dialogue` stores
the specialist name, an expiry timestamp, and whether its response appears to
ask for a reply (a question or an explicit request to confirm/choose/provide).
The default inactivity TTL is 1,800 seconds (30 minutes), renewed after each
successful reply. State survives router/server restarts; expiry is checked when
the next request arrives, with no background cleanup job. Set the TTL to zero
to disable continuity. State is scoped to the account and conversation ID.

Short replies such as `yes`, `no` and `go ahead` stay with the specialist without
another classifier call. `ok`/`okay` stay with it when a reply is pending;
otherwise they close the dialogue. Standalone `thanks`, `thank you`, `bye` and
`that's all` close it. The closing message goes to the current specialist, then
affinity is released. With no active specialist, standalone acknowledgements
use the fallback agent. Attachments and substantive suffixes (for example,
`thanks, now write a blog`) are classified instead of treated as closure.

For substantive messages the classifier receives the active specialist and
recent conversation so it can distinguish a continuation from new work. Clear
changes of skillset select a different specialist: image work can move from
Lumia to Belle (`writing`), or to a development agent. A tie asks for an agent
name; if the active specialist already covers the required labels, it is kept.
Unknown/uncertain work still asks for guidance rather than silently handing it
to the current specialist. Natural-language continuation/end detection remains
a model heuristic; standalone acknowledgements and direct selections follow
the deterministic rules above.

## Direct answers for simple questions (#200)

By default, the same routing LLM call may return `kind: "answer"` with empty
capabilities and a brief `answer` (maximum 2,000 characters). This is restricted
by the prompt to simple, self-contained stable facts, basic arithmetic and unit
conversions that need no tools or conversation/account/project context. For
example, `What is the capital of Brazil?` can return `Brasília`, and
`What is 70°F in centigrade?` can return `approximately 21.1°C`.

These requests bypass agent construction, Galet prompt compilation, memory
retrieval, skill loading, tool selection and the worker LLM/tool loop. The
router still reads its bounded recent conversation and makes one LLM call.
User and assistant messages are persisted with run/trace identity under the
same conversation ID. JSON returns the ordinary response fields with routing
reason `direct_answer` and `needs_clarification: false`; streaming sends the
ordinary routing action, text and done events, so clients need no changes.
The answer itself is omitted from routing diagnostics to avoid duplicating
reply content in logs and event metadata.

The prompt excludes files/attachments, current facts, personal/project data,
research, medical/legal/financial advice and requests to perform actions. The
server separately validates answer type/length, confidence and capability
consistency. Attachments or disabled direct answers force normal general-agent
processing even if the classifier returns an answer. A classifier failure or
uncertain/malformed answer never delivers that answer. Semantic suitability
and factual correctness remain LLM judgments and need live evaluation.

Use `request_routing.direct_answers_enabled: false` to compare against normal
agent execution. Direct answers also work when no specialists advertise
skillsets. Manual routing and explicit contexts keep their existing behavior.
A self-contained direct answer is treated as new general work and releases
previous specialist affinity without changing session identity/context.

Manual agent/context selection and new general work release affinity. Failed
or incomplete executions do not establish or renew it. A streaming session
reset releases it. gptChum can continue sending `agentName: "lucy"` with
`routing: "auto"` and the same conversation ID; continuity is enforced by Lucy,
so it also works for other API clients. This is not #200's lightweight pipeline:
normal agent processing still handles acknowledgements and approvals.

After selection, normal request processing uses the specialist's current
`default_context`, all configured `skills` plus context imports, `prompt_policy`,
model policy, partner agent and existing `allowed_tools`. Existing conversation
IDs are preserved. Routing preserves session identity, established context and
unrelated metadata; only `routing_dialogue` is updated. Clarification exchanges are saved as normal visible
messages so the next routing request can interpret the user's answer.

Optional settings in `config.local.json`:

```json
{
  "request_routing": {
    "default_agent": "lucy",
    "minimum_confidence": 0.8,
    "dialogue_ttl_seconds": 1800,
    "direct_answers_enabled": true
  }
}
```

When omitted, routing model/provider use the fallback agent’s configured model/provider.
They can be overridden with `request_routing.model` and `request_routing.provider`.
The classifier requests JSON output and accepts a single fenced JSON object from
providers that wrap their response.

`POST /chats` also accepts `routing: "auto"` with an omitted/empty `agentName`;
it stores the configured default agent (normally `lucy`), never a blank router
identity. Manual chat creation still requires a valid agent. No `*` or special
`router` agent is required. Existing session IDs and identity remain unchanged
when a specialist handles a request.

Both JSON and streaming requests use the same router. JSON responses include
`routing` with requested/selected agent, matched capabilities, decision reason,
classifier-call count and classifier latency. Clarification responses also
include `needs_clarification: true`. Streaming sends an `action` event with
`action: "request_routing"` and the same decision in `action_payload`, followed
by normal response events or clarification text and `done`. Routing decisions
are logged. The latency/call count covers classification, not worker execution;
this is not yet integrated into persisted run-metrics tables.

# Scope and subsequent work

- #239 continues to own execution-skill loading; this does not select skill subsets.
- #241 supplies agent configuration and capability publication. UI changes remain separate.
- #143 owns expertise selection. This implements the LLM-classification family
  already surveyed there, with deterministic capability matching and clarification.
  No new routing-framework dependency is needed for this small local catalog.
- #200's initial lightweight path answers simple self-contained questions here.
  Greetings/acknowledgements and other prompt/retrieval/tool-selection savings remain separate work.
- Remote routing should first select agent expertise, then reuse machine eligibility
  checks from `delegate_task`; machine capability filters are not agent skillsets.
- Multi-specialist decomposition and calibrated/embedding-based routing are deferred.

## Comparing direct and routed requests

Temporarily add this top-level setting to `config.local.json` and restart Lucy:

```json
{
  "request_routing_debug": true
}
```

Records at INFO level start with `request_routing_debug` and contain JSON:

- `incoming_request`: the client payload before routing, including requested
  agent/context, conversation ID, question and attachment IDs.
- `processor_handoff`: selected agent, routing decision, requested and effective
  context, partner agent and attachment IDs. Both JSON and streaming paths emit
  this record with the processor's correlation ID.
- `prepared_prompt`: the model/provider, vision capability, skills and allowed
  tools, rendered system/history/current messages and initially selected tool
  schemas. Worker tasklist calls emit this stage too, with their own agent and
  correlation ID, so filter by agent as well as by turn.

Compare the same image and wording in a direct Lumia request and an automatic
request. Use separate fresh chats to compare clean inputs; then reproduce in
an existing chat to inspect history effects. For direct selection, leave the
context unset to use Lumia's default, matching automatic selection. Check
attachment IDs, effective context, the non-vision attachment instruction,
recalled history and tool definitions. `incoming_request` precedes creation of
execution identity; match it by conversation ID and log order to the correlated
handoff and prompt records.

Inline attachment data, bytes and data URLs are omitted. Each text value is
limited to 20,000 characters; longer values include their sanitized length and
SHA-256 to identify differences beyond the preview. Records contain private
prompt/history text, so disable the setting (or remove it) after diagnosis.
This switch does not change routing, prompt content or tool execution.
