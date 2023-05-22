import os
import re
import yaml
import shlex
import subprocess
from typing import List, Tuple
from src.handlers.handler import Handler
from src.handlers.handler import Handler
from src.container_config import container
from src.config_manager import ConfigManager
from src.handlers.quokka_loki import QuokkaLoki


class FileLoadHandler(Handler):  # Concrete handler


    def handle(self, action: dict) -> List[dict]:
        action_name = action['action_name']
        if action_name != "action_load_file":
            return None
        
        file_path = action['file_path']
        file_name = action['file_name']
  
        config = container.get(ConfigManager) 
        base_path = config.get('code_sandbox_path')

        my_path = base_path + '/' + file_path  

        result = self.read_file(my_path, file_name )

        my_result=[{"result": result},{ "handler": self.__class__.__name__} ].append(action)

        return my_result

  

    def process_inline_file(self, message: str) -> str:
        file_paths = re.findall(r"file_path:(\S+)", message)
        
        for file_path in file_paths:
            directory, filename = os.path.split(file_path)
            file_contents = self.read_file(directory, filename)
            message = message.replace(f"file_path:{file_path}", file_contents, 1)
        
        return message

    def read_file(self, file_path: str, file_name: str) -> str:
        try:
            full_file_path = os.path.join(file_path, file_name)
            full_file_path = full_file_path.replace('//', '/')
            with open(full_file_path, 'r',  encoding='utf-8') as file:
                file_contents = file.read()
                return file_contents
        except Exception as e:
            print(f"Error occurred while reading file: {e}")
            return str(e)
  


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