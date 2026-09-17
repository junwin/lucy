# Repository Index

Repository: `lucy`
Python files: 331
Git commit: `eb70a5da92fae1a34bb93a4c45c7e9eb85f30d07`

---

## `_debug_kw.py`

> Check POS tagging for 'endpoints' in different contexts.

**Imports**

- `spacy`
- `src.keywords.keywords: Keywords`

## `_grep_sandbox.py`

**Imports**

- `subprocess`
- `sys`

## `_test_sandbox.py`

> Smoke test for sandbox_execute — all tools + continue_on_error.

**Imports**

- `json`
- `src.config_manager: ConfigManager`
- `src.handlers.registry_bootstrap: build_registry`

**Functions**

- `_print_steps(result)` — line 11

## `app.py`

**Imports**

- `flask: Flask, request, jsonify, send_file, make_response, Response`
- `flask_cors: CORS`
- `flask_swagger_ui: get_swaggerui_blueprint`
- `logging`
- `logging.handlers: RotatingFileHandler`
- `os`
- `src.agent: AgentManager`
- `src.api_key: validate_api_key`
- `src.chat2.facade: Chat2Store`
- `src.coala_memory.episodic: EpisodicMemoryManager`
- `src.coala_memory.semantic: SemanticMemory`
- `src.config_manager: ConfigManager`
- `src.container_config: container`
- `src.http_endpoints.agents_endpoints: get_agents_impl`
- `src.http_endpoints.chats_endpoints: post_chat_impl, get_chats_impl, get_chat_impl, post_chat_message_impl, delete_chat_impl, update_chat_impl`
- `src.http_endpoints.context_endpoints: list_context_names_impl`
- `src.http_endpoints.documents_endpoints: search_documents_impl`
- `src.http_endpoints.metrics_endpoints: get_metrics_runs_impl`
- `src.http_endpoints.prompt_builder_debug_endpoints: prompt_builder_debug_impl`
- `src.http_endpoints.prompt_builder_endpoints: build_prompt_impl`
- `src.http_endpoints.prompt_builder_metrics_endpoints: prompt_builder_metrics_impl`
- `src.http_endpoints.tasklist_endpoints: list_tasklists_impl, get_tasklist_impl, put_tasklist_impl, delete_tasklist_impl`
- `src.http_endpoints.upload_endpoints: post_upload_image_impl`
- `src.message_endpoints.ask_request_handler: AskRequestHandler, resolve_or_create_session`
- `src.message_processors.sse_events: SSEEvent`
- `src.prompt_builders.prompt_builder: PromptBuilder`
- `src.request_context: request_id_var`
- `src.storage.base: Storage`
- `src.tasklists.task: Task`
- `src.tasklists.task_list: TaskList`
- `ssl`
- `time`
- `uuid`

**Classes**

- `RequestIdFilter(logging.Filter)` — line 63
  - `filter(self, record: logging.LogRecord) -> bool [line 64]`

**Functions**

- `_ensure_logs_dir_exists() -> None` — line 70
- `configure_logging() -> None` — line 75
- `swagger_json()` — line 122
- `_set_request_id() -> None` — line 169
- `_check_api_key() -> None` — line 177
- `_enforce_api_key(response)` — line 211
- `_clear_request_id(response)` — line 220
- `_teardown_request_id(exc)` — line 227
- `ask()` — line 236
- `list_context_names()` — line 335
- `list_tasklists()` — line 358
- `get_tasklist(tasklist_name: str)` — line 365
- `put_tasklist(tasklist_name: str)` — line 372
- `delete_tasklist(tasklist_name: str)` — line 380
- `get_agents()` — line 387
- `build_prompt()` — line 393
- `prompt_builder_debug()` — line 401
- `prompt_builder_metrics()` — line 408
- `metrics_runs()` — line 415
- `post_chat()` — line 426
- `get_chats()` — line 432
- `get_chat(session_id: str)` — line 442
- `post_chat_message(session_id: str)` — line 448
- `delete_chat(session_id: str)` — line 456
- `update_chat(session_id: str)` — line 462
- `search_documents()` — line 469
- `upload_image()` — line 479
- `admin_reload()` — line 512
- `get_complete_path(base_path, agent_name, account_name)` — line 561
- `get_processor_name(agent_name, account_name)` — line 566

## `automation/__init__.py`

## `main.py`

**Imports**

- `argparse`
- `datetime`
- `logging`
- `src.agent_manager: AgentManager`
- `src.container_config: container`
- `src.message_endpoints.ask_request_handler: AskRequestHandler`

**Functions**

- `role_play(agent_name: str, account_name: str, friendly_name: str, context_name: str | None = None) -> None` — line 71
- `ask(message: str, agent_name: str, account_name: str, conversation_id: str | None = None, friendly_name: str | None = None, context_name: str | None = None) -> tuple[str, str | None]` — line 139

## `scripts/__init__.py`

## `scripts/_fix_prompt_builder.py`

> Apply step-4 + cleanup changes to prompt_builder.py using line-based editing.

**Functions**

- `find_line(text: str, start: int = 0) -> int` — line 10
- `insert_at(idx: int, block: str)` — line 16
- `delete_range(start: int, end: int)` — line 21

## `scripts/check_channels.py`

> Check channel config on both T-Decks via serial.

**Imports**

- `meshtastic.serial_interface`

## `scripts/check_embedding_retrieval.py`

> Probe C — live document retrieval through CoALA semantic memory.

**Imports**

- `__future__: annotations`
- `pathlib: Path`
- `src.coala_memory.semantic: SemanticMemory, SemanticMemoryRequest`
- `src.config_manager: ConfigManager`
- `sys`

**Functions**

- `main() -> int` — line 32

## `scripts/check_nodedb.py`

> Wait a bit then check the nodeDB for jupx.

**Imports**

- `meshtastic.serial_interface`
- `time`

## `scripts/curate_chats.py`

> CLI command to curate chat sessions — filter, summarize, or archive.

**Imports**

- `__future__: annotations`
- `argparse`
- `json`
- `logging`
- `pathlib: Path`
- `src.coala_memory.episodic: EpisodicMemoryManager, EpisodicSessionQuery`
- `src.curation.container_factory: get_curation_engine`
- `src.curation.core: CurationEngine`
- `sys`
- `typing: Any, Dict, List, Optional`

**Functions**

- `_get_episodic_store() -> EpisodicMemoryManager` — line 24
- `_curate_all_sessions(engine: CurationEngine, store: EpisodicMemoryManager, account: str, mode: str, preview: bool, publish: bool, template_name: str, curation_rules: Optional[Dict[str, Any]], dry_run: bool) -> List[Dict[str, Any]]` — line 32
- `main(argv: Optional[List[str]] = None) -> int` — line 101

## `scripts/dedup_corpus.py`

> Deduplicate the prompt corpus by fuzzy-prefix matching.

**Imports**

- `__future__: annotations`
- `argparse`
- `collections: Counter, defaultdict`
- `json`
- `pathlib: Path`
- `sys`
- `typing: Any, Dict, List, Optional`

**Functions**

- `_load_corpus(corpus_path: Path) -> Dict[str, Any]` — line 42
- `_save_corpus(corpus_path: Path, corpus: Dict[str, Any]) -> None` — line 50
- `_find_collisions(prompts: List[Dict[str, Any]], prefix_len: int) -> Dict[str, List[int]]` — line 62
- `_deduplicate(prompts: List[Dict[str, Any]], prefix_len: int) -> tuple[List[Dict[str, Any]], int, int]` — line 79
- `_recompute_meta(corpus: Dict[str, Any]) -> None` — line 99
- `_print_stats(prompts: List[Dict[str, Any]], prefix_len: int) -> None` — line 127
- `_list_groups(prompts: List[Dict[str, Any]], prefix_len: int, limit: int = 20) -> None` — line 145
- `main(argv: Optional[List[str]] = None) -> int` — line 173

## `scripts/embed_digests.py`

> Batch-embed existing chat digests into the embedding store.

**Imports**

- `__future__: annotations`
- `argparse`
- `galet.router_api: RouterApi`
- `logging`
- `pathlib: Path`
- `scripts.embed_sync: StoreConfig, is_unchanged, prune_missing, sha256_file`
- `src.config_manager: ConfigManager`
- `src.embeddings.facade: EmbeddingFacade`
- `src.storage.interfaces: EmbeddingStore`
- `src.storage.models: EmbeddingRecord`
- `src.storage.primitives_embedding_store: build_primitives_embedding_store`
- `sys`
- `typing: Any, Callable, Dict, List, Optional`

**Functions**

- `parse_args() -> argparse.Namespace` — line 65
- `resolve_paths(args: argparse.Namespace, cfg: ConfigManager) -> tuple[str, str, str]` — line 137
- `summarize_text(text: str, *, llm_api: RouterApi, model: str = 'deepseek-chat', max_chars: int = 1024) -> str` — line 157
- `_collect_files(args: argparse.Namespace, digests_dir: Path) -> list[Path]` — line 190
- `sync_digests(*, store: EmbeddingStore, account: str, digests_dir: Path, digest_files: List[Path], embed_fn: Callable[[str], List[float]], summarize_fn: Optional[Callable[[str], str]] = None, summary_model: str = 'deepseek-chat', min_chars: int = 100, force: bool = False, dry_run: bool = False, log: Callable[[str], None] = print) -> Dict[str, int]` — line 218
- `main() -> None` — line 326

## `scripts/embed_external.py`

> Batch-embed markdown files from an external folder into the embedding store.

**Imports**

- `__future__: annotations`
- `argparse`
- `galet.router_api: RouterApi`
- `logging`
- `pathlib: Path`
- `scripts.embed_sync: StoreConfig, is_unchanged, prune_missing, sha256_file`
- `src.config_manager: ConfigManager`
- `src.embeddings.facade: EmbeddingFacade`
- `src.storage.interfaces: EmbeddingStore`
- `src.storage.models: EmbeddingRecord`
- `src.storage.primitives_embedding_store: build_primitives_embedding_store`
- `sys`
- `typing: Any, Callable, Dict, List, Optional`

**Functions**

- `parse_args() -> argparse.Namespace` — line 60
- `resolve_storage_paths(args: argparse.Namespace, cfg: ConfigManager) -> tuple[str, str]` — line 137
- `record_id_from_file(source_root: Path, md_file: Path) -> str` — line 150
- `summarize_text(text: str, *, llm_api: RouterApi, model: str = 'deepseek-chat', max_chars: int = 1024) -> str` — line 155
- `sync_directory(*, store: EmbeddingStore, account: str, namespace: str, source_type: str, source_dir: Path, md_files: List[Path], embed_fn: Callable[[str], List[float]], summarize_fn: Optional[Callable[[str], str]] = None, summary_model: str = 'deepseek-chat', min_chars: int = 100, force: bool = False, dry_run: bool = False, log: Callable[[str], None] = print) -> Dict[str, int]` — line 188
- `main() -> None` — line 298

## `scripts/embed_sync.py`

**Imports**

- `__future__: annotations`
- `hashlib`
- `pathlib: Path`
- `src.storage.interfaces: EmbeddingStore`
- `src.storage.models: EmbeddingRecord`
- `typing: Any, Callable, List, Optional`

**Classes**

- `StoreConfig` — line 79
  - `__init__(self, config: Any, storage_root: str, storage_namespace: str) -> None [line 80]`
  - `get(self, key: str, default: Any = None) -> Any [line 85]`

**Functions**

- `sha256_file(path: Path) -> str` — line 11
- `stored_content_hash(record: Optional[EmbeddingRecord]) -> Optional[str]` — line 19
- `is_unchanged(record: Optional[EmbeddingRecord], current_hash: str) -> bool` — line 28
- `resolve_record_source_path(record: EmbeddingRecord, source_root: Path) -> Optional[Path]` — line 32
- `prune_missing(store: EmbeddingStore, *, account_name: str, namespace: str, source_root: Path, dry_run: bool = False, log: Callable[[str], None] = print) -> List[str]` — line 52

## `scripts/eval_enrichment.py`

> Evaluate the document enrichment pipeline against the prompt corpus.

**Imports**

- `__future__: annotations`
- `argparse`
- `collections: Counter`
- `json`
- `logging`
- `pathlib: Path`
- `src.config_manager: ConfigManager`
- `src.keywords.keywords: Keywords`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage_paths.storage_paths: StoragePaths`
- `src.utils.document_context: get_document_context_traced`
- `sys`
- `time`
- `typing: Any, Dict, List, Optional, Tuple`

**Functions**

- `_load_corpus(corpus_path: Path) -> Dict[str, Any]` — line 68
- `_compute_corpus_meta(corpus: Dict[str, Any]) -> None` — line 81
- `_save_corpus(corpus_path: Path, corpus: Dict[str, Any]) -> None` — line 114
- `_ensure_fields(prompts: List[Dict[str, Any]]) -> int` — line 122
- `_build_storage(config: ConfigManager) -> JsonFileStorage` — line 135
- `_evaluate_one(storage: JsonFileStorage, account_name: str, prompt: Dict[str, Any], prompt_index: int, kind: Optional[str], docs_tag: Optional[str], limit: int, max_chars: int, keywords: Keywords) -> Dict[str, Any]` — line 143
- `_aggregate(results: List[Dict[str, Any]]) -> Dict[str, Any]` — line 228
- `main(argv: Optional[List[str]] = None) -> int` — line 320

## `scripts/extract_prompt_corpus.py`

> Extract a deduplicated corpus of user prompts from all chat sessions.

**Imports**

- `__future__: annotations`
- `argparse`
- `json`
- `logging`
- `pathlib: Path`
- `src.chat2.adapters.jfs_adapter: JfsChat2Primitives`
- `src.chat2.facade: Chat2Store`
- `src.config_manager: ConfigManager`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage_paths.storage_paths: StoragePaths`
- `sys`
- `typing: Any, Dict, List, Optional`

**Functions**

- `_build_store(config: ConfigManager) -> Chat2Store` — line 43
- `_make_prompt_entry(content: str, source: str, session_id: str, friendly_name: str, agent_name: str, utc_timestamp: str) -> Dict[str, Any]` — line 53
- `extract_old_format(lucy_data_root: str, account: str) -> List[Dict[str, Any]]` — line 75
- `extract_new_format(store: Chat2Store, account: str) -> List[Dict[str, Any]]` — line 124
- `deduplicate(prompts: List[Dict[str, Any]]) -> List[Dict[str, Any]]` — line 170
- `_merge_with_existing(new_prompts: List[Dict[str, Any]], existing_corpus: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]` — line 192
- `build_corpus(lucy_data_root: str, store: Chat2Store, account: str, existing_corpus: Optional[Dict[str, Any]] = None) -> Dict[str, Any]` — line 229
- `main(argv: Optional[List[str]] = None) -> int` — line 277

## `scripts/fix_jutx.py`

> Fix jutx region to ANZ (Australia/New Zealand).

**Imports**

- `meshtastic.serial_interface`
- `time`

## `scripts/grep_correlation.py`

> Show execute_command tool calls for a correlation id from the log file.

**Imports**

- `argparse`
- `pathlib: Path`

**Functions**

- `extract_payload(line)` — line 9
- `extract_field(payload, field)` — line 20
- `main()` — line 47

## `scripts/grep_max_iterations.py`

> Analyze FunctionCallingProcessor loop iterations from the log file.

**Imports**

- `argparse`
- `pathlib: Path`
- `re`
- `sys`

**Functions**

- `parse_log(path)` — line 17
- `main()` — line 46

## `scripts/mark_excluded_prompts.py`

> Mark/unmark prompts in the corpus for exclusion from evaluation.

**Imports**

- `__future__: annotations`
- `argparse`
- `json`
- `pathlib: Path`
- `re`
- `sys`
- `typing: Any, Dict, List, Optional`

**Functions**

- `_load_corpus(corpus_path: Path) -> Dict[str, Any]` — line 53
- `_save_corpus(corpus_path: Path, corpus: Dict[str, Any]) -> None` — line 61
- `_ensure_fields(prompts: List[Dict[str, Any]]) -> int` — line 69
- `_print_stats(prompts: List[Dict[str, Any]]) -> None` — line 82
- `_list_excluded(prompts: List[Dict[str, Any]], limit: int = 50) -> None` — line 112
- `_query_prompts(prompts: List[Dict[str, Any]], *, limit: int = 50, output_path: Optional[str] = None, max_docs: int = 0, max_length: Optional[int] = None) -> None` — line 126
- `_apply_rules(prompts: List[Dict[str, Any]], *, min_length: Optional[int] = None, max_length: Optional[int] = None, pattern: Optional[str] = None) -> int` — line 188
- `_clear_excludes(prompts: List[Dict[str, Any]]) -> int` — line 218
- `main(argv: Optional[List[str]] = None) -> int` — line 228

## `scripts/migrate_chat2_to_sqlite.py`

**Imports**

- `__future__: annotations`
- `argparse`
- `dataclasses: dataclass, field`
- `pathlib: Path`
- `src.chat2.adapters.jfs_adapter: JfsChat2Primitives`
- `src.chat2.sqlite: SqliteChat2Primitives, correlation_key, session_events_key, session_meta_key, sessions_prefix`
- `src.chat2.store_primitives: StoreKey`
- `src.config_manager: ConfigManager`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage_paths.storage_paths: StoragePaths`
- `sys`
- `typing: List, Optional`

**Classes**

- `Counters` — line 33
  - `record(self, category: str, status: str, key: StoreKey) -> None [line 43]`
  - `total(self, status: str) -> int [line 51]`

**Functions**

- `classify(key: StoreKey) -> str` — line 55
- `is_migratable(key: StoreKey) -> bool` — line 59
- `resolve_config_path(arg: Optional[str]) -> str` — line 79
- `resolve_source_root(config: ConfigManager, override: Optional[str]) -> Path` — line 85
- `resolve_db_path(config: ConfigManager, override: Optional[str]) -> Path` — line 93
- `build_source(source_root: Path) -> JfsChat2Primitives` — line 104
- `copy_key(source: JfsChat2Primitives, dest: SqliteChat2Primitives, key: StoreKey, dry_run: bool) -> str` — line 115
- `migrate(source: JfsChat2Primitives, dest: SqliteChat2Primitives, dry_run: bool, verbose: bool) -> Counters` — line 139
- `verify(source: JfsChat2Primitives, dest: SqliteChat2Primitives, keys: List[StoreKey]) -> List[str]` — line 159
- `main(argv: Optional[List[str]] = None) -> int` — line 178

## `scripts/migrate_contexts_json_to_md.py`

> migrate_contexts_json_to_md.py

**Imports**

- `__future__: annotations`
- `argparse`
- `json`
- `os`
- `pathlib: Path`
- `sys`
- `tempfile`
- `yaml`

**Functions**

- `convert_file(json_path: Path, overwrite: bool = False, remove_original: bool = True, dry_run: bool = False) -> bool` — line 51
- `find_json_context_files(base_dir: Path) -> list[Path]` — line 156
- `_self_test() -> bool` — line 173
- `main(argv: list[str] | None = None) -> int` — line 248

## `scripts/migrate_embeddings_to_sqlite.py`

> migrate_embeddings_to_sqlite.py

**Imports**

- `__future__: annotations`
- `argparse`
- `os`
- `pathlib: Path`
- `src.chat2.fs_primitives: FileChat2Primitives`
- `src.chat2.sqlite: SqliteChat2Primitives`
- `src.chat2.store_primitives: StoreKey`
- `sys`
- `tempfile`

**Functions**

- `migrate_embeddings(file_store: FileChat2Primitives, sqlite_store: SqliteChat2Primitives, *, dry_run: bool = False, verbose: bool = False, log = print) -> tuple[int, int, list[str]]` — line 58
- `_self_test() -> bool` — line 97
- `main(argv: list[str] | None = None) -> int` — line 150

## `scripts/msg_pix.py`

> Just send a text message to pix and list what we know.

**Imports**

- `meshtastic.serial_interface`

## `scripts/obsidian_index.py`

> Canonical CLI entrypoint to index an Obsidian vault into Lucy's document store.

**Imports**

- `__future__: annotations`
- `argparse`
- `getpass`
- `logging`
- `os`
- `pathlib: Path`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage_paths.storage_paths: StoragePaths`
- `src.utils.obsidian_importer: index_obsidian_vault, index_obsidian_file`
- `sys`
- `typing: Optional`

**Functions**

- `default_storage_root() -> str` — line 66
- `default_vault_path() -> str` — line 71
- `_fatal(msg: str, exit_code: int = 2) -> None` — line 76
- `main(argv: Optional[list[str]] = None) -> None` — line 81

## `scripts/query_pix.py`

> Query pix and try to send a message.

**Imports**

- `meshtastic.serial_interface`
- `time`

## `scripts/read_meshtastic_msgs.py`

> Read Meshtastic messages from the connected radio.

**Imports**

- `json`
- `meshtastic`
- `meshtastic.serial_interface`
- `time`

## `scripts/run_workflow.py`

> Load a YAML workflow definition and run it end to end.

**Imports**

- `__future__: annotations`
- `argparse`
- `pathlib: Path`
- `src.workflows.result: VALID_OUTCOMES`
- `src.workflows: AskWorkflowExecutor, FakeWorkflowExecutor, WorkflowLoader, WorkflowNode, WorkflowResult, WorkflowRunner`
- `sys`

**Functions**

- `parse_args(argv: list[str] | None = None) -> argparse.Namespace` — line 45
- `resolve_path(raw: str) -> Path` — line 77
- `parse_fake_script(spec: str) -> tuple[list[str], dict[str, list[str]]]` — line 82
- `build_fake_results(root: WorkflowNode, default: list[str], overrides: dict[str, list[str]], fake_tokens: int) -> dict[str, list[WorkflowResult]]` — line 120
- `build_fake_executor(args: argparse.Namespace, root: WorkflowNode) -> tuple[FakeWorkflowExecutor, dict[str, list[WorkflowResult]]]` — line 152
- `build_ask_executor(args: argparse.Namespace) -> AskWorkflowExecutor` — line 158
- `print_tree(root: WorkflowNode) -> None` — line 168
- `print_script(root: WorkflowNode, scripted: dict[str, list[WorkflowResult]]) -> None` — line 175
- `print_calls(executor: object) -> None` — line 182
- `print_trace(root: WorkflowNode) -> None` — line 190
- `print_feedback(executor: object) -> None` — line 199
- `print_result(result: WorkflowResult, runner: WorkflowRunner) -> None` — line 211
- `_depth(node: WorkflowNode) -> int` — line 224
- `main(argv: list[str] | None = None) -> int` — line 233

## `scripts/test_doc_context.py`

> Quick test for get_document_context() — run from repo root with venv active.

**Imports**

- `json`
- `logging`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage_paths.storage_paths: StoragePaths`
- `src.utils.document_context: get_document_context`
- `sys`

## `scripts/test_embeddings.py`

> Test embeddings: compare a source string against test strings.

**Imports**

- `__future__: annotations`
- `argparse`
- `json`
- `pathlib: Path`
- `src.embeddings: EmbeddingFacade`
- `sys`

**Functions**

- `parse_args() -> argparse.Namespace` — line 25
- `load_tests(args: argparse.Namespace) -> list[str]` — line 55
- `main() -> None` — line 70

## `scripts/test_keywords.py`

> Test what keywords are extracted from various queries.

**Imports**

- `src.keywords.keywords: Keywords`
- `sys`

## `scripts/test_prompt_builder.py`

> Test the prompt_builder endpoint.

**Imports**

- `json`
- `urllib.request`

## `scripts/test_prompt_builder_metrics.py`

> Test the prompt_builder/metrics endpoint.

**Imports**

- `json`
- `sys`
- `urllib.error`
- `urllib.request`

## `src/__init__.py`

## `src/agent/__init__.py`

**Imports**

- `.agent: Agent, ModelPolicy`
- `.agent_manager: AgentManager`

## `src/agent/agent.py`

> Agent configuration model with robust loading and logging.

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass, fields`
- `logging`
- `typing: Optional, List, Any, Dict, Tuple`

**Classes**

- `ModelPolicy` — line 25
  - `from_dict(cls, data: Dict[str, Any]) -> 'ModelPolicy' [line 35]`
  - `to_dict(self) -> Dict[str, Any] [line 73]`
- `Agent` — line 96
  - `_coerce_bool(value: Any) -> bool [line 137]`
  - `_format_unknown_fields_message(agent_name: Any, unknown_keys: set[str]) -> str [line 148]`
  - `from_dict(data: Dict[str, Any], strict: bool = True) -> 'Agent' [line 162]`
  - `to_dict(self) -> Dict[str, Any] [line 327]`
  - `model_requirements(self) [line 362]`
  - `allows_tool(self, tool_name: str) -> bool [line 382]`

**Functions**

- `_optional_policy_string(value: Any) -> Optional[str]` — line 87

## `src/agent/agent_manager.py`

**Imports**

- `.agent: Agent`
- `json`
- `logging`
- `pathlib: Path`
- `typing: List, Dict, Optional, Any`

**Classes**

- `AgentManager` — line 11
  - `__init__(self, path: str = './agents.json', strict_fields: bool = True) [line 18]`
  - `get_agent(self, name: str) -> Optional[Agent] [line 24]`
  - `is_valid(self, name: str) -> bool [line 30]`
  - `load_agents(self, strict: Optional[bool] = None) -> None [line 33]`
  - `save_agents(self) -> None [line 87]`
  - `get_agent_names(self) -> List[str] [line 96]`
  - `get_available_agents(self) -> List[Agent] [line 99]`
  - `upsert_agent(self, agent: Agent) -> None [line 102]`
  - `remove_agent(self, name: str) -> bool [line 111]`

## `src/agent/caps.py`

**Imports**

- `os`
- `typing: Any, Optional`

**Functions**

- `resolve_effective_cap(key: str, agent: Optional[Any], config: Optional[Any], code_default: int, *, disable_on_non_positive: bool = False) -> Optional[int]` — line 5
- `_agent_value(agent: Optional[Any], key: str) -> Optional[int]` — line 35
- `_config_value(config: Optional[Any], key: str) -> Optional[int]` — line 45
- `_env_value(name: str) -> Optional[int]` — line 60
- `_as_int(value: Any) -> Optional[int]` — line 64

## `src/agent_manager.py`

**Imports**

- `src.agent.agent_manager: AgentManager`

## `src/api_key.py`

> API key validation middleware.

**Imports**

- `logging`
- `src.config_manager: ConfigManager`
- `typing: Optional, Tuple`

**Functions**

- `validate_api_key(config: ConfigManager, header_value: Optional[str]) -> Tuple[bool, Optional[str]]` — line 15

## `src/chat2/__init__.py`

> Chat v2 storage module.

**Imports**

- `src.chat2.errors: Chat2Error, CorruptEventLogError, CorruptMetaError, EventNotFoundError, SessionNotFoundError, StorageOperationError`
- `src.chat2.facade: Chat2Store`

## `src/chat2/adapters/__init__.py`

> Adapters that bridge chat2 primitives to existing storage backends.

**Imports**

- `src.chat2.adapters.jfs_adapter: JfsChat2Primitives`

## `src/chat2/adapters/jfs_adapter.py`

> JFS (JsonFileStorage) adapter for Chat v2 storage primitives.

**Imports**

- `__future__: annotations`
- `pathlib: Path`
- `src.chat2.store_primitives: Chat2Primitives, StoreKey`
- `src.storage.json_file_storage: JsonFileStorage`
- `typing: Iterable, Optional`

**Classes**

- `JfsChat2Primitives` — line 20
  - `__init__(self, storage: JsonFileStorage) -> None [line 33]`
  - `_resolve(self, key: StoreKey) -> Path [line 38]`
  - `_ensure_parent(self, path: Path) -> None [line 50]`
  - `read_text(self, key: StoreKey) -> Optional[str] [line 58]`
  - `write_text(self, key: StoreKey, text: str) -> None [line 64]`
  - `append_text(self, key: StoreKey, text: str) -> None [line 70]`
  - `read_lines(self, key: StoreKey) -> Optional[list[str]] [line 76]`
  - `append_lines(self, key: StoreKey, lines: Iterable[str]) -> None [line 83]`
  - `truncate(self, key: StoreKey) -> None [line 93]`
  - `exists(self, key: StoreKey) -> bool [line 98]`
  - `delete(self, key: StoreKey) -> None [line 101]`
  - `list_keys(self, prefix: StoreKey) -> list[StoreKey] [line 106]`

## `src/chat2/correlation.py`

> Correlation to event mapping for Chat v2.

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `json`
- `pydantic: BaseModel, field_validator`
- `src.chat2.store_primitives: Chat2Primitives, StoreKey`
- `typing: List, Optional`
- `uuid: UUID`

**Classes**

- `CorrelationLink(BaseModel)` — line 29
  - `validate_uuid(cls, v: str) -> str [line 38]`
  - `ensure_utc(cls, v: datetime) -> datetime [line 48]`

**Functions**

- `_key(correlation_id: str) -> StoreKey` — line 55
- `link_event(store: Chat2Primitives, correlation_id: Optional[str], session_id: str, event_id: str) -> None` — line 76
- `get_links(store: Chat2Primitives, correlation_id: Optional[str]) -> List[CorrelationLink]` — line 103
- `get_event_ids(store: Chat2Primitives, correlation_id: Optional[str]) -> List[str]` — line 140

## `src/chat2/errors.py`

> Exception classes for Chat v2 operations.

**Classes**

- `Chat2Error(Exception)` — line 9
- `SessionNotFoundError(Chat2Error)` — line 13
  - `__init__(self, session_id: str) -> None [line 16]`
- `EventNotFoundError(Chat2Error)` — line 21
  - `__init__(self, event_id: str) -> None [line 24]`
- `CorruptEventLogError(Chat2Error)` — line 29
  - `__init__(self, session_id: str, line_number: int, detail: str = '') -> None [line 32]`
- `CorruptMetaError(Chat2Error)` — line 42
  - `__init__(self, session_id: str, detail: str = '') -> None [line 45]`
- `StorageOperationError(Chat2Error)` — line 54
  - `__init__(self, operation: str, key: str, detail: str = '') -> None [line 57]`

## `src/chat2/facade.py`

> Facade for Chat v2 storage operations.

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `src.chat2.correlation: get_links, link_event`
- `src.chat2.jsonl_store: append_event, create_session, delete_session, get_session_meta, list_sessions, read_events, reset_session_events, stream_events, update_session_meta`
- `src.chat2.models: ChatEvent, ChatSessionMeta, SessionLinks`
- `src.chat2.store_primitives: Chat2Primitives`
- `typing: Iterator, List, Optional`

**Classes**

- `Chat2Store` — line 33
  - `__init__(self, store: Chat2Primitives) -> None [line 44]`
  - `create_session(self, user_id: str, account_name: str, agent_name: str, *, session_id: Optional[str] = None, friendly_name: Optional[str] = None, context_name: Optional[str] = None, tags: Optional[List[str]] = None, session_type: str = 'user', participants: Optional[List[str]] = None, links: Optional[SessionLinks] = None) -> ChatSessionMeta [line 51]`
  - `get_session(self, session_id: str) -> Optional[ChatSessionMeta] [line 86]`
  - `update_session(self, session_id: str, **patch_fields) -> ChatSessionMeta [line 93]`
  - `delete_session(self, session_id: str) -> None [line 104]`
  - `session_exists(self, session_id: str) -> bool [line 111]`
  - `list_sessions(self, *, account_name: Optional[str] = None, agent_name: Optional[str] = None, limit: int = 50) -> List[ChatSessionMeta] [line 115]`
  - `add_event(self, session_id: str, event: ChatEvent) -> ChatEvent [line 138]`
  - `add_events(self, session_id: str, events: List[ChatEvent]) -> List[ChatEvent] [line 149]`
  - `stream_events(self, session_id: str) -> Iterator[ChatEvent] [line 162]`
  - `get_events(self, session_id: str, *, start_ts: Optional[datetime] = None, end_ts: Optional[datetime] = None, role_filter: Optional[str] = None, actor_filter: Optional[str] = None, kind_filter: Optional[str] = None) -> List[ChatEvent] [line 169]`
  - `reset_events(self, session_id: str) -> None [line 190]`
  - `event_count(self, session_id: int) -> int [line 197]`
  - `link_event(self, correlation_id: Optional[str], session_id: str, event_id: str) -> None [line 208]`
  - `get_events_by_correlation(self, correlation_id: Optional[str]) -> List[ChatEvent] [line 220]`
  - `create_and_add(self, user_id: str, account_name: str, agent_name: str, events: List[ChatEvent], *, session_id: Optional[str] = None, friendly_name: Optional[str] = None, context_name: Optional[str] = None, tags: Optional[List[str]] = None, session_type: str = 'user', participants: Optional[List[str]] = None, links: Optional[SessionLinks] = None) -> ChatSessionMeta [line 247]`

## `src/chat2/fs_primitives.py`

> Filesystem adapter for Chat v2 storage primitives.

**Imports**

- `__future__: annotations`
- `pathlib: Path`
- `src.chat2.store_primitives: Chat2Primitives, StoreKey`
- `typing: Iterable, Optional, Union`

**Classes**

- `FileChat2Primitives` — line 19
  - `__init__(self, root_dir: str | Path) -> None [line 29]`
  - `_key(key: Union[StoreKey, str]) -> StoreKey [line 33]`
  - `_resolve(self, key: Union[StoreKey, str]) -> Path [line 43]`
  - `read_text(self, key: Union[StoreKey, str]) -> Optional[str] [line 56]`
  - `write_text(self, key: Union[StoreKey, str], text: str) -> None [line 62]`
  - `append_text(self, key: Union[StoreKey, str], text: str) -> None [line 67]`
  - `read_lines(self, key: Union[StoreKey, str]) -> Optional[list[str]] [line 73]`
  - `append_lines(self, key: Union[StoreKey, str], lines: Iterable[str]) -> None [line 80]`
  - `truncate(self, key: Union[StoreKey, str]) -> None [line 90]`
  - `exists(self, key: Union[StoreKey, str]) -> bool [line 95]`
  - `delete(self, key: Union[StoreKey, str]) -> None [line 98]`
  - `list_keys(self, prefix: Union[StoreKey, str]) -> list[StoreKey] [line 103]`

## `src/chat2/jsonl_store.py`

> JSONL store functions for Chat v2.

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `json`
- `src.chat2.models: ChatEvent, ChatSessionMeta, SessionLinks`
- `src.chat2.store_primitives: Chat2Primitives, StoreKey`
- `typing: Iterator, List, Optional`
- `uuid: uuid4`

**Functions**

- `_meta_key(session_id: str) -> StoreKey` — line 27
- `_events_key(session_id: str) -> StoreKey` — line 31
- `_sessions_prefix() -> StoreKey` — line 35
- `create_session(store: Chat2Primitives, user_id: str, account_name: str, agent_name: str, *, session_id: Optional[str] = None, friendly_name: Optional[str] = None, context_name: Optional[str] = None, tags: Optional[List[str]] = None, session_type: str = 'user', participants: Optional[List[str]] = None, links: Optional[SessionLinks] = None) -> ChatSessionMeta` — line 43
- `get_session_meta(store: Chat2Primitives, session_id: str) -> Optional[ChatSessionMeta]` — line 90
- `update_session_meta(store: Chat2Primitives, session_id: str, **patch_fields) -> ChatSessionMeta` — line 101
- `delete_session(store: Chat2Primitives, session_id: str) -> None` — line 124
- `list_sessions(store: Chat2Primitives, *, account_name: Optional[str] = None, agent_name: Optional[str] = None, limit: int = 50) -> List[ChatSessionMeta]` — line 133
- `append_event(store: Chat2Primitives, session_id: str, event: ChatEvent) -> ChatEvent` — line 186
- `stream_events(store: Chat2Primitives, session_id: str) -> Iterator[ChatEvent]` — line 208
- `read_events(store: Chat2Primitives, session_id: str, *, start_ts: Optional[datetime] = None, end_ts: Optional[datetime] = None, role_filter: Optional[str] = None, actor_filter: Optional[str] = None, kind_filter: Optional[str] = None) -> List[ChatEvent]` — line 228
- `reset_session_events(store: Chat2Primitives, session_id: str) -> None` — line 259

## `src/chat2/models.py`

> Pydantic models for Chat v2 storage system.

**Imports**

- `datetime: datetime`
- `pydantic: BaseModel, Field, field_validator`
- `typing: Literal, Optional`
- `uuid: UUID, uuid4`

**Classes**

- `SessionLinks(BaseModel)` — line 13
  - `validate_uuid(cls, v: Optional[str]) -> Optional[str] [line 21]`
- `ChatEvent(BaseModel)` — line 32
  - `validate_event_id(cls, v: str) -> str [line 46]`
  - `ensure_utc(cls, v: datetime) -> datetime [line 56]`
  - `validate_payload(cls, v: dict | str) -> dict | str [line 65]`
  - `model_dump_json(self, **kwargs) -> str [line 71]`
  - `model_validate_json(cls, json_data: str, **kwargs) -> 'ChatEvent' [line 76]`
- `ChatSessionMeta(BaseModel)` — line 81
  - `validate_session_id(cls, v: str) -> str [line 100]`
  - `ensure_utc(cls, v: datetime) -> datetime [line 110]`
  - `updated_at_not_before_created_at(cls, v: datetime, info) -> datetime [line 119]`
  - `model_dump_json(self, **kwargs) -> str [line 125]`
  - `model_validate_json(cls, json_data: str, **kwargs) -> 'ChatSessionMeta' [line 130]`

## `src/chat2/prompt_slice.py`

> Prompt slicing for Chat v2.

**Imports**

- `__future__: annotations`
- `src.chat2.models: ChatEvent`
- `typing: Iterable, List`

**Functions**

- `get_last_n_events(events: Iterable[ChatEvent], n: int) -> List[ChatEvent]` — line 23

## `src/chat2/sqlite/__init__.py`

> SQLite backend package for chat2 storage primitives.

**Imports**

- `__future__: annotations`
- `src.chat2.sqlite.backend: SqliteChat2Primitives`
- `src.chat2.store_primitives: StoreKey`

**Functions**

- `session_meta_key(session_id: str) -> StoreKey` — line 38
- `session_events_key(session_id: str) -> StoreKey` — line 47
- `sessions_prefix() -> StoreKey` — line 55
- `correlation_key(correlation_id: str) -> StoreKey` — line 63

## `src/chat2/sqlite/backend.py`

> SQLite backend for the generic-store doc/log protocol (chat2 primitives).

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `sqlite3`
- `src.chat2.store_primitives: StoreKey`
- `threading`
- `typing: Iterable, List, Optional, Union`

**Classes**

- `SqliteChat2Primitives` — line 40
  - `__init__(self, db_path: Union[str, Path]) -> None [line 47]`
  - `_init_schema(self) -> None [line 56]`
  - `_key(key: Union[StoreKey, str]) -> str [line 75]`
  - `read_text(self, key: Union[StoreKey, str]) -> Optional[str] [line 89]`
  - `write_text(self, key: Union[StoreKey, str], text: str) -> None [line 98]`
  - `exists(self, key: Union[StoreKey, str]) -> bool [line 111]`
  - `delete(self, key: Union[StoreKey, str]) -> None [line 123]`
  - `read_lines(self, key: Union[StoreKey, str]) -> Optional[List[str]] [line 135]`
  - `append_lines(self, key: Union[StoreKey, str], lines: Iterable[str]) -> None [line 149]`
  - `truncate(self, key: Union[StoreKey, str]) -> None [line 173]`
  - `list_keys(self, prefix: Union[StoreKey, str]) -> List[StoreKey] [line 188]`
  - `close(self) -> None [line 215]`
  - `__enter__(self) -> 'SqliteChat2Primitives' [line 220]`
  - `__exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None [line 223]`

## `src/chat2/store_primitives.py`

> Media-neutral storage primitives for Chat v2.

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass`
- `typing: Iterable, Optional, Protocol, Union, runtime_checkable`

**Classes**

- `StoreKey` — line 18
  - `__post_init__(self) -> None [line 30]`
  - `__str__(self) -> str [line 38]`
- `Chat2Primitives(Protocol)` — line 43
  - `read_text(self, key: StoreKey) -> Optional[str] [line 55]`
  - `write_text(self, key: StoreKey, text: str) -> None [line 62]`
  - `append_text(self, key: StoreKey, text: str) -> None [line 69]`
  - `read_lines(self, key: StoreKey) -> Optional[list[str]] [line 76]`
  - `append_lines(self, key: StoreKey, lines: Iterable[str]) -> None [line 83]`
  - `truncate(self, key: StoreKey) -> None [line 90]`
  - `exists(self, key: StoreKey) -> bool [line 98]`
  - `delete(self, key: StoreKey) -> None [line 102]`
  - `list_keys(self, prefix: StoreKey) -> list[StoreKey] [line 109]`
- `InMemoryStore` — line 118
  - `__init__(self) -> None [line 126]`
  - `_key(key: Union[StoreKey, str]) -> str [line 131]`
  - `read_text(self, key: Union[StoreKey, str]) -> Optional[str] [line 141]`
  - `write_text(self, key: Union[StoreKey, str], text: str) -> None [line 144]`
  - `append_text(self, key: Union[StoreKey, str], text: str) -> None [line 147]`
  - `read_lines(self, key: Union[StoreKey, str]) -> Optional[list[str]] [line 152]`
  - `append_lines(self, key: Union[StoreKey, str], lines: Iterable[str]) -> None [line 156]`
  - `truncate(self, key: Union[StoreKey, str]) -> None [line 162]`
  - `exists(self, key: Union[StoreKey, str]) -> bool [line 165]`
  - `delete(self, key: Union[StoreKey, str]) -> None [line 169]`
  - `list_keys(self, prefix: Union[StoreKey, str]) -> list[StoreKey] [line 174]`

## `src/coala_memory/__init__.py`

> CoALA-inspired memory contracts for Lucy.

**Imports**

- `.episodic: EpisodicMemory, EpisodicMemoryRequest, EpisodicMemoryResult, EpisodicMemoryManager, EpisodicSession, EpisodicSessionQuery, EpisodicCurationRequest, EpisodicCurationResult, Chat2EpisodicMemory, EmbeddingDigestRecall`
- `.procedural: ProceduralMemory, ProceduralMemoryRequest, ProceduralMemoryResult, ContextProceduralMemory`
- `.semantic: SemanticMemory, SemanticMemoryRequest, SemanticMemoryResult, SqliteVecSemanticMemory`

## `src/coala_memory/episodic/__init__.py`

**Imports**

- `.chat2_memory: Chat2EpisodicMemory`
- `.embedding_digest_recall: EmbeddingDigestRecall`
- `.interface: EpisodicMemory, EpisodicMemoryRequest, EpisodicMemoryResult, EpisodicEvent, EpisodicDigest`
- `.management: EpisodicMemoryManager, EpisodicSession, EpisodicSessionQuery, EpisodicCurationRequest, EpisodicCurationResult`

## `src/coala_memory/episodic/chat2_memory.py`

**Imports**

- `.interface: EpisodicDigest, EpisodicEvent, EpisodicMemory, EpisodicMemoryRequest, EpisodicMemoryResult`
- `.management: EpisodicMemoryManager, EpisodicSession, EpisodicSessionQuery`
- `__future__: annotations`
- `json`
- `pathlib: Path`
- `src.chat2.facade: Chat2Store`
- `src.chat2.models: ChatEvent, SessionLinks`
- `typing: Any, Callable, Dict, List, Optional`

**Classes**

- `Chat2EpisodicMemory(EpisodicMemory, EpisodicMemoryManager)` — line 26
  - `__init__(self, chat2_store: Chat2Store, *, digests_root: str | Path | None = None, digest_recall: DigestRecall | None = None) -> None [line 42]`
  - `from_sqlite(cls, db_path: str | Path, *, digests_root: str | Path | None = None, digest_recall: DigestRecall | None = None) -> 'Chat2EpisodicMemory' [line 54]`
  - `recall(self, request: EpisodicMemoryRequest) -> EpisodicMemoryResult [line 74]`
  - `save_overflow_digest(self, *, account_name: str, conversation_id: str, snippet: str) -> Optional[str] [line 126]`
  - `create_session(self, *, account_name: str, agent_name: str, user_id: Optional[str] = None, session_id: Optional[str] = None, friendly_name: Optional[str] = None, context_name: Optional[str] = None, tags: Optional[List[str]] = None, session_type: str = 'user', participants: Optional[List[str]] = None, links: Optional[Dict[str, Any]] = None, metadata: Optional[Dict[str, Any]] = None) -> EpisodicSession [line 151]`
  - `get_session(self, session_id: str, *, include_events: bool = True) -> Optional[EpisodicSession] [line 183]`
  - `session_exists(self, session_id: str) -> bool [line 190]`
  - `list_sessions(self, query: EpisodicSessionQuery) -> List[EpisodicSession] [line 193]`
  - `append_event(self, session_id: str, event: EpisodicEvent) -> EpisodicEvent [line 210]`
  - `add_events(self, session_id: str, events: List[EpisodicEvent]) -> List[EpisodicEvent] [line 214]`
  - `link_event(self, correlation_id: Optional[str], session_id: str, event_id: str) -> None [line 219]`
  - `update_session(self, session_id: str, patch: Dict[str, Any]) -> EpisodicSession [line 232]`
  - `reset_session(self, session_id: str) -> None [line 239]`
  - `delete_session(self, session_id: str) -> None [line 242]`
  - `_to_session(cls, meta: Any, events: Optional[List[ChatEvent]] = None) -> EpisodicSession [line 250]`
  - `_to_chat_event(event: EpisodicEvent) -> ChatEvent [line 270]`
  - `_to_episodic_event(event: ChatEvent) -> EpisodicEvent [line 301]`
  - `_payload_text(payload: Any) -> str [line 313]`

## `src/coala_memory/episodic/embedding_digest_recall.py`

**Imports**

- `.interface: EpisodicDigest, EpisodicMemoryRequest`
- `__future__: annotations`
- `logging`
- `src.storage.interfaces: EmbeddingStore`
- `src.utils.text_snippet_loader: load_text_snippet`
- `typing: Any`

**Classes**

- `EmbeddingDigestRecall` — line 12
  - `__init__(self, *, embedding_facade: Any, embedding_store: EmbeddingStore, namespaces: list[str] | None = None, score_threshold: float = 0.25, embedding_model: str = 'text-embedding-3-small') -> None [line 15]`
  - `__call__(self, request: EpisodicMemoryRequest) -> list[EpisodicDigest] [line 30]`

## `src/coala_memory/episodic/interface.py`

**Imports**

- `__future__: annotations`
- `abc: ABC, abstractmethod`
- `dataclasses: dataclass, field`
- `datetime: datetime`
- `typing: Any, Dict, List, Optional`

**Classes**

- `EpisodicMemoryRequest` — line 10
- `EpisodicEvent` — line 35
- `EpisodicDigest` — line 48
- `EpisodicMemoryResult` — line 57
- `EpisodicMemory(ABC)` — line 74
  - `recall(self, request: EpisodicMemoryRequest) -> EpisodicMemoryResult [line 78]`
  - `save_overflow_digest(self, *, account_name: str, conversation_id: str, snippet: str) -> Optional[str] [line 83]`

## `src/coala_memory/episodic/management.py`

**Imports**

- `.interface: EpisodicEvent`
- `__future__: annotations`
- `abc: ABC, abstractmethod`
- `dataclasses: dataclass, field`
- `datetime: datetime`
- `typing: Any, Dict, List, Optional`

**Classes**

- `EpisodicSessionQuery` — line 12
- `EpisodicSession` — line 22
- `EpisodicCurationRequest` — line 40
- `EpisodicCurationResult` — line 60
- `EpisodicMemoryManager(ABC)` — line 71
  - `create_session(self, *, account_name: str, agent_name: str, user_id: Optional[str] = None, session_id: Optional[str] = None, friendly_name: Optional[str] = None, context_name: Optional[str] = None, tags: Optional[List[str]] = None, session_type: str = 'user', participants: Optional[List[str]] = None, links: Optional[Dict[str, Any]] = None, metadata: Optional[Dict[str, Any]] = None) -> EpisodicSession [line 80]`
  - `get_session(self, session_id: str, *, include_events: bool = True) -> Optional[EpisodicSession] [line 98]`
  - `list_sessions(self, query: EpisodicSessionQuery) -> List[EpisodicSession] [line 102]`
  - `session_exists(self, session_id: str) -> bool [line 106]`
  - `append_event(self, session_id: str, event: EpisodicEvent) -> EpisodicEvent [line 111]`
  - `add_events(self, session_id: str, events: List[EpisodicEvent]) -> List[EpisodicEvent] [line 115]`
  - `link_event(self, correlation_id: Optional[str], session_id: str, event_id: str) -> None [line 120]`
  - `update_session(self, session_id: str, patch: Dict[str, Any]) -> EpisodicSession [line 128]`
  - `reset_session(self, session_id: str) -> None [line 132]`
  - `delete_session(self, session_id: str) -> None [line 137]`

## `src/coala_memory/procedural/__init__.py`

**Imports**

- `.context_memory: ContextProceduralMemory`
- `.interface: ProceduralMemory, ProceduralMemoryRequest, ProceduralMemoryResult, ProceduralSkill`

## `src/coala_memory/procedural/context_memory.py`

**Imports**

- `.interface: ProceduralMemory, ProceduralMemoryRequest, ProceduralMemoryResult, ProceduralSkill`
- `__future__: annotations`
- `src.storage.interfaces: ContextStore`
- `typing: Optional`

**Classes**

- `ContextProceduralMemory(ProceduralMemory)` — line 15
  - `__init__(self, context_store: ContextStore) -> None [line 22]`
  - `recall(self, request: ProceduralMemoryRequest) -> ProceduralMemoryResult [line 25]`

## `src/coala_memory/procedural/interface.py`

**Imports**

- `__future__: annotations`
- `abc: ABC, abstractmethod`
- `dataclasses: dataclass, field`
- `typing: Any, Dict, List, Optional`

**Classes**

- `ProceduralMemoryRequest` — line 9
- `ProceduralSkill` — line 26
- `ProceduralMemoryResult` — line 34
- `ProceduralMemory(ABC)` — line 48
  - `recall(self, request: ProceduralMemoryRequest) -> ProceduralMemoryResult [line 52]`

## `src/coala_memory/semantic/__init__.py`

**Imports**

- `.interface: SemanticMemory, SemanticMemoryRequest, SemanticMemoryResult, SemanticDocument`
- `.sqlite_vec_memory: SqliteVecSemanticMemory`

## `src/coala_memory/semantic/interface.py`

**Imports**

- `__future__: annotations`
- `abc: ABC, abstractmethod`
- `dataclasses: dataclass, field`
- `typing: Any, Dict, List, Optional`

**Classes**

- `SemanticMemoryRequest` — line 9
- `SemanticDocument` — line 34
- `SemanticMemoryResult` — line 47
- `SemanticMemory(ABC)` — line 52
  - `recall(self, request: SemanticMemoryRequest) -> SemanticMemoryResult [line 56]`

## `src/coala_memory/semantic/sqlite_vec_memory.py`

**Imports**

- `.interface: SemanticDocument, SemanticMemory, SemanticMemoryRequest, SemanticMemoryResult`
- `__future__: annotations`
- `src.storage.interfaces: EmbeddingStore`
- `src.utils.text_snippet_loader: load_text_snippet`
- `typing: Any, Optional`

**Classes**

- `SqliteVecSemanticMemory(SemanticMemory)` — line 16
  - `__init__(self, *, embedding_facade: Any, embedding_store: EmbeddingStore) -> None [line 29]`
  - `list_namespaces(self, account_name: str) -> list[str] [line 33]`
  - `recall(self, request: SemanticMemoryRequest) -> SemanticMemoryResult [line 36]`

## `src/config_manager.py`

**Imports**

- `copy`
- `json`
- `logging`
- `os`
- `typing: Any, Optional, Dict`

**Classes**

- `ConfigManager` — line 63
  - `__init__(self, file_name: str) [line 64]`
  - `load_config(self, file_name: str) -> dict [line 69]`
  - `get(self, key: str, default = None) [line 91]`
  - `reload(self) -> Dict[str, Any] [line 94]`

**Functions**

- `validate_sandbox_relative_paths(config: dict) -> None` — line 17
- `_deep_merge(base: dict, override: dict) -> dict` — line 40
- `_local_config_path(file_name: str) -> str` — line 55

## `src/container_config.py`

**Imports**

- `galet.adapter_interface: LLMAdapter`
- `galet.embedding_router: EmbeddingRouter`
- `galet.interface: LLMApi`
- `galet.mistral_embedding: MistralEmbeddingApi`
- `galet.openai_embedding: OpenAIEmbeddingApi`
- `galet.openai_responses_adapter: OpenAIResponsesAdapter`
- `galet.router_api: RouterApi`
- `galet.settings: Settings`
- `pathlib: Path`
- `src.agent: AgentManager`
- `src.chat2.adapters.jfs_adapter: JfsChat2Primitives`
- `src.chat2.facade: Chat2Store`
- `src.coala_memory.episodic: EpisodicMemory, EpisodicMemoryManager, Chat2EpisodicMemory, EmbeddingDigestRecall`
- `src.coala_memory.procedural: ProceduralMemory, ContextProceduralMemory`
- `src.coala_memory.semantic: SemanticMemory, SqliteVecSemanticMemory`
- `src.config_manager: ConfigManager`
- `src.embeddings.facade: EmbeddingFacade`
- `src.handlers.handler_registry: HandlerRegistry`
- `src.handlers.registry_bootstrap: build_registry`
- `src.message_endpoints.ask_request_handler: AskRequestHandler`
- `src.message_processors.automation_processor: AutomationProcessor`
- `src.message_processors.message_processor_interface: ProcessorFactoryInterface`
- `src.message_processors.processor_factory: ProcessorFactory`
- `src.metrics: MetricsRepository`
- `src.prompt_builders.coala_prompt_builder: CoALAPromptBuilder`
- `src.prompt_builders.galet_prompt_builder_adapter: GaletPromptBuilderAdapter`
- `src.prompt_builders.prompt_builder_interface: PromptBuilderInterface`
- `src.storage.base: Storage`
- `src.storage.interfaces: ContextStore, DocumentStore, EmbeddingStore, TasklistStore`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage.primitives_embedding_store: build_primitives_embedding_store`
- `src.storage_paths.storage_paths: StoragePaths`

**Classes**

- `ConfigManagerModule(Module)` — line 64
  - `provide_prompts(self) -> ConfigManager [line 67]`
- `AgentManagerModule(Module)` — line 71
  - `provide_agent_manager(self) -> AgentManager [line 74]`
- `StorageModule(Module)` — line 79
  - `provide_storage(self) -> Storage [line 82]`
  - `provide_context_store(self, storage: Storage) -> ContextStore [line 98]`
  - `provide_tasklist_store(self, storage: Storage) -> TasklistStore [line 103]`
  - `provide_document_store(self, storage: Storage) -> DocumentStore [line 108]`
  - `provide_embedding_store(self, storage: Storage) -> EmbeddingStore [line 113]`
  - `provide_chat2_store(self, storage: Storage) -> Chat2Store [line 126]`
- `MetricsModule(Module)` — line 144
  - `provide_metrics_repository(self) -> MetricsRepository [line 147]`
- `EmbeddingModule(Module)` — line 163
  - `provide_embedding_facade(self) -> EmbeddingFacade [line 166]`
- `CoALAMemoryModule(Module)` — line 179
  - `provide_semantic_memory(self, embedding_facade: EmbeddingFacade, embedding_store: EmbeddingStore) -> SemanticMemory [line 182]`
  - `provide_episodic_memory(self, chat2_store: Chat2Store, embedding_facade: EmbeddingFacade, embedding_store: EmbeddingStore) -> EpisodicMemory [line 194]`
  - `provide_episodic_memory_manager(self, episodic_memory: EpisodicMemory) -> EpisodicMemoryManager [line 211]`
  - `provide_procedural_memory(self, context_store: ContextStore) -> ProceduralMemory [line 220]`
- `HandlerRegistryModule(Module)` — line 227
  - `provide_handler_registry(self) -> HandlerRegistry [line 230]`
- `PromptBuilderModule(Module)` — line 234
  - `provide_prompt_builder(self, agent_manager: AgentManager, config: ConfigManager, storage: Storage, semantic_memory: SemanticMemory, episodic_memory: EpisodicMemory, procedural_memory: ProceduralMemory) -> PromptBuilderInterface [line 237]`
- `LLMModule(Module)` — line 265
  - `provide_llm_api(self) -> LLMApi [line 268]`
  - `provide_llm_adapter(self, api: LLMApi) -> LLMAdapter [line 277]`
- `AutomationProcessorModule(Module)` — line 281
  - `provide_automation_processor(self, config: ConfigManager, registry: HandlerRegistry, storage: Storage, prompt_builder: PromptBuilderInterface, episodic_memory_manager: EpisodicMemoryManager, llm_adapter: LLMAdapter, agent_manager: AgentManager) -> AutomationProcessor [line 284]`
- `ProcessorFactoryModule(Module)` — line 305
  - `provide_processor_factory(self, injector: Injector) -> ProcessorFactoryInterface [line 308]`
- `EndpointHandlersModule(Module)` — line 312
  - `provide_ask_request_handler(self, agent_manager: AgentManager, config: ConfigManager, storage: Storage, processor_factory: ProcessorFactory, episodic_memory_manager: EpisodicMemoryManager) -> AskRequestHandler [line 315]`

**Functions**

- `configure_container()` — line 332

## `src/curation/__init__.py`

> Curation library — session digest, archive, and filter operations.

**Imports**

- `src.curation.archiver: archive_session`
- `src.curation.core: CurationEngine`
- `src.curation.resolver: resolve_session`
- `src.curation.summarizer: summarize_session`
- `src.curation.templates: render_template, resolve_template`

## `src/curation/archiver.py`

> Archive support for curation.

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `json`
- `logging`
- `pathlib: Path`
- `src.coala_memory.episodic: EpisodicEvent, EpisodicMemoryManager`
- `typing: Any, Dict, List`

**Functions**

- `_next_archive_path(archive_account_dir: Path, session_id: str) -> Path` — line 20
- `_archive_record(event: EpisodicEvent) -> Dict[str, Any]` — line 34
- `archive_session(session_id: str, digest_text: str, *, episodic_store: EpisodicMemoryManager, archive_dir: Path, account: str) -> bool` — line 51
- `_replace_with_digest(episodic_store: EpisodicMemoryManager, session_id: str, digest_text: str) -> None` — line 96

## `src/curation/container_factory.py`

> Composition helper for the application-level curation service.

**Imports**

- `__future__: annotations`
- `functools: lru_cache`
- `galet.interface: LLMApi`
- `pathlib: Path`
- `src.coala_memory.episodic: EpisodicMemoryManager`
- `src.config_manager: ConfigManager`
- `src.curation.core: CurationEngine`
- `src.embeddings.facade: EmbeddingFacade`
- `src.storage.interfaces: EmbeddingStore`

**Functions**

- `get_curation_engine() -> CurationEngine` — line 23

## `src/curation/core.py`

> CurationEngine — application service for episodic memory curation.

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `galet.interface: LLMApi`
- `json`
- `logging`
- `pathlib: Path`
- `src.coala_memory.episodic: EpisodicEvent, EpisodicMemoryManager`
- `src.curation.archiver: archive_session`
- `src.curation.resolver: resolve_session`
- `src.curation.summarizer: summarize_session`
- `src.curation.templates: render_template, resolve_template`
- `src.embeddings.facade: EmbeddingFacade`
- `src.storage.interfaces: EmbeddingStore`
- `src.storage.models: EmbeddingRecord`
- `typing: Any, Dict, List, Optional`

**Classes**

- `CurationEngine` — line 30
  - `__init__(self, episodic_store: EpisodicMemoryManager, llm_api: LLMApi, llm_model: str = 'gpt-4o-mini', digests_root: Optional[Path] = None, archives_root: Optional[Path] = None, chats_index_path: Optional[Path] = None, embedding_facade: Optional[EmbeddingFacade] = None, storage: Optional[EmbeddingStore] = None) -> None [line 33]`
  - `curate(self, *, session_id: Optional[str] = None, friendly_name: Optional[str] = None, account: str, mode: str = 'filter', preview: bool = True, publish: bool = False, template_name: str = 'default', context_state_template: Optional[str] = None, curation_rules: Optional[Dict[str, Any]] = None, max_chars: int = 32000) -> Dict[str, Any] [line 53]`
  - `_mode_filter(self, *, sid: str, events: List[EpisodicEvent], rules: Dict[str, Any]) -> Dict[str, Any] [line 125]`
  - `_mode_summarize(self, *, sid: str, events: List[EpisodicEvent], account: str, friendly_name: str, template_name: str, context_state_template: Optional[str], preview: bool, publish: bool, max_chars: int) -> Dict[str, Any] [line 176]`
  - `_mode_archive(self, *, sid: str, events: List[EpisodicEvent], account: str, friendly_name: str, template_name: str, context_state_template: Optional[str], preview: bool, publish: bool, max_chars: int) -> Dict[str, Any] [line 229]`
  - `_timestamp() -> str [line 302]`
  - `_write_digest(self, session_id: str, account: str, note_text: str) -> Path [line 305]`
  - `_maybe_embed_digest(self, note_text: str, note_path: Path, session_id: str, account: str) -> None [line 318]`

## `src/curation/resolver.py`

> Session resolution by friendly name or session ID.

**Imports**

- `__future__: annotations`
- `json`
- `logging`
- `pathlib: Path`
- `src.coala_memory.episodic: EpisodicMemoryManager, EpisodicSession, EpisodicSessionQuery`
- `typing: Any, Dict, List, Optional`

**Functions**

- `resolve_session(*, session_id: Optional[str] = None, friendly_name: Optional[str] = None, account: str, episodic_store: EpisodicMemoryManager, chats_index_path: Optional[Path] = None) -> Optional[EpisodicSession]` — line 23

## `src/curation/summarizer.py`

> LLM-based summarization for curation digest mode.

**Imports**

- `__future__: annotations`
- `galet.dto: LLMResponse`
- `galet.interface: LLMApi`
- `json`
- `logging`
- `src.coala_memory.episodic: EpisodicEvent`
- `typing: List`

**Functions**

- `_build_events_text(events: List[EpisodicEvent], max_chars: int = 32000) -> str` — line 50
- `summarize_session(events: List[EpisodicEvent], *, llm_api: LLMApi, model: str = 'gpt-4o-mini', friendly_name: str = '', session_id: str = '', account: str = '', temperature: float = 0.0, max_chars: int = 32000) -> str` — line 72
- `_fallback_digest(events: List[EpisodicEvent], *, friendly_name: str = '', session_id: str = '') -> str` — line 131

## `src/curation/templates.py`

> Template rendering and resolution for curation digests.

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `logging`
- `src.coala_memory.episodic: EpisodicEvent`
- `typing: Any, Dict, List, Optional`

**Functions**

- `resolve_template(template_name: str, *, context_state_override: Optional[str] = None) -> str` — line 49
- `render_template(template: str, *, friendly_name: str = '', session_id: str = '', account: str = '', archive_path: str = '', events: Optional[List[EpisodicEvent]] = None, summary_text: str = '', decisions: str = '', files: str = '', commands: str = '', next_steps: str = '', **extra: Any) -> str` — line 76

## `src/embeddings/__init__.py`

> src.embeddings — embedding generation, comparison, and utilities.

**Imports**

- `.comparison: DistanceMetric, cosine_similarity, rank, top_k`
- `.facade: EmbeddingFacade`
- `.registry: EmbeddingModelInfo, get_model_info, known_models`

## `src/embeddings/comparison.py`

> Vector comparison utilities — pure math, no external dependencies.

**Imports**

- `__future__: annotations`
- `enum`
- `math`
- `typing: List, Tuple`

**Classes**

- `DistanceMetric(enum.Enum)` — line 16

**Functions**

- `cosine_similarity(a: List[float], b: List[float]) -> float` — line 22
- `euclidean_distance(a: List[float], b: List[float]) -> float` — line 40
- `dot_product(a: List[float], b: List[float]) -> float` — line 51
- `_score(a: List[float], b: List[float], metric: DistanceMetric) -> float` — line 67
- `rank(query: List[float], candidates: List[List[float]], *, metric: DistanceMetric = DistanceMetric.COSINE) -> List[float]` — line 85
- `top_k(query: List[float], candidates: List[List[float]], k: int, *, metric: DistanceMetric = DistanceMetric.COSINE) -> List[Tuple[int, float]]` — line 98

## `src/embeddings/facade.py`

> EmbeddingFacade — one-stop shop for embedding generation and comparison.

**Imports**

- `.comparison: DistanceMetric, cosine_similarity, rank, top_k`
- `.registry: EmbeddingModelInfo, get_model_info, known_models`
- `__future__: annotations`
- `dataclasses: asdict`
- `galet.embedding_dto: EmbeddingResponse`
- `galet.embedding_interface: EmbeddingApi`
- `galet.embedding_router: EmbeddingRouter`
- `logging`
- `typing: Any, Dict, List, Optional, Tuple`

**Classes**

- `EmbeddingFacade` — line 29
  - `__init__(self, *, embedding_api: Optional[EmbeddingApi] = None) [line 42]`
  - `embed(self, texts: List[str], *, model: str) -> EmbeddingResponse [line 49]`
  - `cosine_similarity(self, a: List[float], b: List[float]) -> float [line 60]`
  - `rank(self, query: List[float], candidates: List[List[float]], *, metric: DistanceMetric = DistanceMetric.COSINE) -> List[float] [line 68]`
  - `top_k(self, query: List[float], candidates: List[List[float]], k: int, *, metric: DistanceMetric = DistanceMetric.COSINE) -> List[Tuple[int, float]] [line 78]`
  - `model_info(self, model: str) -> Optional[EmbeddingModelInfo] [line 93]`
  - `models(self) -> List[Dict[str, Any]] [line 97]`

## `src/embeddings/registry.py`

> Registry of known embedding models — provider, dimensions, metadata.

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass`
- `typing: Dict, Optional`

**Classes**

- `EmbeddingModelInfo` — line 10

**Functions**

- `get_model_info(model: str) -> Optional[EmbeddingModelInfo]` — line 57
- `known_models() -> Dict[str, EmbeddingModelInfo]` — line 62

## `src/handlers/__init__.py`

> Package exports for handler implementations.

**Imports**

- `.agents_manage_handler: AgentsManageHandler`
- `.command_execution_handler2: CommandExecutionHandler2`
- `.delegate_task_handler: DelegateTaskHandler`
- `.file_load_handler2: FileLoadHandler2`
- `.file_save_handler: FileSaveHandler2`
- `.patch_apply_handler: PatchApplyHandler`
- `.remote_execute_handler: RemoteExecuteHandler`
- `.reset_session_handler: ResetSessionHandler`
- `.scrape_web_page_handler2: ScrapeWebPageHandler2`
- `.tool_handler_meta_handler: ToolHandlerMetaHandler`
- `.web_search_handler2: WebSearchHandler2`

## `src/handlers/agents_manage_handler.py`

> Tool handler for managing agent definitions at runtime.

**Imports**

- `__future__: annotations`
- `logging`
- `src.agent.agent_manager: AgentManager`
- `src.agent: Agent`
- `src.handlers.handler_v2: HandlerV2`
- `typing: Any, Dict, Optional`

**Classes**

- `AgentsManageHandler(HandlerV2)` — line 34
  - `__init__(self, config: Any) [line 37]`
  - `name(cls) -> str [line 42]`
  - `tool_def(cls) -> Dict[str, Any] [line 46]`
  - `result_schema(cls) -> Dict[str, Any] [line 79]`
  - `_get_agent_manager(self, context: Dict[str, Any]) -> AgentManager [line 100]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context: Any) -> Dict[str, Any] [line 118]`
  - `_handle_list(self, am: AgentManager) -> Dict[str, Any] [line 165]`
  - `_handle_get(self, am: AgentManager, args: Dict[str, Any]) -> Dict[str, Any] [line 175]`
  - `_handle_upsert(self, am: AgentManager, args: Dict[str, Any]) -> Dict[str, Any] [line 203]`
  - `_handle_delete(self, am: AgentManager, args: Dict[str, Any]) -> Dict[str, Any] [line 247]`
  - `_handle_reload(self, am: AgentManager) -> Dict[str, Any] [line 270]`

## `src/handlers/command_execution_handler2.py`

> Lucy compatibility adapter for galet-tools' execute_command handler.

**Imports**

- `galet_tools.host.security: DefaultSecurityPolicy`
- `galet_tools.tools.command_execution_handler2: CommandExecutionHandler2`
- `src.handlers.galet_adapters: LucySandboxRootResolver, LucyStorageLocationResolver`

**Classes**

- `CommandExecutionHandler2(GaletCommandExecutionHandler2)` — line 14
  - `__init__(self, config) -> None [line 17]`
  - `execute(self, args, *, account_name: str = 'auto') [line 26]`

## `src/handlers/context_handler.py`

> context_handler — manage conversation contexts stored as Markdown + YAML.

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `logging`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_v2: HandlerV2`
- `src.storage.interfaces: ContextStore`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage_paths.storage_paths: StoragePaths`
- `typing: Any, Dict, List, Optional`

**Classes**

- `ContextHandler(HandlerV2)` — line 35
  - `__init__(self, config: Optional[ConfigManager]) [line 38]`
  - `name(cls) -> str [line 47]`
  - `tool_def(cls) -> Dict[str, Any] [line 51]`
  - `result_schema(cls) -> Dict[str, Any] [line 110]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context: Any) -> Dict[str, Any] [line 134]`
  - `_get_storage(self, context: Dict[str, Any]) -> Optional[ContextStore] [line 170]`
  - `_build_storage(config: Optional[ConfigManager]) [line 177]`
  - `_resolve_account_name(account_name: str, context: Dict[str, Any]) -> str [line 191]`
  - `_resolve_context_name(args: Dict[str, Any], context: Dict[str, Any]) -> Optional[str] [line 206]`
  - `_require_context_name(self, args: Dict[str, Any], context: Dict[str, Any], action: str) [line 222]`
  - `_handle_list(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any] [line 237]`
  - `_handle_load(self, account_name: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any] [line 260]`
  - `_handle_set_mandatory_tools(self, account_name: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any] [line 294]`
  - `_handle_save(self, account_name: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any] [line 334]`

## `src/handlers/curate_chat_handler.py`

> curate_chat handler — thin HandlerV2 facade over ``CurationEngine``.

**Imports**

- `__future__: annotations`
- `json`
- `logging`
- `src.config_manager: ConfigManager`
- `src.curation.container_factory: get_curation_engine`
- `src.curation.core: CurationEngine`
- `src.handlers.handler_v2: HandlerV2`
- `typing: Any, Dict, Optional`

**Classes**

- `CurateChatHandler(HandlerV2)` — line 19
  - `__init__(self, config: ConfigManager, engine: Optional[CurationEngine] = None) -> None [line 29]`
  - `_engine(self, context: Dict[str, Any]) -> CurationEngine [line 37]`
  - `name(cls) -> str [line 46]`
  - `tool_def(cls) -> Dict[str, Any] [line 50]`
  - `result_schema(cls) -> Dict[str, Any] [line 134]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context: Any) -> Dict[str, Any] [line 151]`

## `src/handlers/delegate_task_handler.py`

> Delegate a task to an agent on an eligible Lucy machine.

**Imports**

- `galet: default_model_catalog`
- `json`
- `logging`
- `src.agent: AgentManager`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_v2: HandlerV2`
- `src.handlers.remote_execute_handler: RemoteExecuteHandler`
- `src.machine_catalog: MachineConfigError, MachineDefinition, MachineManager`
- `typing: Any, Dict, Optional`

**Classes**

- `DelegateTaskHandler(HandlerV2)` — line 19
  - `__init__(self, config: ConfigManager, agent_manager: Optional[AgentManager] = None) [line 25]`
  - `name(cls) -> str [line 37]`
  - `tool_def(cls) -> Dict[str, Any] [line 41]`
  - `result_schema(cls) -> Dict[str, Any] [line 104]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto') -> Dict[str, Any] [line 121]`
  - `_text(value: Any) -> str [line 224]`
  - `_select_machine(eligible: tuple[MachineDefinition, ...], preferred: str) -> Optional[MachineDefinition] [line 228]`
  - `_requirements(agent: str, source: str, model: str, capabilities: tuple[str, ...], project: str, machine: str) -> str [line 240]`
  - `_error(self, message: str, **extra: Any) -> Dict[str, Any] [line 257]`
  - `execute_raw(self, arguments_raw: str, *, account_name: str = 'auto', call_id: str = '', **context: Any) -> str [line 266]`

## `src/handlers/episodic_memory_handler.py`

> HandlerV2 tool for integration-testing CoALA episodic memory via Lucy agents.

**Imports**

- `__future__: annotations`
- `src.coala_memory.episodic: EpisodicEvent, EpisodicMemoryManager, EpisodicMemoryRequest, EpisodicSessionQuery`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_v2: HandlerV2`
- `typing: Any, Dict, List, Optional`

**Classes**

- `EpisodicMemoryHandler(HandlerV2)` — line 17
  - `__init__(self, config: ConfigManager, memory: Optional[EpisodicMemoryManager] = None) [line 22]`
  - `name(cls) -> str [line 31]`
  - `tool_def(cls) -> Dict[str, Any] [line 35]`
  - `result_schema(cls) -> Dict[str, Any] [line 74]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context: Any) -> Dict[str, Any] [line 90]`
  - `_session_dict(cls, session: Any) -> Dict[str, Any] [line 255]`
  - `_event_dict(event: EpisodicEvent) -> Dict[str, Any] [line 274]`
  - `_error(cls, action: str, message: str) -> Dict[str, Any] [line 286]`

## `src/handlers/file_load_handler2.py`

> Lucy compatibility adapter for galet-tools' file_load handler.

**Imports**

- `galet_tools.tools.file_load_handler2: FileLoadHandler2`
- `src.handlers.galet_adapters: LucyStorageLocationResolver`

**Classes**

- `FileLoadHandler2(GaletFileLoadHandler2)` — line 10
  - `__init__(self, config) -> None [line 13]`

## `src/handlers/file_save_handler.py`

> Lucy compatibility adapter for galet-tools' file_save handler.

**Imports**

- `galet_tools.tools.file_save_handler: FileSaveHandler2`
- `src.handlers.galet_adapters: LucyStorageLocationResolver`

**Classes**

- `FileSaveHandler2(GaletFileSaveHandler2)` — line 10
  - `__init__(self, config) -> None [line 13]`

## `src/handlers/galet_adapters.py`

> Lucy configuration adapters for galet-tools' narrow handler ports.

**Imports**

- `__future__: annotations`
- `os`
- `typing: Any`

**Classes**

- `LucyStorageLocationResolver` — line 9
  - `__init__(self, config: Any) -> None [line 12]`
  - `storage_base_dir(self) -> str [line 15]`
  - `external_root_dir(self, name: str) -> str [line 28]`
- `LucySandboxRootResolver` — line 38
  - `__init__(self, config: Any) -> None [line 41]`
  - `sandbox_base_dir(self, *, account_name: str) -> str [line 44]`
- `LucyConfigProvider` — line 53
  - `__init__(self, config: Any) -> None [line 61]`
  - `truetype_font_paths(self) -> list[str] [line 64]`

## `src/handlers/generate_doc_handler.py`

> generate_doc handler — HandlerV2-compliant, callable by agents via FCP.

**Imports**

- `__future__: annotations`
- `galet.interface: LLMApi`
- `galet.router_api: RouterApi`
- `galet.settings: Settings`
- `hashlib`
- `logging`
- `pathlib: Path`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_v2: HandlerV2`
- `typing: Any, Dict, List, Optional`

**Classes**

- `GenerateDocHandler(HandlerV2)` — line 24
  - `__init__(self, config: ConfigManager) [line 32]`
  - `name(cls) -> str [line 44]`
  - `tool_def(cls) -> Dict[str, Any] [line 48]`
  - `result_schema(cls) -> Dict[str, Any] [line 119]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context) -> Dict[str, Any] [line 140]`
  - `_load_template(self, doc_type: str, custom_instructions: str) -> str [line 277]`
  - `_build_prompt(template: str, module_path: str, files: Dict[str, str]) -> str [line 300]`
  - `_hash_path(self, output_path: str) -> Path [line 317]`
  - `_read_hash(self, output_path: str) -> Optional[str] [line 321]`
  - `_save_hash(self, output_path: str, hash_value: str) -> None [line 328]`

## `src/handlers/generate_image_handler.py`

> Lucy compatibility adapter for galet-tools' generate_image handler.

**Imports**

- `galet_tools.tools.generate_image_handler: GenerateImageHandler`
- `src.handlers.galet_adapters: LucyConfigProvider`

**Classes**

- `GenerateImageHandler(GaletGenerateImageHandler)` — line 10
  - `__init__(self, config) -> None [line 13]`

## `src/handlers/generate_svg_handler.py`

> Lucy compatibility adapter for galet-tools' generate_svg handler.

**Imports**

- `galet_tools.tools.generate_svg_handler: ALLOWED_ATTRIBUTES, ALLOWED_ELEMENTS, FORBIDDEN_ATTR_PREFIXES, MAX_SVG_CHARS, SVG_NAMESPACE, GenerateSvgHandler, GenerateSvgInput, SvgSanitizer`

**Classes**

- `GenerateSvgHandler(GaletGenerateSvgHandler)` — line 15
  - `__init__(self, config = None) -> None [line 18]`

## `src/handlers/get_keywords_handler.py`

**Imports**

- `__future__: annotations`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_v2: HandlerV2`
- `src.keywords.keywords: Keywords`
- `typing: Any, Dict`

**Classes**

- `GetKeywordsHandler(HandlerV2)` — line 10
  - `__init__(self, config: ConfigManager) [line 22]`
  - `name(cls) -> str [line 26]`
  - `tool_def(cls) -> Dict[str, Any] [line 30]`
  - `result_schema(cls) -> Dict[str, Any] [line 61]`
  - `execute(self, args: Dict[str, Any], **context: Any) -> Dict[str, Any] [line 74]`

## `src/handlers/handler.py`

**Classes**

- `Handler` — line 3
  - `handle(self, request, account_name: str = 'auto') [line 4]`
  - `get_function_calling_definition(self) -> str [line 6]`

## `src/handlers/handler_registry.py`

> Compatibility imports for the canonical galet-tools registry.

**Imports**

- `galet_tools.framework.handler_registry: HandlerRegistry, _context_tool_list, filter_eligible_tool_defs`

## `src/handlers/handler_utils.py`

**Imports**

- `logging`
- `os`
- `shlex`
- `subprocess`

**Functions**

- `get_base_path(config, account_name: str, relative_path: str = '') -> str` — line 7
- `execute_script(command: str, working_dir: str) -> str` — line 101

## `src/handlers/handler_v2.py`

> Compatibility import for the canonical galet-tools handler contract.

**Imports**

- `galet_tools.framework: HandlerV2`

## `src/handlers/lazy_tool_selector_handler.py`

> lazy_tool_selector — scaffolding handler for validating lazy tool loading.

**Imports**

- `__future__: annotations`
- `logging`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_v2: HandlerV2`
- `src.message_processors.lazy_tool_selection: select_active_tool_defs`
- `typing: Any, Dict, List, Optional`

**Classes**

- `LazyToolSelectorHandler(HandlerV2)` — line 43
  - `__init__(self, config: ConfigManager) [line 48]`
  - `name(cls) -> str [line 57]`
  - `tool_def(cls) -> Dict[str, Any] [line 61]`
  - `result_schema(cls) -> Dict[str, Any] [line 143]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', context_state: Any = None, **context: Any) -> Dict[str, Any] [line 176]`
  - `_resolve_eligible(registry: Any, agent: Any, context_state: Any) -> List[Dict[str, Any]] [line 277]`
  - `_call_selector(self, model: str, provider: Optional[str], messages: List[Dict[str, str]]) -> str [line 298]`

## `src/handlers/patch_apply_handler.py`

> Lucy compatibility adapter for galet-tools' patch_apply handler.

**Imports**

- `galet_tools.tools.patch_apply_handler: PatchApplyHandler2`
- `src.handlers.galet_adapters: LucyStorageLocationResolver`

**Classes**

- `PatchApplyHandler(GaletPatchApplyHandler2)` — line 10
  - `__init__(self, config) -> None [line 13]`

## `src/handlers/registry_bootstrap.py`

> Build and populate the HandlerRegistry with available HandlerV2 implementations.

**Imports**

- `galet_tools: HandlerRegistry, register_installed_handlers`
- `logging`
- `src.handlers.agents_manage_handler: AgentsManageHandler`
- `src.handlers.command_execution_handler2: CommandExecutionHandler2`
- `src.handlers.context_handler: ContextHandler`
- `src.handlers.curate_chat_handler: CurateChatHandler`
- `src.handlers.delegate_task_handler: DelegateTaskHandler`
- `src.handlers.episodic_memory_handler: EpisodicMemoryHandler`
- `src.handlers.file_load_handler2: FileLoadHandler2`
- `src.handlers.file_save_handler: FileSaveHandler2`
- `src.handlers.generate_doc_handler: GenerateDocHandler`
- `src.handlers.generate_svg_handler: GenerateSvgHandler`
- `src.handlers.lazy_tool_selector_handler: LazyToolSelectorHandler`
- `src.handlers.patch_apply_handler: PatchApplyHandler`
- `src.handlers.remote_execute_handler: RemoteExecuteHandler`
- `src.handlers.reset_session_handler: ResetSessionHandler`
- `src.handlers.sandbox_execute_handler: SandboxExecuteHandler`
- `src.handlers.scrape_web_page_handler2: ScrapeWebPageHandler2`
- `src.handlers.semantic_memory_handler: SemanticMemoryHandler`
- `src.handlers.serve_image_handler: ServeImageHandler`
- `src.handlers.tasklists_manage_handler: TasklistsManageHandler`
- `src.handlers.tasklists_run_handler: TasklistsRunHandler`
- `src.handlers.tool_handler_meta_handler: ToolHandlerMetaHandler`
- `src.handlers.tool_selection_probe_handler: ToolSelectionProbeHandler`
- `src.handlers.web_search_handler2: WebSearchHandler2`

**Functions**

- `build_registry() -> HandlerRegistry` — line 51

## `src/handlers/remote_execute_handler.py`

> remote_execute — query a remote Lucy instance via its /ask endpoint.

**Imports**

- `json`
- `logging`
- `requests`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_v2: HandlerV2`
- `src.machine_catalog: MachineConfigError, MachineDefinition, MachineManager`
- `typing: Any, Dict, Optional`

**Classes**

- `RemoteExecuteHandler(HandlerV2)` — line 22
  - `__init__(self, config: ConfigManager, machines_config_path: Optional[str] = None) [line 26]`
  - `name(cls) -> str [line 31]`
  - `tool_def(cls) -> Dict[str, Any] [line 35]`
  - `result_schema(cls) -> Dict[str, Any] [line 87]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto') -> Dict[str, Any] [line 106]`
  - `_error(self, message: str, *, machine: str = '', question: str = '', **extra: Any) -> Dict[str, Any] [line 185]`
  - `_machine_manager(self) -> MachineManager [line 196]`
  - `_load_machines(self) -> Dict[str, MachineDefinition] [line 202]`
  - `_parse_response(self, raw: str) -> Optional[str] [line 218]`
  - `execute_raw(self, arguments_raw: str, *, account_name: str = 'auto', call_id: str = '', **context: Any) -> str [line 275]`

## `src/handlers/reset_session_handler.py`

> ResetSessionHandler — clears the current session's events and signals the client.

**Imports**

- `json`
- `logging`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_v2: HandlerV2`
- `typing: Any, Dict`

**Classes**

- `ResetSessionHandler(HandlerV2)` — line 18
  - `__init__(self, config: ConfigManager) -> None [line 21]`
  - `name(cls) -> str [line 25]`
  - `tool_def(cls) -> Dict[str, Any] [line 29]`
  - `result_schema(cls) -> Dict[str, Any] [line 44]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context) -> Dict[str, Any] [line 55]`
  - `execute_raw(self, arguments_raw: str, *, account_name: str = 'auto', call_id: str = '', **context) -> str [line 83]`

## `src/handlers/sandbox_execute_handler.py`

> sandbox_execute handler — chain multiple tool calls in one step.

**Imports**

- `__future__: annotations`
- `json`
- `logging`
- `re`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_registry: HandlerRegistry`
- `src.handlers.handler_v2: HandlerV2`
- `typing: Any, Dict, List, Optional`

**Classes**

- `SandboxExecuteHandler(HandlerV2)` — line 33
  - `__init__(self, config: ConfigManager) [line 36]`
  - `name(cls) -> str [line 41]`
  - `tool_def(cls) -> Dict[str, Any] [line 45]`
  - `result_schema(cls) -> Dict[str, Any] [line 96]`
  - `_resolve_vars(self, value: Any, step_results: Dict[int, Dict[str, Any]]) -> Any [line 125]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', registry: Optional[HandlerRegistry] = None, **context: Any) -> Dict[str, Any] [line 163]`

## `src/handlers/schema_handler_v2.py`

> Compatibility imports for galet-tools' typed handler contract.

**Imports**

- `galet_tools.framework: ErrorCode, ResultEnvelope, SchemaHandlerV2`

## `src/handlers/scrape_web_page_handler2.py`

**Imports**

- `json`
- `logging`
- `shlex`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_utils: execute_script`
- `src.handlers.handler_v2: HandlerV2`
- `sys`
- `typing: Any, Dict`

**Classes**

- `ScrapeWebPageHandler2(HandlerV2)` — line 14
  - `__init__(self, config: ConfigManager) [line 17]`
  - `name(cls) -> str [line 21]`
  - `tool_def(cls) -> Dict[str, Any] [line 25]`
  - `result_schema(cls) -> Dict[str, Any] [line 45]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto') -> Dict[str, Any] [line 59]`
  - `execute_raw(self, arguments_raw: str, *, account_name: str = 'auto', call_id: str = '', **context: Any) -> str [line 99]`

## `src/handlers/semantic_memory_handler.py`

> HandlerV2 tool for integration-testing CoALA semantic memory via Lucy agents.

**Imports**

- `__future__: annotations`
- `galet.embedding_router: EmbeddingRouter`
- `galet.mistral_embedding: MistralEmbeddingApi`
- `galet.openai_embedding: OpenAIEmbeddingApi`
- `galet.settings: Settings`
- `logging`
- `src.coala_memory.semantic: SemanticMemory, SemanticMemoryRequest, SqliteVecSemanticMemory`
- `src.config_manager: ConfigManager`
- `src.embeddings.facade: EmbeddingFacade`
- `src.handlers.handler_v2: HandlerV2`
- `src.storage.primitives_embedding_store: build_primitives_embedding_store`
- `typing: Any, Dict, List, Optional`

**Classes**

- `SemanticMemoryHandler(HandlerV2)` — line 50
  - `__init__(self, config: ConfigManager, memory: Optional[SemanticMemory] = None) [line 60]`
  - `name(cls) -> str [line 92]`
  - `tool_def(cls) -> Dict[str, Any] [line 96]`
  - `result_schema(cls) -> Dict[str, Any] [line 180]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context: Any) -> Dict[str, Any] [line 199]`

**Functions**

- `_models_to_list(resp: Any) -> List[Any]` — line 26

## `src/handlers/serve_image_handler.py`

> ServeImageHandler — reads an image file from disk and returns it as base64.

**Imports**

- `PIL: Image`
- `__future__: annotations`
- `base64`
- `io`
- `logging`
- `mimetypes`
- `os`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_v2: HandlerV2`
- `typing: Any, Dict, Tuple`

**Classes**

- `ServeImageHandler(HandlerV2)` — line 94
  - `__init__(self, config: ConfigManager) [line 99]`
  - `name(cls) -> str [line 103]`
  - `tool_def(cls) -> Dict[str, Any] [line 107]`
  - `result_schema(cls) -> Dict[str, Any] [line 149]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context) -> Dict[str, Any] [line 172]`
  - `_storage_base_dir(self) -> str [line 278]`
  - `_external_root_dir(self, external_root: str) -> str [line 288]`
  - `_has_drive_letter(path: str) -> bool [line 302]`
  - `_validate_and_normalize_relative_path(self, path_in: str) -> Tuple[str, str] [line 305]`

**Functions**

- `_downscale_if_needed(raw_bytes: bytes, mime: str, max_dim: int) -> bytes` — line 59

## `src/handlers/tasklists_manage_handler.py`

**Imports**

- `__future__: annotations`
- `logging`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_v2: HandlerV2`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage.json_file_storage_parts.tasklists: DEFAULT_RUN_TTL_DAYS`
- `src.storage_paths.storage_paths: StoragePaths`
- `src.tasklists.service: TaskListService`
- `typing: Any, Dict, List`

**Classes**

- `TasklistsManageHandler(HandlerV2)` — line 16
  - `__init__(self, config: ConfigManager) [line 19]`
  - `name(cls) -> str [line 29]`
  - `tool_def(cls) -> Dict[str, Any] [line 33]`
  - `result_schema(cls) -> Dict[str, Any] [line 154]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context) -> Dict[str, Any] [line 174]`
  - `_require_key(tasklist_key: str, action: str) -> Dict[str, Any] | None [line 238]`
  - `_require_found(self, tl, tasklist_key: str, action: str) -> Dict[str, Any] | None [line 249]`
  - `_load_and_require(self, account_name: str, tasklist_key: str, action: str) [line 261]`
  - `_service_error(self, exc: ValueError, action: str, tasklist_key: str) -> Dict[str, Any] | None [line 270]`
  - `_handle_list(self, account_name: str) -> Dict[str, Any] [line 290]`
  - `_handle_get(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any] [line 294]`
  - `_handle_get_result(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any] [line 307]`
  - `_handle_delete(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any] [line 342]`
  - `_handle_reset(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any] [line 351]`
  - `_handle_put(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any] [line 374]`
  - `_put_convenience(self, account_name: str, tasklist_key: str, args: Dict[str, Any], validate_only: bool) -> Dict[str, Any] [line 398]`
  - `_put_explicit(self, account_name: str, tasklist_key: str, args: Dict[str, Any], validate_only: bool) -> Dict[str, Any] [line 409]`
  - `_handle_add_task(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any] [line 424]`
  - `_handle_update_task(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any] [line 468]`
  - `_handle_remove_task(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any] [line 524]`
  - `_handle_set_state(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any] [line 557]`
  - `_handle_set_name(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any] [line 585]`
  - `_handle_set_description(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any] [line 613]`
  - `_handle_set_general_instructions(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any] [line 641]`
  - `_handle_update_meta(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any] [line 666]`

## `src/handlers/tasklists_run_handler.py`

> Handler for the tasklists_run tool.

**Imports**

- `__future__: annotations`
- `json`
- `logging`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_v2: HandlerV2`
- `src.message_processors.automation_processor: AutomationProcessor`
- `typing: Any, Dict, Optional`

**Classes**

- `TasklistsRunHandler(HandlerV2)` — line 21
  - `__init__(self, config: ConfigManager) [line 24]`
  - `name(cls) -> str [line 29]`
  - `tool_def(cls) -> Dict[str, Any] [line 33]`
  - `result_schema(cls) -> Dict[str, Any] [line 62]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context) -> Dict[str, Any] [line 78]`

## `src/handlers/tool_handler_meta_handler.py`

**Imports**

- `__future__: annotations`
- `src.handlers.handler_v2: HandlerV2`
- `typing: Any, Dict, Optional`

**Classes**

- `ToolHandlerMetaHandler(HandlerV2)` — line 8
  - `__init__(self, config: Any) [line 22]`
  - `name(cls) -> str [line 27]`
  - `tool_def(cls) -> Dict[str, Any] [line 31]`
  - `result_schema(cls) -> Dict[str, Any] [line 55]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context: Any) -> Dict[str, Any] [line 82]`

## `src/handlers/tool_selection_probe_handler.py`

> tool_selection_probe — diagnostic handler for the tool selection pipeline (issue #126).

**Imports**

- `__future__: annotations`
- `src.handlers.handler_v2: HandlerV2`
- `src.tool_selection: ToolSelectionError, ToolSelectionPipeline`
- `typing: Any, Dict`

**Classes**

- `ToolSelectionProbeHandler(HandlerV2)` — line 43
  - `__init__(self, config: Any) [line 48]`
  - `name(cls) -> str [line 57]`
  - `tool_def(cls) -> Dict[str, Any] [line 61]`
  - `result_schema(cls) -> Dict[str, Any] [line 103]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context: Any) -> Dict[str, Any] [line 128]`

## `src/handlers/web_search_handler2.py`

**Imports**

- `json`
- `logging`
- `os`
- `requests`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_v2: HandlerV2`
- `typing: Any, Dict, List`

**Classes**

- `WebSearchHandler2(HandlerV2)` — line 15
  - `__init__(self, config: ConfigManager) [line 18]`
  - `name(cls) -> str [line 29]`
  - `tool_def(cls) -> Dict[str, Any] [line 33]`
  - `result_schema(cls) -> Dict[str, Any] [line 58]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto') -> Dict[str, Any] [line 85]`
  - `execute_raw(self, arguments_raw: str, *, account_name: str = 'auto', call_id: str = '', **context: Any) -> str [line 118]`
  - `_brave_search(self, *, query: str, count: int) -> List[Dict[str, Any]] [line 126]`
  - `_extract_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]] [line 139]`

## `src/http_endpoints/agents_endpoints.py`

**Imports**

- `logging`
- `src.tasklists: TaskList`
- `typing: Any, Dict, Tuple`

**Functions**

- `get_agents_impl(agent_manager) -> Tuple[Any, int]` — line 7
- `list_context_names_impl(storage, account_name: str) -> Tuple[Any, int]` — line 16
- `list_tasklists_impl(storage, account_name: str) -> Tuple[Any, int]` — line 30
- `get_tasklist_impl(storage, account_name: str, tasklist_key: str) -> Tuple[Any, int]` — line 42
- `put_tasklist_impl(storage, account_name: str, tasklist_key: str, payload: Dict) -> Tuple[Any, int]` — line 63
- `delete_tasklist_impl(storage, account_name: str, tasklist_key: str) -> Tuple[Any, int]` — line 85

## `src/http_endpoints/chats_endpoints.py`

> HTTP endpoint implementations for chat sessions.

**Imports**

- `__future__: annotations`
- `json`
- `src.agent: AgentManager`
- `src.coala_memory.episodic.interface: EpisodicEvent`
- `src.coala_memory.episodic.management: EpisodicMemoryManager, EpisodicSessionQuery`
- `src.coala_memory.episodic.management: EpisodicSession`
- `typing: Any, Dict, List, Optional`

**Functions**

- `_episodic_session_to_response(session: EpisodicSession, include_events: bool = True) -> Dict[str, Any]` — line 21
- `post_chat_impl(episodic_memory_manager: EpisodicMemoryManager, agent_manager: AgentManager, payload: Dict[str, Any]) -> tuple[Dict[str, Any], int]` — line 65
- `get_chats_impl(episodic_memory_manager: EpisodicMemoryManager, agent_manager: AgentManager, agent_name: str, account_name: str, limit: int) -> tuple[Any, int]` — line 94
- `get_chat_impl(episodic_memory_manager: EpisodicMemoryManager, session_id: str) -> tuple[Dict[str, Any], int]` — line 118
- `post_chat_message_impl(episodic_memory_manager: EpisodicMemoryManager, session_id: str, data: Dict[str, Any]) -> tuple[Dict[str, Any], int]` — line 130
- `delete_chat_impl(episodic_memory_manager: EpisodicMemoryManager, session_id: str) -> tuple[Dict[str, Any], int]` — line 164
- `update_chat_impl(episodic_memory_manager: EpisodicMemoryManager, session_id: str, payload: Optional[Dict[str, Any]]) -> tuple[Dict[str, Any], int]` — line 179

## `src/http_endpoints/context_endpoints.py`

**Imports**

- `logging`
- `typing: Any, Tuple`

**Functions**

- `list_context_names_impl(storage, account_name: str) -> Tuple[Any, int]` — line 5

## `src/http_endpoints/documents_endpoints.py`

> HTTP document endpoints using CoALA SemanticMemory.

**Imports**

- `logging`
- `pathlib: Path`
- `src.coala_memory.semantic: SemanticMemory, SemanticMemoryRequest`
- `src.prompt_builders.prompt_builder: DEFAULT_SEARCH_NAMESPACES`
- `typing: List, Any`

**Functions**

- `_parse_namespaces(raw) -> List[str]` — line 16
- `_to_response_item(account_name: str, doc: Any) -> dict` — line 32
- `search_documents_impl(semantic_memory: SemanticMemory, data: dict)` — line 48

## `src/http_endpoints/metrics_endpoints.py`

> HTTP endpoint for querying FCP run metrics (issue #131, design doc

**Imports**

- `__future__: annotations`
- `logging`
- `os`
- `src.metrics: MetricsRepository`
- `typing: Any, Dict, Optional, Tuple`

**Functions**

- `_parse_bool_param(value: Optional[str], name: str) -> Tuple[Optional[bool], Optional[str]]` — line 20
- `_parse_limit(value: Optional[str]) -> Tuple[Optional[int], Optional[str]]` — line 38
- `_resolve_runs_log_path(config: Any) -> str` — line 56
- `_resolve_repository(container: Any, config: Any) -> MetricsRepository` — line 79
- `get_metrics_runs_impl(container: Any, config: Any, query_params: Dict[str, Any]) -> Tuple[Any, int]` — line 92

## `src/http_endpoints/prompt_builder_debug_endpoints.py`

> Debug endpoint for analysing prompt builder document loading effectiveness.

**Imports**

- `__future__: annotations`
- `logging`
- `src.agent: AgentManager`
- `src.config_manager: ConfigManager`
- `src.keywords.keywords: Keywords`
- `src.storage.base: Storage`
- `src.utils.document_context: get_document_context`
- `src.utils.text_snippet_loader: load_text_snippet`
- `typing: Any, Dict, List, Optional, Tuple`

**Functions**

- `prompt_builder_debug_impl(storage: Storage, config: ConfigManager, payload: dict) -> Tuple[Any, int]` — line 25

## `src/http_endpoints/prompt_builder_endpoints.py`

**Imports**

- `logging`
- `src.prompt_builders.prompt_builder_interface: PromptBuilderInterface`
- `typing: Any, Tuple`

**Functions**

- `build_prompt_impl(agent_manager, storage, container, config, payload: dict) -> Tuple[Any, int]` — line 7

## `src/http_endpoints/prompt_builder_metrics_endpoints.py`

> Metrics endpoint for prompt builder token accounting.

**Imports**

- `json`
- `logging`
- `src.agent.caps: resolve_effective_cap`
- `src.handlers.handler_registry: HandlerRegistry`
- `src.message_processors.fcp_models: DEFAULT_MAX_HANDLER_SCHEMA_TOKENS`
- `src.message_processors.function_calling_processor: apply_handler_schema_budget, load_context_state, resolve_tool_defs`
- `src.prompt_builders.prompt_builder: estimate_tokens_from_text`
- `src.prompt_builders.prompt_builder_interface: PromptBuilderInterface`
- `typing: Any, Dict, List, Tuple`

**Functions**

- `_handler_schema_metrics(function_defs: List[Dict[str, Any]]) -> Tuple[int, List[Dict[str, Any]]]` — line 32
- `prompt_builder_metrics_impl(agent_manager, storage, container, config, payload: dict) -> Tuple[Any, int]` — line 56

## `src/http_endpoints/tasklist_endpoints.py`

**Imports**

- `logging`
- `src.tasklists: TaskList`
- `typing: Any, Dict, Tuple`

**Functions**

- `list_tasklists_impl(storage, account_name: str) -> Tuple[Any, int]` — line 8
- `get_tasklist_impl(storage, account_name: str, tasklist_key: str) -> Tuple[Any, int]` — line 20
- `put_tasklist_impl(storage, account_name: str, tasklist_key: str, payload: Dict) -> Tuple[Any, int]` — line 41
- `delete_tasklist_impl(storage, account_name: str, tasklist_key: str) -> Tuple[Any, int]` — line 63

## `src/http_endpoints/upload_endpoints.py`

> HTTP endpoint implementations for image/file uploads.

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `json`
- `logging`
- `os`
- `src.config_manager: ConfigManager`
- `typing: Any, Dict, Tuple`
- `uuid`

**Functions**

- `_build_image_dir(config: ConfigManager, account_name: str) -> str` — line 35
- `post_upload_image_impl(config: ConfigManager, account_name: str, file_data: bytes, original_filename: str, mime_type: str) -> Tuple[Dict[str, Any], int]` — line 41

## `src/injector.py`

**Imports**

- `typing: Any, Callable`

**Classes**

- `Injector` — line 14
  - `__init__(self, modules: Any = None) [line 15]`
  - `get(self, cls: Any) -> Any [line 44]`
- `Module` — line 57

**Functions**

- `inject(fn: Callable) -> Callable` — line 9
- `provider(fn: Callable) -> Callable` — line 61
- `singleton(fn: Callable) -> Callable` — line 65

## `src/keywords/keywords.py`

**Imports**

- `collections: Counter`
- `datetime: datetime`
- `nltk`
- `nltk.corpus: wordnet`
- `nltk.stem: SnowballStemmer`
- `nltk.tokenize: word_tokenize`
- `re`
- `typing: List, Dict, Set`

**Classes**

- `Keywords` — line 64
  - `__init__(self, language_code = 'en') [line 76]`
  - `_initialize_nlp_model(self) [line 81]`
  - `extract_from_content(self, content: str, top_n: int = 10) -> List[str] [line 106]`
  - `extract_keywords(self, content: str, top_n: int = 10) -> List[str] [line 109]`
  - `get_specified_keywords(self, input_str: str) -> List[str] [line 152]`
  - `compare_keyword_lists_semantic_similarity(self, keywords1: List[str], keywords2: List[str]) -> float [line 160]`
  - `compare_semantic_similarity(self, text1: str, text2: str) -> float [line 166]`
  - `compare_keywords(self, set1: set, set2: set, operator: str = 'and') -> bool [line 197]`
  - `concatenate_keywords(self, keyword_list: List[str]) -> str [line 208]`

**Functions**

- `ensure_nltk_data(*, logger = None) -> None` — line 38

## `src/machine_catalog.py`

> Validated machine definitions and loader.

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass, field`
- `json`
- `pathlib: Path`
- `typing: Any, Mapping, Optional`

**Classes**

- `MachineConfigError(ValueError)` — line 9
- `MachineDefinition` — line 34
  - `from_dict(cls, name: str, data: Mapping[str, Any], *, strict: bool = True) [line 52]`
  - `ask_url(self) -> str [line 103]`
  - `session_id_for(self, agent: str) -> str [line 106]`
  - `supports(self, capability: str) -> bool [line 113]`
  - `provides_agent(self, agent: str) -> bool [line 116]`
  - `provides_model(self, source: str, model: str) -> bool [line 119]`
  - `project_path(self, project: str) -> Optional[str] [line 122]`
- `MachineManager` — line 126
  - `__init__(self, path: str, *, strict: bool = True) [line 127]`
  - `beside_config(cls, config_file: str, *, machines_path: Optional[str] = None, strict: bool = True) [line 132]`
  - `load(self) -> dict[str, MachineDefinition] [line 136]`
  - `machines(self, *, enabled_only: bool = False) -> tuple[MachineDefinition, ...] [line 150]`
  - `get(self, name: str, *, require_enabled: bool = False) -> Optional[MachineDefinition] [line 154]`
  - `eligible(self, *, agent = None, capability = None, source = None, model = None, project = None) [line 158]`

**Functions**

- `_text(value: Any, label: str, required: bool = False) -> str` — line 13
- `_items(value: Any, label: str) -> tuple[str, ...]` — line 24

## `src/mcp/__init__.py`

> MCP façade package: expose Lucy's HandlerRegistry to MCP clients.

## `src/mcp/server.py`

> MCP streamable-HTTP server facade over Lucy's HandlerRegistry (design doc).

**Imports**

- `__future__: annotations`
- `asyncio`
- `dataclasses: dataclass`
- `json`
- `logging`
- `src.agent.agent: Agent`
- `src.agent.agent_manager: AgentManager`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_registry: HandlerRegistry`
- `src.mcp.tool_adapter: error_result, handler_tool_def_to_mcp, success_result`
- `src.message_processors.fcp_models: ProcessorContext, ToolHandlerError`
- `src.message_processors.fcp_tool_executor: ToolExecutor, load_context_state`
- `sys`
- `typing: Any, Dict, List, Optional, Tuple`
- `uuid`

**Classes**

- `McpConfigError(Exception)` — line 101
- `McpScope` — line 111

**Functions**

- `_as_bool(value: Any, default: bool = False) -> bool` — line 125
- `_as_text(value: Any, default: str) -> str` — line 134
- `resolve_mcp_config(config_manager: Any) -> Dict[str, Any]` — line 142
- `resolve_scope(agent_manager: AgentManager, cfg: Dict[str, Any]) -> Tuple[Agent, str]` — line 191
- `effective_context_name(agent: Agent, cfg: Dict[str, Any]) -> str` — line 214
- `eligible_tools(registry: HandlerRegistry, agent: Agent, prompt_builder: Any, account_id: str, context_name: str) -> List[Dict[str, Any]]` — line 226
- `resolve_startup_scope(agent_manager: AgentManager, registry: HandlerRegistry, prompt_builder: Any, cfg: Dict[str, Any]) -> Tuple[McpScope, List[Dict[str, Any]]]` — line 247
- `dispatch_tool_call(executor: ToolExecutor, *, scope: McpScope, name: str, arguments: Dict[str, Any], call_id: str, correlation_id: str, conversation_id: str) -> Dict[str, Any]` — line 283
- `_resolve_conversation_id(ctx: Any, fallback: str) -> str` — line 365
- `serve() -> None` — line 386
- `main(argv: Optional[List[str]] = None) -> int` — line 513

## `src/mcp/tool_adapter.py`

> Pure translation between Lucy handler tool defs and MCP tool schemas.

**Imports**

- `__future__: annotations`
- `copy`
- `typing: Any, Dict`

**Functions**

- `handler_tool_def_to_mcp(tool_def: Dict[str, Any]) -> Dict[str, Any]` — line 63
- `text_content(text: str) -> Dict[str, Any]` — line 120
- `success_result(text: str) -> Dict[str, Any]` — line 129
- `error_result(message: str) -> Dict[str, Any]` — line 137

## `src/message_endpoints/ask_request_handler.py`

**Imports**

- `json`
- `logging`
- `src.agent: AgentManager, Agent`
- `src.coala_memory.episodic: EpisodicEvent, EpisodicMemoryManager, EpisodicSessionQuery`
- `src.config_manager: ConfigManager`
- `src.message_processors.function_calling_processor: ToolHandlerError`
- `src.message_processors.processor_factory: ProcessorFactory`
- `src.storage.base: Storage`
- `typing: Any, Dict, Tuple, Optional, Generator`
- `uuid`

**Classes**

- `AskRequestHandler` — line 91
  - `__init__(self, agent_manager: AgentManager, config: ConfigManager, storage: Storage, processor_factory: ProcessorFactory, episodic_store: Optional[EpisodicMemoryManager] = None) -> None [line 98]`
  - `handle(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]] [line 113]`
  - `handle_streaming(self, payload: Dict[str, Any]) -> Generator[str, None, None] [line 353]`

**Functions**

- `resolve_or_create_session(episodic_store: Optional[EpisodicMemoryManager], account_name: str, agent_name: str, friendly_name: Optional[str], context_name: Optional[str] = None, limit: int = 500) -> str` — line 18
- `_backfill_session_context(episodic_store: Optional[EpisodicMemoryManager], conversation_id: str, context_name: Optional[str]) -> None` — line 76

## `src/message_processors/__init__.py`

## `src/message_processors/automation_processor.py`

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `galet.adapter_interface: LLMAdapter`
- `json`
- `logging`
- `src.agent.agent_manager: AgentManager`
- `src.agent: Agent`
- `src.coala_memory.episodic: EpisodicEvent, EpisodicMemoryManager`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_registry: HandlerRegistry`
- `src.message_processors.message_processor_interface: MessageProcessorInterface`
- `src.prompt_builders.prompt_builder_interface: PromptBuilderInterface`
- `src.storage.interfaces: TasklistStore`
- `src.tasklists.task: Task`
- `src.tasklists.task_list: TaskList`
- `src.tasklists.task_states: TASK_STATE_COMPLETED, TASK_STATE_FAILED, TASK_STATE_PENDING, TASK_STATE_RUNNING, TASK_LIST_STATE_COMPLETED, TASK_LIST_STATE_CREATED, TASK_LIST_STATE_FAILED, TASK_LIST_STATE_RUNNING`
- `traceback`
- `typing: Any, Dict, Optional, Tuple, TYPE_CHECKING`
- `uuid`

**Classes**

- `MandatoryStopError(Exception)` — line 75
- `AutomationProcessor(MessageProcessorInterface)` — line 205
  - `__init__(self, config: ConfigManager, registry: HandlerRegistry, storage: TasklistStore, prompt_builder: PromptBuilderInterface, episodic_store: Optional[EpisodicMemoryManager] = None, llm_adapter: Optional[LLMAdapter] = None, agent_manager: Optional[AgentManager] = None) [line 218]`
  - `_ensure_chat2_session(self, conversation_id: str, account_name: str, agent_name: str, friendly_name: Optional[str] = None) -> None [line 240]`
  - `_write_chat2_event(self, conversation_id: str, account_name: str, agent_name: str, role: str, kind: str, payload: str, metadata: Optional[Dict[str, Any]] = None, friendly_name: Optional[str] = None, correlation_id: Optional[str] = None) -> None [line 277]`
  - `_resolve_task_agent(self, task: Task, primary_agent: Agent, agent_name: str, secondary_agent: Optional[Agent] = None) -> Agent [line 338]`
  - `execute_tasklist(self, *, tasklist_id: str, mode: str, account_name: str, agent_name: str, conversation_id: str, context_name: str, primary_agent: Agent, account: Dict[str, Any], secondary_agent: Optional[Agent] = None, processor_factory: Optional[Any] = None, worker_agent: Optional[str] = None, correlation_id: Optional[str] = None) -> str [line 423]`
  - `process_message(self, *, primary_agent: Agent, account: Dict[str, Any], message: str, conversation_id: str = '0', context_name: str = '', secondary_agent: Optional[Agent] = None, processor_factory: Optional[Any] = None, correlation_id: Optional[str] = None) -> str [line 950]`

**Functions**

- `_now_utc() -> datetime` — line 51
- `_safe_preview(text: str, limit: int = 500) -> str` — line 55
- `_is_mandatory_stop_response(text: str) -> bool` — line 83
- `_is_run_command(message: str) -> bool` — line 90
- `_parse_execution_mode_from_text(message: str) -> str` — line 122
- `_find_next_pending_task(tasklist: TaskList) -> Tuple[Optional[int], Optional[Task]]` — line 144
- `_set_task_state(task: Task, state: str) -> None` — line 154
- `_parse_json_command(message: str) -> Tuple[Optional[dict], Optional[str]]` — line 158
- `_map_chat2_kind(automation_kind: str) -> str` — line 197

## `src/message_processors/fcp_chat2.py`

**Imports**

- `logging`
- `src.coala_memory.episodic: EpisodicEvent, EpisodicMemoryManager`
- `src.message_processors.fcp_models: ProcessorContext`
- `src.message_processors.sse_events: SSEEvent`
- `typing: Dict, List, Optional`

**Classes**

- `Chat2Recorder` — line 9
  - `__init__(self, episodic_store: Optional[EpisodicMemoryManager] = None) -> None [line 11]`
  - `ensure_session(self, ctx: ProcessorContext) -> None [line 14]`
  - `write_streaming_events(self, ctx: ProcessorContext, user_message: str, streamed_events: List[SSEEvent], correlation_id: Optional[str] = None) -> None [line 49]`
  - `write_prompt_report(self, ctx: ProcessorContext, breakdown: Dict[str, int], correlation_id: Optional[str] = None) -> None [line 156]`

## `src/message_processors/fcp_loop.py`

**Imports**

- `galet.adapter_interface: LLMAdapter`
- `galet.dto: LLMUsage`
- `galet.provider_registry: ProviderRegistry`
- `json`
- `logging`
- `src.agent: Agent`
- `src.config_manager: ConfigManager`
- `src.message_processors.fcp_models: ProcessorContext, ToolHandlerError, ToolResultTooLargeError, _ToolCall`
- `src.message_processors.fcp_tool_executor: ToolExecutor`
- `src.message_processors.sse_events: SSEEvent`
- `time`
- `typing: Any, Dict, Generator, List, Optional, Tuple`

**Classes**

- `LLMLoopRunner` — line 21
  - `__init__(self, *, llm_adapter: LLMAdapter, config: ConfigManager, tool_executor: ToolExecutor) -> None [line 22]`
  - `_tool_calls_are_duplicate(self, current: List[_ToolCall], previous: List[_ToolCall]) -> bool [line 33]`
  - `_inspect_raw_results(raw_results: List[Tuple[_ToolCall, str]]) -> Generator[SSEEvent, None, None] [line 49]`
  - `run(self, *, ctx: ProcessorContext, prompt_messages: List[Dict[str, Any]], function_defs: List[Dict[str, Any]], primary_agent: Agent, secondary_agent: Optional[Agent], processor_factory: Optional[Any], account: Dict[str, Any], metrics: Dict[str, Any], correlation_id: Optional[str] = None) -> Generator[SSEEvent, None, None] [line 93]`

## `src/message_processors/fcp_models.py`

**Imports**

- `dataclasses: dataclass`
- `galet.provider_registry: ProviderRegistry`
- `galet: default_model_catalog`
- `logging`
- `src.agent: Agent`
- `typing: Optional, Dict, Any`

**Classes**

- `ToolResultTooLargeError(Exception)` — line 10
- `ToolHandlerError(Exception)` — line 14
- `ProcessorContext` — line 24
  - `from_agent(cls, *, primary_agent: Agent, account: Dict[str, Any], conversation_id: str, context_name: str) -> 'ProcessorContext' [line 38]`
- `RequestContext` — line 106
- `_ToolCall` — line 119

## `src/message_processors/fcp_tool_executor.py`

**Imports**

- `galet.adapter_interface: LLMAdapter`
- `json`
- `logging`
- `re`
- `src.agent.agent_manager: AgentManager`
- `src.agent.caps: resolve_effective_cap`
- `src.agent: Agent`
- `src.coala_memory.episodic: EpisodicMemoryManager`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_registry: HandlerRegistry`
- `src.message_processors.fcp_models: ProcessorContext, ToolHandlerError, ToolResultTooLargeError, _ToolCall`
- `src.prompt_builders.prompt_builder_interface: PromptBuilderInterface`
- `typing: Any, Dict, Iterable, List, Optional, Tuple`

**Classes**

- `ToolExecutor` — line 54
  - `__init__(self, *, registry: HandlerRegistry, config: ConfigManager, prompt_builder: PromptBuilderInterface, llm_adapter: LLMAdapter, agent_manager: Optional[AgentManager], episodic_store: Optional[EpisodicMemoryManager] = None) [line 55]`
  - `safe_json_loads(self, s: str, correlation_id: Optional[str] = None) -> Dict[str, Any] [line 72]`
  - `tool_result_to_text(self, tool_result_text: Any, *, max_chars: int, correlation_id: Optional[str] = None) -> str [line 87]`
  - `wrap_tool_calls(self, tool_calls: Iterable[Dict[str, Any]]) -> List[_ToolCall] [line 117]`
  - `execute_tool_calls(self, *, tool_calls: List[_ToolCall], primary_agent: Agent, secondary_agent: Optional[Agent], processor_factory: Optional[Any], account: Dict[str, Any], ctx: ProcessorContext, metrics: Dict[str, Any], correlation_id: Optional[str] = None) -> Tuple[List[Dict[str, Any]], List[Tuple[_ToolCall, str]]] [line 127]`

**Functions**

- `load_context_state(prompt_builder: Any, account_name: str, context_name: str) -> Optional[Any]` — line 24

## `src/message_processors/function_calling_processor.py`

**Imports**

- `contextvars`
- `datetime: datetime, timezone`
- `galet.adapter_interface: LLMAdapter`
- `galet.provider_registry: ProviderRegistry`
- `json`
- `logging`
- `os`
- `src.agent.agent_manager: AgentManager`
- `src.agent.caps: resolve_effective_cap`
- `src.agent: Agent`
- `src.coala_memory.episodic: EpisodicMemoryManager`
- `src.config_manager: ConfigManager`
- `src.handlers.handler_registry: HandlerRegistry, filter_eligible_tool_defs`
- `src.message_processors.fcp_chat2: Chat2Recorder`
- `src.message_processors.fcp_loop: LLMLoopRunner`
- `src.message_processors.fcp_models: ProcessorContext, ToolHandlerError, DEFAULT_MAX_HANDLER_SCHEMA_TOKENS`
- `src.message_processors.fcp_tool_executor: ToolExecutor, load_context_state`
- `src.message_processors.message_processor_interface: MessageProcessorInterface`
- `src.message_processors.run_metrics: RunMetrics`
- `src.message_processors.sse_events: SSEEvent`
- `src.metrics: CorrelationLogHandler, RunMetricsLogger`
- `src.prompt_builders.prompt_builder: estimate_tokens_from_text`
- `src.prompt_builders.prompt_builder_interface: PromptBuilderInterface`
- `src.tool_selection: ToolSelectionError, ToolSelectionPipeline`
- `time`
- `typing: Optional, Dict, Any, List, Generator, NamedTuple`
- `uuid`

**Classes**

- `_CorrelationIdFilter(logging.Filter)` — line 54
  - `filter(self, record: logging.LogRecord) -> bool [line 62]`
- `_PromptSetupResult(NamedTuple)` — line 245
- `FCPResult(NamedTuple)` — line 251
- `FunctionCallingProcessor(MessageProcessorInterface)` — line 289
  - `__init__(self, config: ConfigManager, registry: HandlerRegistry, prompt_builder: PromptBuilderInterface, llm_adapter: LLMAdapter, episodic_store: Optional[EpisodicMemoryManager] = None, agent_manager: Optional[AgentManager] = None, metrics_logger: Optional[RunMetricsLogger] = None, correlation_log_handler: Optional[CorrelationLogHandler] = None) [line 292]`
  - `_get_environment_system_messages(self) -> List[str] [line 337]`
  - `_resolve_tool_defs_pipeline(self, *, primary_agent: Agent, ctx: ProcessorContext, message: str) -> List[Dict[str, Any]] [line 353]`
  - `_prepare_prompt_and_tools(self, *, ctx: ProcessorContext, primary_agent: Agent, message: str, image_ids: Optional[List[str]], file_ids: Optional[List[str]], supports_images: Optional[bool] = None, correlation_id: Optional[str] = None) -> _PromptSetupResult [line 386]`
  - `_write_streaming_chat2_events(self, ctx: ProcessorContext, user_message: str, streamed_events: List[SSEEvent], correlation_id: Optional[str] = None) -> None [line 446]`
  - `_finalize_run(self, metrics: Dict[str, Any], ctx: Optional[ProcessorContext], correlation_id: str, started: str, latency_ms: int, correlation_token: Optional[contextvars.Token] = None) -> RunMetrics [line 458]`
  - `process_message(self, *, primary_agent: Agent, account: Dict[str, Any], message: str, conversation_id: str = '0', context_name: str = '', secondary_agent: Optional[Agent] = None, processor_factory: Optional[Any] = None, image_ids: Optional[List[str]] = None, file_ids: Optional[List[str]] = None, correlation_id: Optional[str] = None) -> FCPResult [line 503]`
  - `process_message_streaming(self, *, primary_agent: Agent, account: Dict[str, Any], message: str, conversation_id: str = '0', context_name: str = '', secondary_agent: Optional[Agent] = None, processor_factory: Optional[Any] = None, image_ids: Optional[List[str]] = None, file_ids: Optional[List[str]] = None, correlation_id: Optional[str] = None) -> Generator[str, None, None] [line 710]`

**Functions**

- `_utc_now_iso() -> str` — line 71
- `_resolve_metrics_logger(config: Any) -> Optional[RunMetricsLogger]` — line 81
- `_compute_prompt_token_breakdown(prompt_builder: Any, filtered_function_defs: List[Dict[str, Any]]) -> Dict[str, int]` — line 105
- `_log_token_breakdown(ctx: ProcessorContext, prompt_builder: Any, filtered_function_defs: List[Dict[str, Any]]) -> Dict[str, int]` — line 142
- `resolve_tool_defs(registry, agent, context_state: Optional[Any] = None) -> List[Dict[str, Any]]` — line 167
- `_handler_schema_tokens(function_defs: List[Dict[str, Any]]) -> int` — line 184
- `apply_handler_schema_budget(function_defs: List[Dict[str, Any]], config: Any, agent: Optional[Any] = None, *, agent_name: str = '<unknown>') -> List[Dict[str, Any]]` — line 195
- `_build_run_metrics(metrics: Dict[str, Any], ctx: Optional[ProcessorContext], correlation_id: str, latency_ms: int, started: str = '', errors: int = 0, warnings: int = 0) -> RunMetrics` — line 256

## `src/message_processors/lazy_tool_selection.py`

> Lazy tool selection for the FunctionCallingProcessor.

**Imports**

- `__future__: annotations`
- `json`
- `re`
- `typing: Any, Callable, Dict, List, Optional, Tuple`

**Functions**

- `estimate_tokens(text: str) -> int` — line 29
- `_one_line_description(td: Dict[str, Any]) -> str` — line 101
- `_build_menu(defs: List[Dict[str, Any]]) -> str` — line 109
- `_build_selection_messages(menu: str, prompt_text: str, prompt_style: str = 'verb_first') -> List[Dict[str, str]]` — line 117
- `_parse_json_array(text: str) -> List[str]` — line 134
- `_clamp_to_known(names: List[str], known: List[str]) -> List[str]` — line 184
- `_apply_sister_group(selected: List[str], known: List[str], group: Tuple[str, ...]) -> List[str]` — line 193
- `_apply_rules(prompt_text: str, selected: List[str], known: List[str]) -> Tuple[List[str], List[str], List[str]]` — line 209
- `_tokens(value: Any) -> int` — line 235
- `select_active_tool_defs(prompt_text: str, eligible_defs: List[Dict[str, Any]], *, llm_call: Callable[[List[Dict[str, str]]], str], prompt_style: str = 'verb_first', three_sisters: bool = True, tasklist_pair: bool = True, rules: bool = True, min_eligible_to_select: int = 5, allow_empty_active_set: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]` — line 244

## `src/message_processors/message_processor_interface.py`

**Imports**

- `__future__: annotations`
- `abc: ABC, abstractmethod`
- `src.agent.agent: Agent`
- `src.message_processors.types: AccountDict`
- `typing: Optional, Dict, Any`
- `typing: Protocol`

**Classes**

- `MessageProcessorInterface(ABC)` — line 12
  - `process_message(self, *, primary_agent: Agent, account: AccountDict, message: str, conversation_id: str = '0', context_name: str = '', secondary_agent: Optional[Agent] = None, processor_factory: Optional[Any] = None) -> str [line 14]`
- `ProcessorFactoryInterface(Protocol)` — line 33
  - `get(self, processor_name: str) -> MessageProcessorInterface [line 34]`

## `src/message_processors/processor_factory.py`

**Imports**

- `__future__: annotations`
- `abc: ABC`
- `importlib: import_module`
- `injector: inject, Injector`

**Classes**

- `ProcessorFactory(ABC)` — line 22
  - `__init__(self, injector: Injector) [line 29]`
  - `get(self, processor_name: str) [line 42]`

## `src/message_processors/run_metrics.py`

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass`
- `pydantic: BaseModel`
- `typing: Any, Dict, Optional`

**Classes**

- `_RunMetricsModel(BaseModel)` — line 9
- `RunMetrics` — line 33
  - `__init__(self, correlation_id: str = '', iterations: int = 0, max_iterations: int = 0, hit_iteration_cap: bool = False, openai_calls: int = 0, tool_calls: int = 0, prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: Optional[int] = None, failures: int = 0, duration_ms: int = 0, agent: str = '', account: str = '', session_id: str = '', started: str = '', errors: int = 0, warnings: int = 0, success: bool = True) -> None [line 53]`
  - `to_dict(self) -> Dict[str, Any] [line 97]`
  - `from_dict(cls, data: Dict[str, Any]) -> 'RunMetrics' [line 120]`

## `src/message_processors/sse_events.py`

> SSE Event model for streaming /ask responses.

**Imports**

- `pydantic: BaseModel`
- `typing: Literal, Optional`

**Classes**

- `SSEEvent(BaseModel)` — line 12
  - `to_sse(self) -> str [line 50]`

## `src/message_processors/types.py`

**Imports**

- `typing: Any, Dict, Optional`

## `src/metrics/__init__.py`

> Metrics logging package (issue #131, design doc metrics-report.md).

**Imports**

- `.correlation_log_handler: CorrelationLogHandler`
- `.metrics_repository: MetricsRepository`
- `.run_metrics_logger: RunMetricsLogger`

## `src/metrics/correlation_log_handler.py`

> Correlation-scoped ERROR/WARNING counting for the run metrics log.

**Imports**

- `logging`
- `src.message_processors.fcp_models: RequestContext`
- `threading`
- `typing: Dict, Optional`

**Classes**

- `CorrelationLogHandler(logging.Handler)` — line 17
  - `__init__(self, level: int = logging.NOTSET) -> None [line 35]`
  - `start_run(self, correlation_id: str) -> RequestContext [line 40]`
  - `end_run(self, correlation_id: str) -> Optional[RequestContext] [line 48]`
  - `emit(self, record: logging.LogRecord) -> None [line 54]`

## `src/metrics/metrics_repository.py`

> Read-only query layer over the FCP run metrics log (issue #131, design doc

**Imports**

- `__future__: annotations`
- `datetime: datetime, timedelta, timezone`
- `json`
- `pathlib: Path`
- `src.message_processors.run_metrics: RunMetrics`
- `typing: Any, Dict, List, Optional, Tuple, Union`

**Classes**

- `MetricsRepository` — line 45
  - `__init__(self, path: Union[str, Path]) -> None [line 48]`
  - `query(self, correlation_id: Optional[str] = None, agent: Optional[str] = None, account: Optional[str] = None, started: Optional[Union[str, datetime]] = None, ended: Optional[Union[str, datetime]] = None, hit_iteration_cap: Optional[bool] = None, success: Optional[bool] = None, limit: int = 50) -> List[Dict[str, Any]] [line 51]`
  - `_read_entries(self) -> List[_Entry] [line 99]`
  - `_parse_entry(line: str, index: int) -> Optional[_Entry] [line 119]`
  - `_matches(entry: _Entry, correlation_id: Optional[str], agent: Optional[str], account: Optional[str], started_filter: Optional[datetime], ended_filter: Optional[datetime], hit_iteration_cap: Optional[bool], success: Optional[bool]) -> bool [line 142]`

**Functions**

- `_parse_iso(value: Union[str, datetime]) -> datetime` — line 24

## `src/metrics/run_metrics_logger.py`

> Append-only JSONL writer for FCP run metrics records (issue #131).

**Imports**

- `__future__: annotations`
- `json`
- `os`
- `pathlib: Path`
- `src.message_processors.run_metrics: RunMetrics`
- `typing: Union`

**Classes**

- `RunMetricsLogger` — line 19
  - `__init__(self, path: Union[str, Path]) -> None [line 22]`
  - `append(self, record: RunMetrics) -> None [line 25]`

## `src/obsidian_index_cli.py`

**Imports**

- `__future__: annotations`
- `argparse`
- `getpass`
- `logging`
- `os`
- `pathlib: Path`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage_paths.storage_paths: StoragePaths`
- `src.utils.obsidian_importer: index_obsidian_vault`
- `sys`
- `typing: Optional`

**Functions**

- `default_storage_root() -> str` — line 23
- `default_vault_path() -> str` — line 28
- `main(argv: Optional[list[str]] = None) -> None` — line 33

## `src/prompt_builders/__init__.py`

## `src/prompt_builders/attachment_resolver.py`

**Imports**

- `__future__: annotations`
- `base64`
- `glob`
- `logging`
- `os`
- `src.config_manager: ConfigManager`
- `typing: Any, Dict, List, Optional`

**Classes**

- `AttachmentResolver` — line 12
  - `__init__(self, config: ConfigManager) -> None [line 15]`
  - `resolve(self, *, account_name: str, image_ids: Optional[List[str]], file_ids: Optional[List[str]], agent_allowed_tools: Optional[List[str]] = None, supports_images: bool = True) -> List[Dict[str, Any]] [line 18]`
  - `build_images_dir(self) -> str [line 114]`
  - `find_image_file(images_dir: str, account_name: str, img_id: str) -> Optional[str] [line 122]`
  - `find_file(cls, images_dir: str, account_name: str, file_id: str) -> Optional[str] [line 130]`
  - `guess_mime_from_path(path: str) -> str [line 136]`

## `src/prompt_builders/coala_prompt_builder.py`

**Imports**

- `__future__: annotations`
- `logging`
- `src.coala_memory.episodic: EpisodicMemoryRequest, EpisodicMemoryResult`
- `src.coala_memory.procedural: ProceduralMemory, ProceduralMemoryRequest, ProceduralMemoryResult`
- `src.prompt_builders.prompt_builder: CONVERSATION_EVENT_KINDS, PromptBuilder`
- `types: SimpleNamespace`
- `typing: Any, Dict, Optional, Tuple`

**Classes**

- `CoALAPromptBuilder(PromptBuilder)` — line 19
  - `__init__(self, *args: Any, procedural_memory: Optional[ProceduralMemory] = None, **kwargs: Any) -> None [line 22]`
  - `build_prompt(self, *args: Any, **kwargs: Any) [line 34]`
  - `_recall_current_episode(self, *, conversation_id: str, account_name: str, agent_name: str, max_events: int) -> Optional[EpisodicMemoryResult] [line 40]`
  - `_load_digest_contexts(self, *, content_text: str, account_name: str, agent_name: str) -> list[dict[str, Any]] [line 85]`
  - `_save_overflow_digest(self, *, account_name: str, conversation_id: str, new_snippet: str) -> Optional[str] [line 105]`
  - `_get_context_state(self, account_name: str, context_name: str) -> Optional[Any] [line 120]`
  - `_result_to_context_state(result: ProceduralMemoryResult) -> Optional[Any] [line 155]`

## `src/prompt_builders/context_retrievers.py`

**Imports**

- `__future__: annotations`
- `logging`
- `src.coala_memory.semantic: SemanticMemory, SemanticMemoryRequest`
- `src.storage.base: Storage`
- `src.storage.interfaces: EmbeddingStore`
- `src.utils.text_snippet_loader: load_text_snippet`
- `typing: Any, Dict, List, Optional`

**Classes**

- `SemanticContextRetriever` — line 17
  - `__init__(self, semantic_memory: Optional[SemanticMemory]) -> None [line 20]`
  - `retrieve(self, *, query: str, account_name: str, namespaces: Optional[List[str]] = None, top_k: int = 3, max_chars: int = 9000, score_threshold: float = DOC_EMBEDDING_SCORE_THRESHOLD) -> List[Dict[str, Any]] [line 23]`
- `DigestContextRetriever` — line 69
  - `__init__(self, *, storage: Storage, embedding_facade: Any = None, embedding_store: Optional[EmbeddingStore] = None) -> None [line 72]`
  - `retrieve(self, *, query: str, account_name: str, namespaces: Optional[List[str]] = None, top_k: int = 3, max_chars: int = 3000) -> List[Dict[str, Any]] [line 83]`

## `src/prompt_builders/galet_prompt_builder_adapter.py`

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass`
- `galet_prompt_builder: PromptBudgets, PromptCompiler, PromptLimits, PromptRequest`
- `src.agent: Agent, AgentManager`
- `src.coala_memory.episodic: EpisodicMemory, EpisodicMemoryRequest`
- `src.coala_memory.procedural: ProceduralMemory, ProceduralMemoryRequest`
- `src.coala_memory.semantic: SemanticMemory, SemanticMemoryRequest`
- `src.config_manager: ConfigManager`
- `src.prompt_builders.attachment_resolver: AttachmentResolver`
- `src.prompt_builders.context_retrievers: DEFAULT_SEARCH_NAMESPACES`
- `src.prompt_builders.prompt_builder_interface: ChatMessageDict, PromptBuilderInterface`
- `src.prompt_builders.prompt_sections: PromptSections`
- `src.storage.base: Storage`
- `typing: Any, Dict, List, Optional`

**Classes**

- `GaletPromptPolicy` — line 45
  - `from_config(cls, config: ConfigManager, agent: Optional[Agent]) -> 'GaletPromptPolicy' [line 62]`
- `_LucySemanticMemoryAdapter` — line 83
  - `__init__(self, memory: SemanticMemory) -> None [line 84]`
  - `recall(self, request: Any) -> Any [line 87]`
- `_LucyEpisodicMemoryAdapter` — line 101
  - `__init__(self, memory: EpisodicMemory, agent_name: str) -> None [line 102]`
  - `recall(self, request: Any) -> Any [line 106]`
  - `save_overflow_digest(self, **kwargs: Any) -> Optional[str] [line 128]`
- `_LucyProceduralMemoryAdapter` — line 132
  - `__init__(self, memory: ProceduralMemory) -> None [line 133]`
  - `recall(self, request: Any) -> Any [line 136]`
- `GaletPromptBuilderAdapter(PromptBuilderInterface)` — line 149
  - `__init__(self, *, agent_manager: AgentManager, config: ConfigManager, storage: Storage, semantic_memory: SemanticMemory, episodic_memory: EpisodicMemory, procedural_memory: ProceduralMemory, compiler_class: type[PromptCompiler] = PromptCompiler) -> None [line 156]`
  - `build_prompt(self, *, content_text: str, conversation_id: str, agent_name: str, account_name: str, context_type: str = 'none', max_prompt_chars: int = 6000, context_name: str = '', extra_system_messages: Optional[List[str]] = None, image_ids: Optional[List[str]] = None, file_ids: Optional[List[str]] = None, supports_images: bool = True) -> List[ChatMessageDict] [line 178]`
  - `_semantic_namespaces(self, account_name: str, context_name: str) -> List[str] [line 302]`
  - `_replace_current_input_with_attachments(self, messages: List[ChatMessageDict], *, content_text: str, account_name: str, agent: Optional[Agent], image_ids: Optional[List[str]], file_ids: Optional[List[str]], supports_images: bool) -> None [line 319]`
  - `_metrics_breakdown(metrics: Any) -> Dict[str, int] [line 347]`

## `src/prompt_builders/history_selector.py`

**Imports**

- `__future__: annotations`
- `logging`
- `src.coala_memory.episodic: EpisodicMemoryResult`
- `src.prompt_builders.token_budget: estimate_tokens_from_text`
- `typing: Any, Callable, Dict, List, Optional, Tuple`

**Classes**

- `HistorySelector` — line 10
  - `event_content(event: Any) -> str [line 14]`
  - `select(self, *, episodic_result: Optional[EpisodicMemoryResult], max_convs: int, history_budget: int, messages: List[Dict[str, Any]], account_name: str, conversation_id: str, agent_name: str, summarize_overflow: Callable[[List[str]], str], save_overflow_digest: Callable[..., Optional[str]]) -> Tuple[List[Dict[str, str]], str] [line 18]`
  - `summarize_overflow(texts: List[str], max_chars: int = 800) -> str [line 102]`

## `src/prompt_builders/prompt_builder.py`

**Imports**

- `__future__: annotations`
- `injector: inject`
- `logging`
- `pathlib: Path`
- `src.agent: Agent, AgentManager`
- `src.coala_memory.episodic: EpisodicMemory, EpisodicMemoryRequest, EpisodicMemoryResult`
- `src.config_manager: ConfigManager`
- `src.prompt_builders.attachment_resolver: AttachmentResolver`
- `src.prompt_builders.context_retrievers: DEFAULT_SEARCH_NAMESPACES, DIGEST_SCORE_THRESHOLD, DIGEST_SEARCH_NAMESPACES, DOC_EMBEDDING_SCORE_THRESHOLD, DigestContextRetriever, SemanticContextRetriever`
- `src.prompt_builders.history_selector: HistorySelector`
- `src.prompt_builders.prompt_builder_interface: PromptBuilderInterface`
- `src.prompt_builders.prompt_sections: PromptSections`
- `src.prompt_builders.token_budget: CONTEXT_TEXT_SOFT_MAX_TOKENS, DEFAULT_PROMPT_BUDGET_TOKENS, PROMPT_BUDGET_SAFETY_MARGIN, TokenBudgetAllocator, estimate_tokens_from_text`
- `src.storage.base: Storage`
- `src.storage.interfaces: EmbeddingStore`
- `typing: Any, Dict, List, Optional`

**Classes**

- `PromptBuilder(PromptBuilderInterface)` — line 37
  - `__init__(self, agent_manager: AgentManager, config: ConfigManager, storage: Storage, embedding_facade = None, embedding_store: Optional[EmbeddingStore] = None, semantic_memory = None, episodic_memory: Optional[EpisodicMemory] = None) [line 41]`
  - `build_prompt(self, *, content_text: str, conversation_id: str, agent_name: str, account_name: str, context_type: str = 'none', max_prompt_chars: int = 6000, context_name: str = '', extra_system_messages: Optional[List[str]] = None, image_ids: Optional[List[str]] = None, file_ids: Optional[List[str]] = None, supports_images: bool = True) -> List[Dict[str, Any]] [line 71]`
  - `_append_session_info(self, **kwargs: Any) -> None [line 226]`
  - `_apply_context_soft_max(self, *, context_text: str, agent: Optional[Agent], account_name: str, context_name: str, agent_name: str) -> str [line 229]`
  - `_get_context_data(self, *, account_name: str, context_name: str) -> Dict[str, Any] [line 246]`
  - `_load_semantic_contexts(self, *, content_text: str, account_name: str, agent_name: str, agent: Optional[Agent], context_type: str, context_data: Dict[str, Any], use_embeddings: bool) -> List[Dict[str, Any]] [line 262]`
  - `_load_digest_contexts(self, *, content_text: str, account_name: str, agent_name: str) -> List[Dict[str, Any]] [line 298]`
  - `_build_user_message(self, *, content_text: str, account_name: str, image_ids: Optional[List[str]], file_ids: Optional[List[str]], agent: Optional[Agent], supports_images: bool) -> Dict[str, Any] [line 321]`
  - `_select_history(self, *, episodic_result: Optional[EpisodicMemoryResult], max_convs: int, history_budget: int, messages: List[Dict[str, Any]], account_name: str, conversation_id: str, agent_name: str) -> tuple[List[Dict[str, str]], str] [line 345]`
  - `_append_document_contexts(self, messages: List[Dict[str, Any]], doc_contexts: List[Dict[str, Any]]) -> None [line 368]`
  - `_append_digest_contexts(self, messages: List[Dict[str, Any]], digest_contexts: List[Dict[str, Any]]) -> None [line 373]`
  - `_build_agent_system_message(self, agent_name: str, agent: Optional[Agent]) -> str [line 378]`
  - `_recall_current_episode(self, *, conversation_id: str, account_name: str, agent_name: str, max_events: int) -> Optional[EpisodicMemoryResult] [line 381]`
  - `_event_content(event: Any) -> str [line 417]`
  - `_get_semantic_memory_context(self, *, query: str, account_name: str, namespaces: Optional[List[str]] = None, top_k: int = 3, max_chars: int = 9000, score_threshold: float = DOC_EMBEDDING_SCORE_THRESHOLD) -> List[Dict[str, Any]] [line 420]`
  - `_get_digest_context(self, *, query: str, account_name: str, namespaces: Optional[List[str]] = None, top_k: int = 3, max_chars: int = 3000) -> List[Dict[str, Any]] [line 439]`
  - `_resolve_attachments(self, *, account_name: str, image_ids: Optional[List[str]], file_ids: Optional[List[str]], agent_allowed_tools: Optional[List[str]] = None, supports_images: bool = True) -> List[Dict[str, Any]] [line 456]`
  - `_build_images_dir(self) -> str [line 473]`
  - `_build_digests_dir(self, account_name: str) -> Path [line 476]`
  - `_save_overflow_digest(self, *, account_name: str, conversation_id: str, new_snippet: str) -> Optional[str] [line 479]`
  - `_find_image_file(self, images_dir: str, account_name: str, img_id: str) -> Optional[str] [line 515]`
  - `_find_file(self, images_dir: str, account_name: str, file_id: str) -> Optional[str] [line 518]`
  - `_guess_mime_from_path(path: str) -> str [line 522]`
  - `_get_context_state(self, account_name: str, context_name: str) -> Optional[Any] [line 525]`
  - `_get_context_text(self, account_name: str, context_name: str) -> str [line 529]`
  - `_ensure_current_query(self, messages: List[Dict[str, Any]], current_query: Any) -> List[Dict[str, Any]] [line 532]`
  - `_summarize_overflow(self, texts: List[str], max_chars: int = 800) -> str [line 537]`

## `src/prompt_builders/prompt_builder_interface.py`

**Imports**

- `abc: ABC, abstractmethod`
- `typing: Any, Dict, List, Optional`

**Classes**

- `PromptBuilderInterface(ABC)` — line 10
  - `build_prompt(self, *, content_text: str, conversation_id: str, agent_name: str, account_name: str, context_type: str = 'none', max_prompt_chars: int = 6000, context_name: str = '', extra_system_messages: Optional[List[str]] = None, image_ids: Optional[List[str]] = None, file_ids: Optional[List[str]] = None, supports_images: bool = True) -> List[ChatMessageDict] [line 12]`

## `src/prompt_builders/prompt_sections.py`

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `src.agent: Agent`
- `src.coala_memory.episodic: EpisodicMemoryResult`
- `typing: Any, Dict, List, Optional`

**Classes**

- `PromptSections` — line 10
  - `append_session_info(*, messages: List[Dict[str, Any]], system_text_parts: List[str], episodic_result: Optional[EpisodicMemoryResult], conversation_id: str, agent_name: str) -> None [line 14]`
  - `append_document_contexts(messages: List[Dict[str, Any]], doc_contexts: List[Dict[str, Any]]) -> None [line 50]`
  - `append_digest_contexts(messages: List[Dict[str, Any]], digest_contexts: List[Dict[str, Any]]) -> None [line 69]`
  - `build_agent_system_message(agent_name: str, agent: Optional[Agent]) -> str [line 87]`
  - `context_text(ctx: Optional[Any]) -> str [line 98]`
  - `ensure_current_query(messages: List[Dict[str, Any]], current_query: Any) -> List[Dict[str, Any]] [line 120]`

## `src/prompt_builders/token_budget.py`

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass`
- `logging`
- `src.agent.caps: resolve_effective_cap`
- `src.config_manager: ConfigManager`
- `typing: Any, Dict, Iterable, Mapping`

**Classes**

- `PromptBudget` — line 22
- `TokenBudgetAllocator` — line 31
  - `__init__(self, config: ConfigManager) -> None [line 34]`
  - `allocate_history_budget(self, *, agent: Any, system_text_parts: Iterable[str], context_text: str, document_text: str, digest_text: str, user_text: str) -> PromptBudget [line 37]`
  - `apply_context_soft_max(self, *, context_text: str, agent: Any, account_name: str, context_name: str, agent_name: str) -> str [line 89]`
  - `build_breakdown(*, budget: PromptBudget, history_messages: Iterable[Mapping[str, Any]], overflow_digest_text: str) -> Dict[str, int] [line 133]`

**Functions**

- `estimate_tokens_from_text(text: str) -> int` — line 15

## `src/request_context.py`

> Request-scoped context utilities.

**Imports**

- `__future__: annotations`
- `contextlib: AbstractContextManager`
- `contextvars`
- `typing: Optional`

**Classes**

- `request_context(AbstractContextManager)` — line 67
  - `__init__(self, request_id: Optional[str] = None, account_name: Optional[str] = None) -> None [line 75]`
  - `__enter__(self) -> 'request_context' [line 80]`
  - `__exit__(self, exc_type, exc, tb) -> bool [line 87]`

**Functions**

- `get_request_id() -> str` — line 39
- `set_request_id(rid: str) -> contextvars.Token` — line 45
- `get_account_name() -> Optional[str]` — line 55
- `set_account_name(account_name: Optional[str]) -> contextvars.Token` — line 61

## `src/storage/__init__.py`

> Lucy's storage layer.

**Imports**

- `.base: Storage`
- `.json_file_storage: JsonFileStorage`
- `.models: UserProfile, Context, Skill, DocumentRef, EmbeddingRecord`

## `src/storage/base.py`

**Imports**

- `.interfaces: ContextStore, DocumentStore, EmbeddingStore, HealthCheckable, TasklistStore`
- `.models: UserProfile`
- `__future__: annotations`
- `abc: ABC, abstractmethod`
- `typing: Optional`

**Classes**

- `Storage(ContextStore, TasklistStore, DocumentStore, EmbeddingStore, HealthCheckable, ABC)` — line 16
  - `get_user_profile(self, account_name: str) -> Optional[UserProfile] [line 27]`

## `src/storage/interfaces.py`

**Imports**

- `.models: Context, DocumentRef, EmbeddingRecord, Skill`
- `__future__: annotations`
- `abc: ABC, abstractmethod`
- `datetime: datetime`
- `src.tasklists: TaskList`
- `src.topics.schemas: TopicEvent, TopicRecord`
- `typing: Any, Dict, Iterator, List, Optional, Tuple`

**Classes**

- `ContextStore(ABC)` — line 12
  - `get_context(self, account_name: str, context_id: str) -> Optional[Context] [line 14]`
  - `get_or_create_context(self, account_name: str, context_id: str) -> Context [line 19]`
  - `save_context(self, context: Context) -> None [line 28]`
  - `list_context_names(self, account_name: str) -> List[str] [line 32]`
  - `get_skill(self, account_name: str, skill_name: str) -> Optional[Skill] [line 48]`
  - `get_skill_text(self, account_name: str, skill_name: str) -> Optional[str] [line 57]`
- `TasklistStore(ABC)` — line 69
  - `list_tasklists(self, account_name: str) -> List[str] [line 71]`
  - `get_tasklist(self, account_name: str, tasklist_key: str) -> Optional[TaskList] [line 80]`
  - `save_tasklist(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None [line 85]`
  - `delete_tasklist(self, account_name: str, tasklist_key: str) -> None [line 90]`
  - `append_task_execution_record(self, account_name: str, tasklist_key: str, record: dict) -> None [line 95]`
  - `get_task_result(self, account_name: str, tasklist_key: str, task_id: str) -> Optional[dict] [line 102]`
- `DocumentStore(ABC)` — line 109
  - `list_documents(self, account_name: str, kind: Optional[str] = None, tag: Optional[str] = None, select_limit: int = 100) -> List[DocumentRef] [line 111]`
  - `get_document(self, document_id: str) -> Optional[DocumentRef] [line 122]`
  - `upsert_document(self, doc: DocumentRef) -> None [line 127]`
- `EmbeddingStore(ABC)` — line 132
  - `upsert_embedding(self, record: EmbeddingRecord) -> None [line 134]`
  - `query_embeddings(self, namespaces: List[str], account_name: str, query_vector: List[float], top_k: int = 10, filter: Optional[Dict[str, Any]] = None) -> List[Tuple[EmbeddingRecord, float]] [line 139]`
  - `delete_embeddings(self, namespace: str, account_name: str, *, source_id: Optional[str] = None, source_type: Optional[str] = None, record_id: Optional[str] = None) -> int [line 155]`
  - `list_embeddings(self, namespace: str, account_name: str) -> List[EmbeddingRecord] [line 175]`
  - `list_embedding_namespaces(self, account_name: str) -> List[str] [line 187]`
- `EventStore(ABC)` — line 197
  - `append_event(self, account: str, stream: str, event: TopicEvent) -> TopicEvent [line 211]`
  - `stream_events(self, account: str, stream: str) -> Iterator[TopicEvent] [line 220]`
  - `read_events(self, account: str, stream: str, *, start_ts: Optional[datetime] = None, end_ts: Optional[datetime] = None, limit: Optional[int] = None) -> List[TopicEvent] [line 225]`
- `TopicStore(ABC)` — line 238
  - `create_topic(self, account: str, name: str, slug_proposal: str, *, agent: str, description: Optional[str] = None) -> str [line 251]`
  - `rename_topic(self, account: str, slug: str, new_name: str, *, agent: str) -> None [line 264]`
  - `link_events(self, account: str, slug: str, event_ids: List[str], *, agent: str, reason: Optional[str] = None) -> None [line 276]`
  - `unlink_events(self, account: str, slug: str, event_ids: List[str], *, agent: str) -> None [line 289]`
  - `merge_topics(self, account: str, source: str, target: str, *, agent: str) -> None [line 301]`
  - `archive_topic(self, account: str, slug: str, *, agent: str, reason: Optional[str] = None) -> None [line 313]`
  - `get_topic(self, account: str, slug: str) -> Optional[TopicRecord] [line 325]`
  - `list_topics(self, account: str, *, kind: Optional[str] = None) -> List[TopicRecord] [line 330]`
- `HealthCheckable(ABC)` — line 341
  - `health_check(self) -> bool [line 343]`

## `src/storage/json_file_storage.py`

**Imports**

- `.base: Storage`
- `.json_file_storage_parts.contexts: ContextsMixin`
- `.json_file_storage_parts.documents: DocumentsMixin`
- `.json_file_storage_parts.embeddings: EmbeddingsMixin`
- `.json_file_storage_parts.tasklists: DEFAULT_RUN_TTL_DAYS, TasklistsMixin`
- `.models: UserProfile`
- `json`
- `logging`
- `os`
- `pathlib: Path`
- `src.storage_paths.storage_paths: StoragePaths`
- `typing: Any, Dict, Optional`
- `uuid`

**Classes**

- `JsonFileStorage(TasklistsMixin, ContextsMixin, DocumentsMixin, EmbeddingsMixin, Storage)` — line 24
  - `__init__(self, storage_paths: StoragePaths, tasklist_run_ttl_days: int = DEFAULT_RUN_TTL_DAYS) [line 38]`
  - `_atomic_write(self, path: Path, data: Dict[str, Any]) -> None [line 52]`
  - `_atomic_write_text(self, path: Path, text: str) -> None [line 65]`
  - `_atomic_replace(self, tmp_path: Path, target_path: Path) -> None [line 75]`
  - `_load_json(self, path: Path) -> Optional[Dict[str, Any]] [line 98]`
  - `_ensure_dir(self, path: Path) -> None [line 111]`
  - `get_user_profile(self, account_name: str) -> Optional[UserProfile] [line 119]`
  - `health_check(self) -> bool [line 135]`

## `src/storage/json_file_storage_parts/__init__.py`

## `src/storage/json_file_storage_parts/contexts.py`

> Context/skill implementation for JsonFileStorage (mixin part).

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `logging`
- `os`
- `re`
- `src.storage.models: Context, Skill`
- `typing: Any, Dict, List, Optional, Tuple`
- `yaml`

**Classes**

- `ContextsMixin` — line 100
  - `get_context(self, account_name: str, context_id: str) -> Optional[Context] [line 111]`
  - `_resolve_context_imports(self, ctx: Context, account_name: str) -> None [line 183]`
  - `get_or_create_context(self, account_name: str, context_id: str, *, default_data: Optional[Dict[str, Any]] = None) -> Context [line 207]`
  - `save_context(self, context: Context) -> None [line 258]`
  - `list_context_names(self, account_name: str) -> List[str] [line 314]`
  - `migrate_context_json_to_md(self) -> None [line 331]`
  - `get_skill(self, account_name: str, skill_name: str) -> Optional[Skill] [line 392]`
  - `get_skill_text(self, account_name: str, skill_name: str) -> Optional[str] [line 449]`

**Functions**

- `_now_utc() -> datetime` — line 21
- `_parse_dt_utc(dt_str: str) -> datetime` — line 26
- `_parse_context_frontmatter(fm: Optional[Dict[str, Any]]) -> Tuple[Optional[str], List[str], List[str], List[str], Dict[str, Any]]` — line 54

## `src/storage/json_file_storage_parts/documents.py`

**Imports**

- `__future__: annotations`
- `logging`
- `src.keywords.keywords: Keywords`
- `src.storage.models: DocumentRef`
- `typing: Any, Dict, List, Optional, Tuple`

**Classes**

- `DocumentsMixin` — line 10
  - `list_documents(self, account_name: str, kind: Optional[str] = None, tag: Optional[str] = None, select_limit: int = 100) -> List[DocumentRef] [line 17]`
  - `get_document(self, document_id: str) -> Optional[DocumentRef] [line 47]`
  - `upsert_document(self, doc: DocumentRef) -> None [line 64]`
  - `_doc_dict_to_ref(self, data: Dict[str, Any]) -> DocumentRef [line 80]`
  - `search_documents_poor_man(self, account_name: str, query: str, kind: Optional[str] = None, tag: Optional[str] = None, limit: int = 10) -> List[DocumentRef] [line 91]`

## `src/storage/json_file_storage_parts/embeddings.py`

> Embedding methods for JsonFileStorage (mixin part).

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `logging`
- `math`
- `src.storage.models: EmbeddingRecord`
- `typing: Any, Dict, List, Optional, Tuple`

**Classes**

- `EmbeddingsMixin` — line 51
  - `upsert_embedding(self, record: EmbeddingRecord) -> None [line 62]`
  - `list_embedding_namespaces(self, account_name: str) -> List[str] [line 90]`
  - `list_embeddings(self, namespace: str, account_name: str) -> List[EmbeddingRecord] [line 109]`
  - `delete_embeddings(self, namespace: str, account_name: str, *, source_id: Optional[str] = None, source_type: Optional[str] = None, record_id: Optional[str] = None) -> int [line 134]`
  - `query_embeddings(self, namespaces: List[str], account_name: str, query_vector: List[float], top_k: int = 10, filter: Optional[Dict[str, Any]] = None) -> List[Tuple[EmbeddingRecord, float]] [line 171]`
  - `_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float [line 220]`

**Functions**

- `_now_utc() -> datetime` — line 18
- `_parse_dt_utc(dt_str: str) -> datetime` — line 23

## `src/storage/json_file_storage_parts/tasklist_runs.py`

**Imports**

- `__future__: annotations`
- `json`
- `pathlib: Path`
- `typing: Optional`

**Classes**

- `TaskExecutionRecorder` — line 8
  - `append(runs_path: Path, record: dict) -> None [line 12]`
- `TaskExecutionReader` — line 21
  - `read_all(runs_path: Path) -> list[dict] [line 25]`
  - `latest(runs_path: Path, task_id: str) -> Optional[dict] [line 41]`

## `src/storage/json_file_storage_parts/tasklists.py`

**Imports**

- `.tasklist_runs: TaskExecutionReader, TaskExecutionRecorder`
- `__future__: annotations`
- `logging`
- `pathlib: Path`
- `src.tasklists: TaskList`
- `time`
- `typing: List, Optional`
- `uuid`

**Classes**

- `TasklistsMixin` — line 17
  - `_tasklists_dir(self, account_name: str) -> Path [line 24]`
  - `_tasklist_path(self, account_name: str, tasklist_id: str) -> Path [line 29]`
  - `_tasklist_runs_path(self, account_name: str, tasklist_key: str) -> Path [line 39]`
  - `list_tasklists(self, account_name: str) -> List[str] [line 43]`
  - `get_tasklist(self, account_name: str, tasklist_key: str) -> Optional[TaskList] [line 63]`
  - `save_tasklist(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None [line 72]`
  - `delete_tasklist(self, account_name: str, tasklist_key: str) -> None [line 116]`
  - `append_task_execution_record(self, account_name: str, tasklist_key: str, record: dict) -> None [line 132]`
  - `get_task_result(self, account_name: str, tasklist_key: str, task_id: str) -> Optional[dict] [line 138]`

## `src/storage/models.py`

> Module for defining data models used in the storage layer, including user profiles, context states, and references.

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass, field`
- `datetime: datetime, timezone`
- `typing: Any, Dict, List, Optional`

**Classes**

- `UserProfile` — line 22
- `Skill` — line 33
- `Context` — line 48
  - `__post_init__(self) [line 80]`
  - `resolved_text(self) -> str [line 86]`
  - `required_tools(self) -> List[str] [line 104]`
  - `to_data(self) -> Dict[str, Any] [line 116]`
- `DocumentRef` — line 146
- `EmbeddingRecord` — line 160

**Functions**

- `_order_preserving_dedupe(items: List[str]) -> List[str]` — line 131

## `src/storage/primitives_embedding_store.py`

> Embedding store backed by the generic-store doc/log protocol.

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `json`
- `logging`
- `pathlib: Path`
- `src.chat2.store_primitives: Chat2Primitives, StoreKey`
- `src.embeddings.comparison: cosine_similarity`
- `src.storage.interfaces: EmbeddingStore`
- `src.storage.models: EmbeddingRecord`
- `typing: Any, Dict, List, Optional, Tuple`

**Classes**

- `PrimitivesEmbeddingStore(EmbeddingStore)` — line 47
  - `__init__(self, store: Chat2Primitives) -> None [line 50]`
  - `_record_key(account_name: str, namespace: str, record_id: str) -> StoreKey [line 54]`
  - `_account_prefix(account_name: str) -> StoreKey [line 58]`
  - `_namespace_prefix(account_name: str, namespace: str) -> StoreKey [line 62]`
  - `_to_doc(record: EmbeddingRecord) -> str [line 66]`
  - `_from_doc(key: StoreKey, raw: str) -> Optional[EmbeddingRecord] [line 85]`
  - `upsert_embedding(self, record: EmbeddingRecord) -> None [line 108]`
  - `list_embedding_namespaces(self, account_name: str) -> List[str] [line 112]`
  - `list_embeddings(self, namespace: str, account_name: str) -> List[EmbeddingRecord] [line 122]`
  - `delete_embeddings(self, namespace: str, account_name: str, *, source_id: Optional[str] = None, source_type: Optional[str] = None, record_id: Optional[str] = None) -> int [line 135]`
  - `query_embeddings(self, namespaces: List[str], account_name: str, query_vector: List[float], top_k: int = 10, filter: Optional[Dict[str, Any]] = None) -> List[Tuple[EmbeddingRecord, float]] [line 162]`

**Functions**

- `_now_utc() -> datetime` — line 29
- `_parse_dt_utc(dt_str: str) -> datetime` — line 33
- `_default_embedding_db_path(config: Any) -> str` — line 196
- `build_primitives_embedding_store(config: Any) -> EmbeddingStore` — line 205

## `src/storage/vec0_embedding_store.py`

> Compatibility adapter for Lucy callers that still use Vec0EmbeddingStore.

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `galet_memory.ports.sqlite_vec: DEFAULT_SQLITE_VEC_EXTENSION_PATH, EmbeddingCompatibilityError, SqliteVecEmbeddingIndex`
- `galet_memory.ports: StoredEmbedding`
- `json`
- `pathlib: Path`
- `src.storage.interfaces: EmbeddingStore`
- `src.storage.models: EmbeddingRecord`
- `typing: Any, Dict, List, Optional, Tuple`

**Classes**

- `Vec0EmbeddingStore(EmbeddingStore)` — line 26
  - `__init__(self, db_path: str, sqlite_vec_extension_path: str | None = DEFAULT_SQLITE_VEC_EXTENSION_PATH) -> None [line 29]`
  - `_to_stored(record: EmbeddingRecord) -> StoredEmbedding [line 43]`
  - `_from_row(row: tuple[Any, ...], vector: List[float]) -> EmbeddingRecord [line 56]`
  - `upsert_embedding(self, record: EmbeddingRecord) -> None [line 71]`
  - `list_embedding_namespaces(self, account_name: str) -> List[str] [line 74]`
  - `list_embeddings(self, namespace: str, account_name: str) -> List[EmbeddingRecord] [line 77]`
  - `delete_embeddings(self, namespace: str, account_name: str, *, source_id: Optional[str] = None, source_type: Optional[str] = None, record_id: Optional[str] = None) -> int [line 103]`
  - `query_embeddings(self, namespaces: List[str], account_name: str, query_vector: List[float], top_k: int = 10, filter: Optional[Dict[str, Any]] = None) -> List[Tuple[EmbeddingRecord, float]] [line 128]`
  - `close(self) -> None [line 154]`
  - `__enter__(self) -> 'Vec0EmbeddingStore' [line 157]`
  - `__exit__(self, *_: object) -> None [line 160]`

## `src/storage_paths/storage_paths.py`

**Imports**

- `pathlib: Path`

**Classes**

- `StoragePaths` — line 3
  - `__init__(self, storage_root_path: str, storage_namespace: str) [line 13]`
  - `contexts(self) -> Path [line 23]`
  - `chats(self) -> Path [line 27]`
  - `documents(self) -> Path [line 31]`
  - `tasklists(self) -> Path [line 35]`
  - `skills(self) -> Path [line 39]`
  - `users(self) -> Path [line 43]`
  - `agents(self) -> Path [line 47]`
  - `resolve_relative(self, relative_path: str) -> Path [line 50]`
  - `index_for(self, domain: str, account: str, filename: str = 'index.json') -> Path [line 64]`
  - `domain_index(self, domain: str, *subpaths: str) -> Path [line 77]`

## `src/tasklists/__init__.py`

**Imports**

- `.service: TaskListService`
- `.task: Task`
- `.task_list: TaskList`
- `__future__: annotations`

## `src/tasklists/interfaces.py`

**Imports**

- `.task_list: TaskList`
- `__future__: annotations`
- `abc: ABC, abstractmethod`
- `typing: Any, Dict, List, Optional`

**Classes**

- `TasklistManager(ABC)` — line 9
  - `list(self, account_name: str) -> List[str] [line 11]`
  - `get(self, account_name: str, tasklist_key: str) -> Optional[TaskList] [line 15]`
  - `get_task_result(self, account_name: str, tasklist_key: str, task_id: str) -> Optional[dict] [line 19]`
  - `save(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None [line 25]`
  - `delete(self, account_name: str, tasklist_key: str) -> None [line 29]`
  - `create(self, tasklist_key: str, name: str, description: str, *, meta: Optional[Dict[str, Any]] = None, general_instructions: str = '') -> TaskList [line 33]`
  - `create_from_goal(self, tasklist_key: str, goal: str, files: Optional[List[str]] = None, worker_agent: Optional[str] = None) -> TaskList [line 45]`
  - `add_task(self, account_name: str, tasklist_key: str, *, task_id: str, task_name: str, task_instructions: str = '', task_state: Optional[str] = None, task_agent: Optional[str] = None, task_meta: Optional[Dict[str, Any]] = None, task_position: Optional[int] = None, task_parent_id: Optional[str] = None, task_files: Optional[List[str]] = None, task_context: Optional[str] = None, after_index: Optional[int] = None, validate_only: bool = False) -> TaskList [line 55]`
  - `update_task(self, account_name: str, tasklist_key: str, task_id: str, *, validate_only: bool = False, **changes: Any) -> TaskList [line 76]`
  - `remove_task(self, account_name: str, tasklist_key: str, task_id: str, *, validate_only: bool = False) -> TaskList [line 88]`
  - `set_state(self, account_name: str, tasklist_key: str, state: str, *, validate_only: bool = False) -> TaskList [line 99]`
  - `set_name(self, account_name: str, tasklist_key: str, name: str, *, validate_only: bool = False) -> TaskList [line 110]`
  - `set_description(self, account_name: str, tasklist_key: str, description: str, *, validate_only: bool = False) -> TaskList [line 121]`
  - `set_general_instructions(self, account_name: str, tasklist_key: str, instructions: str, *, validate_only: bool = False) -> TaskList [line 132]`
  - `update_meta(self, account_name: str, tasklist_key: str, meta: Dict[str, Any], *, validate_only: bool = False) -> TaskList [line 143]`
  - `reset(self, tasklist: TaskList) -> TaskList [line 154]`

## `src/tasklists/service.py`

**Imports**

- `.interfaces: TasklistManager`
- `.task: Task`
- `.task_list: TaskList`
- `.task_states: TASK_LIST_STATE_CREATED, TASK_STATE_PENDING`
- `__future__: annotations`
- `os`
- `typing: TYPE_CHECKING, Any, Dict, List, Optional`

**Classes**

- `TaskListService(TasklistManager)` — line 18
  - `__init__(self, store: TasklistStore) [line 21]`
  - `list(self, account_name: str) -> List[str] [line 24]`
  - `get(self, account_name: str, tasklist_key: str) -> Optional[TaskList] [line 27]`
  - `get_task_result(self, account_name: str, tasklist_key: str, task_id: str) -> Optional[dict] [line 30]`
  - `save(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None [line 35]`
  - `delete(self, account_name: str, tasklist_key: str) -> None [line 38]`
  - `create(self, tasklist_key: str, name: str, description: str, *, meta: Optional[Dict[str, Any]] = None, general_instructions: str = '') -> TaskList [line 41]`
  - `create_from_goal(self, tasklist_key: str, goal: str, files: Optional[List[str]] = None, worker_agent: Optional[str] = None) -> TaskList [line 61]`
  - `add_task(self, account_name: str, tasklist_key: str, *, task_id: str, task_name: str, task_instructions: str = '', task_state: Optional[str] = None, task_agent: Optional[str] = None, task_meta: Optional[Dict[str, Any]] = None, task_position: Optional[int] = None, task_parent_id: Optional[str] = None, task_files: Optional[List[str]] = None, task_context: Optional[str] = None, after_index: Optional[int] = None, validate_only: bool = False) -> TaskList [line 102]`
  - `update_task(self, account_name: str, tasklist_key: str, task_id: str, *, validate_only: bool = False, **changes: Any) -> TaskList [line 138]`
  - `remove_task(self, account_name: str, tasklist_key: str, task_id: str, *, validate_only: bool = False) -> TaskList [line 153]`
  - `set_state(self, account_name: str, tasklist_key: str, state: str, *, validate_only: bool = False) -> TaskList [line 167]`
  - `set_name(self, account_name: str, tasklist_key: str, name: str, *, validate_only: bool = False) -> TaskList [line 181]`
  - `set_description(self, account_name: str, tasklist_key: str, description: str, *, validate_only: bool = False) -> TaskList [line 195]`
  - `set_general_instructions(self, account_name: str, tasklist_key: str, instructions: str, *, validate_only: bool = False) -> TaskList [line 209]`
  - `update_meta(self, account_name: str, tasklist_key: str, meta: Dict[str, Any], *, validate_only: bool = False) -> TaskList [line 223]`
  - `_load_required(self, account_name: str, tasklist_key: str) -> TaskList [line 239]`
  - `reset(self, tasklist: TaskList) -> TaskList [line 245]`

## `src/tasklists/task.py`

**Imports**

- `.task_states: TASK_STATE_PENDING`
- `__future__: annotations`
- `dataclasses: dataclass, field`
- `json`
- `pydantic: BaseModel, Field`
- `typing: Any, Dict, Optional`

**Classes**

- `_TaskModel(BaseModel)` — line 12
- `Task` — line 31
  - `__init__(self, id: Any, name: str, instructions: str = '', *, state: str = TASK_STATE_PENDING, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None, meta: Optional[Dict[str, Any]] = None, agent: Optional[str] = None, position: Optional[int] = None, files: Optional[list[str]] = None, parent_id: Optional[str] = None, run_metrics: Optional[Dict[str, Any]] = None, context: Optional[str] = None) -> None [line 46]`
  - `to_dict(self) -> Dict[str, Any] [line 79]`
  - `from_dict(cls, data: Dict[str, Any]) -> 'Task' [line 101]`
  - `to_json(self) -> str [line 128]`
  - `from_json(cls, s: str) -> 'Task' [line 132]`

## `src/tasklists/task_list.py`

**Imports**

- `.task: Task, _TaskModel`
- `.task_states: TASK_LIST_STATE_CREATED, TASK_STATE_PENDING`
- `__future__: annotations`
- `dataclasses: dataclass, field`
- `json`
- `pydantic: BaseModel, Field, field_validator`
- `typing: Any, Dict, Iterable, List, Optional`
- `uuid`

**Classes**

- `_TaskListModel(BaseModel)` — line 29
  - `check_schema_version(cls, v) [line 44]`
- `TaskList` — line 54
  - `__post_init__(self) -> None [line 65]`
  - `task_list(self) -> Iterable[Task] [line 109]`
  - `get_task(self, id: str) -> Optional[Task] [line 112]`
  - `next_id(self) -> str [line 118]`
  - `add_task(self, task: Task, *, after_index: Optional[int] = None) -> None [line 121]`
  - `update_task(self, id: str, **changes: Any) -> None [line 133]`
  - `remove_task(self, id: str) -> None [line 164]`
  - `update_task_state(self, id: str, new_state: str) -> None [line 171]`
  - `set_task_result(self, id: str, result: Dict[str, Any], *, new_state: Optional[str] = None, error: Optional[str] = None) -> None [line 177]`
  - `get_children(self, parent_id: str) -> List[Task] [line 194]`
  - `to_dict(self) -> Dict[str, Any] [line 206]`
  - `from_dict(cls, data: Dict[str, Any], id: Optional[str] = None) -> 'TaskList' [line 228]`
  - `to_json(self) -> str [line 281]`
  - `from_json(cls, json_str: str) -> 'TaskList' [line 285]`

## `src/tasklists/task_states.py`

> Shared vocabulary constants for task lists.

## `src/tool_selection/__init__.py`

> Tool selection pipeline package (issue #126, design doc §5).

**Imports**

- `.errors: ToolSelectionError`
- `.pipeline: ToolSelection, ToolSelectionPipeline`

## `src/tool_selection/errors.py`

**Imports**

- `__future__: annotations`
- `typing: List, Literal, Sequence, Union`

**Classes**

- `ToolSelectionError(Exception)` — line 33
  - `__init__(self, code: ToolSelectionCode, message_or_tools: Union[str, Sequence[str], None] = None) -> None [line 34]`

**Functions**

- `_format_tools(tools: Sequence[str]) -> str` — line 27

## `src/tool_selection/pipeline.py`

**Imports**

- `.: selection`
- `.errors: ToolSelectionError`
- `__future__: annotations`
- `dataclasses: dataclass`
- `json`
- `logging`
- `src.agent.caps: resolve_effective_cap`
- `typing: Any, Dict, List, Optional, Tuple`

**Classes**

- `ToolSelection` — line 31
- `LLMResolver` — line 71
  - `__init__(self, config, agent, llm_adapter) [line 72]`
  - `resolve(self) -> Tuple[str, Optional[str]] [line 77]`
  - `call_llm(self, messages: List[Dict[str, str]], model: str, provider: Optional[str]) -> str [line 105]`
- `ToolSelectionPipeline` — line 114
  - `__init__(self, registry, storage, llm_adapter, config) [line 115]`
  - `resolve(self, agent, account_name: str, context_name: str, prompt_text: str) -> ToolSelection [line 121]`
  - `get_tool_handler_defs(self, agent, account_name: str, context_name: str, prompt_text: str) -> List[Dict[str, Any]] [line 166]`
  - `_should_select_prompt_based(self, eligible: List[str]) -> Tuple[bool, Dict[str, Any]] [line 170]`
  - `_select_prompt_based(self, prompt_text: str, agent, eligible: List[str]) -> Tuple[List[str], Dict[str, Any]] [line 187]`
  - `_defs_by_name(self, names: List[str]) -> List[Dict[str, Any]] [line 207]`

**Functions**

- `get_agent_allowed_tools(agent) -> List[str]` — line 40
- `get_all_tools_from_registry(registry) -> List[str]` — line 46
- `get_required_tools(storage, account_name: str, context_name: str) -> List[str]` — line 49
- `query_llm(prompt_text: str, eligible_defs: List[Dict[str, Any]], *, llm_call, model: str, provider: Optional[str], config) -> List[str]` — line 213
- `_resolve_prompt_style(config) -> str` — line 233
- `_validate_required(required: List[str], allowed_set: set, registry_names_set: set) -> None` — line 238
- `_schema_tokens(function_defs: List[Dict[str, Any]]) -> int` — line 248
- `_as_int(value, default: int) -> int` — line 258
- `_first_non_empty(*values: Any) -> Optional[str]` — line 264
- `_config_section(config, key: str) -> Dict[str, Any]` — line 273
- `_infer_provider(model: str) -> Optional[str]` — line 288
- `_load_context(storage, account_name: str, context_name: str) -> Optional[Any]` — line 295
- `_order_preserving_dedupe(items: List[str]) -> List[str]` — line 319

## `src/tool_selection/selection.py`

**Imports**

- `__future__: annotations`
- `json`
- `re`
- `typing: Any, Callable, Dict, List, Optional, Tuple`

**Functions**

- `_one_line_description(td: Dict[str, Any]) -> str` — line 28
- `_build_menu(defs: List[Dict[str, Any]]) -> str` — line 35
- `_build_selection_messages(menu: str, prompt_text: str, prompt_style: str = 'verb_first') -> List[Dict[str, str]]` — line 42
- `_parse_json_array(text: str) -> List[str]` — line 47
- `_clamp_to_known(names: List[str], known: List[str]) -> List[str]` — line 81
- `suggest_tools(prompt_text: str, eligible_defs: List[Dict[str, Any]], *, llm_call: Callable[[List[Dict[str, str]]], str], model: str, provider: Optional[str], prompt_style: str = 'verb_first') -> Tuple[List[str], Dict[str, Any]]` — line 86

## `src/topics/__init__.py`

> Standalone topics component (issue #129).

**Imports**

- `.schemas: EVENT_LOG_SCHEMA_VERSION, INBOX_STREAM, KIND_CHAT2_EVENT, KIND_TOPIC_ARCHIVED, KIND_TOPIC_CREATED, KIND_TOPIC_LINK, KIND_TOPIC_MERGED, KIND_TOPIC_RENAMED, KIND_TOPIC_UNLINK, MIGRATION_SOURCE_CHAT2, SLUG_MAX_LENGTH, SLUG_MIN_LENGTH, SLUG_PATTERN, TOPICS_DIR, TOPIC_KINDS, Chat2EventPayload, EventProvenance, TopicArchivedPayload, TopicCreatedPayload, TopicEvent, TopicLinkPayload, TopicMergedPayload, TopicPayload, TopicRecord, TopicRenamedPayload, TopicUnlinkPayload, inbox_path, is_valid_slug, normalize_slug, resolve_slug, stream_path, validate_slug`

## `src/topics/index.py`

> Topic projection / derived index (issue #129).

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass, field`
- `datetime: datetime`
- `src.storage.interfaces: EventStore`
- `src.topics.schemas: INBOX_STREAM, KIND_TOPIC_ARCHIVED, KIND_TOPIC_CREATED, KIND_TOPIC_LINK, KIND_TOPIC_MERGED, KIND_TOPIC_RENAMED, KIND_TOPIC_UNLINK, TopicEvent, TopicRecord`
- `typing: Dict, List, Optional, Set`

**Classes**

- `_TopicState` — line 74
- `_AccountState` — line 87
- `TopicIndex` — line 99
  - `__init__(self, store: EventStore) -> None [line 107]`
  - `rebuild(self, account: str) -> None [line 115]`
  - `apply_event(self, account: str, event: TopicEvent) -> None [line 127]`
  - `get_topic(self, account: str, topic_id: str) -> Optional[TopicRecord] [line 136]`
  - `list_topics(self, account: str, *, include_archived: bool = False) -> List[TopicRecord] [line 150]`
  - `topics_by_kind(self, account: str, kind: str, *, include_archived: bool = False) -> List[TopicRecord] [line 166]`
  - `event_ids(self, account: str, topic_id: str) -> List[str] [line 184]`
  - `is_archived(self, account: str, topic_id: str) -> bool [line 192]`
  - `topic_ids(self, account: str, *, include_archived: bool = False) -> List[str] [line 200]`
  - `_apply(self, state: _AccountState, event: TopicEvent, stream: str) -> None [line 211]`
  - `_record(ts: _TopicState) -> TopicRecord [line 296]`

## `src/topics/migration.py`

> Migration from named chat2 sessions into topics (issue #129, review blocker

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass, field`
- `datetime: datetime, timezone`
- `json`
- `pathlib: Path`
- `src.storage.interfaces: EventStore`
- `src.topics.index: TopicIndex`
- `src.topics.mutation: TopicMutations`
- `src.topics.schemas: KIND_CHAT2_EVENT, MIGRATION_SOURCE_CHAT2, Chat2EventPayload, EventProvenance, TopicEvent`
- `typing: Any, List, Optional, Set`

**Classes**

- `Chat2MigrationError(Exception)` — line 86
- `Chat2ReadError(Chat2MigrationError)` — line 90
- `Chat2EventRecord` — line 98
- `Chat2Session` — line 111
- `Chat2Scan` — line 121
- `MigrationReport` — line 132
  - `ok(self) -> bool [line 147]`
- `TopicMigrator` — line 281
  - `__init__(self, store: EventStore, index: Optional[TopicIndex] = None, *, agent: str = MIGRATION_AGENT) -> None [line 293]`
  - `migrate(self, chat2_root: Path | str, account: str) -> MigrationReport [line 308]`
  - `_migrate_session(self, account: str, session: Chat2Session) -> str [line 340]`
  - `_to_topic_event(self, account: str, slug: str, record: Chat2EventRecord, session_id: str, migrated_at: datetime) -> TopicEvent [line 368]`
  - `_migrated_session_ids(self, account: str) -> Set[str] [line 405]`

**Functions**

- `scan_chat2_sessions(chat2_root: Path | str, *, account: str) -> Chat2Scan` — line 157
- `_read_events(path: Path, *, session_id: str) -> List[Chat2EventRecord]` — line 219

## `src/topics/mutation.py`

> Topic mutation API (issue #129) - create/rename/link/unlink/merge/archive.

**Imports**

- `__future__: annotations`
- `src.storage.interfaces: EventStore`
- `src.topics.index: TopicIndex`
- `src.topics.schemas: INBOX_STREAM, KIND_TOPIC_ARCHIVED, KIND_TOPIC_CREATED, KIND_TOPIC_LINK, KIND_TOPIC_MERGED, KIND_TOPIC_RENAMED, KIND_TOPIC_UNLINK, TopicArchivedPayload, TopicCreatedPayload, TopicEvent, TopicLinkPayload, TopicMergedPayload, TopicRecord, TopicRenamedPayload, TopicUnlinkPayload, resolve_slug`
- `typing: List, Optional, Set`

**Classes**

- `TopicError(Exception)` — line 79
- `TopicNotFoundError(TopicError)` — line 83
- `TopicArchivedError(TopicError)` — line 87
- `TopicMutations` — line 94
  - `__init__(self, store: EventStore, index: Optional[TopicIndex] = None) -> None [line 110]`
  - `create_topic(self, account: str, name: str, slug_proposal: str, *, agent: str, description: Optional[str] = None) -> str [line 123]`
  - `rename_topic(self, account: str, slug: str, new_name: str, *, agent: str) -> None [line 158]`
  - `link_events(self, account: str, slug: str, event_ids: List[str], *, agent: str, reason: Optional[str] = None) -> None [line 179]`
  - `unlink_events(self, account: str, slug: str, event_ids: List[str], *, agent: str) -> None [line 201]`
  - `merge_topics(self, account: str, source: str, target: str, *, agent: str) -> None [line 222]`
  - `archive_topic(self, account: str, slug: str, *, agent: str, reason: Optional[str] = None) -> None [line 286]`
  - `index(self) -> TopicIndex [line 312]`
  - `rebuild(self, account: str) -> None [line 316]`
  - `_ensure_synced(self, account: str) -> None [line 321]`
  - `_require_topic(self, account: str, slug: str) -> TopicRecord [line 327]`
  - `_require_active(self, account: str, slug: str) -> TopicRecord [line 336]`
  - `_append(self, account: str, stream: str, event: TopicEvent) -> None [line 344]`
  - `_event(kind: str, payload, *, account: str, stream: str, agent: str) -> TopicEvent [line 350]`

## `src/topics/queries.py`

> Topic query API (issue #129) - read-only projections over the event log.

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `src.storage.interfaces: EventStore, TopicStore`
- `src.topics.index: TopicIndex`
- `src.topics.mutation: TopicMutations`
- `src.topics.schemas: TopicEvent, TopicRecord`
- `typing: Dict, List, Optional, Set`

**Classes**

- `TopicQueries` — line 57
  - `__init__(self, store: EventStore, index: Optional[TopicIndex] = None) -> None [line 68]`
  - `get_topic(self, account: str, slug: str) -> Optional[TopicRecord] [line 84]`
  - `list_topics(self, account: str, *, kind: Optional[str] = None, include_archived: bool = False) -> List[TopicRecord] [line 94]`
  - `topics_by_kind(self, account: str, kind: str, *, include_archived: bool = False) -> List[TopicRecord] [line 115]`
  - `topic_ids(self, account: str, *, include_archived: bool = False) -> List[str] [line 130]`
  - `is_archived(self, account: str, slug: str) -> bool [line 135]`
  - `events_in_topic(self, account: str, slug: str, *, limit: Optional[int] = None, start_ts: Optional[datetime] = None, end_ts: Optional[datetime] = None) -> List[TopicEvent] [line 144]`
  - `event_ids(self, account: str, slug: str) -> List[str] [line 194]`
  - `index(self) -> TopicIndex [line 204]`
  - `rebuild(self, account: str) -> None [line 208]`
  - `refresh(self, account: str) -> None [line 214]`
  - `_ensure_synced(self, account: str) -> None [line 224]`
  - `_scan_events(self, account: str) -> Dict[str, TopicEvent] [line 229]`
- `TopicStoreImpl(TopicStore)` — line 242
  - `__init__(self, store: EventStore, index: Optional[TopicIndex] = None) -> None [line 258]`
  - `create_topic(self, account: str, name: str, slug_proposal: str, *, agent: str, description: Optional[str] = None) -> str [line 270]`
  - `rename_topic(self, account: str, slug: str, new_name: str, *, agent: str) -> None [line 285]`
  - `link_events(self, account: str, slug: str, event_ids: List[str], *, agent: str, reason: Optional[str] = None) -> None [line 296]`
  - `unlink_events(self, account: str, slug: str, event_ids: List[str], *, agent: str) -> None [line 310]`
  - `merge_topics(self, account: str, source: str, target: str, *, agent: str) -> None [line 321]`
  - `archive_topic(self, account: str, slug: str, *, agent: str, reason: Optional[str] = None) -> None [line 332]`
  - `get_topic(self, account: str, slug: str) -> Optional[TopicRecord] [line 345]`
  - `list_topics(self, account: str, *, kind: Optional[str] = None) -> List[TopicRecord] [line 348]`
  - `topics_by_kind(self, account: str, kind: str, *, include_archived: bool = False) -> List[TopicRecord] [line 358]`
  - `events_in_topic(self, account: str, slug: str, *, limit: Optional[int] = None, start_ts: Optional[datetime] = None, end_ts: Optional[datetime] = None) -> List[TopicEvent] [line 370]`
  - `event_ids(self, account: str, slug: str) -> List[str] [line 384]`
  - `topic_ids(self, account: str, *, include_archived: bool = False) -> List[str] [line 388]`
  - `is_archived(self, account: str, slug: str) -> bool [line 392]`
  - `index(self) -> TopicIndex [line 399]`
  - `mutations(self) -> TopicMutations [line 404]`
  - `queries(self) -> TopicQueries [line 409]`
  - `rebuild(self, account: str) -> None [line 413]`

**Functions**

- `_as_utc(dt: datetime) -> datetime` — line 419

## `src/topics/schemas.py`

> Topic event schemas and stream layout - single source of truth (issue #129).

**Imports**

- `__future__: annotations`
- `collections.abc: Collection`
- `datetime: datetime, timezone`
- `pydantic: BaseModel, ConfigDict, Field, field_validator, model_validator`
- `re`
- `typing: Any, List, Literal, Optional, Union`
- `unicodedata`
- `uuid: uuid4`

**Classes**

- `TopicCreatedPayload(BaseModel)` — line 185
  - `_validate_slug(cls, v: str) -> str [line 201]`
- `TopicRenamedPayload(BaseModel)` — line 205
- `TopicMergedPayload(BaseModel)` — line 217
  - `_validate_slug(cls, v: str) -> str [line 231]`
- `TopicArchivedPayload(BaseModel)` — line 235
- `TopicLinkPayload(BaseModel)` — line 247
  - `_validate_topic(cls, v: str) -> str [line 263]`
  - `_validate_event_ids(cls, v: List[str]) -> List[str] [line 268]`
- `TopicUnlinkPayload(BaseModel)` — line 274
  - `_validate_topic(cls, v: str) -> str [line 288]`
  - `_validate_event_ids(cls, v: List[str]) -> List[str] [line 293]`
- `EventProvenance(BaseModel)` — line 299
- `Chat2EventPayload(BaseModel)` — line 316
- `TopicEvent(BaseModel)` — line 394
  - `_coerce_payload_by_kind(cls, data: Any) -> Any [line 419]`
  - `_ensure_utc(cls, v: datetime) -> datetime [line 442]`
  - `_validate_account(cls, v: str) -> str [line 450]`
  - `_validate_stream(cls, v: str) -> str [line 456]`
  - `_check_kind_payload(self) -> 'TopicEvent' [line 461]`
- `TopicRecord(BaseModel)` — line 477
  - `_validate_topic_id(cls, v: str) -> str [line 502]`

**Functions**

- `normalize_slug(proposal: str) -> str` — line 121
- `is_valid_slug(slug: str) -> bool` — line 138
- `validate_slug(slug: str, *, field: str = 'slug') -> str` — line 143
- `resolve_slug(proposal: str, existing: Collection[str]) -> str` — line 154
- `_validate_account_name(account: str) -> None` — line 365
- `_validate_stream_name(stream: str) -> None` — line 377
- `stream_path(account: str, stream: str) -> str` — line 511
- `inbox_path(account: str) -> str` — line 527

## `src/topics/streams.py`

> Topic stream handling (issue #129) - the EventStore seam over JSONL files.

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `src.storage.interfaces: EventStore`
- `src.topics.schemas: INBOX_STREAM, KIND_TOPIC_ARCHIVED, KIND_TOPIC_CREATED, KIND_TOPIC_LINK, KIND_TOPIC_MERGED, KIND_TOPIC_UNLINK, TopicEvent, inbox_path, stream_path`
- `typing: Iterator, List, Optional, Tuple`

**Classes**

- `StreamError(Exception)` — line 60
- `StreamNotFoundError(StreamError)` — line 64
- `StreamArchivedError(StreamError)` — line 72
- `JsonlEventStore(EventStore)` — line 80
  - `__init__(self, data_root: Path | str) -> None [line 88]`
  - `_path(self, account: str, stream: str) -> Path [line 98]`
  - `_account_dir(self, account: str) -> Path [line 103]`
  - `append_event(self, account: str, stream: str, event: TopicEvent) -> TopicEvent [line 111]`
  - `stream_events(self, account: str, stream: str) -> Iterator[TopicEvent] [line 153]`
  - `read_events(self, account: str, stream: str, *, start_ts: Optional[datetime] = None, end_ts: Optional[datetime] = None, limit: Optional[int] = None) -> List[TopicEvent] [line 164]`
  - `create_stream(self, account: str, stream: str) -> None [line 189]`
  - `stream_exists(self, account: str, stream: str) -> bool [line 204]`
  - `list_streams(self, account: str) -> List[str] [line 208]`
  - `is_archived(self, account: str, stream: str) -> bool [line 222]`
  - `_check_envelope_consistency(self, account: str, stream: str, event: TopicEvent) -> None [line 230]`
  - `_is_archived(self, account: str, stream: str) -> bool [line 263]`

**Functions**

- `_append_line(path: Path, event: TopicEvent) -> None` — line 297
- `_iter_lines(path: Path) -> Iterator[str]` — line 305
- `_as_utc(dt: datetime) -> datetime` — line 311

## `src/utils/document_context.py`

**Imports**

- `__future__: annotations`
- `logging`
- `src.storage.interfaces: DocumentStore`
- `src.utils.text_snippet_loader: load_text_snippet`
- `typing: Any, Dict, List, Optional, Tuple`

**Functions**

- `get_document_context(storage: DocumentStore, account_name: str, query: str, *, kind: str | None = None, docs_tag: str | None = None, limit: int = 3, max_chars: int = 6000) -> List[Dict[str, Any]]` — line 10
- `get_document_context_traced(storage: DocumentStore, account_name: str, query: str, *, kind: str | None = None, docs_tag: str | None = None, limit: int = 3, max_chars: int = 6000, keywords: Any | None = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]` — line 92

## `src/utils/migrate_legacy_completions.py`

**Imports**

- `collections: defaultdict`
- `datetime: datetime, timezone`
- `json`
- `pathlib: Path`
- `typing: Any, Dict, List, Optional`

**Functions**

- `parse_dt_utc(dt_str: str) -> datetime` — line 11
- `iso_utc(dt: datetime) -> str` — line 36
- `safe_first_line(text: str, max_len: int = 80) -> str` — line 45
- `migrate(account_name: str = 'junwin', agent_name: str = 'lucy') -> None` — line 52

## `src/utils/obsidian_importer.py`

**Imports**

- `__future__: annotations`
- `hashlib`
- `logging`
- `pathlib: Path`
- `re`
- `src.storage.base: Storage`
- `src.storage.models: DocumentRef`
- `typing: Optional`
- `yaml`

**Functions**

- `_stable_doc_id_from_path(vault_name: str, relative_path: str) -> str` — line 24
- `_extract_title(md_path: Path, contents: Optional[str] = None) -> str` — line 42
- `_extract_tags(contents: str) -> list[str]` — line 51
- `_generate_search_aliases(relative_path: str, title: str, vault_name: str, tags: list[str] | None = None) -> list[str]` — line 95
- `index_obsidian_file(storage: Storage, account_name: str, md_path: str | Path, *, vault_root: Optional[str | Path] = None, kind: str = 'obsidian_note') -> list[DocumentRef]` — line 152
- `index_obsidian_vault(storage: Storage, account_name: str, vault_path: str | Path, *, kind: str = 'obsidian_note', max_files: Optional[int] = None, recursive: bool = False) -> list[DocumentRef]` — line 256

## `src/utils/scrape.py`

> Simple webpage text scraper.

**Imports**

- `__future__: annotations`
- `bs4: BeautifulSoup`
- `re`
- `requests`
- `sys`
- `typing: Iterable, Optional`

**Functions**

- `_remove_elements(soup: BeautifulSoup, selectors: Iterable[str]) -> None` — line 26
- `extract_text_from_html(html: str) -> str` — line 32
- `scrape_url(url: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str` — line 69
- `main(argv: Optional[list[str]] = None) -> int` — line 84

## `src/utils/text_snippet_loader.py`

**Imports**

- `__future__: annotations`
- `logging`
- `pathlib: Path`
- `typing: Tuple`

**Functions**

- `load_text_snippet(path: str | Path, max_chars: int = DEFAULT_MAX_CHARS) -> Tuple[str, bool]` — line 11

## `src/workflows/__init__.py`

> Goal-driven workflow orchestration prototype.

**Imports**

- `.executor: AskWorkflowExecutor, FakeWorkflowExecutor, WorkflowExecutor`
- `.loader: WorkflowLoader`
- `.node: WorkflowNode`
- `.result: WorkflowResult`
- `.runner: WorkflowRunner`

## `src/workflows/executor.py`

**Imports**

- `.node: WorkflowNode`
- `.result: WorkflowResult`
- `__future__: annotations`
- `collections: defaultdict, deque`
- `json`
- `pathlib: Path`
- `requests`
- `typing: Any, Callable, Deque, Dict, Iterable, Mapping, Protocol`

**Classes**

- `WorkflowExecutor(Protocol)` — line 14
  - `execute(self, node: WorkflowNode) -> WorkflowResult [line 15]`
- `FakeWorkflowExecutor` — line 19
  - `__init__(self, results: Mapping[str, WorkflowResult | Iterable[WorkflowResult]]) [line 22]`
  - `execute(self, node: WorkflowNode) -> WorkflowResult [line 33]`
- `AskWorkflowExecutor` — line 46
  - `__init__(self, *, account_name: str, ask_url: str = 'http://127.0.0.1:5000/ask', default_agent: str = 'peace', default_context: str = 'lucyproject', timeout: float = 300.0, config_path: str | Path = 'config.local.json', api_key: str | None = None, post: Callable[..., Any] | None = None) -> None [line 59]`
  - `execute(self, node: WorkflowNode) -> WorkflowResult [line 80]`
  - `_question(node: WorkflowNode) -> str [line 146]`
  - `_load_api_key(config_path: Path) -> str [line 154]`
  - `_response_body(response: Any) -> Any [line 164]`
  - `_ask_text(body: Any) -> str [line 171]`
  - `_ask_error(body: Any) -> str [line 177]`

## `src/workflows/loader.py`

**Imports**

- `.node: WorkflowNode`
- `__future__: annotations`
- `pathlib: Path`
- `typing: Any, Dict, Iterable`
- `yaml`

**Classes**

- `WorkflowLoader` — line 14
  - `load_file(self, path: str | Path) -> WorkflowNode [line 17]`
  - `load_text(self, text: str) -> WorkflowNode [line 22]`
  - `load_dict(self, data: Dict[str, Any]) -> WorkflowNode [line 25]`
  - `_build_node(self, data: Dict[str, Any], *, default_id: str | None = None) -> WorkflowNode [line 34]`
  - `_validate_unique_ids(nodes: Iterable[WorkflowNode]) -> None [line 93]`
  - `_validate_targets(root: WorkflowNode) -> None [line 101]`

## `src/workflows/node.py`

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass, field`
- `typing: Any, Dict, List, Optional`

**Classes**

- `WorkflowNode` — line 8
  - `add_child(self, child: 'WorkflowNode') -> None [line 32]`
  - `walk(self) -> List['WorkflowNode'] [line 36]`

## `src/workflows/result.py`

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass, field`
- `typing: Any, Dict`

**Classes**

- `WorkflowResult` — line 11
  - `__post_init__(self) -> None [line 24]`

## `src/workflows/runner.py`

**Imports**

- `.executor: WorkflowExecutor`
- `.node: WorkflowNode`
- `.result: WorkflowResult`
- `__future__: annotations`
- `typing: Dict`

**Classes**

- `WorkflowRunner` — line 10
  - `__init__(self, executor: WorkflowExecutor, *, max_tokens: int | None = None) -> None [line 17]`
  - `run(self, root: WorkflowNode) -> WorkflowResult [line 23]`
  - `_run_sequence(self, sequence: WorkflowNode) -> WorkflowResult [line 39]`
  - `_run_node(self, node: WorkflowNode) -> WorkflowResult [line 96]`
  - `_run_retry(self, node: WorkflowNode) -> WorkflowResult [line 117]`
  - `_execute_leaf(self, node: WorkflowNode, *, attempt_limit: int) -> WorkflowResult [line 145]`
  - `_budget_exceeded(self) -> bool [line 169]`

## `static/data/auto/load_scrum_file.py`

## `tests/__init__.py`

## `tests/chat2/test_correlation.py`

> Tests for the correlation to event mapping (src/chat2/correlation.py).

**Imports**

- `__future__: annotations`
- `datetime: datetime`
- `pytest`
- `src.chat2.adapters.jfs_adapter: JfsChat2Primitives`
- `src.chat2.correlation: get_event_ids, get_links, link_event`
- `src.chat2.facade: Chat2Store`
- `src.chat2.models: ChatEvent`
- `src.chat2.store_primitives: Chat2Primitives, InMemoryStore, StoreKey`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage_paths.storage_paths: StoragePaths`
- `uuid`

**Classes**

- `TestCorrelationMapping` — line 74
  - `test_link_round_trip(self, store: Chat2Primitives, facade: Chat2Store) -> None [line 77]`
  - `test_link_order_preserved(self, store: Chat2Primitives, facade: Chat2Store) -> None [line 91]`
  - `test_n_events_per_correlation_across_sessions(self, store: Chat2Primitives, facade: Chat2Store) -> None [line 101]`
  - `test_link_dedupe(self, store: Chat2Primitives, facade: Chat2Store) -> None [line 118]`
  - `test_missing_correlation_empty(self, store: Chat2Primitives, facade: Chat2Store) -> None [line 130]`
  - `test_falsy_correlation_noop(self, store: Chat2Primitives, facade: Chat2Store) -> None [line 139]`
  - `test_invalid_correlation_id_rejected(self, store: Chat2Primitives, facade: Chat2Store) -> None [line 152]`
  - `test_ts_serialized_as_iso(self, store: Chat2Primitives, facade: Chat2Store) -> None [line 164]`
- `TestFacadeCorrelation` — line 186
  - `test_get_events_by_correlation_in_link_order(self, facade: Chat2Store) -> None [line 189]`
  - `test_facade_link_noop_falsy(self, facade: Chat2Store) -> None [line 209]`
  - `test_get_events_by_correlation_skips_missing_events(self, store: Chat2Primitives, facade: Chat2Store) -> None [line 219]`

**Functions**

- `_make_jfs(tmp_path) -> JfsChat2Primitives` — line 29
- `store(request, tmp_path) -> Chat2Primitives` — line 35
- `facade(store: Chat2Primitives) -> Chat2Store` — line 43
- `_new_session_with_events(facade: Chat2Store, count: int) -> tuple[str, list[ChatEvent]]` — line 47

## `tests/chat2/test_edge_cases.py`

> Edge case tests for Chat v2 storage layer.

**Imports**

- `__future__: annotations`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `pytest`
- `src.chat2.fs_primitives: FileChat2Primitives`
- `src.chat2.jsonl_store: create_session, stream_events`
- `src.chat2.models: ChatEvent, ChatSessionMeta, SessionLinks`
- `src.chat2.store_primitives: Chat2Primitives, StoreKey`
- `tests.chat2.test_primitives: InMemoryStore`

**Classes**

- `TestFsPathTraversal` — line 37
  - `test_resolve_outside_root_raises(self, tmp_path: Path) -> None [line 38]`
  - `test_resolve_outside_root_with_absolute_key(self, tmp_path: Path) -> None [line 47]`
- `TestStreamEventsEdgeCases` — line 58
  - `test_skips_empty_lines_in_jsonl(self, store: Chat2Primitives) -> None [line 59]`
  - `test_handles_trailing_newline(self, store: Chat2Primitives) -> None [line 78]`
- `TestSessionLinksEdgeCases` — line 95
  - `test_valid_uuids_accepted(self) -> None [line 96]`
  - `test_none_values_accepted(self) -> None [line 105]`
- `TestPayloadValidation` — line 119
  - `test_rejects_integer_payload(self) -> None [line 120]`
  - `test_rejects_list_payload(self) -> None [line 131]`
- `TestTimezoneHandling` — line 147
  - `test_chat_event_with_timezone_aware_ts(self) -> None [line 148]`
  - `test_chat_event_with_naive_ts(self) -> None [line 160]`
  - `test_session_meta_with_timezone_aware_ts(self) -> None [line 173]`
  - `test_session_meta_with_naive_ts(self) -> None [line 187]`

**Functions**

- `store() -> Chat2Primitives` — line 29

## `tests/chat2/test_errors.py`

> Tests for chat2 error classes.

**Imports**

- `pytest`
- `src.chat2.errors: Chat2Error, CorruptEventLogError, CorruptMetaError, EventNotFoundError, SessionNotFoundError, StorageOperationError`

**Classes**

- `TestChat2Error` — line 17
  - `test_is_exception(self) [line 20]`
  - `test_can_raise_and_catch(self) [line 23]`
  - `test_message(self) [line 27]`
- `TestSessionNotFoundError` — line 32
  - `test_has_session_id(self) [line 35]`
  - `test_is_chat2_error(self) [line 40]`
  - `test_catch_base(self) [line 43]`
- `TestEventNotFoundError` — line 48
  - `test_has_event_id(self) [line 51]`
  - `test_is_chat2_error(self) [line 56]`
- `TestCorruptEventLogError` — line 60
  - `test_has_fields(self) [line 63]`
  - `test_without_detail(self) [line 72]`
  - `test_is_chat2_error(self) [line 77]`
- `TestCorruptMetaError` — line 81
  - `test_has_fields(self) [line 84]`
  - `test_without_detail(self) [line 91]`
  - `test_is_chat2_error(self) [line 95]`
- `TestStorageOperationError` — line 99
  - `test_has_fields(self) [line 102]`
  - `test_without_detail(self) [line 111]`
  - `test_is_chat2_error(self) [line 115]`

## `tests/chat2/test_facade.py`

> Tests for the Chat2Store facade.

**Imports**

- `datetime: datetime, timezone`
- `pytest`
- `src.chat2.facade: Chat2Store`
- `src.chat2.models: ChatEvent, ChatSessionMeta, SessionLinks`
- `src.chat2.store_primitives: InMemoryStore`

**Classes**

- `TestSessionLifecycle` — line 69
  - `test_create_session(self, facade: Chat2Store) -> None [line 72]`
  - `test_create_session_with_optional_fields(self, facade: Chat2Store) -> None [line 90]`
  - `test_get_session(self, facade: Chat2Store) -> None [line 111]`
  - `test_get_session_not_found(self, facade: Chat2Store) -> None [line 123]`
  - `test_update_session(self, facade: Chat2Store) -> None [line 128]`
  - `test_update_session_not_found(self, facade: Chat2Store) -> None [line 145]`
  - `test_delete_session(self, facade: Chat2Store) -> None [line 153]`
  - `test_delete_session_nonexistent(self, facade: Chat2Store) -> None [line 164]`
  - `test_session_exists(self, facade: Chat2Store) -> None [line 168]`
- `TestEventManagement` — line 184
  - `test_add_event(self, facade: Chat2Store, sample_event: ChatEvent) -> None [line 187]`
  - `test_add_events(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None [line 199]`
  - `test_stream_events(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None [line 210]`
  - `test_stream_events_empty(self, facade: Chat2Store) -> None [line 224]`
  - `test_get_events_with_filters(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None [line 234]`
  - `test_get_events_no_filters(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None [line 257]`
  - `test_reset_events(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None [line 268]`
  - `test_reset_events_nonexistent(self, facade: Chat2Store) -> None [line 286]`
  - `test_event_count(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None [line 291]`
  - `test_event_count_nonexistent(self, facade: Chat2Store) -> None [line 302]`
- `TestConvenience` — line 312
  - `test_create_and_add(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None [line 315]`
  - `test_create_and_add_empty_events(self, facade: Chat2Store) -> None [line 331]`
  - `test_create_and_add_with_links(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None [line 342]`
- `TestContextName` — line 362
  - `test_default_is_none(self, facade: Chat2Store) -> None [line 365]`
  - `test_persisted_and_retrieved(self, facade: Chat2Store) -> None [line 374]`
  - `test_none_persisted_and_retrieved(self, facade: Chat2Store) -> None [line 386]`
  - `test_can_be_updated(self, facade: Chat2Store) -> None [line 398]`
- `TestEdgeCases` — line 420
  - `test_add_event_to_nonexistent_session(self, facade: Chat2Store, sample_event: ChatEvent) -> None [line 423]`
  - `test_stream_from_nonexistent_session(self, facade: Chat2Store) -> None [line 431]`
  - `test_get_events_from_nonexistent_session(self, facade: Chat2Store) -> None [line 436]`
  - `test_multiple_sessions_independent(self, facade: Chat2Store, sample_event: ChatEvent) -> None [line 441]`
  - `test_session_updated_at_updates_on_event(self, facade: Chat2Store, sample_event: ChatEvent) -> None [line 460]`

**Functions**

- `store() -> InMemoryStore` — line 21
- `facade(store: InMemoryStore) -> Chat2Store` — line 26
- `sample_event() -> ChatEvent` — line 31
- `sample_events() -> list[ChatEvent]` — line 41

## `tests/chat2/test_fs_primitives.py`

> Tests for FileChat2Primitives (src/chat2/fs_primitives.py).

**Imports**

- `__future__: annotations`
- `pathlib: Path`
- `pytest`
- `src.chat2.fs_primitives: FileChat2Primitives`
- `src.chat2.store_primitives: Chat2Primitives, StoreKey`

**Classes**

- `TestReadWrite` — line 26
  - `test_write_and_read_text(self, store: Chat2Primitives) -> None [line 27]`
  - `test_read_text_missing_key(self, store: Chat2Primitives) -> None [line 32]`
  - `test_write_overwrites(self, store: Chat2Primitives) -> None [line 36]`
  - `test_write_creates_parent_dirs(self, store: Chat2Primitives) -> None [line 42]`
- `TestAppend` — line 48
  - `test_append_text(self, store: Chat2Primitives) -> None [line 49]`
  - `test_append_to_nonexistent_key(self, store: Chat2Primitives) -> None [line 55]`
  - `test_append_creates_parent_dirs(self, store: Chat2Primitives) -> None [line 61]`
- `TestExists` — line 67
  - `test_exists_after_write(self, store: Chat2Primitives) -> None [line 68]`
  - `test_exists_after_append(self, store: Chat2Primitives) -> None [line 74]`
- `TestDelete` — line 80
  - `test_delete(self, store: Chat2Primitives) -> None [line 81]`
  - `test_delete_nonexistent_is_noop(self, store: Chat2Primitives) -> None [line 88]`
- `TestListKeys` — line 97
  - `test_list_keys(self, store: Chat2Primitives) -> None [line 98]`
  - `test_list_keys_no_match(self, store: Chat2Primitives) -> None [line 109]`
  - `test_list_keys_empty_prefix(self, store: Chat2Primitives) -> None [line 113]`
- `TestPathTraversal` — line 125
  - `test_rejects_dotdot_in_key(self, store: Chat2Primitives) -> None [line 126]`
  - `test_rejects_absolute_key(self, store: Chat2Primitives) -> None [line 131]`
- `TestProtocol` — line 141
  - `test_is_chat2_primitives(self, tmp_path: Path) -> None [line 142]`
- `TestJsonlStoreIntegration` — line 151
  - `test_create_session_and_append(self, store: Chat2Primitives) -> None [line 154]`
  - `test_reset_session(self, store: Chat2Primitives) -> None [line 196]`
  - `test_delete_session(self, store: Chat2Primitives) -> None [line 214]`

**Functions**

- `store(tmp_path: Path) -> Chat2Primitives` — line 18

## `tests/chat2/test_jfs_adapter.py`

> Tests for JfsChat2Primitives adapter.

**Imports**

- `__future__: annotations`
- `pathlib: Path`
- `pytest`
- `src.chat2.adapters.jfs_adapter: JfsChat2Primitives`
- `src.chat2.jsonl_store: append_event, create_session, get_session_meta, read_events, reset_session_events, stream_events`
- `src.chat2.models: ChatEvent, SessionLinks`
- `src.chat2.store_primitives: StoreKey`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage_paths.storage_paths: StoragePaths`

**Classes**

- `TestJfsPrimitives` — line 46
  - `test_read_write_roundtrip(self, tmp_path) [line 49]`
  - `test_read_missing_key(self, tmp_path) [line 56]`
  - `test_append_text(self, tmp_path) [line 62]`
  - `test_exists(self, tmp_path) [line 72]`
  - `test_delete(self, tmp_path) [line 80]`
  - `test_delete_missing_is_noop(self, tmp_path) [line 90]`
  - `test_list_keys(self, tmp_path) [line 97]`
  - `test_list_keys_empty_prefix(self, tmp_path) [line 110]`
  - `test_write_creates_parent_dirs(self, tmp_path) [line 115]`
  - `test_path_traversal_blocked_by_storekey(self, tmp_path) [line 122]`
  - `test_storage_root_is_under_chat2(self, tmp_path) [line 129]`
- `TestJfsIntegration` — line 147
  - `test_create_session_and_get_meta(self, tmp_path) [line 150]`
  - `test_append_and_stream_events(self, tmp_path) [line 173]`
  - `test_read_events_with_filters(self, tmp_path) [line 189]`
  - `test_reset_session_events(self, tmp_path) [line 208]`
  - `test_session_with_links(self, tmp_path) [line 225]`
  - `test_missing_session_returns_none(self, tmp_path) [line 244]`
  - `test_reset_nonexistent_session_raises(self, tmp_path) [line 250]`

**Functions**

- `_make_storage(tmp_path: Path) -> JsonFileStorage` — line 29
- `_make_adapter(tmp_path: Path) -> JfsChat2Primitives` — line 35

## `tests/chat2/test_jsonl_store.py`

> Tests for JSONL store functions (src/chat2/jsonl_store.py).

**Imports**

- `__future__: annotations`
- `datetime: datetime, timedelta, timezone`
- `pytest`
- `src.chat2.jsonl_store: append_event, create_session, delete_session, get_session_meta, read_events, reset_session_events, stream_events, update_session_meta`
- `src.chat2.models: ChatEvent, SessionLinks`
- `src.chat2.store_primitives: Chat2Primitives, StoreKey`
- `tests.chat2.test_primitives: InMemoryStore`

**Classes**

- `TestCreateSession` — line 37
  - `test_creates_meta_and_events(self, store: Chat2Primitives) -> None [line 38]`
  - `test_creates_with_optional_fields(self, store: Chat2Primitives) -> None [line 61]`
  - `test_default_participants_is_empty(self, store: Chat2Primitives) -> None [line 82]`
  - `test_default_tags_is_empty(self, store: Chat2Primitives) -> None [line 86]`
  - `test_default_context_name_is_none(self, store: Chat2Primitives) -> None [line 90]`
- `TestGetSessionMeta` — line 99
  - `test_returns_meta(self, store: Chat2Primitives) -> None [line 100]`
  - `test_returns_none_for_missing(self, store: Chat2Primitives) -> None [line 108]`
- `TestContextName` — line 116
  - `test_persisted_and_retrieved(self, store: Chat2Primitives) -> None [line 117]`
  - `test_none_persisted_and_retrieved(self, store: Chat2Primitives) -> None [line 130]`
  - `test_persisted_in_raw_json(self, store: Chat2Primitives) -> None [line 143]`
- `TestUpdateSessionMeta` — line 162
  - `test_updates_fields(self, store: Chat2Primitives) -> None [line 163]`
  - `test_raises_for_missing_session(self, store: Chat2Primitives) -> None [line 175]`
- `TestDeleteSession` — line 184
  - `test_deletes_meta_and_events(self, store: Chat2Primitives) -> None [line 185]`
  - `test_delete_nonexistent_is_noop(self, store: Chat2Primitives) -> None [line 192]`
- `TestAppendAndStreamEvents` — line 200
  - `test_append_and_stream(self, store: Chat2Primitives) -> None [line 201]`
  - `test_stream_empty_session(self, store: Chat2Primitives) -> None [line 216]`
  - `test_stream_nonexistent_session(self, store: Chat2Primitives) -> None [line 221]`
  - `test_append_updates_meta_timestamp(self, store: Chat2Primitives) -> None [line 225]`
- `TestReadEvents` — line 242
  - `session_with_events(self, store: Chat2Primitives) -> str [line 244]`
  - `test_no_filters(self, store: Chat2Primitives, session_with_events: str) -> None [line 288]`
  - `test_role_filter(self, store: Chat2Primitives, session_with_events: str) -> None [line 292]`
  - `test_actor_filter(self, store: Chat2Primitives, session_with_events: str) -> None [line 297]`
  - `test_kind_filter(self, store: Chat2Primitives, session_with_events: str) -> None [line 302]`
  - `test_start_ts_filter(self, store: Chat2Primitives, session_with_events: str) -> None [line 307]`
  - `test_end_ts_filter(self, store: Chat2Primitives, session_with_events: str) -> None [line 312]`
  - `test_combined_filters(self, store: Chat2Primitives, session_with_events: str) -> None [line 317]`
- `TestResetSessionEvents` — line 332
  - `test_reset_clears_events(self, store: Chat2Primitives) -> None [line 333]`
  - `test_reset_preserves_meta(self, store: Chat2Primitives) -> None [line 345]`
  - `test_reset_nonexistent_session_raises(self, store: Chat2Primitives) -> None [line 357]`

**Functions**

- `store() -> Chat2Primitives` — line 29

## `tests/chat2/test_models.py`

> Tests for Chat v2 Pydantic models.

**Imports**

- `datetime: datetime`
- `json`
- `pydantic: ValidationError`
- `pytest`
- `src.chat2.models: ChatEvent, ChatSessionMeta, SessionLinks`
- `uuid: uuid4`

**Functions**

- `test_session_links()` — line 15
- `test_chat_event_basic()` — line 35
- `test_chat_event_with_dict_payload()` — line 53
- `test_chat_event_validation()` — line 66
- `test_chat_event_json_serialization()` — line 106
- `test_chat_event_prompt_report_kind()` — line 137
- `test_chat_session_meta_basic()` — line 175
- `test_chat_session_meta_with_optional_fields()` — line 202
- `test_chat_session_meta_validation()` — line 233
- `test_chat_session_meta_json_serialization()` — line 272
- `test_default_values()` — line 318
- `test_context_name_roundtrip()` — line 350

## `tests/chat2/test_primitives.py`

> Tests for Chat v2 storage primitives (StoreKey + Chat2Primitives protocol).

**Imports**

- `__future__: annotations`
- `pytest`
- `src.chat2.store_primitives: Chat2Primitives, InMemoryStore, StoreKey`

**Classes**

- `TestStoreKey` — line 25
  - `test_valid_key(self) -> None [line 26]`
  - `test_rejects_leading_slash(self) -> None [line 31]`
  - `test_rejects_dotdot(self) -> None [line 35]`
  - `test_rejects_non_string(self) -> None [line 39]`
  - `test_equality(self) -> None [line 43]`
  - `test_hashable(self) -> None [line 50]`
- `TestChat2Primitives` — line 59
  - `test_write_and_read_text(self, store: Chat2Primitives) -> None [line 60]`
  - `test_read_text_missing_key(self, store: Chat2Primitives) -> None [line 65]`
  - `test_write_overwrites(self, store: Chat2Primitives) -> None [line 69]`
  - `test_append_text(self, store: Chat2Primitives) -> None [line 75]`
  - `test_append_to_nonexistent_key(self, store: Chat2Primitives) -> None [line 81]`
  - `test_exists(self, store: Chat2Primitives) -> None [line 87]`
  - `test_delete(self, store: Chat2Primitives) -> None [line 93]`
  - `test_delete_nonexistent_is_noop(self, store: Chat2Primitives) -> None [line 100]`
  - `test_list_keys(self, store: Chat2Primitives) -> None [line 104]`
  - `test_list_keys_no_match(self, store: Chat2Primitives) -> None [line 115]`
  - `test_protocol_runtime_checkable(self) -> None [line 119]`
- `TestLogOps` — line 128
  - `test_append_and_read_lines_roundtrip(self, store: Chat2Primitives) -> None [line 129]`
  - `test_append_lines_preserves_batch_order(self, store: Chat2Primitives) -> None [line 134]`
  - `test_append_lines_empty_batch_is_noop(self, store: Chat2Primitives) -> None [line 140]`
  - `test_read_lines_missing_key(self, store: Chat2Primitives) -> None [line 146]`
  - `test_truncate_clears_log_keeps_doc(self, store: Chat2Primitives) -> None [line 149]`
  - `test_delete_removes_doc_and_log(self, store: Chat2Primitives) -> None [line 158]`
  - `test_list_keys_includes_log_keys(self, store: Chat2Primitives) -> None [line 167]`

**Functions**

- `store() -> Chat2Primitives` — line 17

## `tests/chat2/test_sqlite_chat2_facade.py`

**Imports**

- `pathlib: Path`
- `pytest`
- `src.chat2.facade: Chat2Store`
- `src.chat2.models: ChatEvent, ChatSessionMeta`
- `src.chat2.sqlite: SqliteChat2Primitives`
- `uuid: uuid4`

**Classes**

- `TestSessionRoundTrip` — line 46
  - `test_create_session_then_get_session(self, facade: Chat2Store) -> None [line 47]`
  - `test_get_session_missing_returns_none(self, facade: Chat2Store) -> None [line 58]`
- `TestEventRoundTrip` — line 62
  - `test_add_event_then_stream_events(self, facade: Chat2Store) -> None [line 63]`
  - `test_add_events_then_get_events_round_trip(self, facade: Chat2Store) -> None [line 75]`
  - `test_get_events_role_filter(self, facade: Chat2Store) -> None [line 89]`
  - `test_stream_and_get_events_match(self, facade: Chat2Store) -> None [line 95]`
- `TestListSessions` — line 103
  - `test_list_sessions_account_filter(self, facade: Chat2Store) -> None [line 104]`
  - `test_list_sessions_agent_filter(self, facade: Chat2Store) -> None [line 111]`
  - `test_list_sessions_account_and_agent(self, facade: Chat2Store) -> None [line 118]`
  - `test_list_sessions_returns_all(self, facade: Chat2Store) -> None [line 125]`
- `TestUpdateSession` — line 132
  - `test_update_session_fields_and_updated_at_bump(self, facade: Chat2Store) -> None [line 133]`
  - `test_update_session_missing_raises(self, facade: Chat2Store) -> None [line 150]`
- `TestCorrelation` — line 155
  - `test_link_event_and_get_events_by_correlation(self, facade: Chat2Store) -> None [line 156]`
  - `test_link_event_across_sessions(self, facade: Chat2Store) -> None [line 167]`
  - `test_link_event_none_is_noop(self, facade: Chat2Store) -> None [line 179]`
- `TestResetEvents` — line 184
  - `test_reset_events_preserves_meta_and_empties_events(self, facade: Chat2Store) -> None [line 185]`
- `TestDeleteSession` — line 201
  - `test_delete_session_removes_session_and_events(self, facade: Chat2Store) -> None [line 202]`
  - `test_session_exists_false_after_delete(self, facade: Chat2Store) -> None [line 212]`

**Functions**

- `facade(tmp_path: Path) -> Chat2Store` — line 12
- `_session_id() -> str` — line 19
- `_user_event(payload: str | dict = 'hello') -> ChatEvent` — line 23
- `_assistant_event(payload: str | dict = 'hi there') -> ChatEvent` — line 27
- `_tool_event(payload: str | dict) -> ChatEvent` — line 31
- `_create(facade: Chat2Store, **kwargs) -> ChatSessionMeta` — line 35

## `tests/conformance/store_conformance.py`

> Conformance suite for the generic-store doc/log protocol (chat2 primitives).

**Imports**

- `__future__: annotations`
- `pathlib: Path`
- `pytest`
- `src.chat2.fs_primitives: FileChat2Primitives`
- `src.chat2.sqlite: SqliteChat2Primitives`
- `src.chat2.store_primitives: InMemoryStore, StoreKey`
- `typing: Iterable, List, Optional, Protocol, Union, runtime_checkable`

**Classes**

- `GenericStore(Protocol)` — line 45
  - `read_text(self, key: Union[StoreKey, str]) -> Optional[str] [line 53]`
  - `write_text(self, key: Union[StoreKey, str], text: str) -> None [line 57]`
  - `exists(self, key: Union[StoreKey, str]) -> bool [line 61]`
  - `delete(self, key: Union[StoreKey, str]) -> None [line 65]`
  - `read_lines(self, key: Union[StoreKey, str]) -> Optional[List[str]] [line 69]`
  - `append_lines(self, key: Union[StoreKey, str], lines: Iterable[str]) -> None [line 73]`
  - `truncate(self, key: Union[StoreKey, str]) -> None [line 77]`
  - `list_keys(self, prefix: Union[StoreKey, str]) -> List[StoreKey] [line 81]`
- `TestDocProtocol` — line 132
  - `test_doc_roundtrip(self, store: GenericStore) -> None [line 133]`
  - `test_atomic_replace(self, store: GenericStore) -> None [line 138]`
  - `test_missing_key_returns_none(self, store: GenericStore) -> None [line 148]`
- `TestLogProtocol` — line 159
  - `test_append_order_1000_lines(self, store: GenericStore) -> None [line 160]`
  - `test_truncate_keeps_key(self, store: GenericStore) -> None [line 173]`
  - `test_delete_idempotent(self, store: GenericStore) -> None [line 184]`
- `TestNamespace` — line 201
  - `test_list_keys_prefix_escaping(self, store: GenericStore) -> None [line 202]`
  - `test_list_keys_no_match(self, store: GenericStore) -> None [line 230]`
- `TestKeyValidation` — line 238
  - `test_rejects_leading_slash(self, store: GenericStore) -> None [line 239]`
  - `test_rejects_dotdot(self, store: GenericStore) -> None [line 256]`

**Functions**

- `_memory_factory(tmp_path: Path) -> GenericStore` — line 90
- `_file_factory(tmp_path: Path) -> GenericStore` — line 94
- `_sqlite_factory(tmp_path: Path) -> GenericStore` — line 98
- `store(request: pytest.FixtureRequest, tmp_path: Path) -> GenericStore` — line 110
- `test_backends_implement_generic_store_protocol(store: GenericStore) -> None` — line 123

## `tests/conftest.py`

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass, field`
- `json`
- `os`
- `pytest`
- `src.storage.interfaces: TasklistStore`
- `src.tasklists.task_list: TaskList`
- `sys`
- `typing: Any, Callable, Dict, List, Optional`
- `unittest.mock: Mock`

**Classes**

- `FakeConfig` — line 31
  - `get(self, key: str, default: Any = None) -> Any [line 34]`
- `FakeStorage` — line 39
  - `save_context(self, context: Any) -> None [line 49]`
  - `get_context(self, account_name: str, context_id: str) -> Optional[Any] [line 52]`
  - `list_context_names(self, account_name: str) -> List[str] [line 55]`
- `FakeHandler` — line 65
  - `__init__(self, result: Any = None, exc: Optional[BaseException] = None) [line 66]`
  - `execute(self, args: Dict[str, Any], account_name: Optional[str] = None, **context) -> Any [line 71]`
- `FakeRegistry` — line 78
  - `__init__(self, handler_by_name: Optional[Dict[str, Any]] = None, tool_defs: Optional[List[dict]] = None) [line 79]`
  - `tools(self) -> List[dict] [line 83]`
  - `has_tool(self, name: str) -> bool [line 86]`
  - `tool_names(self) -> List[str] [line 89]`
  - `create(self, name: str, config: Any = None) -> Any [line 92]`
- `FakeAgent` — line 97
- `InMemoryTasklistStore(TasklistStore)` — line 199
  - `__init__(self) -> None [line 200]`
  - `list_tasklists(self, account_name: str) -> List[str] [line 204]`
  - `get_tasklist(self, account_name: str, tasklist_key: str) -> Optional[TaskList] [line 207]`
  - `save_tasklist(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None [line 213]`
  - `delete_tasklist(self, account_name: str, tasklist_key: str) -> None [line 220]`
  - `append_task_execution_record(self, account_name: str, tasklist_key: str, record: dict) -> None [line 224]`
  - `get_task_result(self, account_name: str, tasklist_key: str, task_id: str) -> Optional[dict] [line 227]`

**Functions**

- `setup_no_tool_calls(llm_adapter: Mock, *, response_id: str = 'r1', text: str = 'hello!') -> None` — line 113
- `setup_tool_then_text(llm_adapter: Mock, *, tool_name: str, call_id: str = 'call-1', tool_args: str = '{}', first_response_id: str = 'r1', second_response_id: str = 'r2', final_text: str = 'final') -> None` — line 121
- `config() -> FakeConfig` — line 151
- `storage() -> FakeStorage` — line 156
- `prompt_builder(storage) -> Mock` — line 161
- `llm_adapter() -> Mock` — line 169
- `registry() -> FakeRegistry` — line 177
- `make_proc(config, registry, storage, prompt_builder, llm_adapter) -> Callable[..., Any]` — line 182
- `fake_tasklist_store() -> InMemoryTasklistStore` — line 236

## `tests/test_admin_reload.py`

> Tests for POST /admin/reload endpoint logic.

**Imports**

- `json`
- `logging`
- `pytest`
- `src.config_manager: ConfigManager`

**Classes**

- `TestConfigManagerReload` — line 20
  - `test_reload_returns_summary(self, tmp_path) [line 23]`
  - `test_reload_detects_added_keys(self, tmp_path) [line 39]`
  - `test_reload_detects_removed_keys(self, tmp_path) [line 59]`
  - `test_reload_detects_changed_keys(self, tmp_path) [line 78]`
  - `test_reload_invalid_json_keeps_old_state(self, tmp_path) [line 97]`
  - `test_reload_missing_file_keeps_old_state(self, tmp_path) [line 116]`
  - `test_reload_fails_on_bad_sandbox_path(self, tmp_path) [line 135]`
  - `test_reload_with_strict_agent_fields_toggle(self, tmp_path) [line 160]`
- `TestAgentManagerReload` — line 185
  - `test_reload_with_strict_respects_parameter(self, tmp_path) [line 188]`
  - `test_reload_with_strict_enforcement(self, tmp_path, caplog) [line 206]`
  - `test_reload_with_invalid_json_clears_agents(self, tmp_path) [line 227]`
  - `test_reload_with_missing_file_clears_agents(self, tmp_path) [line 244]`

## `tests/test_agent.py`

**Imports**

- `pytest`
- `src.agent.agent: Agent, ModelPolicy`

**Functions**

- `test_agent_loads_with_provider_field()` — line 13
- `test_agent_loads_without_provider_field_defaults_none()` — line 22
- `test_to_dict_includes_provider_when_set()` — line 30
- `test_typo_in_provider_passes_through()` — line 41
- `test_agent_cap_fields_default_to_none()` — line 51
- `test_agent_from_dict_accepts_and_coerces_cap_fields()` — line 58
- `test_agent_from_dict_accepts_zero_cap_fields()` — line 74
- `test_agent_from_dict_rejects_negative_cap_fields()` — line 80
- `test_agent_from_dict_rejects_non_numeric_cap_fields()` — line 86
- `test_to_dict_emits_cap_fields_only_when_set_and_round_trips()` — line 93
- `test_agent_loads_model_policy_and_builds_galet_requirements()` — line 120
- `test_model_policy_round_trips()` — line 146
- `test_legacy_agent_builds_fixed_model_requirements()` — line 164
- `test_invalid_model_policy_is_rejected(policy, message)` — line 190

## `tests/test_agent_allowed_tools.py`

**Imports**

- `src.agent.agent: Agent`

**Functions**

- `test_allowed_tools_missing_means_allow_none()` — line 4
- `test_allowed_tools_empty_list_means_allow_none()` — line 10
- `test_allowed_tools_non_empty_list_is_allow_list()` — line 16

## `tests/test_agent_caps.py`

> Resolver precedence tests for per-agent cap overrides (issue #171).

**Imports**

- `pytest`
- `src.agent.agent: Agent`
- `src.agent.caps: resolve_effective_cap`
- `src.message_processors.fcp_models: DEFAULT_MAX_HANDLER_SCHEMA_TOKENS`

**Classes**

- `_Cfg` — line 23
  - `__init__(self, values = None) [line 24]`
  - `get(self, key, default = None) [line 27]`
- `TestFallThroughCapKeys` — line 41
  - `test_agent_positive_beats_config(self, key, code_default) [line 44]`
  - `test_agent_positive_wins_when_config_unset(self, key, code_default) [line 47]`
  - `test_agent_non_positive_falls_through_to_config(self, key, code_default) [line 50]`
  - `test_agent_non_positive_uses_code_default_when_config_unset(self, key, code_default) [line 53]`
  - `test_agent_non_positive_uses_code_default_when_config_non_positive(self, key, code_default) [line 56]`
  - `test_agent_none_uses_config_value(self, key, code_default) [line 59]`
  - `test_agent_none_uses_code_default_when_config_non_positive(self, key, code_default) [line 62]`
  - `test_agent_none_uses_code_default_when_config_unset(self, key, code_default) [line 65]`
  - `test_agent_field_none_matches_agent_none(self, key, code_default) [line 68]`
- `TestSchemaCapDisableSemantics` — line 79
  - `test_agent_positive_beats_config(self) [line 84]`
  - `test_agent_positive_wins_when_config_unset(self) [line 96]`
  - `test_agent_non_positive_disables_even_when_config_positive(self) [line 108]`
  - `test_agent_non_positive_disables_when_config_unset(self) [line 120]`
  - `test_agent_none_uses_config_value(self) [line 132]`
  - `test_agent_none_config_zero_disables(self) [line 144]`
  - `test_agent_none_config_negative_disables(self) [line 156]`
  - `test_agent_none_missing_uses_default_constant(self) [line 168]`
  - `test_agent_field_none_matches_agent_none(self) [line 180]`
- `TestBudgetEnvOrdering` — line 195
  - `test_env_wins_over_agent_and_config(self, monkeypatch) [line 198]`
  - `test_env_invalid_falls_through_to_agent(self, monkeypatch) [line 203]`
  - `test_env_only_applies_to_budget_key(self, monkeypatch) [line 208]`
- `TestAgentAsDict` — line 214
  - `test_dict_agent_positive_value_wins(self) [line 217]`
  - `test_dict_agent_non_positive_falls_through_to_config(self) [line 223]`

**Functions**

- `_agent(**overrides)` — line 31
- `_no_budget_env(monkeypatch)` — line 36

## `tests/test_agent_manager_unknown_field.py`

**Imports**

- `json`
- `logging`
- `src.agent.agent_manager: AgentManager`

**Functions**

- `test_agent_manager_skips_unknown_field_agent(tmp_path, caplog)` — line 7

## `tests/test_agents_manage_handler.py`

> Tests for the agents_manage tool handler.

**Imports**

- `json`
- `pytest`
- `src.agent.agent_manager: AgentManager`
- `src.agent: Agent`
- `src.handlers.agents_manage_handler: AgentsManageHandler`

**Classes**

- `FakeConfig` — line 12
  - `__init__(self, agents_path: str, strict: bool = True) [line 15]`
  - `get(self, key, default = None) [line 21]`

**Functions**

- `_write_agents(path, agents)` — line 25
- `agents_path(tmp_path)` — line 30
- `cfg(agents_path)` — line 37
- `handler(cfg)` — line 42
- `test_list(handler)` — line 46
- `test_get(handler)` — line 53
- `test_get_missing(handler)` — line 59
- `test_get_requires_name(handler)` — line 65
- `test_upsert_new_and_persist(handler, agents_path)` — line 71
- `test_upsert_updates_existing(handler, agents_path)` — line 83
- `test_upsert_rejects_unknown_field_when_strict(agents_path)` — line 95
- `test_upsert_requires_agent_dict(handler)` — line 103
- `test_upsert_requires_name(handler)` — line 109
- `test_delete(handler, agents_path)` — line 115
- `test_delete_missing_is_idempotent(handler)` — line 124
- `test_reload_picks_up_disk_changes(handler, agents_path)` — line 130
- `test_uses_shared_agent_manager_from_context(cfg)` — line 138
- `test_invalid_action(handler)` — line 149

## `tests/test_allowed_tools.py`

**Imports**

- `__future__: annotations`
- `logging`
- `pytest`
- `src.agent.agent: Agent`

**Functions**

- `test_allowed_tools_none_no_tools(make_proc, registry, llm_adapter)` — line 9
- `test_allowed_tools_empty_no_tools(make_proc, registry, llm_adapter)` — line 23
- `test_allowed_tools_subset_only_passed(make_proc, registry, llm_adapter)` — line 36
- `test_allowed_tools_unknown_names_ignored_silently(make_proc, registry, llm_adapter)` — line 49
- `test_resolve_tool_defs_none_allows_no_tools()` — line 70
- `test_resolve_tool_defs_empty_allows_no_tools()` — line 80
- `test_resolve_tool_defs_subset_preserves_registry_order()` — line 90
- `test_resolve_tool_defs_unknown_names_ignored_and_logged(caplog)` — line 102
- `test_resolve_tool_defs_agent_without_allowed_tools_attribute()` — line 121
- `test_streaming_applies_allowed_tools_filter(make_proc, registry, llm_adapter)` — line 137
- `test_streaming_allowed_tools_none_no_tools(make_proc, registry, llm_adapter)` — line 150
- `_make_context_state(data)` — line 174
- `test_resolve_tool_defs_no_context_state_uses_agent_tools()` — line 187
- `test_resolve_tool_defs_context_without_tool_list_uses_agent_tools()` — line 198
- `test_resolve_tool_defs_context_list_narrows_agent_tools()` — line 210
- `test_resolve_tool_defs_context_list_exceeding_agent_permissions_clamped(caplog)` — line 222
- `test_resolve_tool_defs_context_cannot_grant_when_agent_has_no_tools()` — line 246
- `test_resolve_tool_defs_context_empty_list_does_not_restrict()` — line 258
- `test_process_message_ignores_context_allowed_tools(make_proc, registry, llm_adapter, prompt_builder)` — line 269
- `test_process_message_context_without_tool_list_uses_agent_tools(make_proc, registry, llm_adapter, prompt_builder)` — line 296
- `test_process_message_context_tool_list_clamped_by_agent_permissions(make_proc, registry, llm_adapter, prompt_builder)` — line 322
- `test_streaming_ignores_context_allowed_tools(make_proc, registry, llm_adapter, prompt_builder)` — line 348
- `_big_tool_def(name: str, desc_len: int = 300) -> dict` — line 386
- `_schema_tokens(function_defs) -> int` — line 398
- `test_handler_schema_cap_over_budget_returns_error(make_proc, registry, llm_adapter, config)` — line 406
- `test_handler_schema_cap_under_budget_no_trim_no_warning(make_proc, registry, llm_adapter, config, caplog)` — line 424
- `test_handler_schema_cap_zero_disables_guardrail(make_proc, registry, llm_adapter, config, caplog)` — line 442
- `test_handler_schema_budget_keeps_single_oversized_def()` — line 459
- `test_streaming_handler_schema_cap_over_budget_emits_error(make_proc, registry, llm_adapter, config)` — line 472
- `test_handler_schema_budget_agent_without_override_uses_config_cap()` — line 491
- `test_handler_schema_budget_agent_small_cap_trims_before_config_cap()` — line 505
- `test_handler_schema_budget_agent_non_positive_disables_despite_config_cap(agent_cap, caplog)` — line 525
- `test_handler_schema_cap_agent_override_tighter_than_config_returns_error(make_proc, registry, llm_adapter, config)` — line 546
- `test_handler_schema_cap_agent_non_positive_disables_despite_config_cap(make_proc, registry, llm_adapter, config, agent_cap)` — line 566

## `tests/test_ask_request_handler.py`

> Tests for AskRequestHandler.handle() with the FCPResult return contract.

**Imports**

- `__future__: annotations`
- `src.message_endpoints.ask_request_handler: AskRequestHandler`
- `src.message_processors.function_calling_processor: FCPResult`
- `src.message_processors.run_metrics: RunMetrics`
- `typing: Any, Dict`
- `unittest.mock: Mock`

**Classes**

- `FakeAgentManager` — line 13
  - `__init__(self, agent: Any) -> None [line 14]`
  - `is_valid(self, name: str) -> bool [line 17]`
  - `get_agent(self, name: str) -> Any [line 20]`
- `FakeStorage` — line 24
  - `__init__(self) -> None [line 25]`
  - `get_or_create_context(self, account_name: str, context_id: str) -> None [line 28]`
- `FakeProcessor` — line 32
  - `__init__(self, result: FCPResult) -> None [line 33]`
  - `process_message(self, **kwargs) -> FCPResult [line 37]`
- `FakeProcessorFactory` — line 42
  - `__init__(self, processor: FakeProcessor) -> None [line 43]`
  - `get(self, name: str) -> FakeProcessor [line 46]`
- `TestAskRequestHandlerHandle` — line 80
  - `test_handle_uses_result_text_from_fcp_result(self) -> None [line 81]`
  - `test_handle_passes_context_and_correlation_to_processor(self) -> None [line 93]`

**Functions**

- `make_agent(name: str = 'lucy') -> Any` — line 50
- `make_handler(processor: FakeProcessor, agent: Any) -> AskRequestHandler` — line 60
- `make_payload(**overrides: Any) -> Dict[str, Any]` — line 70

## `tests/test_automation_processor_mandatory_stop.py`

> Tests for AutomationProcessor mandatory-stop behavior (GH issue #123).

**Imports**

- `src.message_processors.automation_processor: AutomationProcessor, _is_mandatory_stop_response`
- `src.message_processors.function_calling_processor: FCPResult`
- `src.message_processors.run_metrics: RunMetrics`
- `src.tasklists.task: Task`
- `src.tasklists.task_list: TaskList`
- `src.tasklists.task_states: TASK_LIST_STATE_FAILED, TASK_STATE_COMPLETED, TASK_STATE_FAILED`
- `types: SimpleNamespace`
- `uuid`

**Classes**

- `FakeFunctionProcessor` — line 38
  - `__init__(self, response) [line 39]`
  - `process_message(self, **kwargs) [line 43]`
- `FakeProcessorFactory` — line 48
  - `__init__(self, function_processor) [line 49]`
  - `get(self, name) [line 52]`
- `FakeStorage` — line 58
  - `__init__(self, tasklist) [line 59]`
  - `get_tasklist(self, account_name, tasklist_id) [line 64]`
  - `list_tasklists(self, account_name) [line 67]`
  - `save_tasklist(self, account_name, tasklist_id, data) [line 70]`
  - `append_task_execution_record(self, account_name, tasklist_key, record) [line 73]`

**Functions**

- `make_tasklist()` — line 77
- `run_tasklist(processor_factory)` — line 82
- `test_is_mandatory_stop_response_detects_markers()` — line 108
- `test_internal_limit_aborts_tasklist_and_marks_failed()` — line 117
- `test_empty_response_aborts_tasklist()` — line 137
- `test_stuck_loop_aborts_tasklist()` — line 150
- `test_normal_response_still_completes()` — line 163

## `tests/test_automation_processor_nullable_inputs.py`

> Regression tests for GH issue #132.

**Imports**

- `src.message_processors.automation_processor: AutomationProcessor`
- `src.message_processors.function_calling_processor: FCPResult`
- `src.message_processors.run_metrics: RunMetrics`
- `src.tasklists.task: Task`
- `src.tasklists.task_list: TaskList`
- `src.tasklists.task_states: TASK_STATE_COMPLETED`
- `types: SimpleNamespace`
- `uuid`

**Classes**

- `RecordingFunctionProcessor` — line 20
  - `__init__(self, response = 'Task finished successfully.') [line 21]`
  - `process_message(self, **kwargs) [line 25]`
- `RecordingProcessorFactory` — line 30
  - `__init__(self, function_processor) [line 31]`
  - `get(self, name) [line 34]`
- `FakeStorage` — line 40
  - `__init__(self, tasklist) [line 41]`
  - `get_tasklist(self, account_name, tasklist_id) [line 45]`
  - `list_tasklists(self, account_name) [line 48]`
  - `save_tasklist(self, account_name, tasklist_id, data) [line 51]`
  - `append_task_execution_record(self, account_name, tasklist_key, record) [line 54]`

**Functions**

- `make_tasklist(*, instructions = 'Do the thing', agent = None)` — line 58
- `run_tasklist(function_processor, tasklist, **overrides)` — line 68
- `test_none_context_name_does_not_crash()` — line 95
- `test_none_worker_agent_does_not_crash()` — line 113
- `test_nullable_task_fields_do_not_crash()` — line 129

## `tests/test_automation_processor_run_metrics.py`

> Test that AutomationProcessor attaches per-task run metrics and persists them.

**Imports**

- `src.message_processors.automation_processor: AutomationProcessor`
- `src.message_processors.function_calling_processor: FCPResult`
- `src.message_processors.run_metrics: RunMetrics`
- `src.tasklists.task: Task`
- `src.tasklists.task_list: TaskList`
- `src.tasklists.task_states: TASK_LIST_STATE_FAILED`
- `src.tasklists.task_states: TASK_STATE_COMPLETED`
- `src.tasklists.task_states: TASK_STATE_FAILED`
- `types: SimpleNamespace`
- `uuid`

**Classes**

- `MetricsFunctionProcessor` — line 16
  - `__init__(self, text = 'Task finished successfully.', metrics = None) [line 17]`
  - `process_message(self, **kwargs) [line 32]`
- `RecordingProcessorFactory` — line 37
  - `__init__(self, function_processor) [line 38]`
  - `get(self, name) [line 41]`
- `RecordingStorage` — line 47
  - `__init__(self, tasklist) [line 48]`
  - `get_tasklist(self, account_name, tasklist_id) [line 53]`
  - `list_tasklists(self, account_name) [line 56]`
  - `save_tasklist(self, account_name, tasklist_id, data) [line 59]`
  - `append_task_execution_record(self, account_name, tasklist_key, record) [line 62]`
- `FailingAppendStorage(RecordingStorage)` — line 158
  - `append_task_execution_record(self, account_name, tasklist_key, record) [line 159]`

**Functions**

- `run_tasklist(function_processor, tasklist, **overrides)` — line 66
- `make_tasklist(*, instructions = 'Do the thing')` — line 93
- `test_automation_writes_run_metrics_to_runs_record()` — line 98
- `test_automation_mandatory_stop_writes_failure_record()` — line 133
- `test_append_failure_aborts_run_and_marks_task_failed()` — line 163

## `tests/test_automation_processor_sqlite.py`

> Verify AutomationProcessor._ensure_chat2_session persists sessions and events into sqlite.

**Imports**

- `json`
- `pathlib: Path`
- `pytest`
- `src.chat2.facade: Chat2Store`
- `src.chat2.sqlite: SqliteChat2Primitives`
- `src.coala_memory.episodic: Chat2EpisodicMemory`
- `src.message_processors.automation_processor: AutomationProcessor`
- `src.message_processors.function_calling_processor: FCPResult`
- `src.message_processors.run_metrics: RunMetrics`
- `src.tasklists.task: Task`
- `src.tasklists.task_list: TaskList`
- `src.tasklists.task_states: TASK_STATE_COMPLETED`
- `types: SimpleNamespace`
- `uuid`

**Classes**

- `RecordingFunctionProcessor` — line 29
  - `__init__(self, response = 'Task finished successfully.') [line 30]`
  - `process_message(self, **kwargs) [line 34]`
- `RecordingProcessorFactory` — line 39
  - `__init__(self, function_processor) [line 40]`
  - `get(self, name) [line 43]`
- `FakeStorage` — line 49
  - `__init__(self, tasklist) [line 50]`
  - `get_tasklist(self, account_name, tasklist_id) [line 53]`
  - `list_tasklists(self, account_name) [line 56]`
  - `save_tasklist(self, account_name, tasklist_id, data) [line 59]`
  - `append_task_execution_record(self, account_name, tasklist_key, record) [line 62]`

**Functions**

- `chat2_store(tmp_path: Path) -> Chat2Store` — line 22
- `make_tasklist(*, instructions = 'Do the thing')` — line 66
- `make_processor(chat2_store, storage)` — line 71
- `run_tasklist(function_processor, tasklist, chat2_store, **overrides)` — line 83
- `test_execute_tasklist_creates_session_in_sqlite(chat2_store)` — line 103
- `test_execute_tasklist_writes_events_to_sqlite(chat2_store)` — line 121
- `test_execute_tasklist_sessions_listed_for_account(chat2_store)` — line 146
- `test_execute_tasklist_links_events_to_correlation(chat2_store)` — line 156
- `test_execute_tasklist_reuses_existing_session(chat2_store)` — line 168
- `test_process_message_writes_command_event_to_sqlite(chat2_store)` — line 181

## `tests/test_chats_create_endpoints.py`

> Tests for creating chats and posting messages using the Episodic manager (in-memory).

**Imports**

- `__future__: annotations`
- `pytest`
- `src.chat2.facade: Chat2Store`
- `src.chat2.store_primitives: InMemoryStore`
- `src.coala_memory.episodic: Chat2EpisodicMemory`
- `src.http_endpoints.chats_endpoints: post_chat_impl, post_chat_message_impl, get_chat_impl`
- `unittest.mock: Mock`

**Classes**

- `TestPostChat` — line 48
  - `test_create_session_minimal(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 49]`
  - `test_create_session_with_context(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 62]`
  - `test_invalid_agent(self, mgr: Chat2EpisodicMemory, agent_manager_strict: Mock) -> None [line 76]`
- `TestPostMessage` — line 86
  - `test_post_message_and_get(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 87]`
  - `test_message_to_unknown_session(self, mgr: Chat2EpisodicMemory) -> None [line 103]`

**Functions**

- `store() -> InMemoryStore` — line 21
- `mgr(store: InMemoryStore) -> Chat2EpisodicMemory` — line 26
- `agent_manager() -> Mock` — line 31
- `agent_manager_strict() -> Mock` — line 38

## `tests/test_chats_create_endpoints_sqlite.py`

> Tests for creating chats and posting messages using the Episodic manager (sqlite).

**Imports**

- `__future__: annotations`
- `pathlib: Path`
- `pytest`
- `src.chat2.facade: Chat2Store`
- `src.chat2.sqlite: SqliteChat2Primitives`
- `src.coala_memory.episodic: Chat2EpisodicMemory`
- `src.http_endpoints.chats_endpoints: post_chat_impl, post_chat_message_impl, get_chat_impl`
- `unittest.mock: Mock`

**Classes**

- `TestPostChat` — line 49
  - `test_create_session_minimal(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 50]`
  - `test_create_session_with_context(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 63]`
  - `test_invalid_agent(self, mgr: Chat2EpisodicMemory, agent_manager_strict: Mock) -> None [line 77]`
- `TestPostMessage` — line 87
  - `test_post_message_and_get(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 88]`
  - `test_message_to_unknown_session(self, mgr: Chat2EpisodicMemory) -> None [line 104]`

**Functions**

- `store(tmp_path: Path) -> SqliteChat2Primitives` — line 20
- `mgr(store: SqliteChat2Primitives) -> Chat2EpisodicMemory` — line 27
- `agent_manager() -> Mock` — line 32
- `agent_manager_strict() -> Mock` — line 39

## `tests/test_chats_read_endpoints.py`

> Tests that exercise GET /chats and GET /chats/<id> using the

**Imports**

- `__future__: annotations`
- `pytest`
- `src.chat2.facade: Chat2Store`
- `src.chat2.store_primitives: InMemoryStore`
- `src.coala_memory.episodic: Chat2EpisodicMemory, EpisodicEvent`
- `src.http_endpoints.chats_endpoints: get_chat_impl, get_chats_impl`
- `unittest.mock: Mock`

**Classes**

- `TestGetChats` — line 61
  - `test_list_and_filters(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 62]`
  - `test_agent_filter(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 82]`
- `TestGetChat` — line 91
  - `test_get_existing(self, mgr: Chat2EpisodicMemory) -> None [line 92]`
  - `test_get_unknown(self, mgr: Chat2EpisodicMemory) -> None [line 117]`

**Functions**

- `store() -> InMemoryStore` — line 27
- `mgr(store: InMemoryStore) -> Chat2EpisodicMemory` — line 32
- `agent_manager() -> Mock` — line 39
- `agent_manager_strict() -> Mock` — line 46

## `tests/test_chats_read_endpoints_sqlite.py`

> Tests that exercise GET /chats and GET /chats/<id> using the

**Imports**

- `__future__: annotations`
- `pytest`
- `src.chat2.facade: Chat2Store`
- `src.chat2.sqlite: SqliteChat2Primitives`
- `src.coala_memory.episodic: Chat2EpisodicMemory, EpisodicEvent`
- `src.http_endpoints.chats_endpoints: get_chat_impl, get_chats_impl`
- `unittest.mock: Mock`

**Classes**

- `TestGetChatsSQL` — line 51
  - `test_list_and_filters(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 52]`
  - `test_agent_filter(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 72]`
- `TestGetChatSQL` — line 81
  - `test_get_existing(self, mgr: Chat2EpisodicMemory) -> None [line 82]`
  - `test_get_unknown(self, mgr: Chat2EpisodicMemory) -> None [line 107]`

**Functions**

- `db_path(tmp_path) -> str` — line 20
- `mgr(db_path: str) -> Chat2EpisodicMemory` — line 26
- `agent_manager() -> Mock` — line 34
- `agent_manager_strict() -> Mock` — line 41

## `tests/test_chats_update_endpoints.py`

**Imports**

- `__future__: annotations`
- `pytest`
- `src.chat2.facade: Chat2Store`
- `src.chat2.store_primitives: InMemoryStore`
- `src.coala_memory.episodic.chat2_memory: Chat2EpisodicMemory`
- `src.http_endpoints.chats_endpoints: delete_chat_impl, get_chat_impl, update_chat_impl`
- `unittest.mock: Mock`

**Classes**

- `TestUpdateChat` — line 50
  - `test_update_friendly_name(self, manager: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 51]`
  - `test_update_tags_and_metadata(self, manager: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 63]`
  - `test_update_context_name(self, manager: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 76]`
  - `test_update_nonexistent_session(self, manager: Chat2EpisodicMemory) -> None [line 88]`
  - `test_delete_session(self, manager: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 92]`

**Functions**

- `store() -> InMemoryStore` — line 18
- `chat2_store(store: InMemoryStore) -> Chat2Store` — line 23
- `manager(chat2_store: Chat2Store) -> Chat2EpisodicMemory` — line 28
- `agent_manager() -> Mock` — line 33
- `agent_manager_strict() -> Mock` — line 40

## `tests/test_chats_update_endpoints_sqlite.py`

**Imports**

- `__future__: annotations`
- `pathlib: Path`
- `pytest`
- `src.chat2.facade: Chat2Store`
- `src.chat2.sqlite: SqliteChat2Primitives`
- `src.coala_memory.episodic.chat2_memory: Chat2EpisodicMemory`
- `src.http_endpoints.chats_endpoints: delete_chat_impl, get_chat_impl, update_chat_impl`
- `unittest.mock: Mock`

**Classes**

- `TestUpdateChatSqlite` — line 53
  - `test_update_friendly_name(self, manager: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 54]`
  - `test_update_tags_and_metadata(self, manager: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 66]`
  - `test_update_context_name(self, manager: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 79]`
  - `test_update_nonexistent_session(self, manager: Chat2EpisodicMemory) -> None [line 91]`
  - `test_delete_session(self, manager: Chat2EpisodicMemory, agent_manager: Mock) -> None [line 95]`

**Functions**

- `store(tmp_path: Path) -> SqliteChat2Primitives` — line 19
- `chat2_store(store: SqliteChat2Primitives) -> Chat2Store` — line 26
- `manager(chat2_store: Chat2Store) -> Chat2EpisodicMemory` — line 31
- `agent_manager() -> Mock` — line 36
- `agent_manager_strict() -> Mock` — line 43

## `tests/test_coala_episodic_chat2.py`

**Imports**

- `src.coala_memory.episodic: Chat2EpisodicMemory, EpisodicEvent, EpisodicMemoryRequest, EpisodicSessionQuery`
- `uuid: uuid4`

**Functions**

- `test_chat2_episodic_memory_sqlite_round_trip(tmp_path)` — line 11
- `test_chat2_episodic_memory_lists_and_searches_sessions(tmp_path)` — line 64
- `test_chat2_episodic_memory_overflow_digest_is_optional(tmp_path)` — line 91
- `test_session_exists_reflects_session_lifecycle(tmp_path)` — line 118
- `test_add_events_returns_stored_events_and_persists_them(tmp_path)` — line 130
- `test_link_event_with_falsy_correlation_is_noop(tmp_path)` — line 162
- `test_link_event_links_event_to_correlation(tmp_path)` — line 180

## `tests/test_coala_episodic_digest_recall.py`

**Imports**

- `__future__: annotations`
- `src.chat2.facade: Chat2Store`
- `src.chat2.store_primitives: InMemoryStore`
- `src.coala_memory.episodic: Chat2EpisodicMemory, EmbeddingDigestRecall, EpisodicMemoryRequest`
- `types: SimpleNamespace`

**Classes**

- `_EmbeddingFacade` — line 14
  - `__init__(self, *, fail: bool = False) [line 15]`
  - `embed(self, texts, model) [line 19]`
- `_EmbeddingStore` — line 26
  - `__init__(self, results) [line 27]`
  - `query_embeddings(self, **kwargs) [line 31]`

**Functions**

- `_record(source_id: str, path: str | None)` — line 36
- `test_embedding_digest_recall_filters_threshold_and_loads_snippet(tmp_path)` — line 43
- `test_embedding_digest_recall_failure_isolated()` — line 82
- `test_chat2_episodic_memory_returns_archived_digests(tmp_path)` — line 97
- `test_chat2_episodic_memory_persists_overflow_digest(tmp_path)` — line 126

## `tests/test_coala_memory_interfaces.py`

**Imports**

- `src.coala_memory.episodic: EpisodicDigest, EpisodicEvent`
- `src.coala_memory.procedural: ProceduralSkill`
- `src.coala_memory.semantic: SemanticDocument`
- `src.coala_memory: EpisodicCurationRequest, EpisodicMemoryRequest, EpisodicMemoryResult, EpisodicSessionQuery, ProceduralMemoryRequest, ProceduralMemoryResult, SemanticMemoryRequest, SemanticMemoryResult`

**Functions**

- `test_episodic_request_matches_prompt_history_and_digest_inputs()` — line 16
- `test_episodic_management_contract_covers_session_search_and_curation()` — line 37
- `test_semantic_request_supports_embedding_recall()` — line 61
- `test_procedural_request_exposes_resolved_context_skill_and_tool_state()` — line 90

## `tests/test_coala_semantic_sqlite_vec.py`

**Imports**

- `dataclasses: dataclass`
- `datetime: datetime, timezone`
- `src.coala_memory.semantic: SemanticMemoryRequest, SqliteVecSemanticMemory`
- `src.storage.models: EmbeddingRecord`

**Classes**

- `FakeEmbeddingResponse` — line 9
- `FakeEmbeddingFacade` — line 14
  - `__init__(self) [line 15]`
  - `embed(self, texts, model) [line 18]`
- `FakeEmbeddingStore` — line 23
  - `__init__(self, results) [line 24]`
  - `query_embeddings(self, namespaces, account_name, query_vector, top_k = 10, filter = None) [line 28]`

**Functions**

- `_record(*, record_id, source_id, path, title = '', tags = None, source_type = 'obsidian_note')` — line 41
- `test_sqlite_vec_semantic_memory_recalls_matching_documents(tmp_path)` — line 54
- `test_sqlite_vec_semantic_memory_applies_threshold_and_path_requirements(tmp_path)` — line 88
- `test_sqlite_vec_semantic_memory_returns_empty_when_embedding_mode_disabled()` — line 122

## `tests/test_command_execution_handler2.py`

**Imports**

- `pytest`
- `src.handlers.command_execution_handler2: CommandExecutionHandler2`

**Classes**

- `DummyConfig` — line 6
  - `__init__(self, **kwargs) [line 7]`
  - `get(self, key: str, default = None) [line 10]`

**Functions**

- `_mk_handler(tmp_path)` — line 14
- `test_validate_and_normalize_relative_path_allows_dot(tmp_path)` — line 19
- `test_validate_and_normalize_relative_path_empty_normalizes_to_dot(tmp_path)` — line 28
- `test_validate_and_normalize_relative_path_blocks_parent(tmp_path)` — line 38
- `test_validate_and_normalize_relative_path_allows_internal_dotdot_normalization(tmp_path)` — line 47

## `tests/test_container_config_chat2_store.py`

**Imports**

- `pytest`
- `src.chat2.adapters.jfs_adapter: JfsChat2Primitives`
- `src.chat2.facade: Chat2Store`
- `src.chat2.models: ChatEvent`
- `src.chat2.sqlite: SqliteChat2Primitives`
- `src.container_config: StorageModule`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage_paths.storage_paths: StoragePaths`
- `tests.conftest: FakeConfig`

**Functions**

- `_storage_module(monkeypatch, values)` — line 13
- `_sentinel_storage()` — line 20
- `_json_storage(tmp_path)` — line 24
- `_event()` — line 32
- `test_chat2_store_defaults_to_jfs_adapter(monkeypatch, tmp_path)` — line 41
- `test_chat2_store_empty_backend_keeps_jfs_adapter(monkeypatch, tmp_path)` — line 50
- `test_chat2_store_jsonl_backend(monkeypatch, tmp_path)` — line 58
- `test_chat2_store_jsonl_backend_uppercase(monkeypatch, tmp_path)` — line 67
- `test_chat2_store_sqlite_backend(monkeypatch, tmp_path)` — line 74
- `test_chat2_store_sqlite_default_db_path(monkeypatch, tmp_path)` — line 103
- `test_chat2_store_unknown_backend_raises(monkeypatch, bad)` — line 128

## `tests/test_container_config_embedding_store.py`

> DI wiring tests for Lucy embedding-store configuration.

**Imports**

- `pytest`
- `src.chat2.fs_primitives: FileChat2Primitives`
- `src.chat2.sqlite: SqliteChat2Primitives`
- `src.container_config: StorageModule`
- `src.storage.models: EmbeddingRecord`
- `src.storage.primitives_embedding_store: PrimitivesEmbeddingStore`
- `tests.conftest: FakeConfig`

**Functions**

- `_storage_module(monkeypatch, values: dict) -> StorageModule` — line 19
- `_sentinel_storage()` — line 26
- `_record(record_id: str, dimensions: int = 3) -> EmbeddingRecord` — line 30
- `test_embedding_store_defaults_to_shared_storage(monkeypatch)` — line 44
- `test_embedding_store_empty_backend_keeps_shared_storage(monkeypatch)` — line 50
- `test_embedding_store_file_backend(monkeypatch, tmp_path)` — line 56
- `test_embedding_store_file_backend_uppercase(monkeypatch, tmp_path)` — line 85
- `test_embedding_store_sqlite_backend(monkeypatch, tmp_path)` — line 98
- `test_embedding_store_sqlite_default_db_path(monkeypatch, tmp_path)` — line 126
- `test_embedding_store_sqlite_vec_delegates_to_galet_memory(monkeypatch, tmp_path)` — line 145
- `test_embedding_store_unknown_backend_raises(monkeypatch, bad)` — line 175

## `tests/test_container_episodic_manager.py`

**Imports**

- `src.chat2.facade: Chat2Store`
- `src.chat2.store_primitives: InMemoryStore`
- `src.coala_memory.episodic: Chat2EpisodicMemory, EpisodicMemoryManager`
- `src.container_config: AutomationProcessorModule, CoALAMemoryModule, EndpointHandlersModule`
- `unittest.mock: Mock`

**Functions**

- `test_provide_episodic_memory_manager_direct_call() -> None` — line 13
- `test_automation_provider_passes_episodic_manager() -> None` — line 21
- `test_ask_handler_provider_passes_episodic_manager() -> None` — line 36

## `tests/test_correlation_log_handler.py`

> CorrelationLogHandler tests: ERROR/WARNING-only counting, active-context

**Imports**

- `logging`
- `src.message_processors.fcp_models: RequestContext`
- `src.metrics: CorrelationLogHandler`

**Functions**

- `_make_record(level: int, correlation_id: str = None) -> logging.LogRecord` — line 11
- `test_only_error_and_warning_records_are_counted()` — line 26
- `test_records_without_matching_active_context_are_ignored()` — line 44
- `test_counts_reset_per_correlation_id_lifecycle()` — line 58
- `test_start_run_returns_accumulator_exposing_counts()` — line 85
- `test_counts_via_real_logger_with_correlation_filter()` — line 95

## `tests/test_correlation_wiring.py`

> Wiring tests for correlation to event linking.

**Imports**

- `__future__: annotations`
- `src.chat2.facade: Chat2Store`
- `src.chat2.store_primitives: InMemoryStore, StoreKey`
- `src.coala_memory.episodic: Chat2EpisodicMemory`
- `src.message_processors.automation_processor: AutomationProcessor`
- `src.message_processors.fcp_chat2: Chat2Recorder`
- `src.message_processors.fcp_models: ProcessorContext`
- `src.message_processors.sse_events: SSEEvent`
- `uuid`

**Classes**

- `TestRecorderCorrelationWiring` — line 55
  - `test_recorder_links_streaming_events(self) -> None [line 58]`
  - `test_recorder_no_correlation_no_links(self) -> None [line 81]`
  - `test_best_effort_no_store(self) -> None [line 104]`
- `TestAutomationCorrelationWiring` — line 120
  - `test_automation_links_events(self) -> None [line 123]`
  - `test_automation_without_correlation_no_link(self) -> None [line 155]`
  - `test_automation_no_store_noop(self) -> None [line 175]`

**Functions**

- `_ctx(conversation_id: str, store_this_call: bool = True) -> ProcessorContext` — line 21
- `_make_automation_processor(chat2_store) -> AutomationProcessor` — line 36

## `tests/test_curate_chat_handler_settings.py`

> Focused unit tests for CurateChatHandler galet Settings injection.

**Imports**

- `galet.settings: Settings`
- `pytest`
- `src.handlers.curate_chat_handler: CurateChatHandler`
- `unittest.mock: patch`

**Classes**

- `FakeConfig` — line 27
  - `__init__(self, values) [line 30]`
  - `get(self, key, default = None) [line 33]`

**Functions**

- `_make_handler(config)` — line 37
- `test_router_api_injected_with_settings_from_config()` — line 53
- `test_router_api_settings_none_when_config_keys_missing()` — line 72

## `tests/test_delegate_task_handler.py`

**Imports**

- `json`
- `src.config_manager: ConfigManager`
- `src.handlers.delegate_task_handler: DelegateTaskHandler`
- `types: SimpleNamespace`

**Classes**

- `FakeAgentManager` — line 8
  - `__init__(self) [line 9]`
  - `get_agent(self, name) [line 16]`
  - `get_agent_names(self) [line 19]`

**Functions**

- `write_machines(tmp_path)` — line 23
- `base_args(**changes)` — line 54
- `resolved_model(monkeypatch)` — line 69
- `test_selects_eligible_machine_and_reuses_remote_execute(monkeypatch, tmp_path)` — line 79
- `test_unknown_agent_fails_before_machine_selection(tmp_path)` — line 122
- `test_no_machine_matches_requirements(monkeypatch, tmp_path)` — line 132
- `test_machine_override_must_be_eligible(monkeypatch, tmp_path)` — line 143
- `test_invalid_capabilities_are_rejected(tmp_path)` — line 153
- `test_runtime_constructor_loads_agent_manager_from_config(tmp_path)` — line 162

## `tests/test_documents_endpoints_semantic.py`

**Imports**

- `pathlib: Path`
- `pytest`
- `src.http_endpoints.documents_endpoints: search_documents_impl`

**Classes**

- `SemanticDocument` — line 7
  - `__init__(self, source_id: str, source_type: str = 'external', path: str = '', title: str = '', tags = None, snippet: str = '', score: float = 1.0, truncated: bool = False, metadata = None) [line 8]`
- `SemanticMemoryResult` — line 22
  - `__init__(self, documents) [line 23]`
- `FakeSemanticMemory` — line 27
  - `__init__(self, result: SemanticMemoryResult = None, exc: Exception = None) [line 28]`
  - `recall(self, req) [line 33]`

**Functions**

- `_make_doc(stem = 'doc1')` — line 40
- `test_ok_shape()` — line 55
- `test_default_param_mapping()` — line 69
- `test_limit_maps_to_top_k()` — line 84
- `test_namespaces_param_variants()` — line 93
- `test_source_type_passthrough()` — line 109
- `test_missing_account_name_400()` — line 118
- `test_missing_query_400()` — line 126
- `test_recall_exception_500()` — line 134
- `test_empty_results_200()` — line 142

## `tests/test_embed_sync.py`

> Sync-semantics tests for the embedding namespace sync (issue #149).

**Imports**

- `__future__: annotations`
- `pathlib: Path`
- `pytest`
- `scripts.embed_digests: sync_digests`
- `scripts.embed_external: sync_directory`
- `scripts.embed_sync: prune_missing, sha256_file`
- `sqlite3`
- `src.chat2.fs_primitives: FileChat2Primitives`
- `src.chat2.sqlite: SqliteChat2Primitives`
- `src.chat2.store_primitives: InMemoryStore`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage.models: EmbeddingRecord`
- `src.storage.primitives_embedding_store: PrimitivesEmbeddingStore`
- `src.storage.vec0_embedding_store: DEFAULT_SQLITE_VEC_EXTENSION_PATH, Vec0EmbeddingStore`
- `src.storage_paths.storage_paths: StoragePaths`
- `typing: Any, Dict, List, Optional`

**Classes**

- `TestStoreListDelete` — line 126
  - `test_list_embeddings_sorted_roundtrip(self, embedding_store: Any) -> None [line 127]`
  - `test_list_embeddings_empty_for_unknown_scope(self, embedding_store: Any) -> None [line 150]`
  - `test_delete_by_record_id_exact(self, embedding_store: Any) -> None [line 155]`
  - `test_delete_by_record_id_never_expands_shared_source_id(self, embedding_store: Any) -> None [line 173]`
- `TestJsonFileStorageSurface` — line 199
  - `test_list_and_delete_by_record_id_interop(self, tmp_path: Path) -> None [line 200]`
  - `test_list_embeddings_empty_when_namespace_missing(self, tmp_path: Path) -> None [line 220]`
- `TestPruneMissing` — line 230
  - `test_prune_missing_scoped_by_root_namespace_and_account(self, embedding_store: Any, tmp_path: Path) -> None [line 231]`
  - `test_prune_dry_run_writes_nothing(self, embedding_store: Any, tmp_path: Path) -> None [line 267]`
  - `test_prune_digests_shared_session_keeps_survivor(self, embedding_store: Any, tmp_path: Path) -> None [line 286]`
- `TestExternalSync` — line 347
  - `test_first_run_embeds_all_with_content_hash(self, embedding_store: Any, tmp_path: Path) -> None [line 348]`
  - `test_skip_unchanged_reembed_changed_prune_missing(self, embedding_store: Any, tmp_path: Path) -> None [line 376]`
  - `test_dry_run_writes_nothing(self, embedding_store: Any, tmp_path: Path) -> None [line 412]`
  - `test_force_reembeds_everything_without_duplicates(self, embedding_store: Any, tmp_path: Path) -> None [line 444]`
  - `test_too_short_files_are_skipped(self, embedding_store: Any, tmp_path: Path) -> None [line 458]`
- `TestDigestsSync` — line 499
  - `test_shared_session_digests_prune_by_record_id_only(self, embedding_store: Any, tmp_path: Path) -> None [line 500]`
  - `test_digests_dry_run_writes_nothing(self, embedding_store: Any, tmp_path: Path) -> None [line 549]`

**Functions**

- `_vector(index: int = 0) -> List[float]` — line 37
- `_require_vec0() -> None` — line 43
- `embedding_store(request: pytest.FixtureRequest, tmp_path: Path) -> Any` — line 64
- `_record(record_id: str, namespace: str = 'documents', *, account: str = 'junwin', source_type: str = 'document', source_id: str = 'src-1', metadata: Optional[Dict[str, Any]] = None, path: Optional[Path] = None, relative_path: Optional[str] = None, content_hash: Optional[str] = None, vector: Optional[List[float]] = None) -> EmbeddingRecord` — line 81
- `_ids(store: Any, namespace: str = 'documents', account: str = 'junwin') -> List[str]` — line 112
- `_write_md(path: Path, text: str) -> None` — line 116
- `_run_external(store: Any, source_dir: Path, md_files: List[Path], **kwargs: Any) -> Dict[str, int]` — line 328
- `_run_digests(store: Any, digests_dir: Path, digest_files: List[Path], **kwargs: Any) -> Dict[str, int]` — line 482

## `tests/test_embedding_facade_wiring.py`

**Imports**

- `src.config_manager: ConfigManager`
- `src.container_config: EmbeddingModule`

**Functions**

- `test_embedding_facade_wiring_credential_path()` — line 5
- `test_embedding_facade_models_returns_known_model_metadata()` — line 13

## `tests/test_episodic_memory_handler.py`

**Imports**

- `json`
- `src.coala_memory.episodic: Chat2EpisodicMemory, EpisodicEvent`
- `src.config_manager: ConfigManager`
- `src.handlers.episodic_memory_handler: EpisodicMemoryHandler`

**Functions**

- `_config(tmp_path)` — line 8
- `_handler(tmp_path)` — line 25
- `_base_args(**overrides)` — line 32
- `test_tool_def_exposes_expected_integration_actions()` — line 50
- `test_handler_recall_uses_sqlite_chat2_and_returns_recent_events(tmp_path)` — line 60
- `test_handler_list_sessions_can_search_event_text(tmp_path)` — line 91
- `test_handler_append_event_round_trips_through_coala_layer(tmp_path)` — line 113

## `tests/test_episodic_memory_handler_lifecycle.py`

**Imports**

- `json`
- `src.coala_memory.episodic: EpisodicEvent`
- `src.config_manager: ConfigManager`
- `src.handlers.episodic_memory_handler: EpisodicMemoryHandler`
- `tests.test_episodic_memory_handler: _base_args, _handler`
- `uuid: uuid4`

**Functions**

- `test_create_session_honours_required_and_optionals(tmp_path)` — line 11
- `test_update_session_patches_allowed_fields_only(tmp_path)` — line 31
- `test_update_session_unknown_session_id_errors_without_touching_others(tmp_path)` — line 66
- `test_reset_session_clears_events_keeps_metadata(tmp_path)` — line 81
- `test_delete_session_returns_ok_and_session_id(tmp_path)` — line 97

## `tests/test_execute_command_fail_fast.py`

**Imports**

- `json`
- `shlex`
- `src.config_manager: ConfigManager`
- `src.handlers.command_execution_handler2: CommandExecutionHandler2`

**Functions**

- `test_heredoc_is_detected_and_rejected()` — line 7
- `test_heredoc_allowed_when_wrapped_in_bash_lc()` — line 29

## `tests/test_fcp_chat2_sqlite.py`

**Imports**

- `pytest`
- `src.chat2.facade: Chat2Store`
- `src.chat2.sqlite: SqliteChat2Primitives`
- `src.coala_memory.episodic: Chat2EpisodicMemory`
- `uuid: uuid4`

**Classes**

- `TestChat2SqliteEndToEnd` — line 30
  - `test_no_tool_call_records_session_and_event(self, make_proc, prompt_builder, llm_adapter, chat2_store) [line 32]`
  - `test_context_name_persisted_in_session_meta(self, make_proc, prompt_builder, llm_adapter, chat2_store) [line 58]`
  - `test_empty_context_name_persisted_as_none(self, make_proc, prompt_builder, llm_adapter, chat2_store) [line 81]`
  - `test_existing_session_reused_not_recreated(self, make_proc, prompt_builder, llm_adapter, chat2_store) [line 102]`
  - `test_save_responses_false_skips_chat2_write(self, make_proc, prompt_builder, llm_adapter, chat2_store) [line 131]`
  - `test_streaming_persists_events_on_generator_close(self, make_proc, prompt_builder, llm_adapter, chat2_store) [line 151]`

**Functions**

- `chat2_store(tmp_path)` — line 11
- `_session_id() -> str` — line 18
- `_saved_agent(**overrides)` — line 22

## `tests/test_fcp_models.py`

> Regression tests for fcp_models (GH issue #132 crash site).

**Imports**

- `src.agent: Agent`
- `src.message_processors.fcp_models: ProcessorContext`
- `types: SimpleNamespace`

**Functions**

- `make_agent(default_context = None)` — line 13
- `test_from_agent_with_none_context_name_uses_default_context()` — line 27
- `test_from_agent_with_none_context_name_and_no_default_is_empty()` — line 37
- `test_from_agent_resolves_model_policy_through_galet_catalog()` — line 48
- `test_from_agent_preserves_legacy_model_without_policy()` — line 73

## `tests/test_function_calling_processor.py`

**Imports**

- `pytest`
- `unittest.mock: Mock, patch`

**Classes**

- `TestEnsureChat2SessionContextName` — line 271
  - `test_context_name_passed_to_create_session(self, make_proc, prompt_builder, llm_adapter) [line 274]`
  - `test_empty_context_name_becomes_none(self, make_proc, prompt_builder, llm_adapter) [line 306]`
  - `test_session_already_exists_skips_create(self, make_proc, prompt_builder, llm_adapter) [line 336]`
  - `test_no_chat2_store_no_crash(self, make_proc, prompt_builder, llm_adapter) [line 364]`
  - `test_save_responses_false_skips_chat2_write(self, make_proc, prompt_builder, llm_adapter) [line 386]`
- `TestFCPSupportsImagesPassthrough` — line 421
  - `test_fcp_passes_supports_images_true_for_vision_model(self, make_proc, prompt_builder, llm_adapter) [line 424]`
  - `test_fcp_passes_supports_images_false_for_text_model(self, make_proc, prompt_builder, llm_adapter) [line 450]`
  - `test_fcp_streaming_passes_supports_images(self, make_proc, prompt_builder, llm_adapter) [line 476]`

**Functions**

- `test_no_tool_calls_returns_text(make_proc, prompt_builder, llm_adapter)` — line 5
- `test_tool_call_executes_handler_and_chains(make_proc, prompt_builder, llm_adapter, storage)` — line 27
- `test_tool_calls_without_response_id_raises(make_proc, prompt_builder, llm_adapter)` — line 72
- `test_max_iterations_exceeded_returns_limit_message(make_proc, prompt_builder, llm_adapter)` — line 98
- `test_bad_json_tool_args_falls_back_to_empty_dict(make_proc, prompt_builder, llm_adapter)` — line 129
- `test_handler_exception_is_wrapped_in_tool_handler_error(make_proc, prompt_builder, llm_adapter)` — line 164
- `test_duplicate_tool_calls_breaks_loop(make_proc, prompt_builder, llm_adapter)` — line 188
- `test_different_tool_calls_do_not_trigger_duplicate_detection(make_proc, prompt_builder, llm_adapter)` — line 227
- `_make_context_state(data)` — line 506
- `_agent_allowing(allowed_tools)` — line 519
- `_tools_passed_to_model(llm_adapter)` — line 527
- `test_fcp_uses_tool_selection_pipeline(make_proc, prompt_builder, llm_adapter)` — line 532
- `test_required_tools_survive_lazy_selection(make_proc, prompt_builder, llm_adapter, storage, config)` — line 566
- `test_required_tool_not_permissioned_returns_error(make_proc, prompt_builder, llm_adapter, storage)` — line 609
- `test_required_tool_not_registered_returns_error(make_proc, prompt_builder, llm_adapter, storage)` — line 643
- `test_budget_exceeded_returns_error(make_proc, prompt_builder, llm_adapter, config)` — line 674
- `test_required_tool_not_permissioned_in_streaming_path(make_proc, prompt_builder, llm_adapter, storage)` — line 705
- `test_unknown_tool_returns_recoverable_error_to_llm(make_proc, prompt_builder, llm_adapter, storage)` — line 739
- `test_streaming_persists_on_generator_close(make_proc, prompt_builder, llm_adapter)` — line 779
- `test_streaming_and_nonstreaming_paths_produce_same_final_text(make_proc, prompt_builder, llm_adapter, storage)` — line 816

## `tests/test_galet_prompt_builder_adapter.py`

**Imports**

- `galet_prompt_builder.metrics: SectionMetrics`
- `galet_prompt_builder: CompiledPrompt, PromptMessage, PromptMetrics`
- `src.coala_memory.episodic: EpisodicEvent, EpisodicMemoryResult`
- `src.coala_memory.procedural: ProceduralMemoryResult`
- `src.coala_memory.semantic: SemanticDocument, SemanticMemoryResult`
- `src.prompt_builders.galet_prompt_builder_adapter: GaletPromptBuilderAdapter, GaletPromptPolicy`
- `types: SimpleNamespace`

**Classes**

- `_Config` — line 22
  - `__init__(self, values = None) [line 23]`
  - `get(self, key, default = None) [line 26]`
- `_AgentManager` — line 30
  - `__init__(self, agent) [line 31]`
  - `get_agent(self, name) [line 34]`
- `_ProceduralMemory` — line 39
  - `__init__(self) [line 40]`
  - `recall(self, request) [line 43]`
- `_UnusedMemory` — line 48
  - `recall(self, request) [line 49]`
- `_RecordingCompiler` — line 53
  - `__init__(self, **memories) [line 56]`
  - `compile(self, request, budgets, limits) [line 61]`

**Functions**

- `_agent(**overrides)` — line 90
- `test_adapter_translates_lucy_call_to_explicit_galet_policy()` — line 107
- `test_adapter_disables_semantic_budget_when_agent_disables_embeddings()` — line 171
- `test_policy_defaults_are_explicit_and_agent_limits_win()` — line 195
- `test_adapter_compiles_with_lucy_memory_contracts()` — line 205

## `tests/test_galet_tools_integration.py`

**Imports**

- `__future__: annotations`
- `galet_tools.framework: HandlerV2`
- `galet_tools.tools.command_execution_handler2: CommandExecutionHandler2`
- `galet_tools.tools.file_load_handler2: FileLoadHandler2`
- `galet_tools.tools.file_save_handler: FileSaveHandler2`
- `galet_tools.tools.generate_image_handler: GenerateImageHandler`
- `galet_tools.tools.generate_svg_handler: GenerateSvgHandler`
- `galet_tools.tools.patch_apply_handler: PatchApplyHandler2`
- `galet_tools: HandlerRegistry`
- `src.handlers.command_execution_handler2: CommandExecutionHandler2`
- `src.handlers.file_load_handler2: FileLoadHandler2`
- `src.handlers.file_save_handler: FileSaveHandler2`
- `src.handlers.generate_image_handler: GenerateImageHandler`
- `src.handlers.generate_svg_handler: GenerateSvgHandler`
- `src.handlers.handler_registry: HandlerRegistry`
- `src.handlers.handler_v2: HandlerV2`
- `src.handlers.patch_apply_handler: PatchApplyHandler`

**Classes**

- `DictConfig` — line 51
  - `__init__(self, values: dict) -> None [line 52]`
  - `get(self, key: str, default = None) [line 55]`

**Functions**

- `test_lucy_compatibility_imports_use_canonical_galet_contract() -> None` — line 34
- `test_generic_handlers_are_thin_galet_adapters() -> None` — line 39
- `test_file_adapters_round_trip_through_lucy_storage(tmp_path) -> None` — line 59
- `test_registry_bootstrap_loads_installed_handler_plugins(monkeypatch) -> None` — line 92
- `test_file_load_adapter_supports_ranged_reads(tmp_path) -> None` — line 115
- `test_patch_apply_adapter_uses_lucy_external_roots(tmp_path) -> None` — line 151
- `test_file_load_strict_schema_exposes_range_arguments() -> None` — line 185

## `tests/test_generate_image_handler.py`

> Tests for GenerateImageHandler.

**Imports**

- `__future__: annotations`
- `base64`
- `pytest`
- `src.handlers.generate_image_handler: GenerateImageHandler`
- `unittest.mock: MagicMock`

**Classes**

- `TestSuccessfulGeneration` — line 18
  - `test_generates_image_with_defaults(self, handler) [line 19]`
  - `test_custom_dimensions_and_color(self, handler) [line 25]`
  - `test_empty_description_defaults(self, handler) [line 36]`
  - `test_result_is_valid_base64_png(self, handler) [line 41]`
- `TestToolDefinition` — line 49
  - `test_tool_def_has_required_fields(self, handler) [line 50]`
  - `test_result_schema_has_image_field(self, handler) [line 59]`

**Functions**

- `handler()` — line 13

## `tests/test_generate_svg_handler.py`

> Tests for GenerateSvgHandler — validation and sanitization.

**Imports**

- `__future__: annotations`
- `json`
- `pytest`
- `src.handlers.generate_svg_handler: GenerateSvgHandler, GenerateSvgInput, SvgSanitizer, ALLOWED_ELEMENTS, MAX_SVG_CHARS`

**Classes**

- `TestInputValidation` — line 34
  - `test_valid_minimal_input(self) [line 35]`
  - `test_missing_svg_code_rejected(self) [line 44]`
  - `test_width_below_min_rejected(self) [line 49]`
  - `test_width_above_max_rejected(self) [line 56]`
  - `test_height_below_min_rejected(self) [line 63]`
  - `test_height_above_max_rejected(self) [line 70]`
- `TestSanitization` — line 80
  - `test_valid_svg_passes_through(self, sanitizer) [line 81]`
  - `test_script_element_stripped(self, sanitizer) [line 89]`
  - `test_onclick_handler_stripped(self, sanitizer) [line 99]`
  - `test_foreignObject_stripped(self, sanitizer) [line 107]`
  - `test_onerror_stripped(self, sanitizer) [line 117]`
  - `test_namespace_preserved(self, sanitizer) [line 124]`
  - `test_all_whitelisted_elements_preserved(self, sanitizer) [line 133]`
  - `test_disallowed_elements_stripped(self, sanitizer) [line 142]`
- `TestParseErrors` — line 153
  - `test_malformed_xml_rejected(self) [line 154]`
  - `test_non_svg_root_rejected(self, sanitizer) [line 159]`
- `TestHandlerExecute` — line 166
  - `test_successful_generation(self, handler) [line 167]`
  - `test_empty_svg_code_rejected(self, handler) [line 186]`
  - `test_oversized_svg_rejected(self, handler) [line 191]`
  - `test_invalid_svg_xml_rejected(self, handler) [line 197]`
  - `test_xss_sanitized_in_handler(self, handler) [line 202]`
  - `test_result_is_valid_json(self, handler) [line 214]`

**Functions**

- `handler()` — line 20
- `sanitizer()` — line 28

## `tests/test_get_base_path_hanlder_utils.py`

**Imports**

- `os`
- `pytest`
- `src.handlers.handler_utils: get_base_path`

**Classes**

- `DummyConfig` — line 8
  - `__init__(self, **kwargs) [line 9]`
  - `get(self, key: str, default = None) [line 12]`

**Functions**

- `_mk_config(tmp_path)` — line 16
- `test_get_base_path_basic_join(tmp_path)` — line 23
- `test_get_base_path_strips_whitespace(tmp_path)` — line 32
- `test_get_base_path_normalizes_slashes(tmp_path)` — line 41
- `test_get_base_path_resolves_dotdot_inside_sandbox(tmp_path)` — line 51
- `test_get_base_path_blocks_traversal_outside_sandbox(tmp_path)` — line 60
- `test_get_base_path_tilde_means_account_root(tmp_path)` — line 67
- `test_get_base_path_tilde_subdir(tmp_path)` — line 80
- `test_get_base_path_allows_absolute_only_if_within_account_root(tmp_path)` — line 89
- `test_get_base_path_blocks_absolute_outside_account_root(tmp_path)` — line 100

## `tests/test_get_base_path_hybrid.py`

**Imports**

- `os`
- `pathlib: Path`
- `pytest`
- `src.handlers.handler_utils: get_base_path`

**Classes**

- `DummyConfig` — line 8
  - `__init__(self, **kwargs) [line 9]`
  - `get(self, key: str, default = None) [line 12]`

**Functions**

- `test_get_base_path_prefers_lucy_user_root(tmp_path, monkeypatch)` — line 16
- `test_get_base_path_uses_home_for_matching_username(tmp_path, monkeypatch)` — line 29
- `test_get_base_path_falls_back_to_home_account_dir(tmp_path, monkeypatch)` — line 42

## `tests/test_get_keywords_handler.py`

> Tests for GetKeywordsHandler.

**Imports**

- `__future__: annotations`
- `pytest`
- `src.handlers.get_keywords_handler: GetKeywordsHandler`
- `unittest.mock: patch, MagicMock`

**Classes**

- `TestInputValidation` — line 17
  - `test_missing_content_returns_error(self, handler) [line 18]`
  - `test_empty_content_returns_error(self, handler) [line 23]`
- `TestSuccessfulExtraction` — line 29
  - `test_valid_content_returns_keywords(self, handler) [line 30]`
  - `test_language_code_is_passed_through(self, handler) [line 40]`
  - `test_invalid_top_n_defaults_to_10(self, handler) [line 49]`
  - `test_keywords_class_failure_returns_error(self, handler) [line 58]`
- `TestToolDefinition` — line 69
  - `test_tool_def_has_required_fields(self, handler) [line 70]`

**Functions**

- `handler()` — line 12

## `tests/test_json_filestorage_chat_method_guardrails.py`

**Imports**

- `src.storage.json_file_storage: JsonFileStorage`

**Functions**

- `_v1_chat_method_names() -> list[str]` — line 4
- `test_json_file_storage_has_no_v1_chat_methods()` — line 18

## `tests/test_json_specific.py`

## `tests/test_keywords.py`

**Imports**

- `pytest`
- `src.keywords.keywords: Keywords`

**Classes**

- `FakeToken` — line 6
  - `__init__(self, text, lemma_, *, is_punct = False, pos_ = 'NOUN') [line 7]`
- `FakeDoc(list)` — line 15

**Functions**

- `make_fake_nlp(tokens)` — line 19
- `keywords(monkeypatch)` — line 27
- `test_extract_keywords_filters_stopwords_punct_and_respects_top_n(keywords, monkeypatch)` — line 34
- `test_extract_keywords_retains_nouns_mistagged_as_verb(keywords, monkeypatch)` — line 61
- `test_extract_keywords_request_keywords_fenced_block_parsing(keywords)` — line 85
- `test_get_specified_keywords_returns_empty_when_missing(keywords)` — line 91
- `test_compare_keywords_and_or_and_invalid_operator(keywords)` — line 95
- `test_compare_semantic_similarity_identical_is_1_and_different_is_lower(keywords)` — line 106
- `test_compare_keyword_lists_semantic_similarity_identical_is_1_and_different_is_lower(keywords)` — line 114

## `tests/test_live_prompt_builder.py`

> Live integration test: starts the Flask app on port 5001, hits /prompt_builder,

**Imports**

- `__future__: annotations`
- `json`
- `os`
- `pathlib: Path`
- `pytest`
- `signal`
- `subprocess`
- `sys`
- `time`
- `uuid`

**Functions**

- `_generate_self_signed_cert(cert_dir: Path) -> tuple[Path, Path]` — line 49
- `live_config(tmp_path: Path) -> Path` — line 79
- `seeded_chat2_data(tmp_path: Path, live_config: Path) -> str` — line 117
- `app_process(live_config: Path, seeded_chat2_data: str, tmp_path: Path)` — line 160
- `test_live_prompt_builder_returns_chat2_history(app_process, seeded_chat2_data)` — line 252
- `test_live_prompt_builder_fallback_to_v1(app_process, tmp_path)` — line 304

## `tests/test_machine_catalog.py`

**Imports**

- `json`
- `pytest`
- `src.machine_catalog: MachineConfigError, MachineDefinition, MachineManager`

**Functions**

- `data(**changes)` — line 6
- `test_definition_exposes_capabilities_without_exposing_secret()` — line 16
- `test_existing_minimal_format_is_valid()` — line 27
- `test_invalid_definitions_are_rejected(bad, match)` — line 40
- `test_manager_loads_filters_and_resolves_path(tmp_path)` — line 45
- `test_missing_file_is_empty(tmp_path)` — line 55
- `test_bad_json_and_shape_are_rejected(tmp_path)` — line 60

## `tests/test_mcp_server.py`

> Offline tests for ``src.mcp.server`` (design doc Tests table: test_mcp_*).

**Imports**

- `__future__: annotations`
- `json`
- `pathlib: Path`
- `pytest`
- `src.agent.agent: Agent`
- `src.handlers.handler_registry: HandlerRegistry`
- `src.handlers.handler_v2: HandlerV2`
- `src.mcp.server: McpConfigError, McpScope, dispatch_tool_call, effective_context_name, eligible_tools, resolve_mcp_config, resolve_scope, resolve_startup_scope`
- `typing: Any, Dict, List, Optional`

**Classes**

- `_Cfg` — line 62
  - `__init__(self, data: Dict[str, Any]) -> None [line 65]`
  - `get(self, key: str, default: Any = None) -> Any [line 68]`
- `_StubAgentManager` — line 72
  - `__init__(self, agent: Optional[Agent]) -> None [line 75]`
  - `get_agent(self, name: str) -> Optional[Agent] [line 78]`
- `_AlphaHandler(HandlerV2)` — line 82
  - `name(cls) -> str [line 88]`
  - `tool_def(cls) -> Dict[str, Any] [line 92]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context) -> Dict[str, Any] [line 104]`
- `_BetaHandler(_AlphaHandler)` — line 110
- `_GammaHandler(_AlphaHandler)` — line 114
- `_RecordingHandler(_AlphaHandler)` — line 118
  - `__init__(self, config: Any) -> None [line 124]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context) -> Dict[str, Any] [line 127]`
- `_BoomHandler(_RecordingHandler)` — line 134
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context) -> Dict[str, Any] [line 137]`
- `_BigResultHandler(_RecordingHandler)` — line 143
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context) -> Dict[str, Any] [line 148]`
- `_SizeResultHandler(_RecordingHandler)` — line 154
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context) -> Dict[str, Any] [line 157]`
- `_LlamaStub` — line 164
  - `format_tool_output(self, *, call_id: str, output: str, name: str, provider: Optional[str]) -> Dict[str, Any] [line 167]`
- `_ExplodingExecutor` — line 173
  - `__init__(self) -> None [line 176]`
  - `wrap_tool_calls(self, tool_calls: Any) -> List[Any] [line 179]`
  - `execute_tool_calls(self, **kwargs: Any) -> Any [line 183]`
- `_FakePromptBuilder` — line 187
  - `__init__(self, context_state: Any) -> None [line 190]`
  - `_get_context_state(self, account_name: str, context_name: str) -> Any [line 193]`
- `_ToolExecutorStub` — line 404
  - `__init__(self, registry: HandlerRegistry, config: _Cfg) -> None [line 407]`
  - `wrap_tool_calls(self, tool_calls: Any) -> Any [line 419]`
  - `execute_tool_calls(self, **kwargs: Any) -> Any [line 422]`

**Functions**

- `_context_with_allowed_tools(tools: List[str]) -> Any` — line 197
- `_registry_with(*handler_classes: type) -> HandlerRegistry` — line 202
- `_mcp_agent(allowed_tools: Optional[List[str]]) -> Agent` — line 209
- `_scope_for(agent: Agent, eligible: List[str]) -> McpScope` — line 213
- `test_mcp_config_defaults_when_block_absent() -> None` — line 227
- `test_mcp_config_parses_explicit_block() -> None` — line 240
- `test_mcp_config_rejects_unsupported_transport() -> None` — line 253
- `test_mcp_config_rejects_non_loopback_host() -> None` — line 258
- `test_mcp_config_rejects_invalid_port() -> None` — line 263
- `test_mcp_config_block_ships_disabled_in_repo_config_json() -> None` — line 270
- `test_mcp_config_refuses_missing_agent() -> None` — line 278
- `test_mcp_config_refuses_empty_allowlist() -> None` — line 284
- `test_mcp_config_accepts_agent_with_allowlist() -> None` — line 291
- `test_mcp_config_refuses_zero_eligible_tools() -> None` — line 299
- `test_effective_context_name_config_wins_then_agent_default() -> None` — line 308
- `test_mcp_eligibility_tools_list_equals_eligible_defs() -> None` — line 324
- `test_mcp_eligibility_missing_allowlist_exposes_nothing() -> None` — line 344
- `test_mcp_eligibility_context_restriction_narrows_tools() -> None` — line 352
- `_dispatch(registry: HandlerRegistry, agent: Agent, *, name: str, arguments: Dict[str, Any], config: Optional[_Cfg] = None) -> Dict[str, Any]` — line 380
- `test_mcp_call_argument_passing_reaches_execute_unchanged() -> None` — line 426
- `test_mcp_call_result_mapping_structured_result_to_text() -> None` — line 443
- `test_mcp_call_result_mapping_too_large_is_capped_error_text() -> None` — line 457
- `test_mcp_call_tool_result_cap_defaults_to_20000_without_config_or_agent_override() -> None` — line 483
- `test_mcp_call_agent_tool_result_override_smaller_than_config_caps() -> None` — line 501
- `test_mcp_call_error_mapping_handler_exception_is_iserror() -> None` — line 532
- `test_mcp_call_error_mapping_unknown_tool_is_iserror() -> None` — line 542
- `test_mcp_call_error_mapping_unexpected_executor_error_is_iserror() -> None` — line 562

## `tests/test_metrics_endpoints.py`

> Tests for the /metrics/runs endpoint implementation (issue #131, design doc

**Imports**

- `__future__: annotations`
- `json`
- `pytest`
- `src.http_endpoints.metrics_endpoints: get_metrics_runs_impl`
- `src.metrics: MetricsRepository`
- `unittest.mock: Mock`

**Functions**

- `_record(correlation_id: str, started: str, duration_ms: int = 0, agent: str = 'lucy', account: str = 'junwin', hit_iteration_cap: bool = False, success: bool = True) -> dict` — line 19
- `_write(path, records)` — line 50
- `_ids(runs)` — line 55
- `log_path(tmp_path)` — line 60
- `_make_container(repository)` — line 65
- `_call(container, params)` — line 77
- `test_happy_path_returns_all_records_newest_first(log_path)` — line 81
- `test_missing_log_file_returns_empty(log_path)` — line 99
- `test_filter_by_correlation_id(log_path)` — line 108
- `test_filter_by_agent(log_path)` — line 125
- `test_filter_by_account(log_path)` — line 142
- `test_filter_by_started(log_path)` — line 159
- `test_filter_by_ended(log_path)` — line 176
- `test_filter_by_hit_iteration_cap(log_path)` — line 193
- `test_success_filter_accepts_true_forms(log_path, value)` — line 211
- `test_success_filter_accepts_false_forms(log_path, value)` — line 229
- `test_limit_defaults_to_50(log_path)` — line 246
- `test_limit_clamped_to_500(log_path)` — line 261
- `test_limit_non_integer_returns_400(log_path, value)` — line 277
- `test_limit_non_positive_returns_400(log_path, value)` — line 287
- `test_invalid_timestamp_returns_400(log_path, param)` — line 297
- `test_invalid_success_returns_400(log_path)` — line 307
- `test_invalid_hit_iteration_cap_returns_400(log_path)` — line 316

## `tests/test_metrics_repository.py`

> MetricsRepository tests: every filter, newest-first ordering, limit

**Imports**

- `datetime: datetime, timezone`
- `json`
- `pytest`
- `src.metrics: MetricsRepository`

**Functions**

- `_record(correlation_id: str, started: str, duration_ms: int = 0, agent: str = 'lucy', account: str = 'junwin', hit_iteration_cap: bool = False, success: bool = True) -> dict` — line 13
- `_write(path, records)` — line 44
- `_ids(runs)` — line 49
- `test_query_returns_records_newest_first(tmp_path)` — line 53
- `test_newest_first_breaks_ties_by_line_order(tmp_path)` — line 69
- `test_filter_by_correlation_id(tmp_path)` — line 84
- `test_filter_by_agent(tmp_path)` — line 99
- `test_filter_by_account(tmp_path)` — line 114
- `test_filter_by_hit_iteration_cap(tmp_path)` — line 129
- `test_filter_by_success(tmp_path)` — line 144
- `test_filter_by_started_time_range(tmp_path)` — line 159
- `test_started_filter_accepts_iso_string(tmp_path)` — line 177
- `test_filter_by_ended_time_range(tmp_path)` — line 192
- `test_combined_filters(tmp_path)` — line 210
- `test_default_limit_is_50(tmp_path)` — line 226
- `test_limit_clamped_to_500(tmp_path)` — line 240
- `test_limit_invalid_raises(tmp_path)` — line 260
- `test_malformed_lines_are_skipped(tmp_path)` — line 271
- `test_missing_file_returns_empty(tmp_path)` — line 304
- `test_record_with_unparseable_started_is_skipped(tmp_path)` — line 310
- `test_absent_optional_fields_tolerated(tmp_path)` — line 326
- `test_invalid_filter_timestamp_raises(tmp_path)` — line 352

## `tests/test_migrate_embeddings_to_sqlite.py`

> Tests for the file-to-sqlite embedding migration script.

**Imports**

- `__future__: annotations`
- `pathlib: Path`
- `scripts.migrate_embeddings_to_sqlite: migrate_embeddings`
- `src.chat2.fs_primitives: FileChat2Primitives`
- `src.chat2.sqlite: SqliteChat2Primitives`
- `src.chat2.store_primitives: StoreKey`

**Functions**

- `_make_file_store(root: Path, records: dict[str, str]) -> FileChat2Primitives` — line 19
- `test_migrate_copies_verbatim_and_skips_stray(tmp_path)` — line 27
- `test_migrate_is_idempotent(tmp_path)` — line 51
- `test_migrate_dry_run_writes_nothing(tmp_path)` — line 63
- `test_migrate_overwrites_existing_sqlite_values(tmp_path)` — line 79

## `tests/test_mistral_adapter_images.py`

> Tests for Mistral adapter image content-part normalization (Step 6).

**Imports**

- `__future__: annotations`
- `galet.mistral_api: MistralApi`
- `pytest`
- `unittest.mock: Mock`

**Functions**

- `test_normalize_image_part_to_image_url()` — line 27
- `test_normalize_image_part_jpeg()` — line 43
- `test_normalize_image_part_gif()` — line 54
- `test_normalize_image_part_webp()` — line 63
- `test_normalize_missing_source_defaults_png()` — line 72
- `test_normalize_empty_source_uses_defaults()` — line 82
- `test_normalize_text_only_passes_through()` — line 91
- `test_normalize_non_list_passes_through_string()` — line 101
- `test_normalize_non_list_passes_through_none()` — line 107
- `test_normalize_non_dict_part_passes_through()` — line 112
- `test_normalize_unknown_type_passes_through()` — line 123
- `test_normalize_multiple_images()` — line 132
- `test_normalize_messages_with_content_parts()` — line 154
- `test_normalize_messages_all_string_content_unchanged()` — line 173
- `test_normalize_messages_with_mixed_content_types()` — line 184
- `test_normalize_messages_non_dict_passes_through()` — line 199
- `test_normalize_messages_non_list_passes_through()` — line 210
- `test_normalize_messages_empty_list()` — line 215
- `test_normalize_messages_preserves_other_message_fields()` — line 220
- `test_normalize_input_to_messages_with_image_parts()` — line 238
- `test_normalize_input_to_messages_pure_text_passes_through()` — line 260
- `test_normalize_input_to_messages_handles_multiple_messages_with_images()` — line 273
- `test_normalize_input_to_messages_string_input_unchanged()` — line 294
- `test_normalize_input_to_messages_dict_input_wrapped()` — line 304
- `test_normalize_input_to_messages_preserves_original_input()` — line 312
- `_make_mock_mistral_client()` — line 337
- `test_create_response_normalizes_image_parts()` — line 358
- `test_create_response_passes_through_plain_text()` — line 385
- `test_create_response_preserves_original_messages()` — line 401

## `tests/test_obsidian_importer.py`

> Tests for the Obsidian importer module.

**Imports**

- `__future__: annotations`
- `pathlib: Path`
- `pytest`
- `src.utils.obsidian_importer: _stable_doc_id_from_path, index_obsidian_file, index_obsidian_vault`
- `typing: Any, Dict, List, Optional`

**Classes**

- `_DictDocStorage` — line 24
  - `__init__(self) -> None [line 27]`
  - `upsert_document(self, doc: Any) -> None [line 30]`
  - `get_document(self, document_id: str) -> Optional[Any] [line 33]`
  - `list_documents(self, account_name: str, kind: Optional[str] = None, tag: Optional[str] = None, select_limit: int = 100) -> List[Any] [line 36]`
- `TestStableDocIdFromPath` — line 56
  - `test_same_vault_same_path_always_same_id(self) [line 59]`
  - `test_different_vaults_different_ids(self) [line 67]`
  - `test_different_paths_different_ids(self) [line 73]`
  - `test_id_independent_of_absolute_path(self) [line 79]`
  - `test_subdirectory_paths(self) [line 92]`
  - `test_vault_name_with_spaces(self) [line 98]`
  - `test_different_vault_same_path_produces_different_ids(self) [line 104]`
  - `test_id_format_is_hex(self) [line 110]`
- `TestIndexObsidianFile` — line 123
  - `test_indexes_simple_file(self, tmp_path: Path) -> None [line 126]`
  - `test_extracts_frontmatter_tags(self, tmp_path: Path) -> None [line 148]`
  - `test_id_is_stable(self, tmp_path: Path) -> None [line 158]`
  - `test_with_vault_root(self, tmp_path: Path) -> None [line 183]`
  - `test_file_outside_vault_root_raises(self, tmp_path: Path) -> None [line 204]`
  - `test_nonexistent_file_raises(self, tmp_path: Path) -> None [line 219]`
  - `test_non_md_file_raises(self, tmp_path: Path) -> None [line 229]`
  - `test_directory_raises(self, tmp_path: Path) -> None [line 240]`
  - `test_custom_kind(self, tmp_path: Path) -> None [line 249]`
  - `test_nonexistent_vault_root_raises(self, tmp_path: Path) -> None [line 265]`
  - `test_vault_root_is_file_raises(self, tmp_path: Path) -> None [line 279]`
  - `test_upsert_failure_returns_empty(self, tmp_path: Path) -> None [line 294]`

## `tests/test_obsidian_index_cli.py`

**Imports**

- `os`
- `pathlib: Path`
- `subprocess`
- `sys`
- `tempfile`

**Functions**

- `test_obsidian_index_cli_runs_and_indexes_one_file(tmp_path, monkeypatch)` — line 8
- `test_obsidian_index_cli_file_flag(tmp_path, monkeypatch)` — line 41
- `test_obsidian_index_cli_file_flag_dry_run(tmp_path, monkeypatch)` — line 73

## `tests/test_openai_adapter_images.py`

> Tests for OpenAI adapter image content-part normalization (Step 5).

**Imports**

- `__future__: annotations`
- `galet.openai_responses: OpenAIResponsesApi`
- `pytest`
- `unittest.mock: Mock`

**Functions**

- `test_normalize_image_part_to_input_image()` — line 26
- `test_normalize_image_part_jpeg()` — line 42
- `test_normalize_image_part_gif()` — line 53
- `test_normalize_image_part_webp()` — line 62
- `test_normalize_missing_source_defaults_png()` — line 71
- `test_normalize_empty_source_uses_defaults()` — line 81
- `test_normalize_text_parts_renamed_to_input_text()` — line 90
- `test_normalize_non_list_passes_through_string()` — line 100
- `test_normalize_non_list_passes_through_none()` — line 106
- `test_normalize_non_dict_part_passes_through()` — line 111
- `test_normalize_unknown_type_passes_through()` — line 122
- `test_normalize_multiple_images()` — line 131
- `test_normalize_messages_with_content_parts()` — line 153
- `test_normalize_messages_all_string_content_unchanged()` — line 172
- `test_normalize_messages_with_mixed_content_types()` — line 183
- `test_normalize_messages_non_dict_passes_through()` — line 198
- `test_normalize_messages_non_list_passes_through()` — line 209
- `test_normalize_messages_empty_list()` — line 214
- `test_normalize_messages_preserves_other_message_fields()` — line 219
- `_make_mock_openai_client()` — line 237
- `test_create_response_normalizes_image_parts()` — line 251
- `test_create_response_passes_through_plain_text()` — line 278
- `test_create_response_handles_string_input()` — line 294
- `test_create_response_preserves_original_messages()` — line 305

## `tests/test_primitives_embedding_store.py`

> Tests for PrimitivesEmbeddingStore — the embedding store as a second

**Imports**

- `__future__: annotations`
- `pathlib: Path`
- `pytest`
- `src.chat2.fs_primitives: FileChat2Primitives`
- `src.chat2.sqlite: SqliteChat2Primitives`
- `src.chat2.store_primitives: InMemoryStore`
- `src.storage.interfaces: EmbeddingStore`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage.models: EmbeddingRecord`
- `src.storage.primitives_embedding_store: PrimitivesEmbeddingStore, build_primitives_embedding_store`
- `src.storage_paths.storage_paths: StoragePaths`
- `typing: Any, Callable, List`

**Classes**

- `TestUpsertQuery` — line 99
  - `test_upsert_query_roundtrip(self, store: PrimitivesEmbeddingStore) -> None [line 100]`
  - `test_upsert_overwrites_same_id(self, store: PrimitivesEmbeddingStore) -> None [line 129]`
  - `test_query_top_k_sorted(self, store: PrimitivesEmbeddingStore) -> None [line 141]`
  - `test_query_missing_namespace_returns_empty(self, store: PrimitivesEmbeddingStore) -> None [line 156]`
  - `test_query_merges_namespaces(self, store: PrimitivesEmbeddingStore) -> None [line 166]`
  - `test_query_filter_source_type(self, store: PrimitivesEmbeddingStore) -> None [line 188]`
  - `test_account_isolation(self, store: PrimitivesEmbeddingStore) -> None [line 204]`
- `TestDelete` — line 224
  - `test_delete_by_source_id(self, store: PrimitivesEmbeddingStore) -> None [line 225]`
  - `test_delete_by_source_type(self, store: PrimitivesEmbeddingStore) -> None [line 247]`
  - `test_delete_no_match_returns_zero(self, store: PrimitivesEmbeddingStore) -> None [line 261]`
  - `test_delete_missing_namespace_returns_zero(self, store: PrimitivesEmbeddingStore) -> None [line 270]`
- `TestNamespaces` — line 285
  - `test_list_namespaces_sorted(self, store: PrimitivesEmbeddingStore) -> None [line 286]`
  - `test_list_namespaces_unknown_account(self, store: PrimitivesEmbeddingStore) -> None [line 293]`
  - `test_list_namespaces_ignores_other_accounts(self, store: PrimitivesEmbeddingStore) -> None [line 298]`
- `_Cfg` — line 418
  - `__init__(self, values: dict) -> None [line 421]`
  - `get(self, key: str, default: Any = None) -> Any [line 424]`

**Functions**

- `_memory_factory(tmp_path: Path) -> Any` — line 38
- `_file_factory(tmp_path: Path) -> Any` — line 42
- `_sqlite_factory(tmp_path: Path) -> Any` — line 46
- `store(request: pytest.FixtureRequest, tmp_path: Path) -> PrimitivesEmbeddingStore` — line 58
- `_record(record_id: str = 'rec1', namespace: str = 'documents', account: str = 'junwin', vector: List[float] | None = None, source_type: str = 'document', source_id: str = 'src-1', metadata: dict | None = None) -> EmbeddingRecord` — line 67
- `test_implements_embedding_store_interface(store: PrimitivesEmbeddingStore) -> None` — line 91
- `test_reopen_persistence(factory: Callable[[Path], Any], tmp_path: Path) -> None` — line 321
- `test_parity_with_json_file_storage(tmp_path: Path) -> None` — line 352
- `test_factory_defaults_to_file_backend(tmp_path: Path) -> None` — line 428
- `test_factory_sqlite_backend(tmp_path: Path) -> None` — line 451

## `tests/test_prompt_builder_chat2_integration.py`

> Integration tests for PromptBuilder history through CoALA episodic memory.

**Imports**

- `pytest`
- `src.chat2.facade: Chat2Store`
- `src.chat2.models: ChatEvent`
- `src.chat2.prompt_slice: get_last_n_events`
- `src.chat2.store_primitives: InMemoryStore`
- `src.coala_memory.episodic: Chat2EpisodicMemory`
- `src.prompt_builders.prompt_builder: PromptBuilder`
- `unittest.mock: Mock`

**Functions**

- `chat2_store() -> Chat2Store` — line 16
- `seeded_session(chat2_store: Chat2Store) -> str` — line 21
- `session_with_context(chat2_store: Chat2Store) -> str` — line 40
- `session_with_friendly_name(chat2_store: Chat2Store) -> str` — line 50
- `test_get_last_n_events_returns_only_user_assistant(seeded_session, chat2_store)` — line 59
- `test_get_last_n_events_respects_limit(seeded_session, chat2_store)` — line 69
- `test_get_last_n_events_zero_returns_empty(seeded_session, chat2_store)` — line 74
- `test_get_last_n_events_fewer_than_n(seeded_session, chat2_store)` — line 80
- `_make_prompt_builder(chat2_store = None, max_prompt_conversations = 10)` — line 85
- `_find_session_info_message(messages)` — line 108
- `_history(messages, current)` — line 119
- `test_build_prompt_includes_history_from_episodic_memory(seeded_session, chat2_store)` — line 127
- `test_prompt_builder_respects_max_conversations(seeded_session, chat2_store)` — line 146
- `test_prompt_builder_zero_max_conversations(seeded_session, chat2_store)` — line 158
- `test_tool_only_session_produces_no_prompt_history(chat2_store)` — line 170
- `test_missing_session_produces_no_prompt_history(chat2_store)` — line 190
- `test_session_info_includes_context_name(session_with_context, chat2_store)` — line 201
- `test_session_info_context_falls_back_to_friendly_name(session_with_friendly_name, chat2_store)` — line 219
- `test_session_info_omits_context_when_metadata_has_none(seeded_session, chat2_store)` — line 236
- `test_missing_episode_does_not_add_session_info()` — line 249
- `test_nonexistent_session_does_not_add_session_info(chat2_store)` — line 261
- `test_special_conversation_ids_do_not_add_session_info(conversation_id, chat2_store)` — line 273

## `tests/test_prompt_builder_coala_digests.py`

**Imports**

- `__future__: annotations`
- `datetime: datetime`
- `src.coala_memory.episodic: EpisodicDigest, EpisodicEvent, EpisodicMemory, EpisodicMemoryRequest, EpisodicMemoryResult`
- `src.prompt_builders.coala_prompt_builder: CoALAPromptBuilder`
- `types: SimpleNamespace`

**Classes**

- `_Config` — line 16
  - `__init__(self, values = None) [line 17]`
  - `get(self, key, default = None) [line 20]`
- `_AgentManager` — line 24
  - `get_agent(self, name) [line 25]`
- `_Episodic(EpisodicMemory)` — line 40
  - `__init__(self) [line 41]`
  - `recall(self, request: EpisodicMemoryRequest) -> EpisodicMemoryResult [line 45]`
  - `save_overflow_digest(self, *, account_name, conversation_id, snippet) [line 68]`

**Functions**

- `_builder(memory, config = None)` — line 73
- `test_prompt_builder_uses_single_episodic_recall_for_history_and_digests()` — line 83
- `test_prompt_builder_recalls_archived_digests_without_active_session()` — line 112
- `test_prompt_builder_persists_overflow_through_episodic_memory()` — line 135

## `tests/test_prompt_builder_coala_episodic.py`

**Imports**

- `datetime: datetime`
- `src.chat2.facade: Chat2Store`
- `src.chat2.models: ChatEvent`
- `src.chat2.store_primitives: InMemoryStore`
- `src.coala_memory.episodic: Chat2EpisodicMemory, EpisodicEvent, EpisodicMemory, EpisodicMemoryRequest, EpisodicMemoryResult`
- `src.prompt_builders.prompt_builder: PromptBuilder`
- `types: SimpleNamespace`

**Classes**

- `_Config` — line 17
  - `get(self, key, default = None) [line 18]`
- `_Storage` — line 22
  - `get_or_create_context(self, account_name, context_name) [line 23]`
- `_AgentManager` — line 34
  - `__init__(self, agent) [line 35]`
  - `get_agent(self, name) [line 38]`
- `_FakeEpisodicMemory(EpisodicMemory)` — line 42
  - `__init__(self) [line 43]`
  - `recall(self, request: EpisodicMemoryRequest) -> EpisodicMemoryResult [line 46]`
  - `save_overflow_digest(self, *, account_name, conversation_id, snippet) [line 68]`

**Functions**

- `_agent(max_prompt_conversations = 2)` — line 72
- `test_prompt_builder_uses_one_episodic_recall_for_session_info_and_history()` — line 87
- `test_chat2_episodic_memory_filters_kinds_before_max_events()` — line 122

## `tests/test_prompt_builder_coala_procedural.py`

**Imports**

- `datetime: datetime, timezone`
- `src.coala_memory.procedural: ContextProceduralMemory, ProceduralMemory, ProceduralMemoryRequest, ProceduralMemoryResult, ProceduralSkill`
- `src.coala_memory.semantic: SemanticDocument, SemanticMemory, SemanticMemoryRequest, SemanticMemoryResult`
- `src.prompt_builders.coala_prompt_builder: CoALAPromptBuilder`
- `src.storage.models: Context, Skill`
- `types: SimpleNamespace`

**Classes**

- `_Config` — line 21
  - `get(self, key, default = None) [line 22]`
- `_AgentManager` — line 26
  - `__init__(self, agent) [line 27]`
  - `get_agent(self, name) [line 30]`
- `_Storage` — line 34
  - `get_or_create_context(self, account_name, context_name) [line 35]`
- `_ContextStore` — line 39
  - `__init__(self, context) [line 40]`
  - `get_or_create_context(self, account_name, context_id) [line 45]`
  - `get_context(self, account_name, context_id) [line 49]`
- `_FakeProceduralMemory(ProceduralMemory)` — line 54
  - `__init__(self) [line 55]`
  - `recall(self, request: ProceduralMemoryRequest) -> ProceduralMemoryResult [line 58]`
- `_FakeSemanticMemory(SemanticMemory)` — line 80
  - `__init__(self) [line 81]`
  - `recall(self, request: SemanticMemoryRequest) -> SemanticMemoryResult [line 84]`

**Functions**

- `_agent()` — line 99
- `test_context_procedural_memory_maps_resolved_context_and_skills()` — line 115
- `test_context_procedural_memory_can_read_without_creating()` — line 158
- `test_prompt_builder_recalls_procedural_context_once_and_routes_namespaces()` — line 180
- `test_prompt_builder_procedural_cache_is_scoped_to_one_build()` — line 219

## `tests/test_prompt_builder_coala_semantic.py`

**Imports**

- `src.coala_memory.procedural: ProceduralMemoryResult`
- `src.coala_memory.semantic: SemanticDocument, SemanticMemoryResult`
- `src.prompt_builders.coala_prompt_builder: CoALAPromptBuilder`
- `src.prompt_builders.prompt_builder: PromptBuilder`
- `types: SimpleNamespace`
- `unittest.mock: Mock`

**Classes**

- `RecordingSemanticMemory` — line 10
  - `__init__(self) -> None [line 11]`
  - `recall(self, request) [line 14]`
- `FakeProceduralMemory` — line 33
  - `recall(self, request) [line 34]`
- `FakeAgentManager` — line 44
  - `__init__(self, agent) -> None [line 45]`
  - `get_agent(self, name) [line 48]`
- `FakeConfig` — line 52
  - `get(self, key, default = None) [line 53]`

**Functions**

- `_agent()` — line 57
- `test_prompt_builder_uses_coala_semantic_memory_and_context_namespaces()` — line 72
- `test_prompt_builder_semantic_helper_preserves_legacy_doc_context_shape()` — line 108

## `tests/test_prompt_builder_collaborators.py`

**Imports**

- `src.prompt_builders.history_selector: HistorySelector`
- `src.prompt_builders.prompt_sections: PromptSections`
- `src.prompt_builders.token_budget: TokenBudgetAllocator, estimate_tokens_from_text`
- `types: SimpleNamespace`
- `unittest.mock: Mock`

**Classes**

- `FakeConfig` — line 9
  - `get(self, key, default = None) [line 10]`

**Functions**

- `test_estimate_tokens_preserves_prompt_builder_heuristic()` — line 14
- `test_token_budget_allocator_preserves_breakdown_keys()` — line 20
- `test_history_selector_keeps_newest_events_that_fit_budget()` — line 48
- `test_prompt_sections_render_document_context_unchanged()` — line 73

## `tests/test_prompt_builder_context_limit.py`

**Imports**

- `datetime: datetime, timezone`
- `logging`
- `src.agent.agent: Agent`
- `src.coala_memory.procedural: ContextProceduralMemory`
- `src.prompt_builders.coala_prompt_builder: CoALAPromptBuilder`
- `src.storage.models: Context`

**Classes**

- `FakeAgentManager` — line 10
  - `__init__(self, agent = None) [line 11]`
  - `get_agent(self, name) [line 14]`
- `FakeConfig` — line 18
  - `__init__(self, values = None) [line 19]`
  - `get(self, key, default = None) [line 22]`
- `FakeStorage` — line 26
  - `__init__(self, text) [line 27]`
  - `get_or_create_context(self, account_name, context_name) [line 30]`

**Functions**

- `_builder(agent, config_values, context_text)` — line 39
- `test_context_soft_maximum_triggers_warning(caplog)` — line 49
- `_build_prompt_with(agent, config_values, context_text)` — line 65
- `_additional_context_content(messages)` — line 76
- `test_context_truncation_uses_config_when_agent_has_no_override_fields()` — line 85
- `test_context_truncation_defaults_to_2000_when_config_unset_and_agent_has_no_override_fields()` — line 94
- `test_agent_context_soft_max_override_smaller_than_config_still_truncates()` — line 103
- `test_agent_context_soft_max_override_larger_than_config_skips_truncation()` — line 109

## `tests/test_prompt_builder_digest.py`

**Imports**

- `pathlib: Path`
- `src.chat2.facade: Chat2Store`
- `src.chat2.models: ChatEvent`
- `src.chat2.store_primitives: InMemoryStore`
- `src.coala_memory.episodic: Chat2EpisodicMemory`
- `src.prompt_builders.coala_prompt_builder: CoALAPromptBuilder`
- `unittest.mock: Mock`

**Functions**

- `_make_prompt_builder_with_storage(chat2_store: Chat2Store, storage, digests_root: Path, model_limit: int = 1000)` — line 11
- `_digest_path(digests_root: Path, session_id: str, account: str) -> Path` — line 53
- `test_digest_generation_and_persistence(tmp_path)` — line 57
- `test_digest_accumulates_over_multiple_turns(tmp_path)` — line 102
- `test_digest_truncation_for_very_long_overflow(tmp_path)` — line 160

## `tests/test_prompt_builder_images.py`

> Tests for PromptBuilder image/file attachment resolution.

**Imports**

- `__future__: annotations`
- `base64`
- `os`
- `pytest`
- `src.prompt_builders.prompt_builder: PromptBuilder`
- `tempfile`
- `unittest.mock: Mock`

**Classes**

- `TestGuessMimeFromPath` — line 69
  - `test_png(self, pb_with_temp_dir) [line 70]`
  - `test_jpg(self, pb_with_temp_dir) [line 73]`
  - `test_jpeg(self, pb_with_temp_dir) [line 76]`
  - `test_gif(self, pb_with_temp_dir) [line 79]`
  - `test_webp(self, pb_with_temp_dir) [line 82]`
  - `test_unknown_extension(self, pb_with_temp_dir) [line 85]`
  - `test_no_extension(self, pb_with_temp_dir) [line 88]`
- `TestFindImageFile` — line 92
  - `test_finds_matching_file(self, temp_images_root, pb_with_temp_dir) [line 93]`
  - `test_finds_jpg_variant(self, temp_images_root, pb_with_temp_dir) [line 103]`
  - `test_skips_json_sidecar(self, temp_images_root, pb_with_temp_dir) [line 113]`
  - `test_prefers_image_over_json_when_both_exist(self, temp_images_root, pb_with_temp_dir) [line 122]`
  - `test_returns_none_when_nonexistent(self, temp_images_root, pb_with_temp_dir) [line 134]`
- `TestResolveAttachments` — line 139
  - `test_image_ids_resolved_to_base64(self, temp_images_root) [line 140]`
  - `test_missing_image_id_skipped(self, temp_images_root) [line 152]`
  - `test_multiple_image_ids(self, temp_images_root) [line 158]`
- `TestResolveFileAttachments` — line 173
  - `test_file_id_resolved_to_text(self, temp_images_root) [line 174]`
  - `test_binary_file_shows_placeholder(self, temp_images_root) [line 183]`
- `TestResolveMixedAttachments` — line 194
  - `test_image_and_file_together(self, temp_images_root) [line 195]`
  - `test_empty_ids_produces_empty_list(self, temp_images_root) [line 205]`
  - `test_none_ids_produces_empty_list(self, temp_images_root) [line 210]`
  - `test_png_with_uppercase_extension(self, temp_images_root) [line 215]`
- `TestBuildPromptWithAttachments` — line 222
  - `test_attachments_produce_content_parts_array(self, temp_images_root) [line 223]`
  - `test_no_attachments_produces_string_content(self, temp_images_root) [line 238]`
- `TestSupportsImages` — line 249
  - `test_supports_images_false_emits_markers_with_instruction(self, temp_images_root) [line 250]`
  - `test_supports_images_false_emits_instruction_regardless_of_tools(self, temp_images_root) [line 266]`
  - `test_supports_images_false_multiple_images(self, temp_images_root) [line 276]`
  - `test_supports_images_true_still_inlines_base64(self, temp_images_root) [line 288]`
  - `test_supports_images_true_no_instruction(self, temp_images_root) [line 299]`
  - `test_supports_images_false_mixed_attachments(self, temp_images_root) [line 309]`
  - `test_supports_images_false_no_instruction_without_images(self, temp_images_root) [line 321]`
  - `test_supports_images_default_backward_compat(self, temp_images_root) [line 330]`

**Functions**

- `temp_images_root()` — line 16
- `_make_prompt_builder(images_root, allowed_tools = None)` — line 21
- `pb_with_temp_dir(temp_images_root)` — line 45
- `_create_image_file(base_dir: str, account_name: str, img_id: str, filename: str, content: bytes)` — line 49
- `_create_text_file(base_dir: str, account_name: str, file_id: str, filename: str, content: str)` — line 59

## `tests/test_prompt_builder_metrics_endpoints.py`

> Unit tests for /prompt_builder/metrics tool-resolution agreement with the FCP.

**Imports**

- `__future__: annotations`
- `src.handlers.handler_registry: HandlerRegistry`
- `src.http_endpoints.prompt_builder_metrics_endpoints: prompt_builder_metrics_impl`
- `src.message_processors.function_calling_processor: resolve_tool_defs`
- `src.prompt_builders.prompt_builder: PromptBuilder`
- `src.prompt_builders.prompt_builder_interface: PromptBuilderInterface`
- `unittest.mock: Mock`

**Functions**

- `_make_deps(*, allowed_tools, tool_defs)` — line 19
- `_call_metrics(agent_manager, container, context_name = None)` — line 48
- `test_metrics_tool_set_agrees_with_fcp_resolve_tool_defs()` — line 61
- `test_metrics_tool_set_empty_when_allowed_tools_none()` — line 82
- `test_metrics_tool_set_ignores_unknown_allowed_tools()` — line 95
- `test_metrics_tool_set_applies_context_tool_list()` — line 108
- `test_metrics_applies_handler_schema_cap()` — line 131

## `tests/test_prompt_builder_token_history.py`

**Imports**

- `logging`
- `src.chat2.facade: Chat2Store`
- `src.chat2.models: ChatEvent`
- `src.chat2.store_primitives: InMemoryStore`
- `src.coala_memory.episodic: Chat2EpisodicMemory`
- `src.prompt_builders.prompt_builder: PromptBuilder`
- `src.prompt_builders: prompt_builder`
- `unittest.mock: Mock`

**Functions**

- `_make_prompt_builder_with_config(chat2_store, model_limit, max_prompt_conversations = 10)` — line 12
- `_system_token_estimate_for_fake_agent()` — line 42
- `_history_only(messages, current_query)` — line 46
- `test_history_token_allocation_normal_case()` — line 54
- `test_history_token_allocation_giant_message_included()` — line 82
- `test_history_token_allocation_boundary_exact_fit()` — line 102
- `test_max_prompt_conversations_zero_no_history()` — line 130
- `test_max_prompt_conversations_caps_event_count()` — line 161
- `test_max_prompt_conversations_cap_and_budget_combined()` — line 197
- `_make_prompt_builder_with_cap_config(chat2_store, config_values, max_prompt_conversations = 10, agent_budget = None)` — line 251
- `_seed_history_messages(store)` — line 284
- `_budget_fitting_two_history_messages()` — line 293
- `test_history_budget_env_ceiling_wins_over_config_with_fieldless_agent(monkeypatch)` — line 300
- `test_history_budget_config_ceiling_honored_with_fieldless_agent(monkeypatch)` — line 319
- `test_history_budget_defaults_to_module_constant_with_fieldless_agent(caplog, monkeypatch)` — line 341
- `test_history_budget_agent_ceiling_smaller_than_config_caps_history(monkeypatch)` — line 360

## `tests/test_prompt_report_wiring.py`

> Wiring tests for Chat2Recorder.write_prompt_report.

**Imports**

- `__future__: annotations`
- `src.chat2.facade: Chat2Store`
- `src.chat2.store_primitives: InMemoryStore, StoreKey`
- `src.coala_memory.episodic: Chat2EpisodicMemory`
- `src.message_processors.fcp_chat2: Chat2Recorder`
- `src.message_processors.fcp_models: ProcessorContext`
- `uuid`

**Classes**

- `TestWritePromptReportWiring` — line 48
  - `test_write_prompt_report_writes_event(self) -> None [line 51]`
  - `test_write_prompt_report_links_correlation(self) -> None [line 68]`
  - `test_write_prompt_report_no_correlation_no_link(self) -> None [line 88]`
  - `test_write_prompt_report_no_store_noop(self) -> None [line 108]`
  - `test_write_prompt_report_best_effort(self) -> None [line 115]`
- `TestFcpPromptReportWiring` — line 161
  - `test_process_message_emits_prompt_report(self, make_proc, prompt_builder, llm_adapter) -> None [line 164]`
  - `test_process_message_streaming_emits_prompt_report(self, make_proc, prompt_builder, llm_adapter) -> None [line 196]`
  - `test_no_report_when_store_this_call_false(self, make_proc, prompt_builder, llm_adapter) -> None [line 229]`
  - `test_process_message_without_store_noop(self, make_proc, prompt_builder, llm_adapter) -> None [line 252]`
  - `test_one_prompt_report_per_request(self, make_proc, prompt_builder, llm_adapter) -> None [line 276]`

**Functions**

- `_ctx(conversation_id: str, store_this_call: bool = True) -> ProcessorContext` — line 20
- `_breakdown() -> dict` — line 35
- `_pb_breakdown() -> dict` — line 134
- `_expected_report() -> dict` — line 147

## `tests/test_provider_registry.py`

**Imports**

- `galet.provider_registry: ProviderRegistry`
- `pytest`

**Functions**

- `test_explicit_provider_overrides_prefix()` — line 6
- `test_prefix_fallback_works()` — line 14
- `test_ollama_prefix_resolution()` — line 22
- `test_ollama_explicit_provider()` — line 31
- `test_gemini_prefix_resolution()` — line 38
- `test_gemini_explicit_provider()` — line 46
- `test_unknown_model_falls_through_to_openai()` — line 52
- `test_unknown_explicit_provider_raises()` — line 57

## `tests/test_regression_embedding_retrieval.py`

> Regression guards for prompt-builder endpoint interface resolution.

**Imports**

- `__future__: annotations`
- `pytest`
- `src.http_endpoints.prompt_builder_endpoints: build_prompt_impl`
- `src.http_endpoints.prompt_builder_metrics_endpoints: prompt_builder_metrics_impl`
- `src.prompt_builders.prompt_builder: PromptBuilder`
- `src.prompt_builders.prompt_builder_interface: PromptBuilderInterface`
- `unittest.mock: Mock`

**Functions**

- `_agent_manager() -> Mock` — line 20
- `test_prompt_builder_endpoints_resolve_interface_and_fail_loud() -> None` — line 30

## `tests/test_remote_execute_handler.py`

**Imports**

- `json`
- `os`
- `pytest`
- `src.config_manager: ConfigManager`
- `src.handlers.remote_execute_handler: RemoteExecuteHandler`
- `types: SimpleNamespace`

**Classes**

- `FakeResponse` — line 11
  - `__init__(self, text: str, status_code: int = 200) [line 12]`
  - `raise_for_status(self) [line 16]`

**Functions**

- `temp_config(tmp_path)` — line 22
- `test_happy_path_sse(monkeypatch, temp_config)` — line 47
- `test_unknown_machine_lists_available(temp_config)` — line 76
- `test_session_id_reused_from_config(monkeypatch, temp_config)` — line 87
- `test_disabled_machine_is_not_available(tmp_path)` — line 106
- `test_invalid_machine_catalog_fails_closed(tmp_path)` — line 134

## `tests/test_reset_session_handler.py`

**Imports**

- `src.handlers.reset_session_handler: ResetSessionHandler`
- `unittest.mock: Mock`

**Functions**

- `test_reset_session_uses_episodic_store()` — line 6
- `test_reset_session_requires_episodic_store()` — line 21

## `tests/test_run_metrics.py`

> RunMetrics round-trip, hit_iteration_cap flag, and FCPResult tests (design tests 1-4, 9-10).

**Imports**

- `pytest`
- `src.message_processors.function_calling_processor: FCPResult`
- `src.message_processors.run_metrics: RunMetrics`

**Functions**

- `test_run_metrics_round_trip()` — line 9
- `test_run_metrics_total_tokens_derived_when_absent()` — line 42
- `test_run_metrics_from_dict_defaults_envelope_fields()` — line 48
- `test_run_metrics_defaults()` — line 59
- `test_run_metrics_strict_validation_rejects_unknown_field()` — line 83
- `test_run_metrics_from_dict_requires_dict()` — line 88
- `test_hit_iteration_cap_flag(make_proc, prompt_builder, llm_adapter)` — line 93
- `test_streaming_initializes_hit_iteration_cap_false(make_proc, prompt_builder, llm_adapter)` — line 146
- `test_fcp_result_returns_metrics(make_proc, prompt_builder, llm_adapter)` — line 173
- `test_fcp_result_tool_selection_error(make_proc)` — line 235
- `test_fcp_result_early_returns(make_proc)` — line 262
- `_parse_sse(events)` — line 304
- `test_streaming_emits_metrics_event(make_proc, prompt_builder, llm_adapter)` — line 309
- `test_streaming_error_paths_emit_metrics(make_proc, prompt_builder, llm_adapter)` — line 388
- `test_loop_accumulates_token_usage(make_proc, prompt_builder, llm_adapter)` — line 480
- `test_usage_none_leaves_tokens_zero(make_proc, prompt_builder, llm_adapter)` — line 516

## `tests/test_run_metrics_logger.py`

> RunMetricsLogger tests: append creates/extends the log, no partial line on

**Imports**

- `json`
- `pytest`
- `src.message_processors.run_metrics: RunMetrics`
- `src.metrics: RunMetricsLogger`

**Functions**

- `test_append_creates_log(tmp_path)` — line 12
- `test_append_extends_log(tmp_path)` — line 35
- `test_append_no_partial_line_on_failure(tmp_path, monkeypatch)` — line 50
- `test_append_missing_field_tolerance(tmp_path)` — line 69

## `tests/test_scrape_web_page_handler2.py`

> Tests for ScrapeWebPageHandler2.

**Imports**

- `__future__: annotations`
- `pytest`
- `src.handlers.scrape_web_page_handler2: ScrapeWebPageHandler2`
- `unittest.mock: patch, MagicMock`

**Classes**

- `TestInputValidation` — line 17
  - `test_missing_page_url_returns_error(self, handler) [line 18]`
  - `test_empty_page_url_returns_error(self, handler) [line 23]`
- `TestSuccessfulScrape` — line 29
  - `test_valid_url_scrape(self, handler) [line 30]`
  - `test_execute_script_failure(self, handler) [line 39]`
- `TestToolDefinition` — line 47
  - `test_tool_def_has_required_fields(self, handler) [line 48]`
  - `test_result_schema_has_required_fields(self, handler) [line 55]`

**Functions**

- `handler()` — line 12

## `tests/test_semantic_memory_handler.py`

**Imports**

- `src.coala_memory.semantic: SemanticDocument, SemanticMemoryResult`
- `src.embeddings.facade: EmbeddingFacade`
- `src.handlers.semantic_memory_handler: SemanticMemoryHandler`

**Classes**

- `DummyConfig` — line 9
  - `get(self, key, default = None) [line 10]`
- `FakeSemanticMemory` — line 14
  - `__init__(self) [line 15]`
  - `recall(self, request) [line 18]`
- `FakeMemoryWithFacade` — line 153
  - `__init__(self, facade) [line 154]`
  - `recall(self, request) [line 157]`
- `FakeEmbeddingStoreWithNamespaces` — line 188
  - `__init__(self, namespaces) [line 189]`
  - `list_embedding_namespaces(self, account_name) [line 193]`
- `FakeMemoryWithStore` — line 198
  - `__init__(self, store) [line 199]`
  - `recall(self, request) [line 202]`

**Functions**

- `_args(**overrides)` — line 36
- `test_semantic_memory_handler_exposes_handler_v2_tool_contract()` — line 52
- `test_semantic_memory_handler_uses_caller_account_and_returns_documents()` — line 87
- `test_semantic_memory_handler_explicit_account_overrides_caller_account()` — line 106
- `test_semantic_memory_handler_reports_recall_errors()` — line 116
- `test_constructor_injected_path_builds_no_router_or_store()` — line 128
- `test_unknown_action_error_lists_allowed_actions()` — line 139
- `test_models_action_returns_registry_models_via_facade()` — line 161
- `test_models_action_reports_error_when_no_capability()` — line 179
- `test_namespaces_action_lists_namespaces_via_embedding_store()` — line 206
- `test_namespaces_action_explicit_account_overrides_caller()` — line 221
- `test_namespaces_action_prefers_memory_list_namespaces()` — line 234
- `test_namespaces_action_requires_account()` — line 253
- `test_namespaces_action_reports_error_when_no_capability()` — line 263

## `tests/test_semantic_memory_handler_utils.py`

**Imports**

- `src.handlers.semantic_memory_handler: SemanticMemoryHandler`

**Classes**

- `DummyConfig` — line 4
  - `get(self, key, default = None) [line 5]`
- `FakeEmbeddingStoreNamespaces` — line 9
  - `__init__(self, namespaces) [line 10]`
  - `list_embedding_namespaces(self, account_name) [line 14]`
- `FakeUtilsMemory` — line 19
  - `__init__(self) [line 20]`
  - `embed(self, items, model = None) [line 24]`
  - `compare(self, a, b, model = None) [line 28]`
  - `rank(self, items, model = None) [line 32]`
  - `models(self) [line 36]`

**Functions**

- `_args(**overrides)` — line 41
- `test_embed_action_against_injected_facade_expect_success()` — line 57
- `test_compare_action_against_injected_facade_expect_success()` — line 66
- `test_rank_action_against_injected_facade_expect_success()` — line 75
- `test_models_action_against_injected_facade_expect_success()` — line 84
- `test_namespaces_action_against_injected_memory_store()` — line 96

## `tests/test_serve_image_handler.py`

> Tests for ServeImageHandler.

**Imports**

- `PIL: Image`
- `__future__: annotations`
- `base64`
- `os`
- `pytest`
- `unittest.mock: MagicMock`

**Classes**

- `TestInputValidation` — line 60
  - `test_missing_path_returns_error(self, handler) [line 61]`
  - `test_missing_external_root_returns_error(self, handler) [line 66]`
  - `test_invalid_location_returns_error(self, handler) [line 75]`
  - `test_path_traversal_rejected(self, handler) [line 84]`
  - `test_absolute_path_rejected(self, handler) [line 93]`
  - `test_file_not_found(self, handler) [line 102]`
- `TestSuccessfulServe` — line 112
  - `test_serve_from_storage(self, handler, test_image) [line 113]`
  - `test_serve_from_external(self, handler, external_image) [line 123]`
  - `test_max_dimension_capped(self, handler, test_image) [line 132]`
  - `test_result_is_valid_base64(self, handler, test_image) [line 142]`
  - `test_unsupported_mime_type(self, handler, config_with_storage) [line 152]`
- `TestToolDefinition` — line 172
  - `test_tool_def_has_required_fields(self, handler) [line 173]`

**Functions**

- `config_with_storage(tmp_path)` — line 14
- `handler(config_with_storage)` — line 29
- `test_image(tmp_path, config_with_storage)` — line 35
- `external_image(tmp_path, config_with_storage)` — line 49

## `tests/test_session_resolution.py`

> Tests for resolve_or_create_session (Phase 1 /ask -> chat2 migration).

**Imports**

- `pytest`
- `re`
- `src.chat2.facade: Chat2Store`
- `src.chat2.store_primitives: InMemoryStore`
- `src.coala_memory.episodic: Chat2EpisodicMemory, EpisodicMemoryManager, EpisodicSessionQuery`
- `src.message_endpoints.ask_request_handler: resolve_or_create_session`
- `time`
- `unittest.mock: Mock`

**Classes**

- `TestResolveOrCreateSession` — line 46
  - `test_reuses_existing_session_by_friendly_name(self, chat2) -> None [line 47]`
  - `test_match_is_case_insensitive(self, chat2) -> None [line 52]`
  - `test_match_ignores_leading_trailing_whitespace(self, chat2) -> None [line 57]`
  - `test_creates_new_session_when_no_match(self, chat2) -> None [line 62]`
  - `test_creates_session_with_default_name_when_no_friendly_name(self, chat2) -> None [line 72]`
  - `test_creates_session_with_default_name_for_empty_friendly_name(self, chat2) -> None [line 79]`
  - `test_filters_by_account_and_agent(self, chat2) -> None [line 85]`
  - `test_returns_most_recent_match(self, chat2) -> None [line 92]`
  - `test_passes_explicit_limit_to_list_sessions(self, chat2, monkeypatch) -> None [line 99]`
  - `test_custom_limit_is_respected(self, chat2, monkeypatch) -> None [line 110]`
  - `test_returns_uuid_when_chat2_store_is_none(self) -> None [line 120]`
  - `test_no_match_when_stored_friendly_name_is_none(self, chat2) -> None [line 124]`
  - `test_new_session_persists_context_name(self, chat2) -> None [line 131]`
  - `test_existing_session_backfills_missing_context_name(self, chat2) -> None [line 143]`
  - `test_existing_context_name_is_not_overwritten(self, chat2) -> None [line 158]`

**Functions**

- `chat2() -> EpisodicMemoryManager` — line 26
- `_seed(chat2: EpisodicMemoryManager, session_id: str, account_name: str, agent_name: str, friendly_name: str) -> None` — line 30

## `tests/test_sse_events.py`

> SSEEvent metrics event type validation (design test 11).

**Imports**

- `pytest`
- `src.message_processors.sse_events: SSEEvent`

**Functions**

- `test_sse_metrics_event_type_validates()` — line 8
- `test_sse_metrics_defaults_to_none()` — line 15
- `test_sse_metrics_event_serializes_payload()` — line 20
- `test_sse_existing_event_types_unaffected()` — line 26
- `test_sse_unknown_type_rejected()` — line 40

## `tests/test_storage_contexts.py`

**Imports**

- `datetime: datetime, timezone`
- `pathlib: Path`
- `pytest`
- `src.storage.models: Context`
- `src.storage_paths.storage_paths: StoragePaths`
- `yaml`

**Classes**

- `TestContexts` — line 21
  - `test_save_and_load_context(self, storage) [line 24]`
  - `test_update_context(self, storage) [line 45]`
  - `test_get_nonexistent_context(self, storage) [line 64]`
  - `test_list_context_names_sorted(self, storage) [line 68]`
  - `test_list_context_names_missing_account_returns_empty(self, storage) [line 81]`
- `TestContextRoundTrip` — line 86
  - `skill_storage(self, tmp_path: Path) [line 88]`
  - `test_roundtrip_persisted_fields(self, skill_storage) [line 96]`
  - `test_legacy_allowed_tools_preserved_in_extra(self, skill_storage) [line 125]`
  - `test_no_frontmatter_body_only(self, skill_storage) [line 151]`
- `TestSkillLoading` — line 166
  - `skill_storage(self, tmp_path: Path) [line 168]`
  - `_write_skill(self, storage, account_name: str, skill_name: str, content: str) [line 176]`
  - `test_get_skill_text_returns_body(self, skill_storage) [line 182]`
  - `test_get_skill_text_strips_frontmatter(self, skill_storage) [line 187]`
  - `test_get_skill_text_missing_returns_none(self, skill_storage) [line 192]`
  - `test_get_skill_text_missing_account_returns_none(self, skill_storage) [line 195]`
  - `test_get_skill_text_no_frontmatter_returns_whole(self, skill_storage) [line 198]`
  - `test_get_skill_parses_mandatory_tools_and_extra(self, skill_storage) [line 203]`
- `TestContextImportResolution` — line 222
  - `skill_storage(self, tmp_path: Path) [line 224]`
  - `_write_skill(self, storage, account_name: str, skill_name: str, body: str, *, mandatory_tools = None, extra_frontmatter = None) [line 232]`
  - `_save_context(self, storage, ctx: Context) [line 257]`
  - `test_resolves_imports_in_order(self, skill_storage) [line 260]`
  - `test_required_tools_order_preserving_dedupe(self, skill_storage) [line 283]`
  - `test_missing_imports_recorded_and_not_fatal(self, skill_storage) [line 301]`
  - `test_resolved_text_strips_skill_frontmatter(self, skill_storage) [line 321]`
  - `test_top_level_imports_only_no_recursion(self, skill_storage) [line 348]`
  - `test_derived_fields_never_persisted(self, skill_storage) [line 373]`
  - `test_no_imports_backward_compatible(self, skill_storage) [line 397]`
  - `test_skill_without_mandatory_tools_contributes_nothing(self, skill_storage) [line 415]`
  - `test_non_string_import_entries_skipped(self, skill_storage) [line 432]`
- `TestPromptBuilderContextRendering` — line 450
  - `skill_storage(self, tmp_path: Path) [line 452]`
  - `_write_skill(self, storage, account_name: str, skill_name: str, content: str) [line 460]`
  - `_build_context_content(self, skill_storage, context_name: str) -> str [line 466]`
  - `test_context_with_imports_processed_but_directives_excluded(self, skill_storage) [line 487]`
  - `test_context_without_imports_works_normally(self, skill_storage) [line 515]`
  - `test_context_with_missing_skill_import_continues(self, skill_storage) [line 530]`
- `_FakeAgent` — line 550
- `_FakeAgentManager` — line 558
  - `get_agent(self, name: str) [line 559]`
- `_FakeConfig` — line 563
  - `get(self, key, default = None) [line 564]`

**Functions**

- `_now() -> datetime` — line 17

## `tests/test_storage_embeddings.py`

## `tests/test_storage_interfaces.py`

**Imports**

- `datetime: datetime, timezone`
- `inspect`
- `pytest`
- `src.storage.interfaces: ContextStore, DocumentStore, EmbeddingStore, HealthCheckable, TasklistStore`
- `src.storage.models: Context, DocumentRef, EmbeddingRecord, Skill`
- `src.storage: JsonFileStorage, Storage`
- `src.storage_paths.storage_paths: StoragePaths`
- `src.tasklists.task_list: TaskList`

**Classes**

- `InterfacesTestCase` — line 76
  - `test_storage_is_context_store_and_health_checkable(self) [line 77]`
  - `test_storage_aggregate_is_abstract_json_file_storage_concrete(self) [line 89]`
  - `test_json_file_storage_implements_every_context_store_method(self, json_storage) [line 93]`
  - `test_json_file_storage_implements_every_tasklist_store_method(self, json_storage) [line 119]`
  - `test_json_file_storage_implements_every_document_store_method(self, json_storage) [line 137]`
  - `test_json_file_storage_implements_every_embedding_store_method(self, json_storage) [line 165]`
  - `test_methods_callable_with_documented_signatures(self, json_storage) [line 222]`
  - `test_get_skill_returns_skill_and_text(self, json_storage) [line 245]`
  - `test_narrow_interface_subset_holds(self) [line 258]`
- `TestInterfaces(InterfacesTestCase)` — line 306

**Functions**

- `storage_paths(tmp_path) -> StoragePaths` — line 65
- `json_storage(storage_paths) -> JsonFileStorage` — line 72

## `tests/test_storage_paths.py`

**Imports**

- `pathlib: Path`
- `pytest`
- `src.storage_paths.storage_paths: StoragePaths`

**Functions**

- `test_properties_and_resolve_relative_normal(tmp_path)` — line 7
- `test_constructor_rejects_namespaces_that_escape_root(tmp_path, namespace)` — line 45
- `test_resolve_relative_rejects_absolute_and_parent_paths(tmp_path)` — line 54
- `test_resolve_relative_rejects_symlink_escape(tmp_path)` — line 68

## `tests/test_strict_agent_fields.py`

> Tests for strict_agent_fields toggle in Agent.from_dict() and AgentManager.

**Imports**

- `json`
- `logging`
- `pytest`
- `src.agent.agent: Agent`
- `src.agent.agent_manager: AgentManager`

**Classes**

- `TestAgentFromDictStrict` — line 16
  - `test_unknown_field_raises_when_strict_true(self) [line 19]`
  - `test_unknown_field_warns_when_strict_false(self, caplog) [line 28]`
  - `test_strict_false_removes_unknown_keys(self) [line 46]`
  - `test_strict_false_still_validates_name(self) [line 55]`
  - `test_strict_false_combined_with_legacy_keys(self) [line 63]`
  - `test_four_cap_keys_are_known_fields_when_strict(self) [line 75]`
  - `test_strict_still_rejects_unknown_keys_alongside_cap_keys(self) [line 92]`
- `TestAgentManagerStrictFields` — line 101
  - `test_manager_defaults_to_strict(self, tmp_path) [line 104]`
  - `test_manager_lenient_mode(self, tmp_path, caplog) [line 117]`
  - `test_reload_with_changed_strict(self, tmp_path) [line 136]`
  - `test_reload_respects_instance_strict_when_no_override(self, tmp_path) [line 152]`

## `tests/test_task_agent_resolution.py`

> Tests for per-task agent and context resolution (GH issues #121, #137).

**Imports**

- `pytest`
- `src.agent.agent: Agent`
- `src.message_processors.automation_processor: AutomationProcessor`
- `src.message_processors.function_calling_processor: FCPResult`
- `src.message_processors.run_metrics: RunMetrics`
- `src.tasklists.task: Task`
- `src.tasklists.task_list: TaskList`
- `src.tasklists.task_states: TASK_STATE_COMPLETED`
- `uuid`

**Classes**

- `FakeAgentManager` — line 28
  - `__init__(self, agents) [line 29]`
  - `get_agent(self, name) [line 32]`
- `CaptureFunctionProcessor` — line 36
  - `__init__(self) [line 37]`
  - `process_message(self, **kwargs) [line 40]`
- `FakeProcessorFactory` — line 51
  - `__init__(self, function_processor) [line 52]`
  - `get(self, name) [line 55]`
- `FakeStorage` — line 61
  - `__init__(self, tasklist) [line 62]`
  - `get_tasklist(self, account_name, tasklist_id) [line 65]`
  - `list_tasklists(self, account_name) [line 68]`
  - `save_tasklist(self, account_name, tasklist_id, data) [line 71]`
  - `append_task_execution_record(self, account_name, tasklist_key, record) [line 74]`

**Functions**

- `make_processor(agent_manager = None, function_processor = None)` — line 78
- `make_tasklist(task_agent = None, task_context = None)` — line 91
- `callers()` — line 102
- `test_resolve_agent_unset_no_partner_uses_caller()` — line 106
- `test_resolve_agent_same_as_caller_uses_primary()` — line 113
- `test_resolve_agent_finds_worker()` — line 120
- `test_resolve_agent_unknown_raises()` — line 128
- `test_resolve_agent_without_manager_task_agent_raises()` — line 135
- `test_resolve_agent_unset_uses_secondary_partner()` — line 142
- `test_resolve_agent_unset_uses_caller_partner_agent()` — line 150
- `_run_and_capture(agent_manager = None, task_agent = None, caller_name = 'lucy', caller_agent = None, worker_agent = None, context_name = '', secondary_agent = None, task_context = None, task_agent_default_ctx = None)` — line 159
- `test_execute_passes_task_agent_as_primary()` — line 213
- `test_execute_unset_task_agent_uses_secondary_partner()` — line 222
- `test_execute_unset_task_agent_uses_caller_partner()` — line 231
- `test_execute_unset_task_agent_no_partner_uses_caller()` — line 240
- `test_execute_unknown_task_agent_raises()` — line 249
- `test_execute_worker_agent_override_wins_over_task_agent()` — line 258
- `test_execute_unknown_worker_agent_raises()` — line 268
- `test_execute_run_context_override_wins_over_task_context_and_agent_default()` — line 278
- `test_execute_task_context_beats_agent_default_context()` — line 290
- `test_execute_agent_default_context_used_when_task_context_unset()` — line 301
- `test_execute_no_context_resolves_to_empty()` — line 311

## `tests/test_task_list.py`

**Imports**

- `pytest`
- `src.tasklists.task: Task`
- `src.tasklists.task_list: TaskList`

**Functions**

- `_make_list()` — line 7
- `_make_task(task_id, name = 'Task')` — line 11
- `test_add_task_appends_new_ids()` — line 15
- `test_add_task_duplicate_id_raises_value_error()` — line 22
- `test_add_task_duplicate_id_after_removal_allowed()` — line 31
- `test_add_task_after_index_inserts_after_position()` — line 40
- `test_add_task_after_index_out_of_range_appends()` — line 49
- `test_add_task_after_index_negative_raises()` — line 57
- `test_add_task_after_index_rejects_duplicate()` — line 65
- `test_update_task_applies_whitelisted_fields()` — line 73
- `test_update_task_partial_update_leaves_other_fields()` — line 98
- `test_update_task_sets_context()` — line 110
- `test_update_task_clears_context_with_none()` — line 117
- `test_update_task_accepts_context_field()` — line 125
- `test_update_task_merges_meta()` — line 135
- `test_update_task_rejects_result_field()` — line 142
- `test_update_task_rejects_unknown_fields()` — line 150
- `test_update_task_missing_task_raises()` — line 161
- `test_remove_task_removes_only_target()` — line 169
- `test_remove_task_missing_raises()` — line 177
- `test_update_task_state_updates_state()` — line 185
- `test_update_task_state_missing_raises()` — line 192
- `test_set_task_result_replaces_result()` — line 198
- `test_set_task_result_missing_raises()` — line 210
- `test_from_dict_accepts_unique_task_ids()` — line 216
- `test_from_dict_rejects_duplicate_task_ids()` — line 224
- `test_task_constructor_accepts_context()` — line 234
- `test_task_to_dict_omits_context_when_unset()` — line 239
- `test_task_to_dict_emits_context_when_set()` — line 244
- `test_task_round_trip_preserves_context()` — line 249
- `test_task_from_dict_tolerates_missing_context()` — line 256
- `test_tasklist_round_trip_preserves_task_context()` — line 261
- `test_tasklist_from_dict_tolerates_legacy_task_without_context()` — line 270

## `tests/test_tasklist_boundary.py`

**Imports**

- `json`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage_paths.storage_paths: StoragePaths`
- `src.tasklists.service: TaskListService`
- `src.tasklists.task_states: TASK_LIST_STATE_COMPLETED, TASK_LIST_STATE_CREATED, TASK_STATE_COMPLETED, TASK_STATE_PENDING`

**Functions**

- `_make_storage(tmp_path)` — line 14
- `_write_raw_tasklist(storage, account_name, tasklist_key, tasks)` — line 18
- `test_reset_of_legacy_inline_fields_adopts_into_runs_and_leaves_lean_file(tmp_path)` — line 33

## `tests/test_tasklist_http_endpoints.py`

**Imports**

- `src.http_endpoints.agents_endpoints: put_tasklist_impl`
- `src.http_endpoints.tasklist_endpoints: put_tasklist_impl`
- `src.tasklists.task_list: TaskList`

**Functions**

- `_payload()` — line 6
- `test_tasklist_endpoints_put_converts_dict_to_tasklist_at_edge(fake_tasklist_store)` — line 16
- `test_agents_endpoints_put_converts_dict_to_tasklist_at_edge(fake_tasklist_store)` — line 26

## `tests/test_tasklist_runs.py`

**Imports**

- `json`
- `pytest`
- `src.storage.json_file_storage_parts.tasklist_runs: TaskExecutionReader, TaskExecutionRecorder`

**Functions**

- `_record(**overrides)` — line 11
- `test_append_twice_writes_two_valid_json_lines(tmp_path)` — line 24
- `test_append_rejects_record_missing_record_id_or_task_id(tmp_path)` — line 42
- `test_append_propagates_oserror_and_creates_no_parent(tmp_path)` — line 59
- `test_latest_returns_last_record_for_matching_task_id(tmp_path)` — line 69
- `test_read_all_skips_malformed_middle_line(tmp_path)` — line 88
- `test_read_all_skips_partial_tail_line_after_crash(tmp_path)` — line 101
- `test_read_all_and_latest_handle_empty_and_missing_files(tmp_path)` — line 114

## `tests/test_tasklists.py`

**Imports**

- `dataclasses: fields`
- `json`
- `src.tasklists.service: TaskListService`
- `src.tasklists.task: Task`
- `src.tasklists.task_list: TaskList`
- `src.tasklists.task_states: TASK_LIST_STATE_COMPLETED, TASK_LIST_STATE_CREATED, TASK_STATE_COMPLETED, TASK_STATE_PENDING`
- `uuid`

**Functions**

- `test_task_unknown_key_rejection()` — line 16
- `test_task_missing_required_fields()` — line 25
- `test_migration_v1_title_and_int_id_converted()` — line 34
- `test_migration_v1_unknown_fields_moved_to_meta_when_allowed()` — line 49
- `test_round_trip_dump_load()` — line 64
- `test_task_creation_with_new_fields()` — line 99
- `test_task_defaults_for_new_fields()` — line 108
- `test_task_to_dict_omits_none_and_empty_fields()` — line 115
- `test_task_from_dict_with_missing_new_fields()` — line 129
- `test_task_from_dict_with_all_new_fields_present()` — line 137
- `test_task_full_round_trip_dict_task()` — line 152
- `test_tasklist_get_children_basic_filter()` — line 164
- `test_tasklist_service_reset_clears_execution_state(fake_tasklist_store)` — line 175
- `test_tasklist_get_children_no_matches_returns_empty()` — line 213
- `test_task_run_metrics_persist()` — line 220
- `test_task_reset_leaves_result_and_run_metrics_for_adoption(fake_tasklist_store)` — line 258
- `test_tasklist_round_trip_omits_run_metrics_and_result()` — line 285

## `tests/test_tasklists_domain_bridge.py`

**Imports**

- `json`
- `pytest`
- `src.tasklists.task: Task`
- `src.tasklists.task_list: TaskList`

**Functions**

- `test_round_trip_to_dict_and_from_dict()` — line 7
- `test_from_dict_requires_id_unless_provided()` — line 37
- `test_from_dict_rejects_unknown_schema_version()` — line 50
- `test_to_dict_always_includes_id()` — line 56
- `test_meta_roundtrip_in_model()` — line 63

## `tests/test_tasklists_manage_handler.py`

**Imports**

- `json`
- `src.handlers.tasklists_manage_handler: TasklistsManageHandler`
- `src.tasklists.task_states: TASK_LIST_STATE_CREATED, TASK_LIST_STATE_COMPLETED, TASK_LIST_STATE_RUNNING, TASK_STATE_PENDING, TASK_STATE_COMPLETED`
- `unittest.mock: patch`

**Classes**

- `SimpleConfig` — line 14
  - `__init__(self, storage_root_path, storage_namespace) [line 15]`
  - `get(self, k, default = None) [line 21]`

**Functions**

- `_create_tl(h, account, name, tasks = None)` — line 30
- `_create_completed_tasklist(h, account, name)` — line 56
- `test_list_empty(tmp_path)` — line 104
- `test_get_missing_and_delete_missing(tmp_path)` — line 112
- `test_read_actions_route_through_tasklist_service(tmp_path)` — line 125
- `test_write_actions_route_through_tasklist_service(tmp_path)` — line 187
- `test_put_validate_only_does_not_persist(tmp_path)` — line 317
- `test_put_persists_and_get(tmp_path)` — line 337
- `test_general_instructions_roundtrip(tmp_path)` — line 370
- `test_invalid_id_rejected(tmp_path)` — line 393
- `test_reset_missing(tmp_path)` — line 417
- `test_reset_clears_states(tmp_path)` — line 426
- `test_reset_validate_only(tmp_path)` — line 446
- `test_reset_persists_to_same_on_disk_file(tmp_path)` — line 467
- `test_reset_persists_only_for_given_account(tmp_path)` — line 497
- `test_reset_legacy_inline_result_adopts_to_runs(tmp_path)` — line 515
- `test_add_task_append(tmp_path)` — line 569
- `test_add_task_at_index(tmp_path)` — line 591
- `test_update_task(tmp_path)` — line 618
- `test_update_task_not_found(tmp_path)` — line 644
- `test_remove_task(tmp_path)` — line 665
- `test_remove_task_not_found(tmp_path)` — line 688
- `test_set_state(tmp_path)` — line 713
- `test_set_state_validate_only(tmp_path)` — line 732
- `test_update_meta(tmp_path)` — line 755
- `test_set_general_instructions(tmp_path)` — line 775
- `test_set_name(tmp_path)` — line 794
- `test_set_description(tmp_path)` — line 813
- `test_add_task_validate_only(tmp_path)` — line 837
- `test_put_convenience_goal_only(tmp_path)` — line 871
- `test_put_convenience_goal_with_files(tmp_path)` — line 896
- `test_put_convenience_with_worker_agent(tmp_path)` — line 919
- `test_put_explicit_empty(tmp_path)` — line 938
- `test_put_explicit_with_general_instructions(tmp_path)` — line 960
- `test_put_rejects_neither(tmp_path)` — line 980
- `test_add_task_with_meta(tmp_path)` — line 998
- `test_update_task_partial(tmp_path)` — line 1021
- `test_update_task_with_result_and_error(tmp_path)` — line 1047
- `test_update_task_ignores_inline_task_result(tmp_path)` — line 1072
- `test_add_task_duplicate_id_rejected(tmp_path)` — line 1098
- `test_add_task_duplicate_id_rejected_with_after_index(tmp_path)` — line 1131
- `test_get_result_completed_record_latest_wins(tmp_path)` — line 1161
- `test_get_result_failure_record(tmp_path)` — line 1216
- `test_get_result_legacy_inline_fallback(tmp_path)` — line 1254
- `test_get_result_no_result_message(tmp_path)` — line 1282
- `test_get_result_missing_params(tmp_path)` — line 1308
- `test_tool_def_includes_task_context_property(tmp_path)` — line 1326
- `test_add_task_with_task_context(tmp_path)` — line 1333
- `test_update_task_with_task_context(tmp_path)` — line 1355
- `test_update_task_task_context_none_clears(tmp_path)` — line 1377

## `tests/test_tasklists_run_handler.py`

> Tests for TasklistsRunHandler.

**Imports**

- `__future__: annotations`
- `pytest`
- `src.handlers.tasklists_run_handler: TasklistsRunHandler`
- `typing: Any, Dict, Optional`
- `unittest.mock: Mock`

**Classes**

- `SimpleConfig` — line 13
  - `__init__(self) [line 14]`
  - `get(self, k, default = None) [line 17]`
- `FakeAutomationProcessor` — line 21
  - `__init__(self, result: str = 'ok', exc: Optional[Exception] = None) [line 24]`
  - `execute_tasklist(self, **kwargs) -> str [line 29]`
- `FakeProcessorFactory` — line 36
  - `__init__(self, ap: Optional[FakeAutomationProcessor] = None) [line 39]`
  - `get(self, name: str) [line 42]`
- `TestTasklistsRunHandler` — line 67
  - `test_tool_def_structure(self) [line 68]`
  - `test_result_schema_structure(self) [line 78]`
  - `test_missing_tasklist_id_returns_error(self) [line 85]`
  - `test_invalid_mode_returns_error(self) [line 98]`
  - `test_missing_primary_agent_returns_error(self) [line 111]`
  - `test_missing_account_returns_error(self) [line 125]`
  - `test_missing_automation_processor_falls_back_to_processor_factory(self) [line 139]`
  - `test_missing_automation_processor_and_no_factory_returns_error(self) [line 164]`
  - `test_successful_single_step_execution(self) [line 177]`
  - `test_successful_multi_step_execution(self) [line 201]`
  - `test_execution_exception_returns_error(self) [line 220]`
  - `test_default_mode_is_single_step(self) [line 235]`
  - `test_agent_name_extracted_from_primary_agent(self) [line 250]`
  - `test_worker_agent_passed_through_to_execute_tasklist(self) [line 267]`
  - `test_worker_agent_defaults_to_none_when_not_provided(self) [line 284]`
  - `test_worker_agent_empty_string_becomes_none(self) [line 301]`
  - `test_worker_agent_whitespace_only_becomes_none(self) [line 317]`
  - `test_worker_agent_in_tool_def(self) [line 333]`
  - `test_worker_agent_in_result_schema(self) [line 341]`
  - `test_missing_secondary_agent_default_context_passes_empty_context_name(self) [line 346]`
  - `test_present_secondary_agent_default_context_not_used_as_context_name(self) [line 361]`
  - `test_secondary_agent_and_worker_agent_forwarded_unchanged(self) [line 379]`

**Functions**

- `make_context(*, automation_processor = None, **overrides) -> Dict[str, Any]` — line 48

## `tests/test_tasklists_service.py`

**Imports**

- `inspect`
- `pytest`
- `src.tasklists.interfaces: TasklistManager`
- `src.tasklists.service: TaskListService`
- `src.tasklists.task: Task`
- `src.tasklists.task_list: TaskList`
- `src.tasklists.task_states: TASK_LIST_STATE_COMPLETED, TASK_LIST_STATE_CREATED, TASK_LIST_STATE_RUNNING, TASK_STATE_COMPLETED, TASK_STATE_PENDING`

**Functions**

- `_make_tl(key, name = 'n', description = 'd')` — line 18
- `_seed(store, account = 'alice', key = 'tl1', meta = None)` — line 22
- `_reload(store, account = 'alice', key = 'tl1')` — line 37
- `test_tasklist_manager_abc_declares_crud_and_task_ops_surface()` — line 41
- `test_service_conforms_to_tasklist_manager_interface(fake_tasklist_store)` — line 52
- `test_list_delegates_to_store_with_sorted_keys(fake_tasklist_store)` — line 57
- `test_get_returns_tasklist_object(fake_tasklist_store)` — line 67
- `test_get_missing_returns_none(fake_tasklist_store)` — line 77
- `test_get_scoped_per_account(fake_tasklist_store)` — line 82
- `test_get_returns_reloaded_copy_not_shared_reference(fake_tasklist_store)` — line 88
- `test_get_task_result_passthrough_to_store(fake_tasklist_store)` — line 97
- `test_save_persists_through_store(fake_tasklist_store)` — line 113
- `test_delete_removes_and_is_idempotent(fake_tasklist_store)` — line 122
- `test_delete_scoped_per_account(fake_tasklist_store)` — line 131
- `test_create_builds_tasklist_with_id_equal_to_key(fake_tasklist_store)` — line 140
- `test_create_accepts_meta_and_general_instructions(fake_tasklist_store)` — line 153
- `test_create_does_not_persist_until_save(fake_tasklist_store)` — line 160
- `test_create_then_save_round_trips(fake_tasklist_store)` — line 166
- `test_create_from_goal_no_files_builds_execute_goal_task(fake_tasklist_store)` — line 177
- `test_create_from_goal_with_files_builds_one_task_per_file(fake_tasklist_store)` — line 194
- `test_create_from_goal_underscore_key_name_derivation(fake_tasklist_store)` — line 203
- `test_create_from_goal_empty_files_list_falls_back_to_execute_goal(fake_tasklist_store)` — line 209
- `test_add_task_appends_and_persists(fake_tasklist_store)` — line 216
- `test_add_task_after_index_inserts_and_persists(fake_tasklist_store)` — line 226
- `test_add_task_duplicate_id_raises_and_does_not_persist(fake_tasklist_store)` — line 234
- `test_add_task_with_task_context_sets_and_persists_context(fake_tasklist_store)` — line 243
- `test_add_task_without_task_context_leaves_context_none(fake_tasklist_store)` — line 253
- `test_update_task_merges_whitelisted_fields_and_persists(fake_tasklist_store)` — line 260
- `test_update_task_partial_change_leaves_other_fields(fake_tasklist_store)` — line 300
- `test_update_task_context_persists(fake_tasklist_store)` — line 310
- `test_update_task_context_none_clears_persisted_context(fake_tasklist_store)` — line 318
- `test_update_task_rejects_result_field_and_does_not_persist(fake_tasklist_store)` — line 328
- `test_update_task_rejects_unknown_field_and_does_not_persist(fake_tasklist_store)` — line 336
- `test_update_task_missing_task_raises_and_does_not_persist(fake_tasklist_store)` — line 344
- `test_remove_task_removes_and_persists(fake_tasklist_store)` — line 352
- `test_remove_task_missing_task_raises_and_does_not_persist(fake_tasklist_store)` — line 361
- `test_set_state_persists(fake_tasklist_store)` — line 369
- `test_set_name_persists(fake_tasklist_store)` — line 377
- `test_set_description_persists(fake_tasklist_store)` — line 384
- `test_set_general_instructions_persists_and_can_clear(fake_tasklist_store)` — line 391
- `test_update_meta_merges_and_persists(fake_tasklist_store)` — line 400
- `test_update_meta_overwrites_existing_key(fake_tasklist_store)` — line 408
- `test_update_meta_non_dict_raises_and_does_not_persist(fake_tasklist_store)` — line 414
- `test_mutating_op_is_scoped_per_account(fake_tasklist_store)` — line 421
- `test_task_op_on_other_accounts_tasklist_raises(fake_tasklist_store)` — line 430
- `test_task_ops_on_missing_tasklist_raise(fake_tasklist_store, mutate)` — line 450

## `tests/test_tasklists_storage.py`

**Imports**

- `json`
- `os`
- `src.storage.json_file_storage: JsonFileStorage`
- `src.storage.json_file_storage_parts.tasklists: DEFAULT_RUN_TTL_DAYS, TasklistsMixin`
- `src.storage_paths.storage_paths: StoragePaths`
- `src.tasklists.task: Task`
- `src.tasklists.task_list: TaskList`
- `src.tasklists.task_states: TASK_LIST_STATE_CREATED, TASK_STATE_COMPLETED, TASK_STATE_FAILED, TASK_STATE_PENDING`
- `time`

**Classes**

- `TasklistsMixinHost(TasklistsMixin)` — line 18
  - `__init__(self, tmp_path, ns = 'ns') [line 19]`
  - `_ensure_dir(self, path) [line 23]`

**Functions**

- `make_storage(tmp_path, ns = 'ns')` — line 27
- `_write_raw_tasklist(storage, account_name, tasklist_key, tasks)` — line 31
- `test_tasklists_mixin_is_exercised_directly_without_internal_service(tmp_path)` — line 45
- `test_json_file_storage_constructs_without_internal_tasklist_service(tmp_path)` — line 61
- `test_save_tasklist_writes_tasklist_json_readable_directly(tmp_path)` — line 78
- `test_save_and_get_tasklist_roundtrip(tmp_path)` — line 88
- `test_delete_tasklist_and_idempotent(tmp_path)` — line 111
- `test_invalid_tasklist_key_rejected(tmp_path)` — line 125
- `test_id_auto_set_to_match_key(tmp_path)` — line 136
- `test_save_all_pending_persists_created_state(tmp_path)` — line 149
- `test_save_and_get_tasklist_with_meta(tmp_path)` — line 168
- `test_save_tasklist_adopts_legacy_run_metrics(tmp_path)` — line 191
- `test_save_tasklist_adopts_legacy_inline_fields_into_runs_file(tmp_path)` — line 213
- `test_save_tasklist_adoption_is_idempotent(tmp_path)` — line 278
- `test_tasklist_runs_path_is_safe_sibling_of_tasklist_json(tmp_path)` — line 311
- `test_append_task_execution_record_writes_jsonl_line(tmp_path)` — line 345
- `test_get_task_result_returns_latest_record_for_task(tmp_path)` — line 370
- `test_get_task_result_legacy_inline_fallback(tmp_path)` — line 384
- `test_get_task_result_prefers_record_over_legacy_inline(tmp_path)` — line 409
- `test_get_task_result_none_when_no_record_and_no_legacy(tmp_path)` — line 427
- `test_append_task_execution_record_creates_runs_file_without_tasklist_json(tmp_path)` — line 438
- `test_list_tasklists_ttl_sweep_removes_stale_runs_files(tmp_path)` — line 450
- `test_delete_tasklist_removes_runs_file_sibling(tmp_path)` — line 469
- `test_save_tasklist_rejects_plain_dict_with_type_error(tmp_path)` — line 486

## `tests/test_tool_adapter.py`

> Conformance tests for ``src.mcp.tool_adapter`` (design doc Tests table).

**Imports**

- `__future__: annotations`
- `pytest`
- `src.handlers.handler_registry: HandlerRegistry`
- `src.handlers.handler_v2: HandlerV2`
- `src.mcp.tool_adapter: handler_tool_def_to_mcp`
- `typing: Any, Dict`

**Classes**

- `_StubToolHandler(HandlerV2)` — line 100
  - `name(cls) -> str [line 106]`
  - `tool_def(cls) -> Dict[str, Any] [line 110]`
  - `execute(self, args: Dict[str, Any], *, account_name: str = 'auto', **context) -> Dict[str, Any] [line 118]`
- `_StubToolHandlerLookalike(_StubToolHandler)` — line 124

**Functions**

- `real_registry() -> HandlerRegistry` — line 39
- `_source_def(tool_def: Dict[str, Any]) -> Dict[str, Any]` — line 46
- `test_tool_adapter_mapping(real_registry: HandlerRegistry) -> None` — line 57
- `test_tool_adapter_duplicate_defs(real_registry: HandlerRegistry) -> None` — line 128

## `tests/test_tool_selection_pipeline.py`

> Pipeline unit tests for the tool selection pipeline (issue #126, design §3/§5).

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass, field`
- `datetime: datetime, timezone`
- `pytest`
- `src.storage.models: Context, Skill`
- `src.tool_selection: ToolSelection, ToolSelectionError, ToolSelectionPipeline`
- `tests.conftest: FakeConfig, FakeRegistry, FakeStorage`
- `types: SimpleNamespace`
- `typing: Any, Dict, List, Optional, Tuple`

**Classes**

- `FakeLLM` — line 47
  - `call_model(self, **kwargs: Any) -> Any [line 54]`
  - `get_text(self, response: Any) -> str [line 58]`
- `FakeAgent` — line 63

**Functions**

- `_defs(*names: str) -> List[Dict[str, Any]]` — line 77
- `_make_config(*, enabled: bool = True, min_eligible: int = 1, schema_cap: Optional[int] = None) -> FakeConfig` — line 89
- `_make_context(*, mandatory_tools: Optional[List[str]] = None, skills: Optional[List[Skill]] = None) -> Context` — line 106
- `_build(*, tool_names: List[str], allowed: Optional[List[str]] = None, context: Any = None, llm_reply: str = '[]', enabled: bool = True, min_eligible: int = 1, schema_cap: Optional[int] = None, agent_schema_cap: Optional[int] = None) -> Tuple[ToolSelectionPipeline, FakeLLM, FakeAgent]` — line 120
- `_resolve(*, tool_names: List[str], allowed: Optional[List[str]] = None, context: Any = None, llm_reply: str = '[]', enabled: bool = True, min_eligible: int = 1, schema_cap: Optional[int] = None, agent_schema_cap: Optional[int] = None, prompt_text: str = 'do something', context_name: str = CONTEXT_ID) -> Tuple[ToolSelection, FakeLLM]` — line 147
- `test_step3_allowed_none_means_no_tools()` — line 184
- `test_step3_allowed_empty_means_no_tools()` — line 196
- `test_step3_eligible_subset_preserves_registry_order()` — line 204
- `test_step3_unknown_allowed_names_ignored()` — line 212
- `test_step4_required_aggregates_context_and_skills_deduped()` — line 227
- `test_step4_required_empty_when_no_context()` — line 245
- `test_step4_required_empty_when_context_missing()` — line 255
- `test_step4_required_empty_when_no_mandatory_tools()` — line 265
- `test_step4_required_none_attribute_treated_as_empty()` — line 275
- `test_step4_required_normalizes_blank_entries()` — line 291
- `test_step5_validate_passes_when_required_is_allowed_and_registered()` — line 306
- `test_step5_required_not_permissioned_raises_precise_message()` — line 318
- `test_step5_required_not_registered_raises_precise_message()` — line 344
- `test_step5_permission_check_precedes_registry_check()` — line 370
- `test_step7_active_is_union_dedup_required_first()` — line 391
- `test_step7_required_always_present_when_llm_omits_them()` — line 408
- `test_step7_llm_suggestions_outside_eligible_are_clamped()` — line 421
- `test_step7_selection_disabled_active_is_full_eligible()` — line 435
- `test_budget_under_cap_unchanged()` — line 454
- `test_budget_over_cap_raises_budget_exceeded_with_increase_message()` — line 468
- `test_budget_cap_zero_or_negative_disables(cap)` — line 492
- `test_budget_agent_small_cap_beats_large_config_cap()` — line 509
- `test_budget_meta_schema_cap_reports_agent_not_config()` — line 527
- `test_budget_agent_non_positive_disables_despite_tiny_config_cap(agent_cap)` — line 542

## `tests/test_tool_selection_selection.py`

> Selection-stage unit tests for the tool selection pipeline (issue #126, design §5.4/§8).

**Imports**

- `__future__: annotations`
- `dataclasses: dataclass, field`
- `datetime: datetime, timezone`
- `pytest`
- `src.storage.models: Context`
- `src.tool_selection.selection: suggest_tools`
- `src.tool_selection: ToolSelectionPipeline`
- `tests.conftest: FakeConfig, FakeRegistry, FakeStorage`
- `types: SimpleNamespace`
- `typing: Any, Dict, List, Optional, Tuple`

**Classes**

- `FakeLLM` — line 56
  - `call_model(self, **kwargs: Any) -> Any [line 69]`
  - `get_text(self, response: Any) -> str [line 75]`
  - `call_count(self) -> int [line 79]`
  - `llm_call(self, messages: List[Dict[str, str]]) -> str [line 82]`

**Functions**

- `_defs(*names: str) -> List[Dict[str, Any]]` — line 98
- `_make_context(mandatory_tools: Optional[List[str]] = None) -> Context` — line 110
- `_suggest(prompt_text: str, defs: List[Dict[str, Any]], *, reply: str = '[]', exc: Optional[BaseException] = None) -> Tuple[List[str], Dict[str, Any], FakeLLM]` — line 120
- `_resolve(*, tool_names: List[str], allowed: Optional[List[str]] = None, context: Any = None, reply: str = '[]', exc: Optional[BaseException] = None, enabled: bool = True, min_eligible: int = 1, prompt_text: str = 'do something') -> Tuple[Any, FakeLLM]` — line 138
- `test_suggest_valid_json_array_parsed_and_clamped_in_eligible_order()` — line 183
- `test_suggest_garbage_text_yields_empty_suggestion(reply)` — line 210
- `test_suggest_names_not_in_eligible_are_clamped()` — line 220
- `test_suggest_clamped_result_follows_eligible_order()` — line 235
- `test_suggest_empty_result()` — line 248
- `test_suggest_llm_exception_surfaces_for_pipeline_to_handle()` — line 259
- `test_suggest_empty_eligible_never_calls_llm()` — line 275
- `test_suggest_builds_compact_name_first_sentence_menu()` — line 284
- `test_pipeline_valid_json_suggestion_unions_with_required()` — line 320
- `test_pipeline_garbage_reply_yields_required_only()` — line 337
- `test_pipeline_llm_raises_falls_back_to_required_only()` — line 353
- `test_pipeline_below_min_eligible_skips_llm_call()` — line 373
- `test_pipeline_selection_disabled_skips_llm_call_and_active_is_eligible()` — line 391

## `tests/test_upload_endpoints.py`

> Tests for upload_endpoints.py — POST /upload/image.

**Imports**

- `__future__: annotations`
- `json`
- `os`
- `pytest`
- `src.http_endpoints.upload_endpoints: post_upload_image_impl`
- `sys`
- `tempfile`
- `typing: Any, Dict`

**Functions**

- `_make_config(overrides: Dict[str, Any] = None) -> Any` — line 25
- `_make_png_bytes() -> bytes` — line 42
- `_make_jpeg_bytes() -> bytes` — line 47
- `_make_gif_bytes() -> bytes` — line 51
- `_make_webp_bytes() -> bytes` — line 55
- `test_upload_png_success()` — line 64
- `test_upload_jpeg_success()` — line 99
- `test_upload_gif_success()` — line 115
- `test_upload_webp_success()` — line 128
- `test_upload_unique_ids()` — line 141
- `test_upload_different_accounts_separated()` — line 161
- `test_missing_account_name()` — line 189
- `test_empty_file_data()` — line 202
- `test_invalid_mime_type()` — line 215
- `test_file_too_large()` — line 228

## `tests/test_workflow_loader.py`

**Imports**

- `pytest`
- `src.workflows.loader: WorkflowLoader`

**Functions**

- `test_loader_builds_linked_tree_and_preserves_execution_fields()` — line 26
- `test_loader_rejects_unknown_branch_target()` — line 41
- `test_loader_rejects_duplicate_ids()` — line 57

## `tests/test_workflow_runner.py`

**Imports**

- `json`
- `src.workflows.executor: AskWorkflowExecutor, FakeWorkflowExecutor`
- `src.workflows.loader: WorkflowLoader`
- `src.workflows.result: WorkflowResult`
- `src.workflows.runner: WorkflowRunner`

**Classes**

- `FakeResponse` — line 130
  - `__init__(self, status_code, body) [line 131]`
  - `json(self) [line 135]`

**Functions**

- `result(outcome, text = '', tokens = 0, iterations = 0)` — line 46
- `test_runner_executes_clarity_design_review_and_accumulates_metrics()` — line 55
- `test_blocked_clarity_exits_without_running_design()` — line 75
- `test_failed_review_loops_to_design_with_feedback_and_is_bounded()` — line 85
- `test_retry_node_retries_one_child_up_to_bound()` — line 104
- `test_ask_executor_reads_api_key_from_config_local_json(tmp_path)` — line 139
- `test_ask_executor_sends_node_instructions_as_the_question()` — line 152
- `test_ask_executor_does_not_interpret_response_text()` — line 178
- `test_ask_executor_reports_http_error()` — line 191
- `test_ask_executor_reports_ask_error_body()` — line 206
- `test_ask_executor_reports_transport_failure()` — line 220
- `test_ask_executor_writes_no_files(tmp_path)` — line 234

## `tests/topics/__init__.py`

> Tests for the standalone topics component (issue #129).

## `tests/topics/test_edge_cases.py`

> Edge-case coverage for the standalone topics component (issue #129).

**Imports**

- `__future__: annotations`
- `concurrent.futures: ThreadPoolExecutor`
- `datetime: datetime, timedelta, timezone`
- `pathlib: Path`
- `pytest`
- `re`
- `src.topics.mutation: TopicArchivedError`
- `src.topics.queries: TopicStoreImpl`
- `src.topics.schemas: INBOX_STREAM, KIND_TOPIC_CREATED, KIND_TOPIC_LINK, TopicEvent, TopicLinkPayload`
- `src.topics.streams: JsonlEventStore, StreamArchivedError`
- `threading`
- `typing: List`

**Classes**

- `TestEmptyAccount` — line 116
  - `test_queries_on_never_used_account_are_empty(self, impl: TopicStoreImpl) -> None [line 117]`
  - `test_create_works_on_fresh_account(self, impl: TopicStoreImpl) -> None [line 126]`
  - `test_accounts_are_isolated(self, impl: TopicStoreImpl) -> None [line 132]`
  - `test_empty_account_name_rejected(self, impl: TopicStoreImpl) -> None [line 142]`
  - `test_events_in_topic_on_empty_account(self, impl: TopicStoreImpl) -> None [line 146]`
- `TestDuplicateSlugs` — line 156
  - `test_suffix_progression(self, impl: TopicStoreImpl) -> None [line 157]`
  - `test_suffix_skips_free_slots(self, impl: TopicStoreImpl) -> None [line 164]`
  - `test_truncation_at_64_char_limit(self, impl: TopicStoreImpl) -> None [line 172]`
  - `test_exactly_64_char_proposal_accepted(self, impl: TopicStoreImpl) -> None [line 182]`
  - `test_uniqueness_is_per_account(self, impl: TopicStoreImpl) -> None [line 186]`
  - `test_rename_does_not_free_slug(self, impl: TopicStoreImpl) -> None [line 197]`
- `TestMergeChains` — line 212
  - `test_two_hop_chain_collapses_into_target(self, impl: TopicStoreImpl) -> None [line 213]`
  - `test_merged_source_cannot_be_merged_again(self, impl: TopicStoreImpl) -> None [line 240]`
  - `test_chain_into_archived_target_rejected(self, impl: TopicStoreImpl) -> None [line 249]`
  - `test_chain_via_log_replay(self, tmp_path: Path) -> None [line 256]`
- `TestArchiveWriteRejection` — line 279
  - `test_store_rejects_direct_append_after_archive(self, store: JsonlEventStore, impl: TopicStoreImpl) -> None [line 280]`
  - `test_mutations_rejected_on_archived(self, impl: TopicStoreImpl) -> None [line 290]`
  - `test_archived_state_derived_from_log_across_instances(self, tmp_path: Path) -> None [line 302]`
  - `test_archived_stream_still_readable(self, impl: TopicStoreImpl) -> None [line 321]`
- `TestUnicodeWeirdSlugs` — line 338
  - `test_emoji_stripped(self, impl: TopicStoreImpl) -> None [line 339]`
  - `test_cjk_stripped_to_empty_raises(self, impl: TopicStoreImpl) -> None [line 342]`
  - `test_accents_stripped(self, impl: TopicStoreImpl) -> None [line 346]`
  - `test_fullwidth_normalized(self, impl: TopicStoreImpl) -> None [line 350]`
  - `test_control_chars_and_newlines(self, impl: TopicStoreImpl) -> None [line 354]`
  - `test_unicode_dash_removed(self, impl: TopicStoreImpl) -> None [line 359]`
  - `test_mixed_punctuation_and_spaces(self, impl: TopicStoreImpl) -> None [line 364]`
  - `test_overlong_proposal_raises(self, impl: TopicStoreImpl) -> None [line 372]`
  - `test_name_may_be_long_but_proposal_validated(self, impl: TopicStoreImpl) -> None [line 376]`
  - `test_weird_proposal_never_creates_a_stream(self, impl: TopicStoreImpl) -> None [line 384]`
- `TestConcurrentAppends` — line 397
  - `test_many_threads_one_topic_stream(self, tmp_path: Path) -> None [line 398]`
  - `test_many_threads_inbox_first_write(self, tmp_path: Path) -> None [line 451]`
  - `test_concurrent_appends_never_touch_other_streams(self, tmp_path: Path) -> None [line 509]`
- `TestStandaloneGuardrail` — line 541
  - `_imported_src_modules(path: Path) -> List[str] [line 569]`
  - `test_no_fcp_or_agent_imports_in_src_topics(self) -> None [line 581]`
  - `test_no_fcp_or_agent_imports_in_tests_topics(self) -> None [line 590]`
  - `test_forbidden_modules_never_imported(self) -> None [line 599]`
  - `test_component_imports_only_schemas_from_package_root(self) -> None [line 614]`
  - `test_no_dynamic_fcp_imports(self) -> None [line 628]`

**Functions**

- `store(tmp_path: Path) -> JsonlEventStore` — line 68
- `impl(store: JsonlEventStore) -> TopicStoreImpl` — line 73
- `_link_event(slug: str, event_ids: List[str], *, event_id: str | None = None, agent: str = 'lucy', ts: datetime | None = None) -> TopicEvent` — line 77
- `_raw_lines(store: JsonlEventStore, stream: str) -> List[str]` — line 97
- `_read_all(data_root: Path, account: str, stream: str) -> List[TopicEvent]` — line 105

## `tests/topics/test_index.py`

> Tests for src/topics/index.py - the derived topic index (issue #129).

**Imports**

- `__future__: annotations`
- `datetime: datetime, timedelta, timezone`
- `pathlib: Path`
- `pytest`
- `src.storage.interfaces: EventStore`
- `src.topics.index: KIND_EXPLICIT, KIND_INFERRED, KIND_TEMPORAL, TopicIndex`
- `src.topics.schemas: INBOX_STREAM, KIND_TOPIC_ARCHIVED, KIND_TOPIC_CREATED, KIND_TOPIC_LINK, KIND_TOPIC_MERGED, KIND_TOPIC_RENAMED, KIND_TOPIC_UNLINK, TopicArchivedPayload, TopicCreatedPayload, TopicEvent, TopicLinkPayload, TopicMergedPayload, TopicRenamedPayload, TopicUnlinkPayload, inbox_path, stream_path`
- `src.topics.streams: JsonlEventStore`
- `typing: List, Optional`

**Classes**

- `_ConversationEvent` — line 163
  - `__init__(self, event_id: str, stream: str, ts: Optional[datetime] = None) -> None [line 172]`
- `TestRebuildIdempotent` — line 203
  - `_log(self, store: JsonlEventStore) -> None [line 204]`
  - `_all_events(self, store: JsonlEventStore) -> List[TopicEvent] [line 212]`
  - `test_empty_account_rebuild(self, index: TopicIndex) -> None [line 218]`
  - `test_rebuild_twice_identical(self, store: JsonlEventStore, index: TopicIndex) -> None [line 224]`
  - `test_partial_apply_equals_full_rebuild(self, store: JsonlEventStore, index: TopicIndex) -> None [line 231]`
  - `test_apply_every_event_equals_rebuild(self, store: JsonlEventStore, index: TopicIndex) -> None [line 252]`
  - `test_apply_then_rebuild_is_log_faithful(self, store: JsonlEventStore, index: TopicIndex) -> None [line 264]`
- `TestLifecycle` — line 280
  - `test_create_builds_record(self, store: JsonlEventStore, index: TopicIndex) -> None [line 281]`
  - `test_rename_keeps_slug(self, store: JsonlEventStore, index: TopicIndex) -> None [line 293]`
  - `test_created_and_updated_timestamps(self, store: JsonlEventStore, index: TopicIndex) -> None [line 303]`
- `TestReTagging` — line 322
  - `test_link_adds_membership(self, store: JsonlEventStore, index: TopicIndex) -> None [line 323]`
  - `test_unlink_removes_membership(self, store: JsonlEventStore, index: TopicIndex) -> None [line 329]`
  - `test_re_tagging_never_moves_events(self, store: JsonlEventStore, index: TopicIndex) -> None [line 336]`
  - `test_inbox_events_never_members(self, store: JsonlEventStore, index: TopicIndex) -> None [line 356]`
- `TestArchive` — line 370
  - `test_archived_excluded_from_active_queries(self, store: JsonlEventStore, index: TopicIndex) -> None [line 371]`
  - `test_archived_still_queryable_by_id(self, store: JsonlEventStore, index: TopicIndex) -> None [line 387]`
  - `test_archive_before_create_is_order_independent(self, index: TopicIndex) -> None [line 400]`
- `TestMerge` — line 417
  - `test_merge_relinks_and_freezes_source(self, store: JsonlEventStore, index: TopicIndex) -> None [line 418]`
  - `test_merge_before_create_is_order_independent(self, index: TopicIndex) -> None [line 448]`
- `TestTopicsByKind` — line 463
  - `test_explicit_kind_partition(self, store: JsonlEventStore, index: TopicIndex) -> None [line 464]`
  - `test_future_kinds_empty(self, index: TopicIndex) -> None [line 475]`
- `TestStreamBinding` — line 486
  - `test_non_topic_event_binds_to_topic_stream(self, store: JsonlEventStore, index: TopicIndex) -> None [line 487]`
  - `test_inbox_conversation_event_never_binds(self, store: JsonlEventStore, index: TopicIndex) -> None [line 500]`
  - `test_binding_before_create_is_buffered(self, index: TopicIndex) -> None [line 508]`
- `TestInboxNeverTopic` — line 521
  - `test_misplaced_topic_created_in_inbox_ignored(self, store: JsonlEventStore, index: TopicIndex) -> None [line 522]`
  - `test_link_targeting_inbox_changes_nothing(self, store: JsonlEventStore, index: TopicIndex) -> None [line 540]`
- `TestNoAgentPartitioning` — line 555
  - `test_membership_independent_of_agent(self, store: JsonlEventStore, index: TopicIndex) -> None [line 556]`
- `TestSeam` — line 574
  - `test_index_consumes_eventstore_abc(self, store: JsonlEventStore) -> None [line 575]`

**Functions**

- `_event(kind: str, payload, stream: str, agent: str = 'lucy', ts: Optional[datetime] = None) -> TopicEvent` — line 57
- `_created(slug: str, name: Optional[str] = None, description: Optional[str] = None, agent: str = 'lucy', ts: Optional[datetime] = None) -> TopicEvent` — line 70
- `_renamed(slug: str, old_name: str, new_name: str, agent: str = 'lucy', ts: Optional[datetime] = None) -> TopicEvent` — line 86
- `_link(slug: str, event_ids: List[str], reason: Optional[str] = None, agent: str = 'lucy', ts: Optional[datetime] = None) -> TopicEvent` — line 102
- `_unlink(slug: str, event_ids: List[str], agent: str = 'lucy', ts: Optional[datetime] = None) -> TopicEvent` — line 118
- `_merged(source: str, target: str, agent: str = 'lucy', ts: Optional[datetime] = None) -> TopicEvent` — line 133
- `_archived(slug: str, reason: str = 'done', agent: str = 'lucy', ts: Optional[datetime] = None) -> TopicEvent` — line 148
- `store(tmp_path: Path) -> JsonlEventStore` — line 180
- `index(store: JsonlEventStore) -> TopicIndex` — line 185
- `_append(store: JsonlEventStore, event: TopicEvent) -> None` — line 189
- `_snapshot(index: TopicIndex) -> list` — line 193

## `tests/topics/test_migration.py`

> Migration smoke test (issue #129, task t-migration).

**Imports**

- `__future__: annotations`
- `datetime: datetime, timedelta, timezone`
- `json`
- `pathlib: Path`
- `pytest`
- `src.topics.migration: Chat2ReadError, MigrationReport, TopicMigrator, scan_chat2_sessions`
- `src.topics.queries: TopicStoreImpl`
- `src.topics.schemas: KIND_CHAT2_EVENT, KIND_TOPIC_CREATED, KIND_TOPIC_LINK, MIGRATION_SOURCE_CHAT2, TopicEvent, stream_path`
- `src.topics.streams: JsonlEventStore`
- `typing: Any, Dict, List, Optional`

**Classes**

- `TestEverySessionMigrates` — line 172
  - `test_one_topic_per_session(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 173]`
  - `test_topic_created_uses_session_name(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 192]`
  - `test_link_carries_all_original_event_ids(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 201]`
  - `test_exactly_one_topic_created_across_all_streams(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 212]`
- `TestProvenanceMarkers` — line 229
  - `test_every_copied_event_carries_provenance(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 230]`
  - `test_original_envelope_preserved_in_payload(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 243]`
  - `test_original_ts_and_event_id_preserved_on_envelope(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 258]`
  - `test_empty_session_yields_topic_created_only(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 274]`
- `TestIdempotent` — line 293
  - `_snapshot(self, store: JsonlEventStore) -> Dict[str, bytes] [line 294]`
  - `test_rerun_skips_already_migrated(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 300]`
  - `test_rerun_after_new_session_migrates_only_the_new_one(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 314]`
  - `test_fresh_migrator_instance_sees_existing_markers(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 336]`
- `TestDigestsAndEmbeddingsUntouched` — line 354
  - `test_digest_and_embedding_files_unchanged(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 355]`
  - `test_only_topics_dir_created(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 382]`
- `TestSlugFromSessionName` — line 397
  - `test_slug_from_friendly_name(self, tmp_path: Path, migrator: TopicMigrator) -> None [line 398]`
  - `test_colliding_names_get_deterministic_suffixes(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 409]`
  - `test_name_falls_back_to_session_id(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 423]`
- `TestReading` — line 439
  - `test_account_filtering(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 440]`
  - `test_missing_meta_counts_as_unreadable(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 457]`
  - `test_corrupt_events_raise_before_any_write(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 466]`
  - `test_scan_returns_sorted_sessions(self, tmp_path: Path) -> None [line 482]`
- `TestQueryIntegration` — line 498
  - `test_events_in_topic_newest_first(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 499]`
  - `test_index_derives_membership(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 522]`
- `TestGuardrails` — line 540
  - `test_events_never_carry_topic_id(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 541]`
  - `test_session_id_only_as_legacy_metadata(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 550]`
  - `test_agent_is_metadata_not_partition_key(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 566]`
  - `test_no_project_context_or_external_refs(self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator) -> None [line 578]`
- `TestReport` — line 594
  - `test_report_shape(self) -> None [line 595]`

**Functions**

- `store(tmp_path: Path) -> JsonlEventStore` — line 57
- `migrator(store: JsonlEventStore) -> TopicMigrator` — line 62
- `_chat2_event(event_id: str, *, ts: datetime, role: str = 'user', actor: str = 'junwin', kind: str = 'user_message', payload: Any = 'hello', metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]` — line 66
- `_write_session(chat2_root: Path, session_id: str, *, account: str = ACCOUNT, friendly_name: Optional[str] = None, events: Optional[List[Dict[str, Any]]] = None, extra_meta: Optional[Dict[str, Any]] = None) -> Path` — line 87
- `_two_sessions(chat2_root: Path) -> Dict[str, str]` — line 127
- `_stream_lines(store: JsonlEventStore, stream: str) -> List[str]` — line 154
- `_stream_kinds(store: JsonlEventStore, stream: str) -> List[str]` — line 159
- `_stream_events(store: JsonlEventStore, stream: str) -> List[TopicEvent]` — line 163

## `tests/topics/test_mutation_api.py`

> Tests for src/topics/mutation.py - the topic mutation API (issue #129).

**Imports**

- `__future__: annotations`
- `json`
- `pathlib: Path`
- `pytest`
- `src.storage.interfaces: EventStore`
- `src.topics.index: TopicIndex`
- `src.topics.mutation: TopicArchivedError, TopicError, TopicMutations, TopicNotFoundError`
- `src.topics.schemas: INBOX_STREAM, KIND_TOPIC_ARCHIVED, KIND_TOPIC_CREATED, KIND_TOPIC_LINK, KIND_TOPIC_MERGED, KIND_TOPIC_RENAMED, KIND_TOPIC_UNLINK, TopicCreatedPayload, TopicEvent, TopicLinkPayload, inbox_path, stream_path`
- `src.topics.streams: JsonlEventStore, StreamArchivedError`
- `typing: List`

**Classes**

- `TestAppendOnly` — line 99
  - `test_create_appends_one_event(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 100]`
  - `test_rename_appends_without_touching_prior_lines(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 113]`
  - `test_link_appends_one_event(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 127]`
  - `test_unlink_appends_one_event(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 138]`
  - `test_merge_appends_three_events(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 149]`
  - `test_archive_appends_one_event(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 169]`
  - `test_full_sequence_never_rewrites_earlier_lines(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 178]`
- `TestMerge` — line 197
  - `_pair(self, topics: TopicMutations) -> None [line 198]`
  - `test_merge_relinks_all_source_ids(self, topics: TopicMutations) -> None [line 204]`
  - `test_merge_freezes_source_stream(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 218]`
  - `test_merge_into_archived_target_rejected(self, topics: TopicMutations) -> None [line 230]`
  - `test_merge_archived_source_rejected(self, topics: TopicMutations) -> None [line 236]`
  - `test_merge_into_self_rejected(self, topics: TopicMutations) -> None [line 242]`
  - `test_merge_unknown_topics_rejected(self, topics: TopicMutations) -> None [line 247]`
  - `test_merge_empty_source_skips_link_event(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 254]`
- `TestArchiveAndRename` — line 272
  - `test_archive_freezes_stream(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 273]`
  - `test_archive_keeps_events_queryable(self, topics: TopicMutations) -> None [line 282]`
  - `test_archive_twice_rejected(self, topics: TopicMutations) -> None [line 292]`
  - `test_archive_unknown_topic_rejected(self, topics: TopicMutations) -> None [line 298]`
  - `test_rename_keeps_slug(self, topics: TopicMutations) -> None [line 302]`
  - `test_rename_unknown_topic_rejected(self, topics: TopicMutations) -> None [line 311]`
  - `test_rename_archived_topic_rejected(self, topics: TopicMutations) -> None [line 315]`
- `TestSlugResolution` — line 327
  - `test_collision_gets_deterministic_suffix(self, topics: TopicMutations) -> None [line 328]`
  - `test_collision_after_normalization(self, topics: TopicMutations) -> None [line 333]`
  - `test_inbox_slug_is_reserved(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 347]`
  - `test_invalid_proposal_rejected(self, topics: TopicMutations) -> None [line 357]`
- `TestLinkUnlink` — line 369
  - `test_link_then_unlink_updates_membership(self, topics: TopicMutations) -> None [line 370]`
  - `test_link_unknown_topic_rejected(self, topics: TopicMutations) -> None [line 377]`
  - `test_unlink_unknown_topic_rejected(self, topics: TopicMutations) -> None [line 381]`
  - `test_link_archived_topic_rejected(self, topics: TopicMutations) -> None [line 385]`
  - `test_unlink_archived_topic_rejected(self, topics: TopicMutations) -> None [line 391]`
  - `test_empty_event_ids_rejected(self, topics: TopicMutations) -> None [line 397]`
- `TestAgentMetadata` — line 410
  - `test_agent_recorded_on_every_event(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 411]`
  - `test_two_agents_share_one_topic_stream(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 422]`
- `TestIndexSync` — line 441
  - `test_operations_reflect_in_index_without_rebuild(self, topics: TopicMutations) -> None [line 442]`
  - `test_fresh_instance_rebuilds_from_log(self, tmp_path: Path) -> None [line 450]`
  - `test_rebuild_sees_external_writes(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 464]`
- `TestGuardrails` — line 489
  - `test_events_never_carry_topic_id(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 490]`
  - `test_no_project_context_or_external_refs(self, store: JsonlEventStore, topics: TopicMutations) -> None [line 506]`
- `TestStoreContract` — line 527
  - `test_mutations_consume_eventstore_abc(self, store: JsonlEventStore) -> None [line 528]`
  - `test_error_hierarchy(self) -> None [line 533]`

**Functions**

- `store(tmp_path: Path) -> JsonlEventStore` — line 57
- `index(store: JsonlEventStore) -> TopicIndex` — line 62
- `topics(store: JsonlEventStore, index: TopicIndex) -> TopicMutations` — line 67
- `_raw_lines(store: JsonlEventStore, stream: str) -> List[str]` — line 71
- `_kinds(store: JsonlEventStore, stream: str) -> List[str]` — line 78
- `_link_event(slug: str, event_ids: List[str]) -> TopicEvent` — line 84

## `tests/topics/test_query_api.py`

> Tests for src/topics/queries.py - the topic query API (issue #129).

**Imports**

- `__future__: annotations`
- `datetime: datetime, timedelta, timezone`
- `pathlib: Path`
- `pytest`
- `src.storage.interfaces: EventStore, TopicStore`
- `src.topics.index: TopicIndex`
- `src.topics.mutation: TopicMutations`
- `src.topics.queries: TopicQueries, TopicStoreImpl`
- `src.topics.schemas: INBOX_STREAM, KIND_TOPIC_CREATED, KIND_TOPIC_LINK, TopicEvent, TopicLinkPayload`
- `src.topics.streams: JsonlEventStore`
- `typing: List`

**Classes**

- `TestGetTopic` — line 120
  - `test_returns_record_with_derived_event_ids(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 121]`
  - `test_unknown_topic_returns_none(self, queries: TopicQueries) -> None [line 134]`
  - `test_archived_topic_still_queryable(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 137]`
  - `test_lifecycle_events_are_not_members(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 150]`
- `TestEventsInTopic` — line 166
  - `test_newest_first(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 167]`
  - `test_limit_honored(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 172]`
  - `test_limit_none_returns_all(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 178]`
  - `test_unknown_topic_returns_empty(self, queries: TopicQueries) -> None [line 184]`
  - `test_members_resolve_across_streams(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 187]`
  - `test_archived_topic_events_still_queryable(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 216]`
  - `test_dangling_ids_are_skipped(self, queries: TopicQueries) -> None [line 227]`
- `TestTopicsByKind` — line 243
  - `_two_topics(self, store: JsonlEventStore) -> TopicStoreImpl [line 244]`
  - `test_explicit_partition_excludes_archived(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 251]`
  - `test_explicit_partition_with_archived(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 258]`
  - `test_future_kinds_empty_in_v1(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 266]`
  - `test_list_topics_kind_filter_abc_signature(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 274]`
  - `test_list_topics_default_active_only(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 282]`
  - `test_empty_account(self, queries: TopicQueries) -> None [line 288]`
- `TestDateFilter` — line 298
  - `test_inclusive_start(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 299]`
  - `test_inclusive_end(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 304]`
  - `test_inclusive_range(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 309]`
  - `test_full_range_returns_all(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 319]`
  - `test_no_match_returns_empty(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 331]`
  - `test_naive_datetime_assumed_utc(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 342]`
  - `test_filter_combines_with_limit(self, store: JsonlEventStore, queries: TopicQueries) -> None [line 354]`
- `TestTopicStoreImpl` — line 369
  - `test_implements_topicstore_abc(self, impl: TopicStoreImpl) -> None [line 370]`
  - `test_create_visible_in_queries(self, impl: TopicStoreImpl) -> None [line 374]`
  - `test_link_then_events_in_topic(self, store: JsonlEventStore, impl: TopicStoreImpl) -> None [line 382]`
  - `test_unlink_reflected_in_events(self, store: JsonlEventStore, impl: TopicStoreImpl) -> None [line 392]`
  - `test_merge_relinks_into_target(self, store: JsonlEventStore, impl: TopicStoreImpl) -> None [line 402]`
  - `test_rebuild_sees_external_writes(self, store: JsonlEventStore, impl: TopicStoreImpl) -> None [line 416]`
- `TestValidation` — line 435
  - `test_limit_must_be_positive_int(self, queries: TopicQueries) -> None [line 436]`
- `TestGuardrails` — line 450
  - `test_no_semantic_search(self, queries: TopicQueries) -> None [line 451]`
  - `test_agent_never_a_partition_key(self, store: JsonlEventStore, impl: TopicStoreImpl) -> None [line 460]`
  - `test_events_never_carry_topic_id(self, store: JsonlEventStore, impl: TopicStoreImpl) -> None [line 472]`
  - `test_queries_consume_eventstore_abc(self, store: JsonlEventStore) -> None [line 484]`

**Functions**

- `store(tmp_path: Path) -> JsonlEventStore` — line 50
- `index(store: JsonlEventStore) -> TopicIndex` — line 55
- `queries(store: JsonlEventStore, index: TopicIndex) -> TopicQueries` — line 60
- `impl(store: JsonlEventStore) -> TopicStoreImpl` — line 65
- `_seed_inbox_event(store: JsonlEventStore, event_id: str, *, ts: datetime | None = None, agent: str = 'lucy') -> TopicEvent` — line 69
- `_ids(events: List[TopicEvent]) -> List[str]` — line 99
- `_make_topic_with_events(store: JsonlEventStore, queries: TopicQueries) -> str` — line 103

## `tests/topics/test_schemas.py`

> Tests for src/topics/schemas.py - the single source of truth for topic event

**Imports**

- `__future__: annotations`
- `datetime: datetime, timedelta, timezone`
- `inspect`
- `pydantic: ValidationError`
- `pytest`
- `src.topics.schemas: EVENT_LOG_SCHEMA_VERSION, INBOX_STREAM, KIND_CHAT2_EVENT, KIND_TOPIC_ARCHIVED, KIND_TOPIC_CREATED, KIND_TOPIC_LINK, KIND_TOPIC_MERGED, KIND_TOPIC_RENAMED, KIND_TOPIC_UNLINK, MIGRATION_SOURCE_CHAT2, SLUG_MAX_LENGTH, SLUG_MIN_LENGTH, Chat2EventPayload, EventProvenance, TopicArchivedPayload, TopicCreatedPayload, TopicEvent, TopicLinkPayload, TopicMergedPayload, TopicRenamedPayload, TopicUnlinkPayload, inbox_path, is_valid_slug, normalize_slug, resolve_slug, stream_path, validate_slug`

**Classes**

- `TestSlugNormalization` — line 52
  - `test_lowercases_and_replaces_spaces(self) -> None [line 53]`
  - `test_underscores_become_hyphens(self) -> None [line 56]`
  - `test_nfkc_fullwidth_to_ascii(self) -> None [line 59]`
  - `test_strips_disallowed_chars(self) -> None [line 62]`
  - `test_collapses_hyphen_runs(self) -> None [line 66]`
  - `test_trims_leading_trailing_hyphens(self) -> None [line 69]`
  - `test_handles_mixed_garbage(self) -> None [line 72]`
- `TestSlugValidity` — line 77
  - `test_accepts_contract_forms(self) -> None [line 78]`
  - `test_rejects_bad_forms(self) -> None [line 86]`
  - `test_validate_slug_raises_with_message(self) -> None [line 99]`
- `TestSlugResolution` — line 104
  - `test_no_collision_uses_base(self) -> None [line 105]`
  - `test_collision_appends_deterministic_suffix(self) -> None [line 108]`
  - `test_suffix_stays_deterministic_across_calls(self) -> None [line 112]`
  - `test_suffixed_slug_respects_max_length(self) -> None [line 116]`
  - `test_unusable_proposal_raises(self) -> None [line 123]`
- `TestTopicCreatedPayload` — line 134
  - `test_valid_with_required_fields(self) -> None [line 135]`
  - `test_description_optional(self) -> None [line 141]`
  - `test_rejects_invalid_slug(self) -> None [line 145]`
  - `test_rejects_empty_name(self) -> None [line 149]`
- `TestTopicRenamedPayload` — line 154
  - `test_valid(self) -> None [line 155]`
  - `test_requires_both_names(self) -> None [line 159]`
- `TestTopicMergedPayload` — line 164
  - `test_valid(self) -> None [line 165]`
  - `test_rejects_invalid_slugs(self) -> None [line 169]`
- `TestTopicArchivedPayload` — line 174
  - `test_valid_without_reason(self) -> None [line 175]`
  - `test_valid_with_reason(self) -> None [line 178]`
- `TestTopicLinkPayload` — line 182
  - `test_valid(self) -> None [line 183]`
  - `test_reason_optional(self) -> None [line 188]`
  - `test_rejects_empty_event_ids(self) -> None [line 192]`
  - `test_rejects_invalid_topic_slug(self) -> None [line 196]`
- `TestTopicUnlinkPayload` — line 201
  - `test_valid(self) -> None [line 202]`
  - `test_rejects_empty_event_ids(self) -> None [line 206]`
- `TestNoTopicIdOnEvents` — line 211
  - `test_no_topic_id_field_on_any_payload(self) -> None [line 214]`
  - `test_payload_rejects_topic_id_extra_field(self) -> None [line 226]`
- `TestEnvelope` — line 248
  - `test_valid_topic_created_event(self) -> None [line 249]`
  - `test_event_id_can_be_supplied(self) -> None [line 258]`
  - `test_kind_payload_mismatch_rejected(self) -> None [line 262]`
  - `test_unknown_kind_rejected(self) -> None [line 269]`
  - `test_stream_must_be_inbox_or_slug(self) -> None [line 273]`
  - `test_agent_and_account_required(self) -> None [line 280]`
  - `test_account_rejects_path_separators(self) -> None [line 286]`
  - `test_ts_normalized_to_utc(self) -> None [line 292]`
  - `test_ts_converts_other_timezones(self) -> None [line 297]`
  - `test_extra_fields_rejected(self) -> None [line 303]`
  - `test_json_roundtrip(self) -> None [line 309]`
  - `test_json_roundtrip_all_kinds(self) -> None [line 316]`
  - `test_unlink_roundtrip_not_misread_as_link(self) -> None [line 367]`
  - `test_link_without_reason_roundtrips_as_link(self) -> None [line 380]`
  - `test_envelope_has_agent_metadata_field(self) -> None [line 389]`
- `TestStreamLayout` — line 398
  - `test_inbox_path(self) -> None [line 399]`
  - `test_topic_stream_path(self) -> None [line 402]`
  - `test_stream_path_rejects_leading_slash(self) -> None [line 405]`
  - `test_stream_path_rejects_dotdot(self) -> None [line 409]`
  - `test_stream_path_rejects_bad_account(self) -> None [line 413]`
  - `test_stream_path_rejects_non_slug_stream(self) -> None [line 421]`
  - `test_schema_version_bumped_to_2(self) -> None [line 425]`
- `TestAgentIsNotAPartitionKey` — line 429
  - `test_stream_path_has_no_agent_parameter(self) -> None [line 432]`
  - `test_two_agents_share_one_stream_file(self) -> None [line 436]`
- `TestKindConstants` — line 446
  - `test_all_kinds_defined(self) -> None [line 447]`
- `TestMigrationProvenanceMarker` — line 463
  - `test_chat2_event_payload_requires_provenance(self) -> None [line 468]`
  - `test_provenance_fields(self) -> None [line 472]`
  - `test_provenance_rejects_empty_source_or_session(self) -> None [line 482]`
  - `test_chat2_event_payload_roundtrip(self) -> None [line 488]`
  - `test_session_id_is_legacy_metadata_not_envelope_field(self) -> None [line 510]`
  - `test_chat2_event_never_carries_topic_id(self) -> None [line 524]`

**Functions**

- `_event(**overrides) -> TopicEvent` — line 236

## `tests/topics/test_streams.py`

> Tests for src/topics/streams.py - the EventStore seam over account-scoped

**Imports**

- `__future__: annotations`
- `datetime: datetime, timedelta, timezone`
- `pathlib: Path`
- `pytest`
- `src.storage.interfaces: EventStore`
- `src.topics.schemas: INBOX_STREAM, KIND_TOPIC_ARCHIVED, KIND_TOPIC_CREATED, KIND_TOPIC_LINK, TopicArchivedPayload, TopicCreatedPayload, TopicEvent, TopicLinkPayload, inbox_path, stream_path`
- `src.topics.streams: JsonlEventStore, StreamArchivedError, StreamError, StreamNotFoundError`

**Classes**

- `TestInboxStream` — line 113
  - `test_inbox_created_on_first_write(self, store: JsonlEventStore) -> None [line 114]`
  - `test_inbox_is_default_destination_no_create_required(self, store: JsonlEventStore) -> None [line 119]`
  - `test_inbox_preserves_append_order(self, store: JsonlEventStore) -> None [line 128]`
  - `test_create_stream_rejects_inbox(self, store: JsonlEventStore) -> None [line 134]`
- `TestTopicStreamCreation` — line 144
  - `test_topic_stream_created_on_topic_created(self, store: JsonlEventStore) -> None [line 145]`
  - `test_topic_created_lands_in_its_own_stream(self, store: JsonlEventStore) -> None [line 151]`
  - `test_append_to_unknown_stream_rejected(self, store: JsonlEventStore) -> None [line 158]`
  - `test_error_is_a_stream_error(self) -> None [line 164]`
  - `test_create_stream_explicit_and_idempotent(self, store: JsonlEventStore) -> None [line 168]`
  - `test_stream_exists(self, store: JsonlEventStore) -> None [line 176]`
  - `test_topic_created_slug_must_match_stream(self, store: JsonlEventStore) -> None [line 181]`
  - `test_link_target_must_match_stream(self, store: JsonlEventStore) -> None [line 189]`
- `TestArchiveFreeze` — line 203
  - `_active_topic(self, store: JsonlEventStore, slug: str = 'my-topic') -> None [line 204]`
  - `test_archive_is_event_driven(self, store: JsonlEventStore) -> None [line 207]`
  - `test_archived_stream_rejects_new_writes(self, store: JsonlEventStore) -> None [line 216]`
  - `test_archived_stream_still_queryable(self, store: JsonlEventStore) -> None [line 225]`
  - `test_archive_state_survives_restart(self, tmp_path: Path) -> None [line 236]`
  - `test_inbox_never_archived(self, store: JsonlEventStore) -> None [line 245]`
- `TestNoAgentPartitioning` — line 259
  - `test_two_agents_share_one_topic_stream(self, store: JsonlEventStore) -> None [line 260]`
  - `test_agent_never_part_of_the_path(self, store: JsonlEventStore) -> None [line 272]`
- `TestReadEvents` — line 287
  - `test_order_and_limit(self, store: JsonlEventStore) -> None [line 288]`
  - `test_time_bounds_inclusive(self, store: JsonlEventStore) -> None [line 298]`
  - `test_missing_stream_yields_nothing(self, store: JsonlEventStore) -> None [line 319]`
  - `test_roundtrip_across_instances(self, tmp_path: Path) -> None [line 323]`
  - `test_persisted_line_is_json_and_append_only(self, store: JsonlEventStore) -> None [line 332]`
- `TestListStreams` — line 351
  - `test_empty_account(self, store: JsonlEventStore) -> None [line 352]`
  - `test_returns_inbox_and_topic_streams_sorted(self, store: JsonlEventStore) -> None [line 355]`
- `TestStoreContract` — line 367
  - `test_implements_eventstore_abc(self, store: JsonlEventStore) -> None [line 368]`
  - `test_account_mismatch_rejected(self, store: JsonlEventStore) -> None [line 371]`
  - `test_stream_field_mismatch_rejected(self, store: JsonlEventStore) -> None [line 377]`
  - `test_non_topic_event_rejected(self, store: JsonlEventStore) -> None [line 383]`

**Functions**

- `_created(slug: str = 'my-topic', name: str = 'My Topic', agent: str = 'lucy') -> TopicEvent` — line 50
- `_link(slug: str, event_ids = None, agent: str = 'lucy') -> TopicEvent` — line 60
- `_archived(slug: str, reason: str = 'done', agent: str = 'lucy') -> TopicEvent` — line 76
- `_inbox_event(agent: str = 'lucy') -> TopicEvent` — line 86
- `store(tmp_path: Path) -> JsonlEventStore` — line 104

## `tmp_debug_heredoc.py`

**Imports**

- `json`
- `src.config_manager: ConfigManager`
- `src.handlers.command_execution_handler2: CommandExecutionHandler2`

## `tools/repo_index.py`

> Generate a compact structural index of a Python repository.

**Imports**

- `__future__: annotations`
- `argparse`
- `ast`
- `dataclasses: dataclass, field`
- `pathlib: Path`
- `subprocess`

**Classes**

- `ClassInfo` — line 38
- `ModuleInfo` — line 46

**Functions**

- `expr_name(node: ast.AST) -> str` — line 54
- `format_arguments(args: ast.arguments) -> str` — line 62
- `function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str` — line 109
- `first_docstring_line(node: ast.AST) -> str | None` — line 119
- `parse_module(path: Path) -> ModuleInfo | None` — line 128
- `should_exclude(path: Path, root: Path) -> bool` — line 176
- `find_python_files(root: Path) -> list[Path]` — line 185
- `git_commit(root: Path) -> str | None` — line 195
- `render_module(info: ModuleInfo, root: Path) -> list[str]` — line 209
- `generate_index(root: Path) -> str` — line 258
- `parse_args() -> argparse.Namespace` — line 301
- `main() -> None` — line 323

---

Indexed 331 Python files.
