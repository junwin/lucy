# Prompt building

This document explains how prompts are built, how storage is involved (chat history, contexts, external documents), and what the main dependencies are.

## Overview

Prompt building is responsible for turning a user message plus surrounding context into an OpenAI-compatible `messages` array.

The main entry point is:

- `PromptBuilderInterface.build_prompt(...)` – abstract interface.
- `PromptBuilder.build_prompt(...)` – concrete implementation used by message processors.

`PromptBuilder` is used primarily by `FunctionCallingProcessor` to prepare the prompt before calling the model.

## Interfaces and implementations

### `PromptBuilderInterface`

File: `src/prompt_builders/prompt_builder_interface.py`

```python
class PromptBuilderInterface(ABC):
    @abstractmethod
    def build_prompt(
        self,
        *,
        content_text: str,
        conversation_id: str,
        agent_name: str,
        account_name: str,
        context_type: str = "none",
        max_prompt_chars: int = 6000,
        max_prompt_conversations: int = 20,
        context_name: str = "",
        extra_system_messages: Optional[List[str]] = None,
    ) -> List[ChatMessageDict]:
        """Builds an OpenAI-compatible messages array."""
        raise NotImplementedError
```

Key points:

- `content_text` – the current user message.
- `conversation_id` – the storage-backed chat session id (UUID) used to fetch history.
- `agent_name` / `account_name` – used to load agent config and account-specific data.
- `context_type` – controls whether external documents are included (`"documents"`, `"hybrid"`, or `"none"`).
- `context_name` – optional named context to load from storage.
- `extra_system_messages` – optional additional system messages (e.g., tool instructions).

### `PromptBuilder`

File: `src/prompt_builders/prompt_builder.py`

Constructor and dependencies:

```python
class PromptBuilder(PromptBuilderInterface):
    @inject
    def __init__(
        self,
        agent_manager: AgentManager,
        config: ConfigManager,
        storage: Storage,
        context_manager: ContextManager,
    ):
        self.agent_manager = agent_manager
        self.config = config
        self.storage = storage
        self.context_manager = context_manager
```

Dependencies:

- `AgentManager` – provides agent configuration (system prompt, persona, style, budgets).
- `ConfigManager` – global configuration (not heavily used in the current implementation, but available).
- `Storage` – used to load chat history and documents.
- `ContextManager` – used to load named contexts for an account.

## How prompts are built

`PromptBuilder.build_prompt(...)` returns a list of messages like:

```python
[
    {"role": "system", "content": "..."},
    {"role": "system", "content": "extra system message"},
    {"role": "user", "content": "previous question"},
    {"role": "assistant", "content": "previous answer"},
    {"role": "system", "content": "Additional context..."},
    {"role": "system", "content": "The following Obsidian notes may be relevant..."},
    {"role": "user", "content": "current question"},
]
```

The steps are:

1. **Load agent config and build base system message**
2. **Add any extra system messages**
3. **Load and append chat history from storage**
4. **Load and append named context (if any)**
5. **Load and append external document context (if requested)**
6. **Append the current user message**
7. **Ensure the last message is the current user query**

### 1. Agent system message

```python
agent = self.agent_manager.get_agent(agent_name)
_budget_info = get_prompt_budget_for_agent(agent)

system_message = self._build_agent_system_message(agent_name, agent)

messages: List[Dict[str, str]] = [{"role": "system", "content": system_message}]
```

`_build_agent_system_message` composes:

- `agent["system_prompt"]` – main instruction for the agent.
- `agent["persona"]` – optional persona description.
- `agent["style_prompt"]` – optional style/tone guidance.

If `system_prompt` is missing, it falls back to a generic:

> "You are {agent_name}, a helpful assistant."

### 2. Extra system messages

```python
for extra in (extra_system_messages or []):
    if extra and extra.strip():
        messages.append({"role": "system", "content": extra.strip()})
```

Message processors can pass additional system messages to:

- Inject tool usage instructions.
- Add temporary constraints for a single call.

### 3. Chat history from storage

```python
history_messages = self._get_chat_history_messages(
    conversation_id=conversation_id,
    account_name=account_name,
    agent_name=agent_name,
    max_conversations=max_prompt_conversations,
)
messages.extend(history_messages)
```

`_get_chat_history_messages` uses `Storage`:

```python
session = self.storage.get_chat_session(conversation_id)
if not session:
    return []

msgs = session.messages[-max_messages_per_session:]
return [{"role": m.role, "content": m.content} for m in msgs]
```

Notes:

- `conversation_id` is the canonical `ChatSession.id` from storage (UUID), created by the `/ask` handler.
- If `conversation_id` is empty or special (`"none"`, `"new"`), no history is included.
- Up to `max_messages_per_session` messages are included (default 50, from the tail of the session).

This is how storage participates in prompt building for **conversations**: the prompt includes the recent chat history for the session.

### 4. Named context from storage

```python
context_text = self._get_context_text(account_name=account_name, context_name=context_name)
if context_text:
    messages.append({"role": "system", "content": f"Additional context for this conversation:\n{context_text}"})
```

