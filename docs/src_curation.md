---
tags:
  - src_curation
  - lucyproject
  - CurationEngine
  - resolve_session
  - summarize_session
  - archive_session
  - render_template
  - resolve_template
  - SUMMARIZE_SYSTEM_PROMPT
  - FALLBACK_TEMPLATE
  - DEFAULT_SUMMARIZE_TEMPLATE
---

## 1. Summary

`src/curation` is the chat curation library. It provides the core logic for three curation modes on chat sessions: **filter** (rule-based event removal), **summarize** (LLM-powered digest generation), and **archive** (summarize + archive original events + replace with digest). The module is the engine behind both the `curate_chat` tool handler and any CLI or automated curation workflows.

It sits between the handler layer (`src/handlers/curate_chat_handler.py`) and the lower-level services (`src/chat2` for session storage, `src/llm` for LLM calls). The problem it solves: sessions accumulate hundreds of tool-call/result events that obscure the meaningful conversation. Curation distills a session down to decisions, file changes, and outcomes — either by filtering, by asking an LLM to summarize, or by fully archiving and replacing the session.

## 2. Architecture & Design

### Orchestrator pattern

`CurationEngine` is the single entry point. It owns references to `Chat2Store` (session I/O), `LLMApi` (summarization), and two output directories (`digests_root`, `archives_root`). Its `curate()` method dispatches to one of three private mode methods based on `mode`:

| Mode | Method | Side effects |
|------|--------|-------------|
| `filter` | `_mode_filter()` | Rewrites session events in-place |
| `summarize` | `_mode_summarize()` | Generates digest via LLM; optionally writes to disk |
| `archive` | `_mode_archive()` | Summarizes, writes digest, archives original events, replaces session with digest |

### Function-level delegation

The three non-core operations are implemented as standalone module-level functions rather than methods on the engine:

- **`resolve_session()`** — resolves a session by ID or friendly name (used by the handler directly and also called internally by the engine via `curate()`).
- **`summarize_session()`** — takes a list of `ChatEvent`, calls the LLM, returns a Markdown digest string. Includes a fallback path that produces a plain event listing if the LLM call fails.
- **`archive_session()`** — moves original events to a timestamped JSONL file under `archives_root`, then replaces the session with a single digest event.
- **`render_template()`** / **`resolve_template()`** — template resolution (ContextState override → built-in → hardcoded fallback) and placeholder substitution.

### Template resolution order

1. **ContextState override** — if a `context_state_template` string is passed, it wins unconditionally.
2. **Built-in config templates** — `"default"` resolves to `DEFAULT_SUMMARIZE_TEMPLATE`, `"minimal"` resolves to `FALLBACK_TEMPLATE`.
3. **Fallback hardcoded template** — `FALLBACK_TEMPLATE` is the last resort for any unrecognized template name.

This three-tier resolution allows account-scoped template customization via ContextState without changing code.

### Preview vs. publish

Every mode supports a `preview` flag. When `True`, the result dict includes `note_text` but writes nothing to disk. When `publish=True`, digests are written to `<digests_root>/<account>/<session_id>_<timestamp>.md`. The archive mode additionally writes original events to `<archives_root>/<account>/<session_id>_<timestamp>.jsonl`.

### No exceptions from this module

The module defines zero custom exception classes. All error handling is done via:
- `try`/`except` with `logger.exception()` and graceful fallbacks (e.g., `_fallback_digest()` in summarizer)
- Result dicts with `"status": "error"` and an `"error"` string field
- Boolean return values (`archive_session` returns `False` on failure)

## 3. Key Classes

| Class | Base/Parent | Purpose |
|-------|-------------|---------|
| `CurationEngine` | (none) | High-level orchestrator: resolves sessions, dispatches by mode, writes output files |

## 4. Source Files

