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

    #!inline_file_path:"C:\temp\sandbox\Whiteboard.txt"  
    # please save a file file_path: 'your path' file_name: 'your file name' file_content``` your file content ```
    def handle(self, request:str) -> Tuple[str, str]:
        if "action_load_file:" in request:
            config = container.get(ConfigManager) 
            my_action = QuokkaLoki.extract_action(request, "action_load_file:", ['file_path', 'file_name'] )
            my_action_name = my_action['action']
            if my_action_name != "action_load_file:":
                return [{ "handler": self.__class__.__name__}, {"result": "Error: Invalid action name for 'save a file' command."}]

            file_path = my_action['file_path']
            file_path = file_path.replace('.', '')
            file_name = my_action['file_name']

            base_path = config.get('code_sandbox_path') 
            my_full_path = base_path+ '/' + file_path + '/'


            result = self.read_file(my_full_path, file_name )

            return [{ "handler": self.__class__.__name__}, {"result": result}]




        #elif "inline_file_path:" in request:
         #   return self.process_inline_file(request)

        return None
        


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