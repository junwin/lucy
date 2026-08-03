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
from src.storage.json_file_storage import JsonFileStorage

from src.handlers.handler_registry import HandlerRegistry
from src.handlers.registry_bootstrap import build_registry
from src.message_processors.processor_factory import ProcessorFactory
from src.message_processors.message_processor_interface import ProcessorFactoryInterface        
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.prompt_builders.prompt_builder import PromptBuilder

from src.message_endpoints.ask_request_handler import AskRequestHandler

from src.llm.adapter_interface import LLMAdapter
from src.llm.openai_responses_adapter import OpenAIResponsesAdapter
from src.llm.interface import LLMApi
from src.llm.router_api import RouterApi

from src.chat2.facade import Chat2Store
from src.chat2.adapters.jfs_adapter import JfsChat2Primitives

from src.message_processors.automation_processor import AutomationProcessor


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


        storage_root_path = config.get("storage_root_path") or "/home/junwin/lucydata"
        storage_namespace = config.get("storage_namespace") or "data"

        storage_paths = StoragePaths(
            storage_root_path=storage_root_path,
            storage_namespace=storage_namespace,
        )

        return JsonFileStorage(storage_paths)

    @provider
    @singleton
    def provide_chat2_store(self, storage: Storage) -> Chat2Store:
        """Provide a Chat2Store backed by the same JsonFileStorage.

        Uses JfsChat2Primitives adapter to map chat2 logical keys to
        filesystem paths under <storage_base>/chat2/. This is a parallel
        storage layer — existing v1 code continues to use Storage directly.
        """
        adapter = JfsChat2Primitives(storage)
        return Chat2Store(adapter)


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
    ) -> PromptBuilderInterface:
        return PromptBuilder(
            agent_manager=agent_manager,
            config=config,
            storage=storage,
            chat2_store=chat2_store,
        )


class LLMModule(Module):
    @provider
    @singleton
    def provide_llm_api(self) -> LLMApi:
        # RouterApi dispatches to the correct backend based on model name.
        # Model names starting with "deepseek" → DeepSeekApi, else → OpenAIResponsesApi.
        return RouterApi()

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
    ) -> AutomationProcessor:
        """Provide AutomationProcessor as a singleton so it can be injected
        into FunctionCallingProcessor (step 3 of issue #37 tasklist decomposition).

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