| File | Responsibility | Notable Exports |
|------|---------------|-----------------|
| `__init__.py` | Package exports | `CurationEngine`, `resolve_session`, `render_template`, `resolve_template`, `summarize_session`, `archive_session` |
| `core.py` | `CurationEngine` class — orchestration, mode dispatch, file I/O | `CurationEngine` |
| `resolver.py` | Session resolution by ID or friendly name (index.json + fallback) | `resolve_session` |
| `summarizer.py` | LLM-based summarization of events into Markdown digest | `summarize_session`, `SUMMARIZE_SYSTEM_PROMPT` |
| `archiver.py` | Archive original events to JSONL, replace session with digest event | `archive_session` |
| `templates.py` | Template resolution (3-tier) and placeholder rendering | `resolve_template`, `render_template`, `FALLBACK_TEMPLATE`, `DEFAULT_SUMMARIZE_TEMPLATE` |

## 5. Dependencies

### Standard library
`json`, `logging`, `datetime` (datetime, timezone), `pathlib` (Path), `typing` (Any, Dict, List, Optional), `__future__` (annotations)

### Third-party packages
None directly. The module uses only standard library and internal Lucy modules.

### Internal modules
- `src.chat2.facade` — `Chat2Store` (session CRUD, event streaming, reset/add)
- `src.chat2.models` — `ChatEvent`, `ChatSessionMeta` (data models)
- `src.llm.interface` — `LLMApi` (protocol for LLM calls)
- `src.llm.dto` — `LLMResponse` (type hint only, in summarizer)

### Optional dependencies
None. All imports are unconditional.

## 6. Configuration / Settings

This module reads **no config keys directly**. All configuration is injected via constructor or function parameters:

| Parameter | Passed by | Default | What it controls |
|-----------|-----------|---------|------------------|
| `digests_root` | `CurateChatHandler` → `CurationEngine.__init__()` | `Path("data/digests")` | Directory for digest `.md` output files |
| `archives_root` | `CurateChatHandler` → `CurationEngine.__init__()` | `Path("data/archives")` | Directory for archive `.jsonl` files |
| `chats_index_path` | `CurateChatHandler` → `CurationEngine.__init__()` | `None` | Optional path to `index.json` for friendly-name resolution |
| `llm_model` | `CurateChatHandler` (reads `curation_llm_model` from config, default `"gpt-4o-mini"`) → `CurationEngine.__init__()` | `"gpt-4o-mini"` | LLM model used for summarization |
| `llm_api` | `CurateChatHandler` → `CurationEngine.__init__()` | (required) | LLMApi instance for LLM calls |
| `chat2_store` | `CurateChatHandler` → `CurationEngine.__init__()` | (required) | Chat2Store instance for session I/O |

The handler layer (`src/handlers/curate_chat_handler.py`) owns config reading; the curation module itself is config-free.

## 7. Exceptions

**None.** No custom exception classes are defined in this module.

Error handling patterns:
- `archive_session()` catches `Exception` around file writes and returns `False`
- `summarize_session()` catches `Exception` around the LLM call and returns `_fallback_digest()`
- `resolve_session()` catches `Exception` around `index.json` reads and falls through to the session-listing path
- `CurationEngine._mode_*()` methods return result dicts with `"status": "error"` on failure

## 8. Module-Level Constants

| Constant | File | Value / Purpose |
|----------|------|-----------------|
| `SUMMARIZE_SYSTEM_PROMPT` | `summarizer.py` | System prompt instructing the LLM how to distill chat events into a structured digest (decisions, files, commands, next steps) |
| `FALLBACK_TEMPLATE` | `templates.py` | Minimal hardcoded template used when no named template matches: `# Session Digest: {friendly_name}` with session ID, date, account, summary, and event bullets |
| `DEFAULT_SUMMARIZE_TEMPLATE` | `templates.py` | Built-in `"default"` template: sections for decisions, files, commands, next steps |
| `_BUILTIN_TEMPLATES` | `templates.py` | Dict mapping template names to strings: `{"default": DEFAULT_SUMMARIZE_TEMPLATE, "minimal": FALLBACK_TEMPLATE}` |

