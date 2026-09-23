# CoALA memory scaffold

This package contains Lucy-specific semantic and procedural memory adapters.
Episodic memory is supplied directly by `galet-memory`.

## Mapping from current Lucy code

### Episodic memory

Prompt-time sources:

- The Galet prompt-builder receives the `galet-memory` episodic interface.
- `SqliteEpisodicMemory` supplies session metadata and conversational events.
- `_get_digest_context()` performs similarity lookup over archived chat digests.
- `_save_overflow_digest()` persists history dropped by the prompt token budget.

Lifecycle and curation sources:

- `src/handlers/episodic_memory_handler.py` exposes session lifecycle
  operations (create, get, list, update, reset, delete), append_event and
  recall over the `galet-memory` interface.
- `src/handlers/curate_chat_handler.py` adds summarize/archive workflows,
  preview/publish controls, templates and digest embedding publication.
- `src/http_endpoints/chats_endpoints.py` exposes session create/get/list,
  append-message, update and delete operations.
- `app.py` wires those operations into `/chats` and also resolves or creates
  sessions for `/ask` via `resolve_or_create_session()`.

Storage structure:

- `container_config.py` constructs `galet_memory.SqliteEpisodicMemory` at the
  composition root. Application code depends only on Galet interfaces.
- `src/chat2` temporarily retains generic document/log primitives used by the
  embedding store; it no longer contains Lucy's episodic storage facade.
- Archived digest similarity search is injected because those digests
  currently live in Lucy's embedding subsystem.

Contracts:

- `EpisodicMemory.recall(EpisodicMemoryRequest)` is the prompt-time read seam.
- `EpisodicMemory.save_overflow_digest(...)` owns prompt overflow persistence.
- `EpisodicMemoryManager` owns session lifecycle plus filter/summarize/archive
  curation. It is deliberately separate from HTTP and handler schemas.
- `SqliteEpisodicMemory` implements both contracts; Lucy handlers and curation
  code do not depend on its storage medium.

### Semantic memory

Prompt-time sources:

- `_get_document_embedding_context()` -> embedding facade + `EmbeddingStore`.
- `get_document_context()` -> `DocumentStore`, normally `obsidian_note` records
  filtered by context tag.

Embedding infrastructure:

- `src/handlers/semantic_memory_handler.py` exposes recall over semantic
  memory plus the embed, compare, rank and models utilities (absorbed from the
  retired embedding_handler).
- The memory boundary absorbed those vector utilities: semantic memory owns the
  higher-level operation "retrieve durable knowledge relevant to this query"
  (recall) alongside the embed, compare, rank and models utilities, while the
  raw stored-vector search operation was retired in favour of recall.
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
PromptBuilder output against the current episodic/document/context reads
before replacing those calls.
