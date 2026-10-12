# /ask request components

`AskRequestHandler` keeps its constructor, dependency attributes and public
`handle()` / `handle_streaming()` methods. It owns the injected agent manager,
configuration, storage, processor factory, episodic store and optional router
and procedural memory. It passes itself explicitly to endpoint functions;
there is no container lookup, inheritance chain or new framework. Component
imports of the handler type are annotation-only, preventing runtime cycles.

| Module | Responsibility |
| --- | --- |
| `ask_request_handler.py` | Public facade and dependency ownership |
| `ask_request.py` | Payload normalization, required-field rule, execution identity |
| `ask_routing.py` | Endpoint routing, clarification/direct replies, dialogue persistence; agent selection remains in `SkillsetRouter` |
| `ask_session.py` | Friendly-name session resolution, context backfill and procedural context creation |
| `ask_ordinary.py` | Ordinary preparation, processor call, JSON response and errors |
| `ask_streaming.py` | Streaming preparation, processor call, SSE events and dialogue updates |

The facade re-exports `resolve_or_create_session` for `app.py` and existing
callers. Session names, context fallback, lineage, attachments, processor
arguments and routing behavior retain their previous semantics.

## Deliberate transport differences

Ordinary responses expose HTTP status codes and JSON errors. Streaming
validation errors produce `error` then `done`. Streaming routing decisions
produce an action event before subsequent output. Session-creation failure
messages differ between transports. Ordinary context-backfill failures stop
the request; streaming backfill failures are logged and processing continues.
These differences are preserved rather than collapsed into a common catch-all.

The shared required-field rule still rejects an empty question even with
attachments. Issue #260 changes that behavior separately. Automatic routing
has its own preconditions in `ask_routing.py`; an attachment-only routing
change must review those too.

## Reading scope and measurements

Baseline: develop `e1ba2f50ecf0a2bb1c63eb75f71278fe75d5acf5`.
Measurements count source characters, not bytes, tokens or serialized tool
results. They do not include tests or imported modules.

| Module | Before lines / characters | After lines / characters |
| --- | ---: | ---: |
| `ask_request_handler.py` | 647 / 29,263 | 56 / 2,384 |
| `ask_request.py` | — | 55 / 1,959 |
| `ask_routing.py` | — | 72 / 3,741 |
| `ask_session.py` | — | 92 / 3,536 |
| `ask_ordinary.py` | — | 258 / 10,421 |
| `ask_streaming.py` | — | 213 / 8,868 |

For a focused explicit-request required-field change, read `ask_request.py`
and `tests/test_ask_request_validation.py` (4,144 characters). That is 6,103
characters of directly relevant code/tests, compared with the previous
29,263-character endpoint source alone. The facade explains the call boundary;
response adapter modules are available when an output contract changes.
A change to routing or session semantics still requires their components and
tests. Total source across the new modules is slightly larger due to explicit
imports and the facade: the benefit is smaller, cohesive reading scope, not
fewer total lines or proven live token savings. Character-bounded file reading
remains a separate safeguard.

## Validation

The 18 request-contract regression cases pass against both the original
implementation and this extraction. They cover required fields (including
unchanged empty-question attachment rejection), input normalization, legacy
context precedence, attachment forwarding and the distinct JSON/SSE session
failure contracts. Existing endpoint, routing/direct-answer/dialogue, session,
attachment and execution identity tests exercise the extracted components.
