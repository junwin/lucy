# Lucy

Lucy is a small, experimental assistant built on top of OpenAI's APIs. It focuses on:

- **Agents** with different behaviors (simple chat, tools/function calling, automation).
- **Storage-backed conversations** (sessions, messages, context).
- **A simple HTTP API and CLI** so you can exercise the system without the web UI.

For a high-level view of the architecture, see:

- `docs/architecture_overview.md`
- `docs/storage.md`
- `docs/ask_request_handler.md`

---

## Quick start

### 1. Run Lucy (HTTP server — recommended)

From the project root:

```bash
python app.py
```

By default this starts the HTTP server. The main endpoint is `POST /ask`.

### 2. Call the HTTP `/ask` endpoint

Send a request with `curl`:

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

### 3. Run Lucy (CLI mode — optional)

The CLI is useful for quick local testing, but most usage is expected to be via HTTP/REST.

From the project root:

```bash
python main.py --agentName lucy --accountName junwin --friendlyName talisker
```

Type a message at the prompt, for example:

```text
>> What can you do?
```

Lucy will:

- Create a new chat session in storage (with a friendly name like `cli-YYYY-MM-DD`).
- Call the OpenAI API via the configured message processor.
- Store the conversation so you can inspect it later.

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

- `data/contexts/junwin/lucyproject.md`

When the `lucyproject` context is selected for account `junwin`, its `data["text"]` (the Markdown body) and any frontmatter keys are available to the PromptBuilder and agents as additional system/context content.

Note: there is no `src/context` package in this repository. The request/context helper lives at `src/request_context.py` and the JSON/MD persistence logic is implemented in `src/storage/json_file_storage.py` (see the "Context / Whiteboard" section there).

---

## Automation: runs, storage layout, and JSON payloads (developer notes)

This project includes an AutomationProcessor that can:

- Create a run record for a task list stored inside a context.
- Resume an existing run when a run id is supplied.
- Persist run and task state back into storage after every state change so runs can be resumed or inspected.

Where automation data lives

- Context files are stored as Markdown with YAML frontmatter under the storage root calculated by StoragePaths. The canonical location is:

  <storage_root>/<storage_namespace>/contexts/<account_name>/<context_id>.md

  - Frontmatter keys map into ContextState.data (except the Markdown body, which is placed in data['text']).
  - The task list must be available at context.data['tasklist'] (a serialized TaskList dict or JSON string).
  - Automation run metadata is stored inside the tasklist under a top-level `runs` key (a dict keyed by run_id).

- Chat sessions continue to live under:

  <storage_root>/<storage_namespace>/chats/<account_name>/<session_id>.json

  See `src/storage/json_file_storage.py` and `src/storage_paths/storage_paths.py` for details.

How runs are created and resumed

- The AutomationProcessor (src/message_processors/automation_processor.py) accepts either free-text commands or a small JSON payload in the message body.

- Free-text examples:
  - "run tasks single step"
  - "run tasks multi-step"

- JSON payload example (create a new run or resume if run_id provided):

```json
{
  "action": "run",
  "mode": "single-step",   // or "multi-step"
  "id": "optional-run-id", // or "run_id"
  "name": "friendly name for this run"
}
```

- Behavior:
  - If `id`/`run_id` is provided and that id exists in tasklist.runs, the processor will attempt to resume that run.
  - If no run id is provided, a new run id is created (of the form `run-<ISO timestamp>`) and a run metadata object is attached to tasklist.runs.
  - The run metadata object contains at least: id, name, state (created/running/completed/failed), created_at, updated_at, executed_count.

Persistence and safety

- The processor updates task and run states in memory and serializes the whole tasklist back into context.data['tasklist'] on every state change.
- After each change it calls storage.save_context(ctx) so the on-disk context (the Markdown file) is updated atomically. This allows resuming runs if the process restarts.
- Context frontmatter remains a plain dict; the TaskList is saved in the body/frontmatter as a serialized dict so tools that read contexts can find `tasklist` under context.data.

Where to look in the code

