# Lucy — Personal AI Assistant

Lucy is a self-hosted AI chat platform running on a Raspberry Pi 5. It supports multiple agents, tool execution, chat sessions, and document context — all through a local web UI.

## Quick Start

### 1. Create a virtual environment

**Linux / Raspberry Pi:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Windows (Command Prompt):**

```cmd
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
```

### galet dependencies

The galet stack is a provider-agnostic LLM/embedding/image-generation family extracted from Lucy. All four distributions are published to PyPI, and `requirements.txt` pins them as released index artefacts — so a fresh install needs no git access and uses no editable installs:

| Package | Pinned version | Purpose |
|---------|----------------|---------|
| `galet` | 0.1.2 | Provider-agnostic LLM, embedding and image-generation core |
| `galet-memory[vec]` | 0.1.0 | Provider-neutral memory implementations, plus sqlite-vec/vec0 support |
| `galet-prompt-builder` | 0.1.1 | Prompt selection, budgeting and compilation |
| `galet-tools` | 0.1.0 | Shared handler ABI and external handler discovery |

Everything then resolves from a single index; `pip check` should report no broken requirements.

Source repositories (same order as `update-galet-repos.sh`):

- https://github.com/junwin/galet.git
- https://github.com/junwin/galet-memory.git
- https://github.com/junwin/galet-prompt-builder.git
- https://github.com/junwin/galet-tools.git

**Optional manual dev workflow:** to work on a galet package locally, clone it as a sibling repo and install it editable, so local edits are picked up without reinstalling:

```bash
git clone https://github.com/junwin/galet.git ../galet
pip install -e ../galet
```

Tradeoff: an editable install overrides the PyPI pin for that package, so the venv is no longer purely index-based. To go back to the released version, reinstall it from the index:

```bash
pip install --force-reinstall --no-deps galet==0.1.2
```

### 2. Run Lucy

Once the venv is active:

```bash
# Server (from repo root)
python app.py

# CLI single query
python main.py --agentName lucy --accountName junwin --query "What's the weather?"

# CLI REPL
python main.py --agentName lucy --accountName junwin
```

## Key Features

- **Multi-agent**: Switch between agents (lucy, peace, colin, star) with different system prompts and tool permissions
- **Tool execution**: Agents can read/write files, run commands, search the web, scrape pages
- **Chat sessions**: Persistent, searchable chat history via JSONL storage
- **Document context**: Agents pull relevant context from your Obsidian notes
- **Web UI**: Vue 3 frontend served at `http://<pi>:5000`
- **SSE streaming**: Real-time token streaming in the chat UI

## Architecture

```
HTTP Request → Flask Routes → MessageProcessor → LLM Adapter → Model
                    ↓
              Prompt Builder ← Document Context (embeddings)
                    ↓
              Tool Execution (handlers)
```

### Key Modules

| Module | Path | Purpose |
|--------|------|---------|
| Agent Config | `src/agent/` | Agent definitions, tool permissions |
| Chat Sessions | `src/chat2/` | JSONL session store |
| Handlers | `src/handlers/` | Tool implementations |
| HTTP Endpoints | `src/http_endpoints/` | Flask routes |
| LLM Adapters | `src/llm/` | Provider adapters (OpenAI, Mistral, etc.) |
| Message Processors | `src/message_processors/` | FCP, SSE streaming |
| Prompt Builders | `src/prompt_builders/` | System prompts + context assembly |
| Storage | `src/storage/` | JSON file persistence |
| Tasklists | `src/tasklists/` | Sequential task execution |

## API Examples

```bash
# Ask a question
curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"Hello","agent_name":"lucy","account":"junwin"}'

# List agents
curl http://localhost:5000/agents

# List chat sessions
curl http://localhost:5000/chats?account=junwin
```

## Agent Definitions

Agents are defined in `static/data/agents.json`. Each has:

- `system_prompt` — Instructions for the model
- `tools` — Allowed tool functions
- `model` — LLM model name
- `description` — Shown in the UI

## Configuration

Main config lives in `config.json` (repo root). This file is checked into git.

Machine-specific overrides go in `config.local.json` (not tracked by git). Lucy merges it on top of `config.json` at startup — any key in `config.local.json` overrides the matching key in `config.json`. Typical uses:

- API keys (different per machine)
- Storage paths (different filesystem layouts)
- Port or host overrides

Config keys:

- **LLM providers**: API keys, base URLs, available models
- **Storage paths**: Where chats, contexts, and data live
- **Server settings**: Host, port, debug mode

## Development

```bash
# Run tests (always in venv)
bash -lc "source venv/bin/activate && pytest"

# Format
black src/ tests/

# Generate docs
python -c "from src.handlers import ..."
```

### Test conventions

- Tests in `tests/` mirror `src/` structure
- Pydantic always present (don't test for missing installs)
- Use existing venv — don't create a new one

## Deployment (Raspberry Pi 5)

Runs as a systemd service:

```bash
sudo systemctl status lucy
sudo systemctl restart lucy
journalctl -u lucy -f
```

## Key Docs

- Design docs: `software/ai/lucy/design/`
- Kanban board: `software/ai/lucy/backlog/`
- Process: `software/ai/lucy/backlog/process.md`
- Repo: `~/src/repos/lucy`
