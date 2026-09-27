# UC1: execution trace identity

Status: initial contract for implementation on `feature/uc1-execution-trace-identity`.

## Purpose

An inbound chat request can start one or more agent runs, including delegation and
remote execution. The diagnostic trace must reconstruct their relationship while
the user-facing stream contains only assistant output, deliverables, and short
status messages.

## Identifiers

| Field | Owner | Meaning |
| --- | --- | --- |
| `message_id` | Client | Optional identifier for the inbound chat message. Treat as untrusted metadata, never as a unique database key. |
| `trace_id` | Lucy | Server-generated UUID for the inbound request and every descendant run. |
| `run_id` | Lucy | Server-generated UUID for one agent execution. The existing `correlation_id` is the initial implementation of this identity. |
| `parent_run_id` | Lucy | Direct caller's `run_id`; null for the root run. |
| `event_id` | Event store | Identity of one persisted event. Event ordering within a run must be recoverable independently of timestamp ties. |

At the root, one server-generated UUID may serve as both `trace_id` and
`run_id`. A child or a retried execution receives a fresh `run_id`,
retains the `trace_id`, and sets `parent_run_id` to the run that launched
it. A new inbound request receives a new trace even if its client repeats a
`message_id`; any desired idempotency policy is separate.

The HTTP logging `request_id` is also separate. Today `app.py` accepts
`X-Request-Id` from a caller for log correlation, whereas the `/ask`
handler generates a `correlation_id`. Do not promote the caller's header
to `run_id` or `trace_id`.

## Propagation and recording

- Pass the identity envelope explicitly to delegated and remote runs:
  `trace_id`, `run_id`, `parent_run_id`, and optional source
  `message_id`. The receiver mints its own new run ID when starting its
  execution; it does not trust a caller-supplied run ID as its own.
- Keep existing `correlation_id` fields and queries working while introducing
  `run_id`; map them to the same run identity during migration.
- Record the run start/end, parent relationship, outcome, and event links in
  diagnostic persistence. A trace lookup must traverse runs across instances
  and return a stable event order.
- Keep internal agent exchanges, tool arguments/results, and diagnostic
  records out of the user-facing SSE contract. Existing short status events
  remain useful.
- Do not assume that a `conversation_id` identifies a run: one conversation
  can contain many inbound messages and runs.

## First implementation slice

1. Add a small typed identity envelope and a root/child constructor in Lucy.
   Generate IDs server-side; preserve the existing correlation ID as `run_id`.
2. Thread the envelope through `/ask` (streaming and ordinary) and one
   delegated-run path without changing visible response behavior.
3. Persist run lineage and expose retrieval by `trace_id` through
   `galet-memory`'s provider-neutral interface. Keep old correlation links
   readable.
4. Verify duplicate or malformed client message IDs cannot collide, and that
   parent, child, and retry runs can be reconstructed in order.

UC2's `task_context_id` is a distinct shared-working-state identity. It
may travel beside this envelope later but is not part of the UC1 trace key.
