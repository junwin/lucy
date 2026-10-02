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
capabilities, or a clarification. It receives only the catalog, the request
(requests exceeding 12,000 characters ask for guidance without classification), attachment counts, and up to four recent active
user/assistant messages (800 characters each). It does not retrieve embeddings,
archived digests, tool results, or procedural skill text, and does not inspect
attachment contents. Session ownership is checked before reading history.
General requests remain with the fallback agent. A specialist is selected only
if exactly one advertised agent covers all required labels and the classifier
confidence meets the configured threshold. Unknown labels, ties, insufficient
confidence and unknown matches ask the user for guidance; ties name the eligible agents.
Direct capability/agent selections and replies to routing clarification can resolve
a unique specialist without another model call. Malformed output and provider
failures report that automatic routing is unavailable instead of repeating an
unanswerable clarification;
no worker executes in that case. Model-reported confidence is a heuristic,
not a calibrated probability. Routing quality needs evaluation on real requests.

Standalone acknowledgements bypass specialist classification and run with the
fallback agent. This is not the lightweight response pipeline in #200: normal
processing still runs, because `okay` may authorize pending work. Attachments
and substantive acknowledgement suffixes do not take this bypass.

After selection, normal request processing uses the specialist's current
`default_context`, all configured `skills` plus context imports, `prompt_policy`,
model policy, partner agent and existing `allowed_tools`. Existing conversation
IDs are preserved. Routing does not modify an agent definition or session's
established metadata. Clarification exchanges are saved as normal visible
messages so the next routing request can interpret the user's answer.

Optional settings in `config.local.json`:

```json
{
  "request_routing": {
    "default_agent": "lucy",
    "minimum_confidence": 0.8
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
`router` agent is required. Existing session IDs and metadata remain unchanged
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
- #200 remains the separate lightweight prompt/retrieval/tool-selection route.
- Remote routing should first select agent expertise, then reuse machine eligibility
  checks from `delegate_task`; machine capability filters are not agent skillsets.
- Multi-specialist decomposition and calibrated/embedding-based routing are deferred.
