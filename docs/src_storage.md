# Documentation for `src/storage` Module

## Summary

`src/storage` contains Lucy's application storage contracts and generic storage
implementations. It owns file/SQLite persistence used directly by Lucy, but it
no longer owns sqlite-vec or vec0 persistence.

## Main storage types

- `Storage` / `JsonFileStorage`: Lucy's general application storage.
- `ContextStore`, `TasklistStore`, `DocumentStore`, `EmbeddingStore`: storage
  interfaces consumed by Lucy.
- `PrimitivesEmbeddingStore`: generic embedding-store implementation over the
  Chat2/generic-store primitives.
- `EmbeddingRecord`: Lucy's embedding record model.

## Embedding backends

Lucy supports two explicit `embedding_store_backend` values:

| Backend | Implementation |
| --- | --- |
| `file` | `PrimitivesEmbeddingStore` over `FileChat2Primitives` |
| `sqlite` | `PrimitivesEmbeddingStore` over `SqliteChat2Primitives` |

When the setting is omitted, Lucy continues to use the embedding behavior of
the shared `JsonFileStorage` instance.

`sqlite_vec` is intentionally not a Lucy backend. Native sqlite-vec loading,
vec0 schema management, KNN querying, and vec0 migration utilities are owned by
`galet-memory`.

## Source files

| File | Responsibility |
| --- | --- |
| `base.py` | Base storage abstraction |
| `interfaces.py` | Context/document/tasklist/embedding store interfaces |
| `json_file_storage.py` | JSON/file-backed Lucy storage |
| `json_file_storage_parts/` | Mixins for contexts, documents, embeddings and tasklists |
| `models.py` | Storage data models including `EmbeddingRecord` |
| `primitives_embedding_store.py` | Generic file/SQLite embedding store |

## Boundary with galet-memory

Lucy should depend on memory/storage contracts rather than native vector-index
implementation details. Code that needs sqlite-vec directly belongs in
`galet-memory`, including:

- sqlite-vec native extension loading;
- vec0 table DDL and validation;
- vector-index KNN behavior;
- vec0 migration and schema-conversion scripts;
- implementation-specific sqlite-vec tests.

This keeps Lucy's storage tests platform-neutral and leaves native vector-store
behavior independently testable in `galet-memory`.
