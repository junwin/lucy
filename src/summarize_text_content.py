import os
import logging
from src.api_helpers import ask_question, get_completion

from src.config_manager import ConfigManager
#from src.message_processor_store import MessageProcessorStore

class SummarizeTextContent:
    def __init__(self, account_output_path:str, agent:dict, account_name:str, max_words=500):
        self.max_words = max_words
        self.output_folder = account_output_path
        self.agent = agent
        self.account_name = account_name
        self.request_instruction = f'Summarize the content of the following text or code in less then {max_words} words:'
        self.digest = ''

    def handle_response(self, content: str, file_name:str) ->str:
        #message_processor_store = MessageProcessorStore()
        #agent_name = self.agent['name']
        #processor = message_processor_store.get_message_processor(agent_name, self.account_name)
        full_request = self.request_instruction + ' ' + content  
        logging.info(f'Processing message prompt: {content}')
        response = get_completion(full_request, self.agent['temperature'], self.agent['model'] )  
        #response = processor.process_message(self.request_instruction, self.conversation_id)
        self.persist_response(response, file_name)
        self.digest += response

    def persist_response(self, response:str, file_name:str):
        # check self.output folder exists if not create it
        if not os.path.exists(self.output_folder):
            try:
                os.makedirs(self.output_folder)
            except Exception as e:
                print(f"Error while creating directory: {str(e)}")
                return

        # strip filename of any existing extension
        base_file_name = os.path.splitext(file_name)[0]

        # save response to file
        output_file_path = os.path.join(self.output_folder, base_file_name + '.txt')
        try:
            with open(output_file_path, 'w') as file:
                file.write(response)
        except Exception as e:
            print(f"Error while writing to file: {str(e)}")

    def get_digest(self) ->str:
        return self.digest