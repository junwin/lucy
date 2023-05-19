import os
import re
import yaml
import shlex
import subprocess
from typing import List,  Tuple
from src.handlers.handler import Handler

class UserActionRequiredHandler(Handler):  # Another concrete handler
    def handle(self, request)-> Tuple[str, str]:
        if "user action required:" in request:
            user_action_pattern = "```(.*?)```"
            user_action = re.search(user_action_pattern, request)

            #if user_action:
            #    print(user_action.group(1))
            #else:
            #    return "Error: Invalid parameters for 'user action required' command."

        return None