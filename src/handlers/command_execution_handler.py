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


class CommandExecutionHandler(Handler):  
    def handle(self, action: dict) -> List[dict]:
        action_name = action['action_name']
        if action_name != "action_execute_command":
            return None
        
        print(action)
        
        command = action['command']  
        working_directory = action['working_directory']  

        config = container.get(ConfigManager) 
        base_path = config.get('code_sandbox_path')

        working_directory = base_path + '/' + working_directory   

        result = self.execute_script(command, working_directory)

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
            result = subprocess.run(split_command, shell=True, cwd=script_path, capture_output=True, text=True)

            if len(result.stderr) > 0:
                return f"an error ocurred: {result.stderr} {result.stdout}"
            
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