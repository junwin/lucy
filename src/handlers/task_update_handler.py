import os
import re
import yaml
import shlex
import subprocess
from typing import List, Tuple
from src.handlers.handler import Handler

class TaskUpdateHandler(Handler):  # Another concrete handler
    def handle(self, request:str) -> Tuple[str, str]:
        if "update steps:" in request:
            steps_pattern = "```(.*?)```"
            #steps = re.search(steps_pattern, request, re.DOTALL)

            #if steps:
            #    self.steps = yaml.safe_load(steps.group(1))
            #else:
            #    return ["Error: Invalid parameters for 'update steps' command."]
            
        return None
