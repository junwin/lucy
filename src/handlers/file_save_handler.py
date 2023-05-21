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
    def handle(self, request:str) :
        if "action_save_file:" in request:
            config = container.get(ConfigManager) 
            my_action = QuokkaLoki.extract_action(request, "action_save_file:", ['file_path', 'file_name', 'file_content'] )
            my_action_name = my_action['action']
            if my_action_name != "action_save_file:":
                return [{ "handler": self.__class__.__name__}, {"result": "Error: Invalid action name for 'save a file' command."}]

            file_path = my_action['file_path']
            file_name = my_action['file_name']
            file_content =  my_action['file_content']
            base_path = config.get('code_sandbox_path')  

            folders = os.path.dirname(file_path)
            my_path = base_path + '/' + folders
            
            #my_full_path = base_path

            if file_path and file_name and file_content:
                my_full_path = os.path.join(my_path, file_name)
                self.save_file(my_path, file_name, file_content)

                return [{ "handler": self.__class__.__name__}, {"result": f"File saved at {my_full_path}"}]
            else:
                return [{ "handler": self.__class__.__name__}, {"result": "Error: Invalid parameters for 'save a file' command."}]
            
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