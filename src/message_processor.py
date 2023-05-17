import openai
import logging
import re
from injector import Injector

from src.container_config import container
from src.config_manager import ConfigManager  
from src.response_handler import FileResponseHandler
from src.source_code_response_handler import SourceCodeResponseHandler
from src.agent_manager import AgentManager
from src.message_preProcess import MessagePreProcess
from src.api_helpers import ask_question, get_completion

from src.prompt_builders.prompt_builder import PromptBuilder
# from src.completion.completion_manager import CompletionManager
from src.completion.completion_store import CompletionStore
# from src.completion.completion import Completion
# from src.completion.message import Message


class MessageProcessor:
    def __init__(self ):
        # self.name = name
        agent_manager = container.get(AgentManager)
        self.config = container.get(ConfigManager) 
        prompt_base_path=self.config.get('prompt_base_path')  
        self.seed_conversations = []
        


    def process_message(self, agent_name:str, account_name:str, message, conversationId="0") -> str:
        logging.info(f'Processing message inbound: {message}')
        agent_manager = container.get(AgentManager)
        agent = agent_manager.get_agent(agent_name)
        model = agent["model"]
        temperature = agent["temperature"]
        context_type = agent["select_type"]

        completion_manager_store = container.get(CompletionStore)
        account_completion_manager = completion_manager_store.get_completion_manager(agent_name, account_name, agent['language_code'][:2])


        # Check for alternative processing
        preprocessor = MessagePreProcess()
        myResult = preprocessor.alternative_processing(message, conversationId, agent_name, account_name)

        if myResult["action"] == "return":
            return myResult["result"]
        if myResult["action"] == "storereturn":
            self.add_response_message(conversationId,  message, myResult["result"])
            return myResult["result"]
        elif myResult["action"] == "continue":
             message = myResult["result"]
        elif myResult["action"] == "swapseed":
             seed_info = myResult["result"]
             seed_name=seed_info["seedName"]
             seed_paramters=seed_info["values"]
        elif myResult["action"] == "updatemessage":
             message =  myResult["result"]
 

        prompt_builder = PromptBuilder()
        conversation = prompt_builder.build_prompt( message, conversationId, agent_name, account_name, context_type)
       
       
        # coversations [ {role: user, content: message} ]
        logging.info(f'Processing message prompt: {conversation}')

        response = ask_question(conversation, model, temperature)  #string response

        logging.info(f'Processing code response: {response}')
        if 'program_language' in response and 'file_path' in response:
            handler = container.get(SourceCodeResponseHandler)
        else:
            handler = container.get(FileResponseHandler)   

        response = handler.handle_response(account_name, response)  # Use the handler instance
            

        logging.info(f'Processing message response: {response}')

        if agent['save_reposnses']:
            if message is not self.is_none_or_empty(message):
                account_completion_manager.create_store_completion(conversationId, message, response)
                account_completion_manager.save()

        logging.info(f'Processing message complete: {message}')

        return response
    
    def is_none_or_empty(self, string):
        return string is None or string.strip() == ""
    


    def remove_utc_timestamp(self, data):
        new_data = []
        for item in data:
            new_item = {"role": item["role"], "content": item["content"]}
            new_data.append(new_item)
        return new_data
    
   
    
    def get_data_item(self, input_string, data_point):
        regex_pattern = f"{re.escape(data_point)}\\s*(.*)"
        result = re.search(regex_pattern, input_string)
        if result:
            return result.group(1).strip()
        else:
            return None

    
    

        

    
