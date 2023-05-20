
from typing import List,  Tuple
import re
from src.handlers.handler import Handler



class QuokkaLoki:
    def __init__(self):
        self.handlers = []  

    @classmethod
    def extract_action(cls, request: str, action_name: str, parameter_names:List[str]) -> List[dict]:
        # Find the action command in the request
        action_index = request.find(action_name)
        if action_index == -1:
            raise ValueError(f"Action command '{action_name}' not found in request")
        
        # Find the end index of the current action
        end_index = request.find('action_', action_index + len(action_name))
        if end_index == -1:
            end_index
        
        # Extract the parameters
        result = [('action', action_name)]
        param_dict = {}
        param_dict['action'] = action_name
        param_dict[action_name] = end_index
        for param_name in parameter_names:
            param_index = request.find(param_name + ':', action_index, end_index)
            if param_index == -1:
                raise ValueError(f"Parameter '{param_name}' not found for action '{action_name}'")
            param_value_start = request.find('```', param_index) + 3
            param_value_end = request.find('```', param_value_start)
            param_value = request[param_value_start:param_value_end].strip()
            param_dict[param_name] = param_value
            
        # Check if we have the correct parameters
        #if set(param_dict.keys()) != set(parameter_names):
        #    raise ValueError(f"Parameter mismatch for action '{action_name}'")
        
        return param_dict
    
    @classmethod
    def get_value_from_action(cls, action: List[Tuple[str, str]], key: str) -> str:
        for i in range(0, len(action), 2):
            if action[i] == key:
                return action[i+1]
        return None


    def add_handler(self, handler: Handler):
        self.handlers.append(handler)

    def process_request(self, request:str):
        results = []
        for handler in self.handlers:
            try:
                result = handler.handle(request)
                if result is not None:
                    results.append(result)
            except Exception as e:
                print( f"An error occurred while processing the request with {handler.__class__.__name__}: {e}")
        
        return (results)