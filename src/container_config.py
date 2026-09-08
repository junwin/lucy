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
from src.coala_memory.semantic import SemanticMemory, SqliteVecSemanticMemory
from src.coala_memory.episodic import EpisodicMemory, Chat2EpisodicMemory
from src.coala_memory.procedural import ProceduralMemory, ContextProceduralMemory

from src.handlers.handler_registry import HandlerRegistry
from src.handlers.registry_bootstrap import build_registry
from src.message_processors.processor_factory import ProcessorFactory
from src.message_processors.message_processor_interface import ProcessorFactoryInterface
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.prompt_builders.coala_prompt_builder import CoALAPromptBuilder
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
        from src.storage.json_file_storage_parts.tasklists import DEFAULT_RUN_TTL_DAYS

        storage_root_path = config.get("storage_root_path") or "/home/junwin/lucydata"
        storage_namespace = config.get("storage_namespace") or "data"
        storage_paths = StoragePaths(
            storage_root_path=storage_root_path,
            storage_namespace=storage_namespace,
        )
        ttl_days = (config.get("tasklists", {}) or {}).get(
            "run_ttl_days", DEFAULT_RUN_TTL_DAYS
        )
        return JsonFileStorage(storage_paths, tasklist_run_ttl_days=ttl_days)

    @provider
    @singleton
    def provide_context_store(self, storage: Storage) -> ContextStore:
        return storage

    @provider
    @singleton
    def provide_tasklist_store(self, storage: Storage) -> TasklistStore:
        return storage

    @provider
    @singleton
    def provide_document_store(self, storage: Storage) -> DocumentStore:
        return storage

    @provider
    @singleton
    def provide_embedding_store(self, storage: Storage) -> EmbeddingStore:
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


class CoALAMemoryModule(Module):
    @provider
    @singleton
    def provide_semantic_memory(
        self,
        embedding_facade: EmbeddingFacade,
        embedding_store: EmbeddingStore,
    ) -> SemanticMemory:
        return SqliteVecSemanticMemory(
            embedding_facade=embedding_facade,
            embedding_store=embedding_store,
        )

    @provider
    @singleton
    def provide_episodic_memory(
        self,
        chat2_store: Chat2Store,
    ) -> EpisodicMemory:
        return Chat2EpisodicMemory(chat2_store)

    @provider
    @singleton
    def provide_procedural_memory(
        self,
        context_store: ContextStore,
    ) -> ProceduralMemory:
        return ContextProceduralMemory(context_store)


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
        embedding_facade: EmbeddingFacade,
        embedding_store: EmbeddingStore,
        semantic_memory: SemanticMemory,
        episodic_memory: EpisodicMemory,
        procedural_memory: ProceduralMemory,
    ) -> PromptBuilderInterface:
        return CoALAPromptBuilder(
            agent_manager=agent_manager,
            config=config,
            storage=storage,
            embedding_facade=embedding_facade,
            embedding_store=embedding_store,
            semantic_memory=semantic_memory,
            episodic_memory=episodic_memory,
            procedural_memory=procedural_memory,
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
    def provide_processor_factory(self, injector: Injector) -> ProcessorFactoryInterface:
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
    return Injector(
        [
            AgentManagerModule(),
            ConfigManagerModule(),
            StorageModule(),
            MetricsModule(),
            EmbeddingModule(),
            CoALAMemoryModule(),
            HandlerRegistryModule(),
            ProcessorFactoryModule(),
            PromptBuilderModule(),
            LLMModule(),
            AutomationProcessorModule(),
            EndpointHandlersModule(),
        ]
    )


container = configure_container()
