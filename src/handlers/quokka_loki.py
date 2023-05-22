
from typing import List,  Tuple
import re
from src.handlers.handler import Handler



class QuokkaLoki:
    def __init__(self):
        self.handlers = []  


    def add_handler(self, handler: Handler):
        self.handlers.append(handler)

    def process_request(self, request:str):
        results = []
        actions = QuokkaLoki.extract_actions(request)
        for action in actions:
            action_dict = QuokkaLoki.parse_action(action)
            for handler in self.handlers:
                try:
                    action_result = handler.handle(action_dict)
                    results.append(action_result)
                except Exception as e:
                    print( f"An error occurred while processing the request with {handler.__class__.__name__}: {e}")
                    return [{ "handler": handler.__class__.__name__}, {"result": f"An error occurred while processing the request with: {e} check the format of your request!."}]

        return results
    


    @classmethod
    def extract_action(cls, request: str, action_name: str, parameter_names:List[str]) -> List[dict]:
        # Find the action command in the request
        action_index = request.find(action_name)
        if action_index == -1:
            raise ValueError(f"Action command '{action_name}' not found in request")

        # Find the end index of the current action
        end_index = request.find('\n', action_index + len(action_name))
        if end_index == -1:
            end_index = len(request)  # if there's no line feed, use the end of the string

        # Extract the parameters
        result = [('action', action_name)]
        param_dict = {}
        param_dict['action'] = action_name
        param_dict[action_name] = end_index
        for param_name in parameter_names:
            zz =  request[action_index:end_index]
            param_index = request.find(param_name + ':', action_index, end_index)
            if param_index == -1:
                raise ValueError(f"Parameter '{param_name}' not found for action '{action_name}'")
            param_value_start = request.find('```', param_index) + 3
            param_value_end = request.find('```', param_value_start)
            param_value = request[param_value_start:param_value_end].strip()
            param_dict[param_name] = param_value

        # Uncomment below if you need to check parameters
        #if set(param_dict.keys()) != set(parameter_names):
        #    raise ValueError(f"Parameter mismatch for action '{action_name}'")

        return param_dict

    
    @classmethod
    def get_value_from_action(cls, action: List[Tuple[str, str]], key: str) -> str:
        for i in range(0, len(action), 2):
            if action[i] == key:
                return action[i+1]
        return None




    @classmethod
    def extract_actions(cls, input_string):
        actions = []

        start_index = input_string.find('<action_')
        while start_index != -1:
            end_index = input_string.find('</action>', start_index)
            if end_index == -1:
                raise ValueError("Missing closing tag for action at index {}".format(start_index))
            end_index += len('</action>')  # include closing tag in extracted action
            actions.append(input_string[start_index:end_index])
            start_index = input_string.find('<action_', end_index)

        return actions

    @classmethod
    def parse_action(cls, action):
        # Validate the presence of '<action_'
        if not action.startswith('<action_'):
            raise ValueError("Input action does not start with '<action_'")

        # Locate the first '>' after '<action_'
        action_end = action.find('>')
        if action_end == -1:
            raise ValueError("Missing '>' in action")

        # Extract action name
        action_name = action[1:action_end]
        action_dict = {'action_name': action_name}

        # Initialize parameters start index
        param_start = action_end + 1

        while param_start < len(action) - 9:  # 9 is the length of '</action>'
            # Extract parameter name
            param_end = action.find(': ```', param_start)
            if param_end == -1:
                break
            param_name = action[param_start:param_end].strip()

            # Update parameters start index
            param_start = param_end + 5

            # Extract parameter value
            param_end = action.find('``` ', param_start)
            if param_end == -1:
                param_end = action.find('</action>', param_start) - 1
            param_value = action[param_start:param_end]

            # Update parameters start index
            param_start = param_end + 4

            # Add parameter to the dictionary
            action_dict[param_name] = param_value

        return action_dict
