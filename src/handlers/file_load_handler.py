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
        
        print(action)
        
        directory_path = action['directory_path']
        file_name = action['file_name']
  
        config = container.get(ConfigManager) 
        base_path = config.get('code_sandbox_path')

        my_path = base_path + '/' + directory_path  

        result = self.read_file(my_path, file_name )

        temp = [{"result": result},{ "handler": self.__class__.__name__} ]
        temp.append(action)
        return temp


  

    def process_inline_file(self, message: str) -> str:
        file_paths = re.findall(r"file_path:(\S+)", message)
        
        for file_path in file_paths:
            directory, filename = os.path.split(file_path)
            file_contents = self.read_file(directory, filename)
            message = message.replace(f"file_path:{file_path}", file_contents, 1)
        
        return message

    def read_file(self, directory_path: str, file_name: str) -> str:
        try:
            full_directory_path = os.path.join(directory_path, file_name)
            full_directory_path = full_directory_path.replace('//', '/')
            with open(full_directory_path, 'r',  encoding='utf-8') as file:
                file_contents = file.read()
                return file_contents
        except Exception as e:
            print(f"Error occurred while reading file: {e}")
            return str(e)
  

