# CoALA memory scaffold

This package introduces typed seams around the memory access already performed
inside `src/prompt_builders/prompt_builder.py` and related chat/curation APIs.
It does **not** yet change runtime behaviour.

## Mapping from current Lucy code

### Episodic memory

Prompt-time sources:

- `PromptBuilder` uses `Chat2Store.get_session()` for session metadata.
- `PromptBuilder` uses `session_exists()` / `stream_events()` for recent
  conversational events.
- `_get_digest_context()` performs similarity lookup over archived chat digests.
- `_save_overflow_digest()` persists history dropped by the prompt token budget.

Lifecycle and curation sources:

- `src/handlers/chat2_handler.py` exposes reset, search, curate, get, list,
  delete and update operations over Chat2 sessions.
- `src/handlers/curate_chat_handler.py` adds summarize/archive workflows,
  preview/publish controls, templates and digest embedding publication.
- `src/http_endpoints/chats_endpoints.py` exposes session create/get/list,
  append-message, update and delete operations.
- `app.py` wires those operations into `/chats` and also resolves or creates
  sessions for `/ask` via `resolve_or_create_session()`.

Storage/facade structure:

- `src/chat2/facade.py` is the high-level session/event API and is the natural
  adaptation point for CoALA episodic memory.
- `src/chat2/sqlite/backend.py` implements the generic Chat2 document/log
  primitives using SQLite (`kv` + append-only `logs`, WAL mode). It should stay
  in `src/chat2`; CoALA should not duplicate its storage mechanics.
- `Chat2EpisodicMemory` wraps `Chat2Store`, so it works with SQLite, JSONL or
  other Chat2 primitive backends.
- `Chat2EpisodicMemory.from_sqlite(db_path)` is a convenience constructor using
  `SqliteChat2Primitives` for the concrete SQLite deployment.
- Archived digest similarity search is optional/injected because those digests
  currently live in Lucy's embedding subsystem, not in the Chat2 SQLite store.

Contracts:

- `EpisodicMemory.recall(EpisodicMemoryRequest)` is the prompt-time read seam.
- `EpisodicMemory.save_overflow_digest(...)` owns prompt overflow persistence.
- `EpisodicMemoryManager` owns session lifecycle plus filter/summarize/archive
  curation. It is deliberately separate from HTTP and handler schemas.
- `Chat2EpisodicMemory` implements both contracts over the existing Chat2
  facade; curation can be supplied by injecting the existing curation engine.

### Semantic memory

Prompt-time sources:

- `_get_document_embedding_context()` -> embedding facade + `EmbeddingStore`.
- `get_document_context()` -> `DocumentStore`, normally `obsidian_note` records
  filtered by context tag.

Embedding infrastructure:

- `src/handlers/embedding_handler.py` exposes raw embed, compare, rank and
  stored-vector search operations.
- The memory boundary should *not* absorb all of those vector utilities.
  Embedding generation/comparison is infrastructure; semantic memory owns the
  higher-level operation "retrieve durable knowledge relevant to this query".
- The handler confirms that embedding model, namespace, account, top-k and
  source_type are real vector-search parameters, so the semantic request keeps
  those retrieval-relevant fields explicit.
- `SqliteVecSemanticMemory` adapts the existing `EmbeddingStore`; production can
  supply `Vec0EmbeddingStore` without moving sqlite-vec persistence into CoALA.

Contract: `SemanticMemory.recall(SemanticMemoryRequest)`.

### Procedural memory

Current sources:

- `_get_context_state()` -> `ContextStore.get_or_create_context()`.
- `_get_context_text()` -> `Context.resolved_text`.
- `Context.resolved_skills`, `required_tools`, `search_namespaces`, `tag` and
  `missing_imports`.

The resolved Context already combines the intrinsic context body with imported
skill bodies. That makes it the natural Lucy representation of procedural
memory.

Contract: `ProceduralMemory.recall(ProceduralMemoryRequest)`.

## Architectural boundary

The CoALA package is a domain layer, not a replacement API layer.

Expected direction:

- PromptBuilder depends on recall interfaces.
- Chat handlers and `/chats` endpoints may eventually share an
  `EpisodicMemoryManager` adapter.
- Semantic adapters depend on Lucy's `DocumentStore`, `EmbeddingStore` and
  embedding facade internally.
- Procedural adapters depend on `ContextStore` and return fully-resolved context
  state without exposing storage/import mechanics to PromptBuilder.

## Next step

Wire the concrete adapters through Lucy's dependency/container setup and compare
PromptBuilder output against the current direct Chat2/document/context reads
before replacing those calls.
