
from typing import List,  Tuple
import re
from src.handlers.handler import Handler
import yaml

action_start_delimiter = '<action_'
action_end_delimiter = '</action'
content_delimiter = '```'

class QuokkaLoki:
    def __init__(self, account_name:str = "auto"):
        self.handlers = []
        self.account_name = account_name


    def add_handler(self, handler: Handler):
        self.handlers.append(handler)

    def process_request(self, request:str):
        results = []
        actions = QuokkaLoki.extract_actions(request)
        for action in actions:
            action_dict = QuokkaLoki.parse_action(action)
            for handler in self.handlers:
                try:
                    action_result = handler.handle(action_dict, self.account_name)
                    if action_result != None:
                        results.append(action_result)
                except Exception as e:
                    print( f"An error occurred while processing the request with {handler.__class__.__name__}: {e}")
                    return [{ "handler": handler.__class__.__name__}, {"result": f"An error occurred while processing the request with: {e} check the format of your request!."}]

        return results
    
    
    @classmethod
    def handler_repsonse_formated_text(cls, handler_response:list) -> str:
        response_text = ''
        for response in handler_response:
            handler_name = QuokkaLoki.get_field_value(response, 'handler')
            response_text += handler_name + '\n'
            if response == None:
                continue
            for item in response:
                if type(item) == dict:  
                    for key, value in item.items():
                        if key == 'action_name':
                            response_text += f"  - {key}:{value}" + '\n'
                        if key == 'command':
                            response_text += f"  - {key}:{value}" + '\n'
                        if key == 'result':
                            response_text += f"  - {key}:{value}" + '\n'
                else:
                    response_text += f"  - {item}" + '\n'
            
        
        return response_text
    
    @classmethod
    def get_field_value(cls, response:list, field_name:str) -> str:
        field_value = ''
        try:
            if response == None:
                    return field_value
            for item in response:
                for key, value in item.items():
                    if key == field_name:
                        field_value = value
                        return field_value
        except Exception as e:
            print(f"An error occurred while getting field value: {e}")
            return field_value


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
            if param_value == ' ':
                param_value = ''
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

        start_index = input_string.find(action_start_delimiter)
        while start_index != -1:
            end_index = input_string.find(action_end_delimiter, start_index)
            if end_index == -1:
                raise ValueError("Missing closing tag for action at index {}".format(start_index))
            end_index += len('</action')  # include closing tag in extracted action
            actions.append(input_string[start_index:end_index])
            start_index = input_string.find(action_start_delimiter, end_index)

        return actions

    @classmethod
    def parse_action(cls, action):
        # Validate the presence of 'action_start_delimiter'
        if not action.startswith(action_start_delimiter):
            raise ValueError("Input action does not start with action_start_delimiter")

        # Locate the first '>' after 'action_start_delimiter'
        action_end = action.find('>')
        if action_end == -1:
            raise ValueError("Missing '>' in action")

        # Extract action name
        action_name = action[1:action_end]
        action_dict = {'action_name': action_name}

        # Initialize parameters start index
        param_start = action_end + 1

        while param_start < len(action) - len(action_end_delimiter): 

            # Extract parameter name - do not assume a space after the colon
            param_end = action.find(':', param_start)
            if param_end == -1:
                break

            param_name = action[param_start:param_end].strip()

            # Update parameters start index
            param_start = action.find(content_delimiter, param_end) + len(content_delimiter)

            # Extract parameter value
            param_end = action.find(content_delimiter, param_start)
            if param_end == -1:
                param_end = action.find(action_end_delimiter, param_start) - 1
            param_value = action[param_start:param_end]
            if param_value == ' ':
                param_value = ''    

            # Update parameters start index
            param_start = param_end + 3

            # Add parameter to the dictionary
            action_dict[param_name] = param_value

        return action_dict
    
    def yaml_to_dict(self, yaml_str:str):
        yaml_list = yaml.safe_load(yaml_str)
        dict_list = []
        for item in yaml_list:
            dict_list.append({"name": item["name"], "description": item["description"]})
        return dict_list


    def process_yaml_goals(self, goal:str, current_node_id:str, account_name:str, conversation_id:str, working_directory:str):

        

        add_tasks = ''
    
        spec = self.yaml_to_dict(goal)
        x = 0
        for item in spec:
            if x >= 0:
                add_tasks += self.format_task(current_node_id, item["name"], item["description"], working_directory='fpe_assembly')
            else:
                add_tasks += self.format_task(current_node_id, item["name"], item["description"])

            x += 1

        results = self.process_request(add_tasks)
        return results

    def format_task(self, current_node_id, name:str, description:str, working_directory:str = ''):
        print(f"adding task {name}")
        t =  f" <action_add_steps> current_node_id: ```{current_node_id}``` name: ```{name}  ``` description: ``` {description} ``` state: ```none```  working_directory: ```{working_directory}```</action>\n"
        return t
    
