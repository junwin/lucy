# container_config.py

from injector import Injector
from injector import Module, provider, singleton
from injector import inject
from src.config_manager import ConfigManager
from src.agent_manager import AgentManager
from src.response_handler import FileResponseHandler
from src.source_code_response_handler import SourceCodeResponseHandler
from src.completion.completion_store import CompletionStore





config = ConfigManager('config.json')


class ConfigManagerModule(Module):
    @provider
    @singleton
    def provide_prompts(self) -> ConfigManager:
        return ConfigManager('config.json')




class AgentManagerModule(Module):
    @provider
    @singleton
    def provide_agent_manager(self) -> AgentManager:
        return AgentManager(config.get('agents_path'))

class CompletionStoreModule(Module):
    @provider
    @singleton
    def provide_completion_store(self) -> CompletionStore:
        base_path = config.get('completion_base_path')  
        return CompletionStore(base_path)



    
class FileResponseHandlerModule(Module):
    @provider
    @singleton
    def provide_agent_manager(self) -> FileResponseHandler:
        return FileResponseHandler(config.get('account_output_path'), 5000)
    
class SourceCodeResponseHandlerModule(Module):
    @provider
    @singleton
    def provide_agent_manager(self) -> SourceCodeResponseHandler:
        return SourceCodeResponseHandler(config.get('account_output_path'), 5000)

def configure_container():
    container = Injector([AgentManagerModule(), FileResponseHandlerModule(), SourceCodeResponseHandlerModule(), ConfigManagerModule(), CompletionStoreModule()])
    return container

container = configure_container()


    
#class MessageProcessorStoreModule(Module):
#    @provider
#    @singleton
#    def provide_agent_manager(self) -> MessageProcessorStore:
 #       return MessageProcessorStore()

#class MessageProcessor:
#    @inject
#    def __init__(self, agent_prompt_manager: PromptManager, account_prompt_manager: PromptManager, handler: FileResponseHandler, context_type: str):
#        ...