## 9. Methods (by class)

### CurationEngine

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `__init__` | instance | `(self, chat2_store: Chat2Store, llm_api: LLMApi, llm_model: str = "gpt-4o-mini", digests_root: Optional[Path] = None, archives_root: Optional[Path] = None, chats_index_path: Optional[Path] = None) -> None` | Stores all dependencies. `digests_root` and `archives_root` default to `Path("data/digests")` and `Path("data/archives")` respectively. `chats_index_path` defaults to `None` (friendly-name resolution falls back to listing sessions). |
| `curate` | instance | `(self, *, session_id: Optional[str] = None, friendly_name: Optional[str] = None, account: str, mode: str = "filter", preview: bool = True, publish: bool = False, template_name: str = "default", context_state_template: Optional[str] = None, curation_rules: Optional[Dict[str, Any]] = None) -> Dict[str, Any]` | Main entry point. Resolves the session (calls `resolve_session`), reads all events, dispatches to `_mode_filter`, `_mode_summarize`, or `_mode_archive`. Returns a result dict with `status` (`"preview"`, `"published"`, `"archived"`, or `"error"`), `note_text`, `output_path`, and `session_id`. If session resolution fails, returns `{"status": "error", "error": ...}`. All parameters are keyword-only. |
| `_mode_filter` | instance | `(self, sid: str, events: List[ChatEvent], rules: Dict[str, Any], account: str, friendly_name: str) -> Dict[str, Any]` | Applies rule-based filtering. Supports `remove_kinds` (list of kind strings to drop), `keep_roles` (list of role strings to retain — all others dropped), and `deduplicate` (bool, drops events with identical payloads). Resets the session events and rewrites only the kept events. Returns counts of original, kept, and removed events broken down by removal reason. Side effect: mutates session events in storage. |
| `_mode_summarize` | instance | `(self, sid: str, events: List[ChatEvent], account: str, friendly_name: str, template_name: str, context_state_template: Optional[str], preview: bool, publish: bool) -> Dict[str, Any]` | Calls `summarize_session()` for LLM digest, then `resolve_template()` + `render_template()` to produce final note text. If `preview=True`, returns the text without writing. If `publish=True`, calls `_write_digest()` to persist. Does not modify session events. |
| `_mode_archive` | instance | `(self, sid: str, events: List[ChatEvent], account: str, friendly_name: str, template_name: str, context_state_template: Optional[str], preview: bool, publish: bool) -> Dict[str, Any]` | Same as `_mode_summarize` for digest generation, plus calls `archive_session()` to move original events to archive and replace the session with the digest. If `preview=True`, skips all writes. If `archive_session()` fails, returns error. Returns `"archived"` status on success. |
| `_timestamp` | static | `() -> str` | Returns current UTC time as a compact string like `"20250115T143022Z"`. Used for archive and digest filenames. |
| `_write_digest` | instance | `(self, session_id: str, account: str, note_text: str) -> Path` | Creates `<digests_root>/<account>/` if needed, writes `note_text` to `<session_id>_<timestamp>.md`. Returns the output `Path`. Logs at INFO level. |

### Module-level functions

#### resolve_session (resolver.py)

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `resolve_session` | function | `(*, session_id: Optional[str] = None, friendly_name: Optional[str] = None, account: str, chat2_store: Chat2Store, chats_index_path: Optional[Path] = None) -> Optional[ChatSessionMeta]` | Resolves a session to its `ChatSessionMeta`. Resolution order: (1) direct `session_id` takes precedence; (2) if `friendly_name` given, tries `index.json` lookup first (case-insensitive, tie-breaks by `updated_at` descending), then falls back to listing sessions via `chat2_store.list_sessions()`. Returns `None` if no match. All parameters are keyword-only. Logs warnings for missing sessions and empty friendly names; logs exceptions from `index.json` reads. |

