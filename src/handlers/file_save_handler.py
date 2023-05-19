import os
import re
import yaml
import shlex
import subprocess
from typing import List, Tuple
from src.handlers.handler import Handler
from src.container_config import container
from src.config_manager import ConfigManager


class FileSaveHandler(Handler):  # Concrete handler
    def handle(self, request:str) -> Tuple[str, str]:
        if "please save a file" in request:
            config = container.get(ConfigManager) 

            file_path_pattern = "file_path: ```(.*?)```"
            file_name_pattern = "file_name: ```(.*?)```"
            file_content_pattern = "file_content:```(.*?)```"

            file_path = re.search(file_path_pattern, request)
            file_name = re.search(file_name_pattern, request)
            file_content = re.search(file_content_pattern, request, re.DOTALL)
            base_path = config.get('code_sandbox_path')  
            #my_path = base_path + '/' + file_path.group(1)
            my_path = base_path
            
            #my_full_path = base_path

            if file_path and file_name and file_content:
                my_full_path = os.path.join(my_path, file_name.group(1))
                self.save_file(my_path, file_name.group(1), file_content.group(1))
                return (self.__class__.__name__, f"File saved at {my_full_path}")
            else:
                return (self.__class__.__name__, "Error: Invalid parameters for 'save a file' command.")
            
        return None
        
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