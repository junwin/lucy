import logging
import re
from typing import List, Dict, Set

from src.api_helpers import ask_question, get_completion
from src.presets.preset_handler import PresetHandler
from src.summarize_request_handler import SummarizeRequestHandler
from src.summarize_text_content import SummarizeTextContent
from src.folder_processor import FolderProcessor



class MessagePreProcess:

    def __init__(self):
        self.preset_handler = PresetHandler()
        self.summarize_request_handler = SummarizeRequestHandler()

    def alternative_processing(self, message: str, conversationId : str, agent_name:str, account_name:str):
        response = {"action": None, "result": None}
        
        if message == "please summarize":
            myResult = self.summarize_request_handler.process_summarize_request(message, conversationId, agent_name, account_name)
            response["action"] = "return"
            response["result"] = myResult
        elif message.startswith("/"):
            response["action"] = "return"
            response["result"] = self.preset_handler.process_preset_prompt(message, agent_name, account_name)
        elif message.startswith("!folder_summarize"):
            response["action"] = "return"
            response["result"] = self.do_folder_summarize(agent_name, message)  
        elif "!inline_file_path:" in message:
            response["action"] = "updatemessage"
            response["result"] = self.process_inline_file(message)
 
        return response
    
    def process_inline_file(self, message: str) -> str:
        file_paths = re.findall(r"file_path:(\S+)", message)
        
        for file_path in file_paths:
            with open(file_path, 'r') as file:
                file_contents = file.read()
                message = message.replace(f"file_path:{file_path}", file_contents, 1)
        
        return message



    def read_file_as_string(self, file_path: str) -> str:
        with open(file_path, 'r') as file:
            return file.read()  
        
    def do_folder_summarize(self, agent_name: str, message:str) ->str:
        my_params = self.get_action_and_parameters( message)
        input_path = my_params["input_path"]
        output_path = my_params["output_path"]
        file_type = my_params["file_type"] 
        summarizer = SummarizeTextContent(output_path, agent_name, "test")
        processor = FolderProcessor(input_path, file_type, summarizer)
        processor.process_folder()
        return summarizer.get_digest()
    
    def get_action_and_parameters(self, input_text: str) -> Dict[str, str]:
        # Extract action
        action = re.match(r"!(\w+),", input_text)
        action = action.group(1) if action else None

        # Extract parameters
        parameters = re.findall(r'(\w+)\s*=\s*"([^"]*)"', input_text)

        params_dict = {'action': action}
        params_dict.update(dict(parameters))
        return params_dict