#### summarize_session (summarizer.py)

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `summarize_session` | function | `(events: List[ChatEvent], *, llm_api: LLMApi, model: str = "gpt-4o-mini", friendly_name: str = "", session_id: str = "", account: str = "", temperature: float = 0.0) -> str` | Builds a text representation of events (truncated to 32,000 chars via `_build_events_text`), constructs a system+user prompt, and calls `llm_api.create_response()`. Returns the LLM's digest text. If the LLM call raises any exception, logs it and returns `_fallback_digest()` (a plain event listing). Temperature defaults to 0.0 for deterministic output. |
| `_build_events_text` | function | `(events: List[ChatEvent], max_chars: int = 32000) -> str` | Iterates events, formats each as `[timestamp] role/actor (kind): payload[:500]`. Stops when total character count exceeds `max_chars`, appending `"... (truncated)"`. |
| `_fallback_digest` | function | `(events: List[ChatEvent], *, friendly_name: str = "", session_id: str = "") -> str` | Produces a simple Markdown listing: a heading, then one bullet per event with role, kind, and payload snippet (first 200 chars). No LLM call. |

#### archive_session (archiver.py)

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `archive_session` | function | `(session_id: str, digest_text: str, *, chat2_store: Chat2Store, archive_dir: Path, account: str) -> bool` | Reads all events from the session, writes them as JSONL to `<archive_dir>/<account>/<session_id>_<timestamp>.jsonl`, then calls `_replace_with_digest()` to reset the session and insert a single digest event. Returns `True` on success, `False` if the session is not found or the archive file write fails. If there are no events, skips the archive write but still inserts the digest. |
| `_replace_with_digest` | function | `(chat2_store: Chat2Store, session_id: str, digest_text: str) -> None` | Calls `chat2_store.reset_events(session_id)` then adds a single `ChatEvent` with `role="system"`, `actor="curation"`, `kind="summary"`, `payload=digest_text`, and metadata including `curation_mode: "archive"` and an ISO timestamp. |
| `_timestamp` | function | `() -> str` | Returns current UTC time as compact string `"YYYYMMDDTHHMMSSZ"`. Used for archive filenames. |

#### Templates (templates.py)

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `resolve_template` | function | `(template_name: str, *, context_state_override: Optional[str] = None) -> str` | Resolves a template by name. Priority: (1) `context_state_override` string if provided, (2) `_BUILTIN_TEMPLATES` dict lookup, (3) `FALLBACK_TEMPLATE`. Logs which source was used at INFO level. |
| `render_template` | function | `(template: str, *, friendly_name: str = "", session_id: str = "", account: str = "", events: Optional[List[ChatEvent]] = None, summary_text: str = "", decisions: str = "", files: str = "", commands: str = "", next_steps: str = "", **extra: Any) -> str` | Substitutes `{placeholder}` values in the template string. Builds `events_bullets` from the event list (one bullet per event, first 120 chars of payload). Adds a `date` placeholder from current UTC time. Uses `str.format(**context)`; if a `KeyError` occurs (missing placeholder), falls back to manual string replacement so unknown placeholders are left as-is rather than crashing. Additional `**extra` kwargs become template variables. |

## 10. Usage Examples

### Example 1: Preview a summary digest

```python
from pathlib import Path
from src.curation.core import CurationEngine
from src.chat2.facade import Chat2Store

engine = CurationEngine(
    chat2_store=chat2_store,
    llm_api=llm_api,
    llm_model="gpt-4o-mini",
    digests_root=Path("data/digests"),
    archives_root=Path("data/archives"),
)

result = engine.curate(
    friendly_name="my-session",
    account="junwin",
    mode="summarize",
    preview=True,      # don't write to disk
    template_name="default",
)

print(result["status"])      # "preview"
print(result["note_text"])   # Rendered Markdown digest
```

### Example 2: Archive a session (full replacement)

