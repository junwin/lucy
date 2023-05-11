import logging
import re
from typing import List, Dict, Set
from src.prompt_manager import PromptManager
from src.response_handler import ResponseHandler
from src.response_handler import FileResponseHandler
from src.agent_manager import AgentManager
from src.api_helpers import ask_question, get_completion
from src.preset_prompts import PresetPrompts
from src.preset_handler import PresetHandler
from src.summarize_request_handler import SummarizeRequestHandler
from src.summarize_text_content import SummarizeTextContent
from src.folder_processor import FolderProcessor


class MessagePreProcess:

    def __init__(self, preset_prompts: PresetPrompts):
        self.preset_prompts = preset_prompts
        self.preset_handler = PresetHandler(self.preset_prompts)
        self.summarize_request_handler = SummarizeRequestHandler()

    def alternative_processing(self, message: str, conversationId : str, agent, account_prompt_manager: PromptManager):
        response = {"action": None, "result": None}
        
        if message == "please summarize":
            myResult = self.summarize_request_handler.process_summarize_request(message, conversationId, account_prompt_manager)
            response["action"] = "return"
            response["result"] = myResult
        elif message.startswith("/"):
            response["action"] = "return"
            response["result"] = self.preset_handler.process_preset_prompt(message, account_prompt_manager)
        elif message.startswith("!folder_summarize"):
            response["action"] = "return"
            response["result"] = self.do_folder_summarize(agent, message)   
 
        return response
    

    def do_folder_summarize(self, agent: dict, message:str) ->str:
        my_params = self.get_action_and_parameters( message)
        input_path = my_params["input_path"]
        output_path = my_params["output_path"]
        file_type = my_params["file_type"] 
        summarizer = SummarizeTextContent(output_path, agent, "test")
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

