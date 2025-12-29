# Ask Request Handler

This document describes how the `AskRequestHandler` works, how it interacts with storage, and how conversations are created and identified.

## Overview

`AskRequestHandler` is responsible for handling `/ask`-style requests (including the CLI path) and orchestrating:

- Input normalization (field names, casing).
- Resolving the primary agent, account, and optional partner agent.
- Ensuring there is a valid chat session in storage.
- Invoking the appropriate message processor.
- Returning the answer and canonical `conversation_id` to the caller.

It is the main bridge between external clients (web, CLI) and the internal storage + processing pipeline.

## Request Payload

The handler accepts a JSON-like payload with these relevant fields:

- `message` (or `question`): the user’s input text.
- `agent_name` / `agentName`: the primary agent to use.
- `account_name` / `accountName`: the account under which the conversation is stored.
- `context_name` / `selectType` (optional): context selection for prompt building.
- `conversation_id` / `conversationId` (optional): existing conversation/session id.
- `partnerAgentName` (optional): secondary agent for certain flows.
- `friendly_name` (optional): human-friendly label for a new session.

The handler normalizes these into internal variables:

- `message`
- `agent_name` (lowercased)
- `account_name` (lowercased)
- `context_name`
- `conversation_id`
- `partner_agent_name` (lowercased)
- `friendly_name`

## Conversation and Storage Interaction

The key responsibility of `AskRequestHandler` with respect to storage is to ensure that **every call into the message processor has a valid, storage-backed conversation id**.

### Creating or Resolving a Session

The handler uses the following logic:

1. Read `conversation_id` from the payload (if present).
2. If **no** `conversation_id` is provided:
   - Call `storage.create_chat_session(...)` with:
     - `account_name`
     - `agent_name`
     - `friendly_name` (if provided)
     - `tags=None` (or empty)
   - Use the returned `ChatSession.id` as `session_id`.
3. If a `conversation_id` **is** provided:
   - Call `storage.get_chat_session(conversation_id)`.
   - If it exists, use that id as `session_id`.
   - If it does **not** exist:
     - Treat this as a request to start a new session.
     - Call `storage.create_chat_session(...)` with:
       - `account_name`
       - `agent_name`
       - `friendly_name` set to the provided `conversation_id` (e.g. `"cli-2025-12-28"`).
     - Use the new `ChatSession.id` as `session_id`.

From this point on, the handler always works with `session_id`, which is guaranteed to be a valid `ChatSession.id` in storage.

### Friendly Names

`friendly_name` is a human-readable label for a session. The handler supports two ways to set it:

1. **Explicit `friendly_name` field** when no `conversation_id` is provided.
   - Example: the CLI sends `friendly_name="cli-2025-12-28"` on the first message.
2. **Implicitly from a client-supplied `conversation_id`** that does not exist in storage.
   - Example: a client sends `conversation_id="cli-2025-12-28"` but storage has no such session.
   - The handler creates a new session and stores `"cli-2025-12-28"` as `friendly_name`.

In all cases, the canonical identifier for the session is the UUID `ChatSession.id` returned by storage.

## Calling the Message Processor

Once `session_id` is determined, the handler:

1. Resolves the primary agent and account using the configured managers.
2. Optionally resolves a partner agent if `partner_agent_name` is provided.
3. Selects the appropriate message processor (e.g., `FunctionCallingProcessor`).
4. Calls `processor.process_message(...)` with:
   - `primary_agent`
   - `secondary_agent` (if any)
   - `account`
   - `message`
   - `conversation_id=session_id`
   - `context_name`
   - `processor_factory`

Because `session_id` is always a valid storage id, the processor can safely:

- Build prompts that include prior messages from this session.
- Append new `ChatMessage` entries via `storage.append_chat_message(session_id, ...)`.

This design avoids `FileNotFoundError` from storage when appending messages.

## Response Contract

The handler returns a response object like:

```json
{
  "ok": true,
  "answer": "...model response text...",
  "conversation_id": "<uuid>"
}
``

Key points:

- `conversation_id` is always the **canonical** `ChatSession.id` from storage (a UUID), even if the client originally sent a different identifier.
- Clients should store and reuse this `conversation_id` on subsequent calls to continue the same conversation.

If an error occurs, the handler returns:

```json
{
  "ok": false,
  "error": "<error message>"
}
```

with an appropriate HTTP status code.

## CLI Usage Pattern

The CLI uses `AskRequestHandler` as a simple way to exercise the system without the web client:

- On startup, it computes a default friendly name, e.g. `cli-YYYY-MM-DD`.
- On the **first** user message:
  - It calls the handler with `friendly_name` set and **no** `conversation_id`.
  - The handler creates a new session and returns its UUID.
- On subsequent messages:
  - The CLI passes the returned `conversation_id` back to the handler.

This pattern ensures:

- Conversations are properly persisted in storage.
- Each CLI run is easy to identify via `friendly_name`.
- The same `/ask` path is exercised as the web client would use.
