from typing import Dict, Tuple
from src.prompt_manager import PromptManager

class PromptStore:
    prompt_managers = {}
    def __init__(self, prompt_base_path: str):
        self.prompt_base_path = prompt_base_path

    def get_prompt_manager(self, agent_name: str, account_name: str, language_code: str):
        key = PromptManager.get_key(agent_name, account_name)
        if key not in self.prompt_managers:
            prompt_manager = PromptManager(self.prompt_base_path, agent_name, account_name, language_code[:2])
            prompt_manager.load()
            self.prompt_managers[key] = prompt_manager
        return self.prompt_managers[key]
    

    def get_key(self,agent_name, account_name):
        key = agent_name + account_name
        return key


