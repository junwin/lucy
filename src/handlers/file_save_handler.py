import os
import re
import yaml
import shlex
import subprocess
from typing import List, Tuple
from src.handlers.handler import Handler
from src.container_config import container
from src.config_manager import ConfigManager
from src.handlers.quokka_loki import QuokkaLoki


class FileSaveHandler(Handler):  # Concrete handler

    def handle(self, action: dict) -> List[dict]:
        action_name = action['action_name']
        if action_name != "action_save_file":
            return None
        
        file_path = action['file_path']
        file_name = action['file_name']
        file_content =  action['file_content']
        
        config = container.get(ConfigManager) 
        base_path = config.get('code_sandbox_path')

        my_path = base_path + '/' + file_path  
        result = self.save_file(self, my_path, file_name, file_content)

        my_result=[{"result": result},{ "handler": self.__class__.__name__} ].append(action)

        return my_result

        
    def save_file(self, path, filename, text_content):
        # Make sure the directory exists. If it doesn't, create it.
        if not os.path.exists(path):
            os.makedirs(path)
        
        # Join the path and filename
        file_path = os.path.join(path, filename)

        # Write the text content to the file.
        with open(file_path, 'w') as file:
            file.write(text_content)
        print(f"File saved at {file_path}")