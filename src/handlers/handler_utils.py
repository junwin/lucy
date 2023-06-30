
import os
import shlex
import subprocess
import logging
from subprocess import check_output


def get_base_path(config, account_name:str, relative_path: str = '')-> str:
    relative_path = relative_path.strip()
    relative_path = relative_path.replace('~', '')   # we allways use the the config to determine the base path
    base_path = config.get('code_sandbox_path')
    base_path = base_path + '/' + account_name + '/' + relative_path + '/'
    return base_path




def execute_script(command: str, script_path: str)-> str:
    # https://docs.python.org/3/library/subprocess.html
    if not os.path.exists(script_path):
        result = f"path does not exist {script_path}"
        return result

    try:
        #command = command.replace('\', '/')
        split_command = shlex.split(command)
        #aa = subprocess.Popen('dir ', shell=True, cwd=script_path)
        result = subprocess.run(split_command, shell=False, cwd=script_path, capture_output=True, text=True, timeout=30)

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
           
