# container_config.py

from injector import Injector
from injector import Module, provider, singleton

from src.config_manager import ConfigManager
from src.agent import AgentManager

from src.storage.base import Storage
from src.storage.json_file_storage import JsonFileStorage

from src.handlers.handler_registry import HandlerRegistry
from src.handlers.registry_bootstrap import build_registry
from src.message_processors.processor_factory import ProcessorFactory
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.prompt_builders.prompt_builder import PromptBuilder

from src.message_endpoints.ask_request_handler import AskRequestHandler

from src.llm.adapter_interface import LLMAdapter
from src.llm.openai_responses_adapter import OpenAIResponsesAdapter
from src.llm.openai_responses import OpenAIResponsesApi
from src.llm.interface import LLMApi


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
        return AgentManager(config.get("agents_path"))


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
        storage_base_path = config.get("storage_base_path") or "data"

        base_str = os.path.expanduser(str(storage_base_path)).strip()
        base = Path(base_str)
        if base.is_absolute() or ".." in base.parts:
            raise ValueError(
                "storage_base_path must be a relative subfolder name (no absolute paths or '..')"
            )

        root = Path(os.path.expanduser(str(storage_root_path)))
        effective_base_path = root / base

        return JsonFileStorage(str(effective_base_path))


class HandlerRegistryModule(Module):
    @provider
    @singleton
    def provide_handler_registry(self) -> HandlerRegistry:
        return build_registry()


class PromptBuilderModule(Module):
    @provider
    @singleton
    def provide_prompt_builder(self, pb: PromptBuilder) -> PromptBuilderInterface:
        return pb


class LLMModule(Module):
    @provider
    @singleton
    def provide_llm_api(self) -> LLMApi:
        # Default LLM transport: OpenAI Responses API
        return OpenAIResponsesApi()

    @provider
    @singleton
    def provide_llm_adapter(self, api: LLMApi) -> LLMAdapter:
        # Default adapter: OpenAI Responses protocol glue
        return OpenAIResponsesAdapter(api)


class ProcessorFactoryModule(Module):
    @provider
    @singleton
    def provide_processor_factory(self, injector: Injector) -> ProcessorFactory:
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
    ) -> AskRequestHandler:
        return AskRequestHandler(
            agent_manager=agent_manager,
            config=config,
            storage=storage,
            processor_factory=processor_factory,
        )


def configure_container():
    container = Injector(
        [
            AgentManagerModule(),
            ConfigManagerModule(),
            StorageModule(),
            HandlerRegistryModule(),
            ProcessorFactoryModule(),
            PromptBuilderModule(),
            LLMModule(),
            EndpointHandlersModule(),
        ]
    )
    return container


container = configure_container()
