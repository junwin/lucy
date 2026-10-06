# CoALA memory scaffold

This package contains Lucy-specific semantic and procedural memory adapters.
Episodic memory is supplied directly by `galet-memory`.

## Mapping from current Lucy code

### Episodic memory

Lucy injects one `LucyEpisodicStore` backend implementing Galet's separate
`SessionStore`, `EventStore` and `CurationStore` protocols. Every operation is
account-scoped. Session metadata has no event collection or owning agent;
`metadata.default_agent` is Lucy's initial routing/display hint, while events
retain their actual actors.

The prompt compiler receives this backend as both `episodic_memory` and
`digest_memory`. It reads recent events separately from digest search and uses
an active snapshot to preserve the latest archive boundary digest.

Recording uses `NewEvent` and `append_events`, with correlation IDs stored in
the same append. HTTP chat history uses an active snapshot. Routing reads only
recent conversational event kinds. Corpus extraction uses the transcript
snapshot, retaining archived conversation but excluding invalidated exchanges.

The `episodic_memory` handler advertises galet-tools' explicit actions, including
`get_recent_events`, `clear_session_events` and `invalidate_exchange`.
`curate_chat` archives through `CurationService`; `reset_session` calls
`reset_context`, preserving the transcript while hiding previous prompt context.
Destructive filter/rewrite curation is rejected; use exchange invalidation.

The default database is `<storage_root_path>/<storage_namespace>/episodic-v2.sqlite`.
An explicit `episodic_memory_db_path` overrides it and must name a fresh database.
Older schemas are rejected by Galet; no migration or automatic deletion occurs.

`GET`, `PATCH` and `DELETE /chats/<session_id>` and message appends require
`accountName`. GET and DELETE take the query parameter; PATCH and message
appends also accept it in the JSON body. An absent account returns 400; a
session outside the supplied account returns 404. Chat listing and friendly
name resolution span the account's sessions across agents.

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
