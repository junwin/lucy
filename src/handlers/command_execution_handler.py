import os
import re
import yaml
import shlex
import subprocess
from typing import List, Tuple
from src.handlers.handler import Handler
from src.container_config import container
from src.config_manager import ConfigManager


class CommandExecutionHandler(Handler):  
    def handle(self, request:str) -> Tuple[str, str]:
        if "please execute a command:" in request:
            config = container.get(ConfigManager) 
            base_path = config.get('code_sandbox_path')  

            command_pattern = "```(.*?)```"
            commands = re.findall(command_pattern, request)

            if commands:
                results = []
                for command in commands:
                    my_command = command
                    result = self.execute_script(my_command, base_path)
                    results.append(result)
                return (self.__class__.__name__, ', '.join(results))

            else:
                return "Error: Invalid parameters for 'execute a command' command."
            
        return None


    def execute_script(self, command: str, script_path: str)-> str:
        # Make sure the script exists before attempting to execute it
        if os.path.exists(script_path):
            try:
                split_command = self.split_command(command)
                result = subprocess.run(split_command, cwd=script_path, capture_output=True, text=True)
                print("Script output:")
                print(result.stdout)
                print("Script error (if any):")
                print(result.stderr)
                return result.stdout
            except Exception as e:
                print(f"Error occurred while executing script: {e}")
                return str(e)
        else:
            #print(f"No script found at {script_path}")
            return None
        
    def split_command(self, command):
        my_safe_command = command.replace('npm', 'npm.cmd')
        half_baked = shlex.split(my_safe_command)
        #half_baked[0] = half_baked[0].replace('rippingMaHairOut', 'Program Files')
        return half_baked