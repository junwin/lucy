import os
import re
import yaml
import shlex
import subprocess
from typing import List, Tuple
from src.handlers.handler import Handler


class FileLoadHandler(Handler):  # Concrete handler

    #!inline_file_path:"C:\temp\sandbox\Whiteboard.txt"  
    # please save a file file_path: 'your path' file_name: 'your file name' file_content``` your file content ```
    def handle(self, request:str) -> Tuple[str, str]:
        if "please load a file" in request:
            file_path_pattern = "file_path: '(.*?)'"
            file_name_pattern = "file_name: '(.*?)'"


            file_path = re.search(file_path_pattern, request)
            file_name = re.search(file_name_pattern, request)
            result = self.read_file(file_path.group(1), file_name.group(1))
            return (self.__class__.__name__, result)



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
            with open(file_path, 'r') as file:
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