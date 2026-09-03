# container_config.py

# injector is optional for unit tests that only exercise Flask endpoints.
try:
    from injector import Injector
    from injector import Module, provider, singleton
except ModuleNotFoundError:  # pragma: no cover
    Injector = None  # type: ignore
    class Module:  # type: ignore
        pass
    def provider(fn):  # type: ignore
        return fn
    def singleton(fn):  # type: ignore
        return fn

from src.config_manager import ConfigManager
from src.agent import AgentManager
from src.storage_paths.storage_paths import StoragePaths  
from src.storage.base import Storage
from src.storage.interfaces import ContextStore, DocumentStore, EmbeddingStore, TasklistStore
from src.storage.json_file_storage import JsonFileStorage
from src.storage.primitives_embedding_store import build_primitives_embedding_store

from src.handlers.handler_registry import HandlerRegistry
from src.handlers.registry_bootstrap import build_registry
from src.message_processors.processor_factory import ProcessorFactory
from src.message_processors.message_processor_interface import ProcessorFactoryInterface        
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.prompt_builders.prompt_builder import PromptBuilder

from src.message_endpoints.ask_request_handler import AskRequestHandler

from galet.adapter_interface import LLMAdapter
from galet.embedding_router import EmbeddingRouter
from galet.interface import LLMApi
from galet.mistral_embedding import MistralEmbeddingApi
from galet.openai_embedding import OpenAIEmbeddingApi
from galet.openai_responses_adapter import OpenAIResponsesAdapter
from galet.router_api import RouterApi
from galet.settings import Settings

from src.chat2.facade import Chat2Store
from src.chat2.adapters.jfs_adapter import JfsChat2Primitives

from src.message_processors.automation_processor import AutomationProcessor

from src.metrics import MetricsRepository

from src.embeddings.facade import EmbeddingFacade


config = ConfigManager("config.json")


class ConfigManagerModule(Module):
    @provider
    @singleton
    def provide_prompts(self) -> ConfigManager:
        return ConfigManager("config.json")


class AgentManagerModule(Module):
    @provider
    @singleton
    def provide_agent_manager(self) -> AgentManager:
        strict = config.get("strict_agent_fields", True)
        return AgentManager(config.get("agents_path"), strict_fields=strict)


class StorageModule(Module):
    @provider
    @singleton
    def provide_storage(self) -> Storage:
        """Provide the Storage implementation used across the app.

        Config key:
          - storage_root_path
          - storage_base_path

        Notes:
          - JsonFileStorage uses a single root folder. Chats are stored under
            <storage_root_path>/<storage_base_path>/chats/...
          - storage_base_path is treated as a subfolder name under
            storage_root_path (no absolute paths, no '..').
        """
        import os
        from pathlib import Path

        from src.storage.json_file_storage_parts.tasklists import DEFAULT_RUN_TTL_DAYS


        storage_root_path = config.get("storage_root_path") or "/home/junwin/lucydata"
        storage_namespace = config.get("storage_namespace") or "data"

        storage_paths = StoragePaths(
            storage_root_path=storage_root_path,
            storage_namespace=storage_namespace,
        )

        ttl_days = (config.get("tasklists", {}) or {}).get("run_ttl_days", DEFAULT_RUN_TTL_DAYS)
        return JsonFileStorage(storage_paths, tasklist_run_ttl_days=ttl_days)

    @provider
    @singleton
    def provide_context_store(self, storage: Storage) -> ContextStore:
        """Provide the same JsonFileStorage instance bound to ContextStore."""
        return storage

    @provider
    @singleton
    def provide_tasklist_store(self, storage: Storage) -> TasklistStore:
        return storage

    @provider
    @singleton
    def provide_document_store(self, storage: Storage) -> DocumentStore:
        """Provide the same JsonFileStorage instance bound to DocumentStore."""
        return storage

    @provider
    @singleton
    def provide_embedding_store(self, storage: Storage) -> EmbeddingStore:
        """Provide the EmbeddingStore, optionally backed by the generic store.

        Config key: ``embedding_store_backend`` (optional). When unset or
        empty, the container keeps today's behavior — the shared
        JsonFileStorage instance (byte-identical on disk).

        - ``file``   -> ``PrimitivesEmbeddingStore`` over
          ``FileChat2Primitives`` rooted at
          ``<storage_root_path>/<storage_namespace>``, the same on-disk
          layout as JsonFileStorage (interchangeable).
        - ``sqlite`` -> ``PrimitivesEmbeddingStore`` over
          ``SqliteChat2Primitives`` at ``embedding_store_db_path`` (default
          ``<storage_root_path>/<storage_namespace>/embeddings.sqlite``).
        - ``sqlite_vec`` -> ``Vec0EmbeddingStore`` (sqlite-vec vec0 KNN) at
          ``embedding_store_db_path`` with the extension loaded from
          ``sqlite_vec_extension_path`` (default
          ``/usr/local/lib/sqlite-vec/vec0.so``).

        Any other value raises ``ValueError`` so a misconfiguration fails
        loudly at container build time instead of silently writing
        embeddings to the wrong place.
        """
        backend = str(config.get("embedding_store_backend", "") or "").strip().lower()
        if not backend:
            return storage
        if backend not in ("file", "sqlite", "sqlite_vec"):
            raise ValueError(
                "Unknown embedding_store_backend %r: expected 'file', 'sqlite' or 'sqlite_vec'"
                % backend
            )
        return build_primitives_embedding_store(config)

    @provider
    @singleton
    def provide_chat2_store(self, storage: Storage) -> Chat2Store:
        backend = str(config.get("chat2_store_backend", "") or "").strip().lower()
        if backend == "sqlite":
            from pathlib import Path

            from src.chat2.sqlite import SqliteChat2Primitives

            db_path = config.get("chat2_store_db_path")
            if not db_path:
                storage_root = config.get("storage_root_path") or "/home/junwin/lucydata"
                storage_namespace = config.get("storage_namespace") or "data"
                db_path = str(Path(storage_root) / storage_namespace / "chat2.sqlite")
            return Chat2Store(SqliteChat2Primitives(db_path))
        if not backend or backend == "jsonl":
            return Chat2Store(JfsChat2Primitives(storage))
        raise ValueError(
            "Unknown chat2_store_backend %r: expected 'jsonl' or 'sqlite'" % backend
        )



