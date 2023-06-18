import os
import re
import yaml
import shlex
import subprocess
import logging
from typing import List, Tuple
from src.handlers.handler import Handler
from src.handlers.handler import Handler
from src.container_config import container
from src.config_manager import ConfigManager
from src.handlers.quokka_loki import QuokkaLoki
from src.chunkers.chuncked_file_processor import ChunkedFileProcessor
from src.chunkers.text_chunker import TextChunker
from src.handlers.handler_utils import get_base_path


class FileLoadHandler(Handler):  # Concrete handler

    functDef =  {
        "name": "file_load_handler",
            "description": "Load a file from a directory relative to the home and chunk if needed",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "the location of the file to be loaded relative to the home folder ",
                    },
                    "file_name": {"type": "string", 
                        "description": "the name of the file to be loaded",},
                },
                "required": ["directory_path", "file_name"],
            },
        }
      
    
    def get_function_calling_definition(self):
        return self.functDef
    
    def handle(self, action: dict, account_name:str = "auto") -> List[dict]:
        
        action_name = action['action_name']
        if action_name not in ["action_load_file", "file_load_handler"]:
            return None

        
        print(action)
        logging.info(self.__class__.__name__ )
        
        directory_path = action['directory_path']
        file_name = action['file_name']
  
        config = container.get(ConfigManager) 
        
        #base_path = directory_path + "/" + 'junwin'

        base_path = get_base_path(config, account_name, directory_path)

        file_chunk_threshold = config.get('file_chunk_threshold')
        file_chunk_size = config.get('file_chunk_size')

        result = self.read_file(base_path, file_name )

        if len(result) > file_chunk_threshold:
            chunk_processor = ChunkedFileProcessor()
            chunker = TextChunker()
            result = chunk_processor.process_text_data(result, chunker, file_chunk_size)
        

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
  

