# Lucy semantic memory adapter

All memory contracts and models are supplied by `galet-memory`. Import semantic
types from `galet_memory.semantic` and procedural types from `galet_memory`.
This package retains only Lucy's `SqliteVecSemanticMemory` implementation for
the fallback path without a shared memory configuration.

The retired `ContextProceduralMemory` adapter and duplicate local contracts have
been removed. Procedural memory is composed in `src/procedural_memory_config.py`
using Galet's `FileProceduralMemory` or the shared runtime. Galet's procedural
request defaults to `create_if_missing=False`; prompt recall does not create
missing contexts.

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

Contract: `galet_memory.semantic.SemanticMemory.recall(SemanticMemoryRequest)`.

### Procedural memory

Prompts and tools use Galet's procedural memory, including context and skill
resolution, required tools and search namespaces. Lucy converts the resolved
result to its `Context` representation where tool eligibility needs it.

Contract: `galet_memory.ProceduralMemory.recall(ProceduralMemoryRequest)`.

## Architectural boundary

Galet owns memory contracts and reusable implementations. Lucy owns application
configuration, process lifetime and integration adapters.

Expected direction:

- PromptBuilder depends on recall interfaces.
- Chat handlers and `/chats` endpoints may eventually share an
  `EpisodicMemoryManager` adapter.
- Semantic adapters depend on Lucy's `DocumentStore`, `EmbeddingStore` and
  embedding facade internally.
- Procedural memory is supplied directly by Galet and returns resolved context
  state without exposing storage/import mechanics to PromptBuilder.

## Next step

Replace the remaining local semantic recall implementation with Galet's
`VectorSemanticMemory`, preserving Lucy's embedding-store integration and file
loading behavior, then remove this package. The shared memory path already
delegates semantic recall to the configured Galet runtime.
