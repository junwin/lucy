from typing import List, Dict
import yaml

class Context:
    
    def __init__(self, name:str, description:str, current_node_id:str,state:str = 'none'):
        self.name = name
        self.info = []
        self.description = description.replace('\n', '')
        self.state = state
        self.actions = [ ]
        self.current_node_id = current_node_id
        self.environment = []
        self.output_folder = 'auto/'
        self.input_folder = 'auto/'
        self.add_environment('os:', 'Microsoft Windows 10')
        

    def add_info(self, info_text:str):     
        self.info.append(info_text.replace('\n', ''))

    def add_action(self, request:str, response:str, interpretation:str):
        action = {"request:":request, "response:":response, "interpretation:":interpretation}
        self.actions.append(action)

    def add_environment(self, name:str, value:str):
        env = {name:value}
        self.environment.append(env)

    def get_info_text(self) -> str: 
        my_text =  self.context_formated_text()   
        return my_text
    
    def context_formated_text(self) -> str:
        #response_text = yaml.dump(self, default_flow_style=False)
        response_text = self.context_formated_text2()

        return response_text
    
    def context_formated_text2(self) -> str:
        response_text = ''
        response_text += 'name: ' + self.name + '\n'
        response_text += 'description: ' + self.description + '\n'
        response_text += 'state: ' + self.state + '\n'
        response_text += 'current_node_id: ' + self.current_node_id + '\n'
        response_text += 'output_folder: ' + self.output_folder + '\n'
        response_text += 'input_folder: ' + self.input_folder + '\n'
        response_text += 'info: ' + '\n'

        for info in self.info:
            response_text += '  - ' + info + '\n'

        response_text += 'actions: ' + '\n'
        for action in self.actions:
            response_text += '  - ' + 'request:' +  action['request:'] + '\n'
            response_text += '    ' + 'response:' +  action['response:'] + '\n'
            response_text += '    ' + 'interpretation:' +  action['interpretation:'] + '\n'

        response_text += 'environment: ' + '\n'
        for env in self.environment:
            for key, value in env.items():
                response_text += '  - ' + key + ' ' + value + '\n'



        return response_text
