import os
import re
import yaml
import shlex
import subprocess
from typing import List,  Tuple
from src.handlers.handler import Handler

class UserActionRequiredHandler(Handler):  # Another concrete handler

    functDef = { }
    def get_function_calling_definition(self):
        return self.functDef

    def handle(self, request, account_name:str = "auto")-> Tuple[str, str]:
        if "user action required:" in request:
            user_action_pattern = "```(.*?)```"
            user_action = re.search(user_action_pattern, request)

            #if user_action:
            #    print(user_action.group(1))
            #else:
            #    return "Error: Invalid parameters for 'user action required' command."

        return None