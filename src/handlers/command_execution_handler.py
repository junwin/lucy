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
from src.handlers.handler_utils import get_base_path


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

        result = self.execute_script(command, base_path)

        temp = [{"result": result},{ "handler": self.__class__.__name__} ]
        temp.append(action)
        return temp

     
     
       

    def execute_script(self, command: str, script_path: str)-> str:
        # https://docs.python.org/3/library/subprocess.html
        if not os.path.exists(script_path):
            result = f"path does not exist {script_path}"
            return result

        try:
            #command = command.replace('\', '/')
            split_command = self.split_command(command)
            #aa = subprocess.Popen('dir ', shell=True, cwd=script_path)
            result = subprocess.run(split_command, shell=False, cwd=script_path, capture_output=True, text=True, timeout=10)

            #if len(result.stderr) > 0:
             #   return f"an error ocurred: {result.stderr} {result.stdout}"
            
            if(result.returncode != 0):
                return f"an error ocurred: {result.returncode} {result.stdout}"
            else:
                if len(result.stdout) == 0:
                    return "success"
        
            return str(result.stdout)
    
        except Exception as e:
            print(f"Error occurred while executing script - possibly a sytax error or file not found: {e}")
            return f"Error occurred while executing script - possibly a sytax error or file not found: {e}"
           
    def split_command(self, command):
        split_command = shlex.split(command)
        return split_command