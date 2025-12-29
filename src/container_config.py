# container_config.py

from injector import Injector
from injector import Module, provider, singleton, inject

from src.config_manager import ConfigManager
from src.agent_manager import AgentManager



from src.storage.base import Storage
from src.storage.json_file_storage import JsonFileStorage

from src.handlers.handler_registry import HandlerRegistry
from src.handlers.registry_bootstrap import build_registry
from src.message_processors.processor_factory import ProcessorFactory
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.prompt_builders.prompt_builder import PromptBuilder
from src.context.context_manager import ContextManager
from src.message_endpoints.ask_request_handler import AskRequestHandler


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

        Primary config key:
          - chat_base_path

        Backwards compatibility:
          - fall back to completion_base_path if chat_base_path is not set.
        """
        base_path = config.get("chat_base_path") or config.get("completion_base_path")
        return JsonFileStorage(base_path)


class HandlerRegistryModule(Module):
    @provider
    @singleton
    def provide_handler_registry(self) -> HandlerRegistry:
        return build_registry()





class ContextManagerModule(Module):
    @provider
    @singleton
    def provide_context_manager(self, config: ConfigManager) -> ContextManager:
        return ContextManager(config)


class PromptBuilderModule(Module):
    @provider
    @singleton
    def provide_prompt_builder(self, pb: PromptBuilder) -> PromptBuilderInterface:
        return pb


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
            ContextManagerModule(),
            EndpointHandlersModule(),
        ]
    )
    return container


container = configure_container()