`_get_context_text` uses `ContextManager`, which in turn uses storage-backed context definitions:

```python
if not context_name or context_name == "none":
    return ""

ctx = self.context_manager.get_context(account_name, context_name)
if ctx is None:
    return ""

return ctx.context_formated_text2("compact")
```

Key points:

- Contexts are named (e.g., `"project_x"`, `"docs"`) and scoped by `account_name`.
- The context object is formatted into text via `context_formated_text2("compact")`.
- The resulting text is injected as a **system** message labeled as additional context.

This is how storage participates in prompt building for **contexts**: named contexts are stored and retrieved, then rendered into the prompt.

### 5. External document context (Obsidian notes)

If `context_type` is `"documents"` or `"hybrid"`, the builder tries to load relevant documents:

```python
if context_type in ("documents", "hybrid"):
    doc_contexts = get_document_context(
        storage=self.storage,
        account_name=account_name,
        query=content_text,
        kind="obsidian_note",
        limit=3,
        max_chars=2000,
    )
    if doc_contexts:
        # build a system message summarizing the notes
```

`get_document_context` (in `src/utils/document_context.py`) uses `Storage` to:

- Search stored documents (e.g., Obsidian notes) for the given `account_name`.
- Use embeddings or metadata to find the most relevant notes for the `query`.
- Return a list of contexts with fields like `title`, `tags`, `snippet`, and `truncated`.

The prompt builder then formats these into a single system message:

```python
"""The following Obsidian notes may be relevant to the user's question:
1. Title: ... | Tags: ...
<snippet>
[Note: content truncated]

2. Title: ...
..."""
```

This is how storage participates in prompt building for **external documents**: documents are stored and indexed via storage, and the prompt builder pulls in the most relevant snippets as a system message.

If anything goes wrong while loading document context, the builder logs a warning and continues without document context.

### 6–7. Current user message and final checks

Finally, the current user message is appended and ensured to be last:

```python
messages.append({"role": "user", "content": content_text})
messages = self._ensure_current_query(messages, content_text)
```

`_ensure_current_query` guarantees that the last message is the current user query, even if history or other logic already added a similar message.

There is also a (currently commented-out) hook to cap the prompt by character count while preserving the last user message:

```python
# messages = self._cap_prompt_by_chars_preserving_last_user(messages, max_prompt_chars)
```

## Prompt budgets

The file defines a simple budgeting helper:

```python
DEFAULT_PROMPT_BUDGET_TOKENS = 12000

DEFAULT_SOURCE_BUDGETS = {
    "agent": 0.4,
    "account": 0.4,
    "context": 0.2,
}


def get_prompt_budget_for_agent(agent: Dict[str, Any]) -> Dict[str, Any]:
    prompt_budget_tokens = int(agent.get("prompt_budget_tokens", DEFAULT_PROMPT_BUDGET_TOKENS))

    source_fracs = agent.get("source_budgets", {}) or {}
    merged_fracs = {**DEFAULT_SOURCE_BUDGETS, **source_fracs}

    total_frac = sum(merged_fracs.values()) or 1.0
    normalized_fracs = {k: v / total_frac for k, v in merged_fracs.items()}

    source_budgets = {name: int(prompt_budget_tokens * frac) for name, frac in normalized_fracs.items()}

    return {"prompt_budget_tokens": prompt_budget_tokens, "source_budgets": source_budgets}
```

Currently, the budgets are computed but not strictly enforced in `build_prompt`. They are intended to:

- Limit how many tokens can be used by different sources (agent instructions, account-specific info, context/documents).
- Guide future logic that might trim history or context when the prompt gets too large.

## How storage is involved

Storage participates in prompt building in three main ways:

1. **Chat history** – via `storage.get_chat_session(conversation_id)` and `session.messages`.
2. **Named contexts** – via `ContextManager`, which uses storage-backed context definitions.
3. **External documents** – via `get_document_context(storage=..., ...)`, which searches stored documents (e.g., Obsidian notes) and returns relevant snippets.

The `conversation_id` used here is the same id created and managed by the `/ask` handler and stored in `ChatSession`. This ensures that prompt building always sees the correct history for the current conversation.

## Dependencies and call flow

High-level call flow:

1. `/ask` handler receives a request and ensures there is a valid `conversation_id` (creating a `ChatSession` in storage if needed).
2. The handler calls a message processor (e.g., `FunctionCallingProcessor`).
3. The processor calls `PromptBuilder.build_prompt(...)` with:
   - `content_text` = current user message
   - `conversation_id` = storage-backed session id
   - `agent_name`, `account_name`, `context_type`, `context_name`
4. `PromptBuilder` uses:
   - `AgentManager` to load agent config and build system messages.
   - `Storage` to load chat history and documents.
   - `ContextManager` (backed by storage) to load named contexts.
5. The processor sends the resulting `messages` array to the model.
6. The processor then appends the new user and assistant messages to storage via `Storage.append_chat_message(...)`.

This keeps prompt building, storage, and conversation management aligned: the same `conversation_id` is used for both reading history (prompt building) and writing new messages (storage).
