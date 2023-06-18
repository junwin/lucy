from abc import ABC, abstractmethod

class MessageProcessorInterface(ABC):

    @abstractmethod
    def process_message(self, agent_name:str, account_name:str, message:str, conversationId="0", context_name='', second_agent_name='') -> str:
        pass

