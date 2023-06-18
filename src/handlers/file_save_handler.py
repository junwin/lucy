import os
import re
import yaml
import shlex
import subprocess
import logging
from typing import List, Tuple
from src.handlers.handler import Handler
from src.container_config import container
from src.config_manager import ConfigManager
from src.handlers.quokka_loki import QuokkaLoki
from src.handlers.handler_utils import get_base_path


class FileSaveHandler(Handler):  # Concrete handler

    functDef = {
        "name": "file_save_handler",
            "description": "save code or text into a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "the location of the file to be loaded",
                    },
                    "file_name": {"type": "string", 
                        "description": "the name of the file to be loaded",},
                    "file_content": {"type": "string",
                        "description": "the content of the file to be saved",},
                },
                "required": ["directory_path", "file_name", "file_content"],
            },
           
        }
        

    def get_function_calling_definition(self) :
        return self.functDef

    def handle(self, action: dict, account_name: str = "auto") -> List[dict]:

        action_name = action['action_name']
        if action_name not in ["action_save_file", "file_save_handler"]:
            return None


        print(action)
        logging.info(self.__class__.__name__)

        directory_path = action['directory_path']
        file_name = action['file_name']
        file_content = action['file_content']

        config = container.get(ConfigManager)

        base_path = get_base_path(config, account_name, directory_path)

        result = self.save_file(base_path, file_name, file_content)

        temp = [{"result": result}, {"handler": self.__class__.__name__}]
        temp.append(action)
        return temp

    def save_file(self, path, filename, text_content):
        # Make sure the directory exists. If it doesn't, create it.
        if not os.path.exists(path):
            os.makedirs(path)

        # Join the path and filename
        file_path = os.path.join(path, filename)

        # Write the text content to the file.
        with open(file_path, 'w') as file:
            file.write(text_content)

        return f"success file saved at {file_path}"
