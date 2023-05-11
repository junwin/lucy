# container_config.py

from injector import Injector
from injector import Module, provider, singleton
from injector import inject
from src.preset_prompts import PresetPrompts
from src.config_manager import ConfigManager
from src.message_preProcess import MessagePreProcess
from src.agent_manager import AgentManager
from src.prompt_store import PromptStore
from src.response_handler import FileResponseHandler 




config = ConfigManager('config.json')


class ConfigManagerModule(Module):
    @provider
    @singleton
    def provide_prompts(self) -> ConfigManager:
        return ConfigManager('config.json')

class PromptStoreModule(Module):
    @provider
    @singleton
    def provide_prompts(self) -> PromptStore:
        return PromptStore(config.get('prompt_base_path'))

class PresetPromptsModule(Module):
    @provider
    @singleton
    def provide_prompts(self) -> PresetPrompts:
        return PresetPrompts(config.get('preset_path'))

class AgentManagerModule(Module):
    @provider
    @singleton
    def provide_agent_manager(self) -> AgentManager:
        return AgentManager(config.get('agents_path'))



class PreProcessModule(Module):
    @provider
    @singleton
    @inject
    def provide_message_preprocess(self, preset_prompts: PresetPrompts) -> MessagePreProcess:
        return MessagePreProcess(preset_prompts)
    
class FileResponseHandlerModule(Module):
    @provider
    @singleton
    def provide_agent_manager(self) -> FileResponseHandler:
        return FileResponseHandler(config.get('account_output_path'), 1000)

def configure_container():
    container = Injector([AgentManagerModule(), PresetPromptsModule(), PreProcessModule(), PromptStoreModule(), 
                          FileResponseHandlerModule(), ConfigManagerModule()])
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