class MetricsModule(Module):
    @provider
    @singleton
    def provide_metrics_repository(self) -> MetricsRepository:
        """Provide the MetricsRepository bound to the runs log path.

        Priority: explicit ``metrics_runs_log_path``, then the design default
        ``<storage_root_path>/<storage_namespace>/metrics/runs.jsonl``, which
        matches ``StoragePaths(...).base / metrics / runs.jsonl``.
        """
        import os

        path = config.get("metrics_runs_log_path")
        if not path:
            storage_root = config.get("storage_root_path") or "/home/junwin/lucydata"
            storage_namespace = config.get("storage_namespace") or "data"
            path = os.path.join(
                str(storage_root),
                str(storage_namespace),
                "metrics",
                "runs.jsonl",
            )
        return MetricsRepository(path)


class EmbeddingModule(Module):
    @provider
    @singleton
    def provide_embedding_facade(self) -> EmbeddingFacade:
        """Provide the embedding facade for digest search and other uses."""
        settings = Settings(
            credential_path=config.get("credential_path"),
            ollama_base_url=config.get("ollama_base_url"),
        )
        return EmbeddingFacade(
            embedding_api=EmbeddingRouter(
                openai_api=OpenAIEmbeddingApi(settings=settings),
                mistral_api=MistralEmbeddingApi(settings=settings),
            )
        )


class HandlerRegistryModule(Module):
    @provider
    @singleton
    def provide_handler_registry(self) -> HandlerRegistry:
        return build_registry()


class PromptBuilderModule(Module):
    @provider
    @singleton
    def provide_prompt_builder(
        self,
        agent_manager: AgentManager,
        config: ConfigManager,
        storage: Storage,
        chat2_store: Chat2Store,
        embedding_facade: EmbeddingFacade,
    ) -> PromptBuilderInterface:
        return PromptBuilder(
            agent_manager=agent_manager,
            config=config,
            storage=storage,
            chat2_store=chat2_store,
            embedding_facade=embedding_facade,
        )


class LLMModule(Module):
    @provider
    @singleton
    def provide_llm_api(self) -> LLMApi:
        settings = Settings(
            credential_path=config.get("credential_path"),
            ollama_base_url=config.get("ollama_base_url"),
        )
        return RouterApi(settings=settings)

    @provider
    @singleton
    def provide_llm_adapter(self, api: LLMApi) -> LLMAdapter:
        # Default adapter: OpenAI Responses protocol glue
        return OpenAIResponsesAdapter(api)


class AutomationProcessorModule(Module):
    @provider
    @singleton
    def provide_automation_processor(
        self,
        config: ConfigManager,
        registry: HandlerRegistry,
        storage: Storage,
        prompt_builder: PromptBuilderInterface,
        chat2_store: Chat2Store,
        llm_adapter: LLMAdapter,
        agent_manager: AgentManager,
    ) -> AutomationProcessor:
        """Provide AutomationProcessor as a singleton so ProcessorFactory can
        construct it for agents whose message_processor is "automation_processor".

        Uses the same Optional dependency pattern as chat2_store to avoid
        circular dependencies: AutomationProcessor does not import FCP at
        module level — it resolves FCP lazily via ProcessorFactory.
        """
        return AutomationProcessor(
            config=config,
            registry=registry,
            storage=storage,
            prompt_builder=prompt_builder,
            chat2_store=chat2_store,
            llm_adapter=llm_adapter,
            agent_manager=agent_manager,
        )


class ProcessorFactoryModule(Module):
    @provider
    @singleton
    def provide_processor_factory(self, injector: Injector) -> ProcessorFactoryInterface :
        return ProcessorFactory(injector)


class EndpointHandlersModule(Module):
    @provider
    @singleton
    def provide_ask_request_handler(
        self,
        agent_manager: AgentManager,
        config: ConfigManager,
        storage: Storage,
        processor_factory: ProcessorFactory,
        chat2_store: Chat2Store,
    ) -> AskRequestHandler:
        return AskRequestHandler(
            agent_manager=agent_manager,
            config=config,
            storage=storage,
            processor_factory=processor_factory,
            chat2_store=chat2_store,
        )


def configure_container():
    if Injector is None:  # pragma: no cover
        return None
    container = Injector(
        [
            AgentManagerModule(),
            ConfigManagerModule(),
            StorageModule(),
            MetricsModule(),
            EmbeddingModule(),
            HandlerRegistryModule(),
            ProcessorFactoryModule(),
            PromptBuilderModule(),
            LLMModule(),
            AutomationProcessorModule(),
            EndpointHandlersModule(),
        ]
    )
    return container


container = configure_container()
