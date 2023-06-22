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
from src.handlers.handler_utils import get_base_path,execute_script
from src.handlers.command_execution_handler import CommandExecutionHandler


class ScrapeWebPage(Handler):  # Concrete handler

    functDef =  {
        "name": "scrape_web_page",
            "description": "read the text from a webpage and  chunk if needed",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_url": {
                        "type": "string",
                        "description": "the url of the page to be scraped ",
                    },
                },
                "required": ["page_url"],
            },
        }
      
    
    def get_function_calling_definition(self):
        return self.functDef
    
    def handle(self, action: dict, account_name:str = "auto") -> List[dict]:
        
        action_name = action['action_name']
        if action_name not in ["action_scrape_web_page", "scrape_web_page"]:
            return None

        
        print(action)
        logging.info(self.__class__.__name__ )
        
        page_url = action['page_url']
        config = container.get(ConfigManager) 

        python_utils_path = config.get("python_utils_path")
        base_path = get_base_path(config, account_name, python_utils_path)

        action["working_directory"] = python_utils_path
        command = f"python3 scrape.py {page_url}" 


        result = execute_script(command, base_path)

        file_chunk_threshold = config.get('file_chunk_threshold')
        file_chunk_size = config.get('file_chunk_size')

        if len(result) > file_chunk_threshold:
            chunk_processor = ChunkedFileProcessor()
            chunker = TextChunker()
            result = chunk_processor.process_text_data(result, chunker, file_chunk_size)
        

        temp = [{"result": result},{ "handler": self.__class__.__name__} ]
        temp.append(action)
        return temp




