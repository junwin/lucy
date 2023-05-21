import os
import re
import yaml
import shlex
import subprocess
from subprocess import check_output
from typing import List, Tuple
from src.handlers.handler import Handler
from src.container_config import container
from src.config_manager import ConfigManager
from src.handlers.quokka_loki import QuokkaLoki


class CommandExecutionHandler(Handler):  
    def handle(self, request:str):

        results = ''
        next_action_index = 0
        request_len = len(request)
        if not "action_execute_command:" in request:
            return None
        
        config = container.get(ConfigManager)
        base_path = config.get('code_sandbox_path')  

        while next_action_index < request_len and next_action_index != -1:

            request_substring = request[next_action_index:request_len]
            my_action = QuokkaLoki.extract_action(request_substring, "action_execute_command:", ['command', 'command_path'] )
            my_action_name = my_action['action']
            next_action_index = my_action[my_action_name]
            if my_action_name != "action_execute_command:":
                return [{ "handler": self.__class__.__name__}, {"result": "Error: Invalid action name for 'action_execute_command:' command."}]
            
            command = my_action['command']  
            command_path = my_action['command_path']  

            result = self.execute_script(command, base_path)
            results += result + '\n'
            results +=  '\n'


        return [{ "handler": self.__class__.__name__}, {"result": results}]
     
       
    def execute_script(self, command: str, script_path: str)-> str:

        drive = 'C:'  # Replace with the appropriate drive letter
        script_path = os.path.abspath('static/data/code_sandbox/')  # Get the absolute path
        absolute_path = os.path.join(drive, script_path)
        # Make sure the script exists before attempting to execute it
        if os.path.exists(absolute_path):
            try:
                #command = command.replace('\\', '/')
                split_command = self.split_command(command)
                #result = subprocess.run(split_command, cwd=script_path, capture_output=True, text=True)
                #result = subprocess.run(command, cwd=absolute_path, capture_output=True, text=True)
                result = check_output(command, cwd=absolute_path,  shell=True)
                #result = subprocess.Popen(command, cwd=absolute_path)
                #print("Script output:")
                #print(result.stdout)
                #print("Script error (if any):")
                #print(result.stderr)
                if len(result) == 0:
                    return "command completed successfully"
                return str(result)
            except Exception as e:
                print(f"Error occurred while executing script - possibly a sytax error or file not found: {e}")
                return str(e)
        else:
            #print(f"No script found at {script_path}")
            return None
        
    def split_command(self, command):
        my_safe_command = command.replace('npm', 'npm.cmd')
        half_baked = shlex.split(my_safe_command)
        #half_baked[0] = half_baked[0].replace('rippingMaHairOut', 'Program Files')
        return half_baked