# container_config.py

from injector import Injector
from injector import Module, provider, singleton, inject

from src.config_manager import ConfigManager
from src.agent_manager import AgentManager
from src.response_handler import FileResponseHandler
from src.source_code_response_handler import SourceCodeResponseHandler
from src.completion.completion_store import CompletionStore
from src.node_manager import NodeManager

from src.storage.base import Storage
from src.storage.json_file_storage import JsonFileStorage

from src.handlers.handler_registry import HandlerRegistry
from src.handlers.registry_bootstrap import build_registry



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
        """
        Provide the Storage implementation used across the app.

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


class CompletionStoreModule(Module):
    @provider
    @singleton
    @inject
    def provide_completion_store(self, storage: Storage) -> CompletionStore:
        return CompletionStore(storage)


class NodeManagerModule(Module):
    @provider
    @singleton
    def provide_node_manager(self) -> NodeManager:
        return NodeManager()


class FileResponseHandlerModule(Module):
    @provider
    @singleton
    def provide_file_response_handler(self) -> FileResponseHandler:
        return FileResponseHandler(config.get("account_output_path"), 5000)


class SourceCodeResponseHandlerModule(Module):
    @provider
    @singleton
    def provide_source_code_response_handler(self) -> SourceCodeResponseHandler:
        return SourceCodeResponseHandler(config.get("account_output_path"), 5000)


def configure_container():
    container = Injector(
        [
            AgentManagerModule(),
            FileResponseHandlerModule(),
            SourceCodeResponseHandlerModule(),
            ConfigManagerModule(),
            StorageModule(),
            CompletionStoreModule(),
            NodeManagerModule(),
            HandlerRegistryModule()
        ]
    )
    return container


container = configure_container()
