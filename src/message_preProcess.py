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
 
        return response
