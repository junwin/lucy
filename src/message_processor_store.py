
import logging
import re
from src.response_handler import FileResponseHandler
from src.agent_manager import AgentManager
from src.config_manager import ConfigManager 
from src.message_processor import MessageProcessor


class MessageProcessorStore:
    processors = {}

    def get_message_processor(self, agent_name: str, account_name: str):
        processor_name = self.get_processor_name(agent_name, account_name)

        logging.info(f'get_message_processor: {processor_name}')

        if processor_name not in self.processors:       
            proc = MessageProcessor(agent_name, account_name)
            self.processors[processor_name] = proc

        return self.processors[processor_name]
    

    def get_processor_name(self, agent_name, account_name):
        processor_name = agent_name + '_' + account_name
        return processor_name