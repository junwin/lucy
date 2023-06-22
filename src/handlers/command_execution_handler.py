import os
import re
import yaml
import shlex
import subprocess
import logging
from subprocess import check_output
from typing import List, Tuple
from src.handlers.handler import Handler
from src.container_config import container
from src.config_manager import ConfigManager
from src.handlers.quokka_loki import QuokkaLoki
from src.handlers.handler_utils import get_base_path, execute_script



class CommandExecutionHandler(Handler):  
    functDef =  {
        "name": "command_execution_handler",
            "description": "execute a OS command in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "the command to be executed - assumes linux bash",
                    },
                    "working_directory": {"type": "string", 
                        "description": "the working directory that the command will execute in ",},
                },
                "required": ["command", "working_directory"],
            },
        }
        
    def get_function_calling_definition(self):
        return self.functDef
    

    def handle(self, action: dict, account_name:str = "auto") -> List[dict]:

        action_name = action['action_name']
        if action_name not in ["action_execute_command", "command_execution_handler"]:
            return None
        
        logging.info(self.__class__.__name__ )
        
        command = action['command']  
        working_directory = action['working_directory']  

        config = container.get(ConfigManager) 
        base_path = get_base_path(config, account_name, working_directory)

        result = execute_script(command, base_path)

        temp = [{"result": result},{ "handler": self.__class__.__name__} ]
        temp.append(action)
        return temp

     
     
       

 