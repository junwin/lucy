# Lucy memory integration

`galet-memory` owns memory contracts, retrieval logic and reusable storage
implementations. Lucy owns application configuration, process lifetime and
adapters to its embedding facade and storage interfaces. The retired
`src/coala_memory` package is no longer needed.

## Shared memory configuration

`src/memory_config.py` owns one process-wide Galet runtime selected by
`memory_config_path` or `GALET_MEMORY_CONFIG_PATH`. Prompts, tools, curation and
HTTP search share that runtime. An invalid selected configuration raises rather
than falling back. Changing the selected source requires a process restart.

`ConfiguredSemanticMemory` retains configured embedding-profile selection for
HTTP and tool requests. It uses the canonical Galet request with the selected
model, preserving the other request fields. Configured prompt compilation
borrows the runtime directly.

## Fallback semantic recall

Without a shared memory configuration, `src/semantic_memory_config.py` composes
Galet's `VectorSemanticMemory` using the adapters in
`src/embeddings/memory_adapters.py`:

- `LucyEmbeddingProvider` delegates embedding generation to `EmbeddingFacade`.
- `LucyEmbeddingIndex` translates Lucy's stored records and queries to Galet's
  embedding ports, including account-scoped namespace listing. Digest
  publication and recall use the same adapters.
- `LucyTextLoader` retains Lucy's home-directory expansion, truncation and
  log-and-skip behavior for unreadable source files.

The container injects its episodic store into semantic recall so Galet can
exclude digests invalidated by exchange corrections. Standalone semantic tools
use `FileDigestValidator` against the same configured episodic database path.
It opens and closes a connection for each validation, does not create missing
files or initialize schemas, and delegates validity rules to Galet.

Semantic retrieval metadata now identifies the recall implementation as
`backend: vector`, including when the embedding store uses sqlite-vec. Galet
also supports inline `metadata.text` sources. No keyword fallback is configured
for the legacy embedding-store path.

The prompt adapter passes canonical semantic memory directly to the Galet
compiler; it no longer translates between duplicate request types. Tool
embedding utilities retain their separate embedding facade.

## Episodic memory

Lucy injects one `LucyEpisodicStore` backend implementing Galet's separate
`SessionStore`, `EventStore` and `CurationStore` protocols. Operations are
account-scoped. Sessions have no event collection or owning agent;
`metadata.default_agent` is an initial routing/display hint, while events retain
their actual actors.

Recording uses `NewEvent` and `append_events`, with correlation IDs stored in
the same append. Prompts and HTTP history use active snapshots. Corpus
extraction uses transcript snapshots, preserving archived conversation while
excluding invalidated exchanges. `curate_chat` archives through
`CurationService`; `reset_session` resets prompt context while retaining the
transcript. Destructive filter/rewrite curation is rejected in favor of exchange
invalidation.

The fallback database is
`<storage_root_path>/<storage_namespace>/episodic-v2.sqlite`.
`episodic_memory_db_path` overrides it. Older schemas are rejected; no automatic
migration or deletion occurs.

## Procedural memory

`src/procedural_memory_config.py` selects Galet's `FileProceduralMemory` or the
shared runtime. Prompt and tool recall share context and skill resolution,
required tools and search namespaces. Galet's request defaults to
`create_if_missing=False`. Lucy converts resolved state to its `Context`
representation where tool eligibility needs it.
