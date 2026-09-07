# CoALA memory scaffold

This package introduces typed seams around the memory access already performed
inside `src/prompt_builders/prompt_builder.py`.  It does **not** yet change
PromptBuilder behaviour.

## Mapping from PromptBuilder

### Episodic memory

Current sources:

- `Chat2Store.get_session()` for session metadata.
- `Chat2Store.session_exists()` / `stream_events()` for recent conversation
  events.
- `_get_digest_context()` for semantic lookup of archived chat digests.
- `_save_overflow_digest()` for history dropped by the prompt token budget.

Contract: `EpisodicMemory.recall(EpisodicMemoryRequest)` plus
`save_overflow_digest(...)`.

### Semantic memory

Current sources:

- `_get_document_embedding_context()` -> embedding facade + `EmbeddingStore`.
- `get_document_context()` -> `DocumentStore`, normally `obsidian_note` records
  filtered by context tag.

Contract: `SemanticMemory.recall(SemanticMemoryRequest)`.  The request keeps
`use_embeddings`, namespaces, tag, top-k, character limit and score threshold
explicit because PromptBuilder currently makes decisions using all of them.

### Procedural memory

Current source:

- `_get_context_state()` -> `ContextStore.get_or_create_context()`.
- `_get_context_text()` -> `Context.resolved_text`.
- `Context.resolved_skills`, `required_tools`, `search_namespaces`, `tag` and
  `missing_imports`.

The resolved Context already combines the intrinsic context body with imported
skill bodies.  That makes it the natural Lucy representation of procedural
memory.

Contract: `ProceduralMemory.recall(ProceduralMemoryRequest)`.

## Next step

Implement adapters around Lucy's current `Chat2Store`, `DocumentStore` /
`EmbeddingStore`, and `ContextStore`, then inject those interfaces into
PromptBuilder.  PromptBuilder should remain responsible for prompt composition
and token budgeting; the CoALA modules should own memory retrieval and memory
source details.
