import json
from typing import List, Dict, Set
from datetime import datetime
from time import time
from src.keywords import Keywords
from src.completion.completion import Completion
from src.completion.message import Message
from src.completion.completion_manager import CompletionManager
from src.completion.utils import get_id, get_complete_path
import logging


class CompletionStore:
    def __init__(self, base_path):
        self.base_path = base_path
        self.completion_managers = dict()

    def get_manager_id(self, agent_name:str, account_name:str) -> str:
        return agent_name + "_" + account_name  

    def get_completion_manager(self, agent_name, account_name, language_code="en") -> CompletionManager:
        manager_id = self.get_manager_id(agent_name, account_name)
        logging.info(f'CompletionStore get: {manager_id}')

        if self.completion_managers.get(manager_id) is None:
            completion_manager = CompletionManager(self.base_path, agent_name, account_name, language_code)
            completion_manager.load()
            self.completion_managers[manager_id] = completion_manager
        return self.completion_managers[manager_id]