```python
result = engine.curate(
    session_id="7bc95f9c-d88f-4023-8ecd-c94e4ede2a39",
    account="junwin",
    mode="archive",
    preview=False,
    publish=True,
    template_name="minimal",
)

# result["status"] == "archived"
# Original events saved to data/archives/junwin/<sid>_<ts>.jsonl
# Digest saved to data/digests/junwin/<sid>_<ts>.md
# Session events replaced with a single digest event
```

### Example 3: Direct summarization without the engine

```python
from src.curation.summarizer import summarize_session

digest_md = summarize_session(
    events,
    llm_api=llm_api,
    model="gpt-4o-mini",
    friendly_name="my-session",
    account="junwin",
)
```

## 11. Edge Cases & Gotchas

1. **Archive mode is destructive.** `_mode_archive()` calls `archive_session()` which calls `chat2_store.reset_events(session_id)` — all original events are wiped and replaced with a single digest event. The original events are preserved in the JSONL archive file, but the live session is permanently altered. Use `preview=True` first to review the digest before committing.

2. **Summarization has a 32K character truncation limit.** `_build_events_text()` hard-caps event text at 32,000 characters. For very long sessions, the LLM only sees the first ~32K chars of event data. Events beyond the cap are silently dropped with only a `"... (truncated)"` marker. No warning is logged when truncation occurs.

3. **LLM failure is silent (with fallback).** If `summarize_session()`'s LLM call raises any exception, it returns `_fallback_digest()` — a plain event listing with no AI summarization. The caller receives a valid string and sees `"preview"` or `"published"` status; the only indication of failure is a log entry at ERROR level and a structurally different digest. Callers cannot distinguish "LLM succeeded" from "LLM failed, used fallback" without inspecting the digest content.

4. **Friendly-name resolution is case-insensitive with tie-breaking.** `resolve_session()` lowercases both the query and stored names. If multiple sessions share the same friendly name (same account), it sorts by `updated_at` descending and picks the most recent. This is deterministic but may surprise users who expect an error for ambiguous names.

5. **`index.json` is optional and silently skipped.** If `chats_index_path` is not provided or the file does not exist, `resolve_session()` falls through to listing sessions via `chat2_store.list_sessions(limit=100)`. If there are more than 100 sessions for the account, sessions beyond the 100th will not be found by friendly name.

6. **Filter mode rewrites events in-place with no undo.** `_mode_filter()` calls `chat2_store.reset_events(sid)` then re-adds the filtered events. There is no archive or backup. If a filter rule accidentally removes too much, the original events are gone.

7. **Template `KeyError` handling is best-effort.** `render_template()` first tries `str.format(**context)`. If a placeholder in the template has no corresponding key in context, Python raises `KeyError`. The except block falls back to iterating known keys with `str.replace()`. Unknown placeholders (typos, custom vars not in `**extra`) are left as literal `{something}` in the output.

8. **`archive_session` succeeds even with zero events.** If a session has no events, `archive_session()` skips the archive file write (log at INFO) but still calls `_replace_with_digest()` to insert the digest event. Returns `True`.

9. **No thread safety.** Neither `CurationEngine` nor any module-level function uses locking. Concurrent curation on the same session (e.g., two archive operations) will race — one may archive an already-emptied session.

10. **Template resolution ignores the template_name when ContextState override is active.** If `context_state_override` is provided, it is returned verbatim regardless of `template_name`. The name is only used for logging.

## 12. Consumers

| Consumer | What it uses |
|----------|-------------|
| `src/handlers/curate_chat_handler.py` | `CurationEngine` — instantiates and calls `engine.curate()` for all three modes; `resolve_session` — used to validate session existence before building the engine |
| `src/handlers/registry_bootstrap.py` | `CurateChatHandler` — registers the handler in the FCP tool registry (indirect consumer via handler) |
| `src/handlers/chat2_handler.py` | **None** — has its own `_curate_session()` method that implements filtering in-place without using `src/curation`. This is legacy duplication; the `curation_rules` parameter schema is shared but the implementation is independent. |
