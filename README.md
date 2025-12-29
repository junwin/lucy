# Lucy

Lucy is a small, experimental assistant built on top of OpenAI’s APIs. It focuses on:

- **Agents** with different behaviors (simple chat, tools/function calling, automation).
- **Storage-backed conversations** (sessions, messages, context).
- **A simple HTTP API and CLI** so you can exercise the system without the web UI.

For a high-level view of the architecture, see:

- `docs/architecture_overview.md`
- `docs/storage.md`
- `docs/ask_request_handler.md`

---

## Quick start

### 1. Run Lucy (CLI mode)

From the project root:

```bash
cd src/repos/lucy
python main.py --agentName lucy --accountName junwin
```

Type a message at the prompt, for example:

```text
>> What can you do?
```

Lucy will:

- Create a new chat session in storage (with a friendly name like `cli-YYYY-MM-DD`).
- Call the OpenAI API via the configured message processor.
- Store the conversation so you can inspect it later.

### 2. Call the HTTP `/ask` endpoint directly (optional)

If you have the HTTP server running (see `docs/architecture_overview.md` for details), you can send a request with `curl`:

```bash
curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the first sentence in The Wind in the Willows?",
    "agentName": "lucy",
    "accountName": "junwin"
  }'
```

Example response:

```json
{
  "ok": true,
  "answer": "The Mole had been working very hard all the morning, spring-cleaning his little home.",
  "conversation_id": "c0a8012e-1234-5678-9abc-def012345678"
}
```

On the first call, omit `conversationId` and (optionally) include a `friendly_name`:

```bash
curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Start a new session for me.",
    "agentName": "lucy",
    "accountName": "junwin",
    "friendly_name": "my-first-session"
  }'
```

On subsequent calls, reuse the returned `conversation_id` so messages are appended to the same session:

```bash
curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Continue our previous chat.",
    "agentName": "lucy",
    "accountName": "junwin",
    "conversationId": "c0a8012e-1234-5678-9abc-def012345678"
  }'
```

---

## Core concepts

### Agents

Agents define how Lucy behaves:

- System prompt / role
- Capabilities (plain chat, tools, function calling, automation)
- Optional context usage

Agents are configured and then used by the message processors to handle user input.

### Storage and conversations

Lucy persists conversations and related data via the storage layer (see `docs/storage.md`).

Key ideas:

- **ChatSession**
  - Identified by a UUID `id` (this is the canonical `conversation_id`).
  - Has a `friendly_name` (e.g. `cli-2025-12-28`) that is human-readable.
  - Scoped by `account_name` and `agent_name`.

- **ChatMessage**
  - Stored under a session.
  - Includes `role` (user/assistant/system), `content`, and timestamps.

The `/ask` endpoint and the CLI always work with a real `ChatSession` in storage. If a client does not provide a `conversation_id`, a new session is created.

### Message processors

Message processors take an incoming message and:

- Build a prompt (using the prompt builder and stored history).
- Call the OpenAI API.
- Optionally use tools / function calling.
- Append messages to the current `ChatSession` via storage.

The main processor in use is the **FunctionCallingProcessor**.

### Handlers and tools

Handlers are small units of functionality that can be invoked by agents via tools/function calling, for example:

- File loading / saving
- Web search
- Web page loading

These are wired into the message processors and agents.

### Context

Context is shared information that can be used by one or more agents when building prompts (e.g. documents, notes, or other long‑lived data). Context is stored via the storage layer (for example, JSON-backed `ContextState` records) and can be injected into prompts by the `PromptBuilder`.

A simple project-level context for this repo lives at:

- `data/contexts/junwin/lucyproject.json`

When the `lucyproject` context is selected for account `junwin`, its `data["text"]` is added as additional system context for the conversation.

---

## Request flow and logging

Very short request flow for `/ask`:

1. HTTP request hits `POST /ask`.
2. `FunctionCallingProcessor` starts for the selected agent and session.
3. `PromptBuilder` builds the prompt (history, agent config, optional storage-based context).
4. The model is called; if it requests tools, `FunctionCallingProcessor` executes them and then returns the final reply.

Logging is initialized once in `app.py` and used throughout the app.

---

## HTTP API (current)

Lucy exposes a small HTTP API. The main endpoint you will use is `/ask`.

### `/ask`

`POST /ask`

Ask a question or send a message to an agent.

**Request body (JSON)**

```json
{
  "question": "What is the first sentence in the wind in the willows?",
  "agentName": "lucy",
  "accountName": "junwin",
  "conversationId": "<optional>",
  "friendly_name": "<optional human label for a new session>",
  "selectType": "<optional context selector>"
}
```

Notes:

- If `conversationId` is omitted, the server will create a new `ChatSession`.
- If `friendly_name` is provided on that first call, it will be stored as the session’s `friendly_name`.
- The response includes the canonical `conversation_id` (a UUID) that you should reuse on subsequent calls.

**Response (JSON)**

```json
{
  "ok": true,
  "answer": "...assistant reply...",
  "conversation_id": "<uuid>"
}
```

Other endpoints (for listing agents, sessions, etc.) are documented in the code and in the docs under `docs/`. The older `/completions` API described in previous versions has been superseded by the storage-backed chat sessions.

---

## CLI usage

Lucy includes a simple CLI that talks to the same `/ask` logic. This is useful for exercising the system without the web client.

From the project root:

```bash
cd src/repos/lucy
python main.py --agentName lucy --accountName junwin
```

Behavior:

- On start, the CLI creates (or reuses) a **friendly name** like `cli-YYYY-MM-DD`.
- On the first message, it calls `/ask` without a `conversationId` but with that `friendly_name`.
- The server creates a new `ChatSession` and returns its UUID.
- On subsequent messages, the CLI reuses that `conversation_id` so all messages go into the same session.

This is the recommended way to quickly test agents, storage, and message processing.

---

## Getting started (development)

### 1. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt

# Optional: language models used by some components
python -m spacy download en_core_web_sm
python -m spacy download es_core_news_sm
```

### 3. Run the app

The current entry point is `main.py`, which wires up the storage, agents, and message processors, and can expose HTTP endpoints and/or the CLI.

For local CLI testing:

```bash
python main.py --agentName lucy --accountName junwin
```

If you are running the HTTP server variant (Flask or similar), follow the instructions in `docs/architecture_overview.md` or the relevant server module. Older instructions that referenced `app.py` and Swagger UI may not match the current setup.

---

## HTTPS (optional)

If you run a Flask-based HTTP server and want HTTPS locally, you can still use `mkcert` to generate a self‑signed certificate. The general pattern is:

1. Install `mkcert` (see https://github.com/FiloSottile/mkcert#installation).
2. Generate a certificate:

   ```bash
   mkcert localhost
   ```

3. In your server code, configure SSL:

   ```python
   import ssl

   if __name__ == "__main__":
       context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
       context.load_cert_chain('localhost.pem', 'localhost-key.pem')
       app.run(host='0.0.0.0', port=5000, ssl_context=context, debug=True)
   ```

This is optional and only needed if you expose an HTTPS endpoint locally.

---

## More documentation

- `docs/architecture_overview.md` – high-level architecture and components.
- `docs/storage.md` – storage model, chat sessions, messages, and context.
- `docs/ask_request_handler.md` – `/ask` request/response flow and session handling.

These docs are the best place to start if you are modifying or extending Lucy.