- AutomationProcessor implementation: `src/message_processors/automation_processor.py` (run creation/resume logic and persistence).
- Storage and context persistence: `src/storage/json_file_storage.py` (get_context, save_context, migration helpers).
- Storage path resolver: `src/storage_paths/storage_paths.py`.

Tests and development guidance

- Unit tests for the AutomationProcessor live at `tests/test_automation_processor.py`.
  - These tests assert mode parsing, missing-context behavior, and basic persistence expectations.

- To run tests locally (must be in a venv):

```bash
# from the project root
bash -lc "source .venv/bin/activate && pytest -q"
```

- If you add/adjust behavior for runs, add tests that cover:
  - Creating a new run (no run_id provided) and verifying tasklist.runs contains the new run.
  - Resuming an existing run by providing run_id and asserting continued processing.
  - Persistence after each task state change (e.g., simulate failure between steps and assert save_context was called).

Documentation updates

- If you modify where run metadata (tasklist.runs) is stored, update `docs/message_processors.md` and `docs/storage.md`.
- If you change the context file schema, update `src/storage/json_file_storage.py` (and the migration helper `migrate_context_json_to_md`) and the docs.

---

## Request flow and logging

Very short request flow for `/ask`:

1. HTTP request hits `POST /ask`.
2. `FunctionCallingProcessor` starts for the selected agent and session.
3. `PromptBuilder` builds the prompt (history, agent config, optional storage-based context).
4. The model is called; if it requests tools, `FunctionCallingProcessor` executes them and then returns the final reply.

> IMPORTANT: Command execution and shell usage
>
> - Commands are executed with `shell=False` by default — the executor runs the program directly, not via a shell.
> - Do NOT rely on shell-only features/operators: piping (`|`), command chaining (`&&`, `||`, `;`), redirection (`>`, `>>`, `<`, `2>`, `2>&1`), globbing/wildcards (`*`, `?`, `[ ]`), environment-variable expansion (`$VAR`), command substitution (`$(...)`, `` `...` ``), here-documents (`<<`), process substitution (`<(...))`, or other shell metacharacters.
> - If you need shell behaviour, explicitly invoke a shell. Recommended wrapper (for now): `bash -lc '...'`. Example:
>
>   `command: "bash -lc 'echo \"Hello\" && ls -la /tmp | grep py'"`
>
> - Note: this relies on the system's `bash` binary. Bash may not be available or behave the same on Windows or other platforms; adjust accordingly.
> - Security: `shell=False` is the default to avoid shell injection and reduce the attack surface. If we add first-class shell support later, it will come with extra security considerations.

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
- If `friendly_name` is provided on that first call, it will be stored as the session's `friendly_name`.
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
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt

# Optional: language models used by some components
python -m spacy download en_core_web_sm
python -m spacy download es_core_news_sm

# Optional: NLTK data used by some components (Lucy will auto-download on first run)
python -c "import nltk; nltk.download('punkt')"
```

### 3. Run the app

HTTP server (recommended):

```bash
python app.py
```

CLI (optional):

```bash
python main.py --agentName lucy --accountName junwin
```

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

## Deployment

Lucy runs as a **systemd service** (`lucy-server`) on the target machine.

### Service overview

- **Service name:** `lucy-server`
- **User:** `junwin`
- **Working directory:** `/home/junwin/src/repos/lucy`
- **Exec:** Flask via the project venv, bound to `0.0.0.0:5000`, with debugger/reloader disabled

### Useful commands

```bash
# Check service status
sudo systemctl status lucy-server

# Restart after code changes
sudo systemctl restart lucy-server

# View recent logs
sudo journalctl -u lucy-server -f

# View last 50 lines
sudo journalctl -u lucy-server -n 50
```

### After making code changes

Any edit to Python files (`app.py`, `src/*`, etc.) requires a restart for the changes to take effect:

```bash
sudo systemctl restart lucy-server
```

The service restarts in under a second, so there's essentially no downtime.

---

## More documentation

- `docs/architecture_overview.md` – high-level architecture and components.
- `docs/storage.md` – storage model, chat sessions, messages, and context.
- `docs/ask_request_handler.md` – `/ask` request/response flow and session handling.
