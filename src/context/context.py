from typing import List, Dict
import yaml
import os
import pickle
import datetime
from src.container_config import container
from src.config_manager import ConfigManager
from src.handlers.quokka_loki import QuokkaLoki

class Context:
    
    def __init__(self, name:str, description:str, current_node_id:str,state:str = 'none', account_name:str = 'auto', conversation_id:str = 'conv1'):
        self.account_name = account_name
        self.conversation_id = conversation_id
        self.name = name
        self.info = []
        self.transcript = []
        self.description = description.replace('\n', '')
        self.retry_information = ''
        self.state = state
        self.actions = []
        self.current_node_id = current_node_id
        self.recomendations = ''
        self.conversation_state = ''
        self.environment = []
        self.files = dict()
        self.output_directory = 'auto/'
        self.input_directory = 'auto/'
        self.add_environment('os:', 'Microsoft Windows 10')
        self.created_timestamp = datetime.datetime.utcnow()
        self.last_updated_timestamp = datetime.datetime.utcnow()
        

    def add_info(self, info_text:str):     
        self.info.append(info_text.replace('\n', ''))

    def add_action(self, request:str, response:str, interpretation:str):
        action = {"request:":request, "response:":response, "interpretation:":interpretation}
        self.actions.append(action)

    def add_environment(self, name:str, value:str):
        env = {name:value}
        self.environment.append(env)

    def add_transcript_item(self, account_name:str, item:str):
        newItem = f"{account_name}: {item}\n"
        self.transcript.insert(0, newItem)


    def add_replace_file(self, file_name:str, content:str):
        self.files[file_name] = content

    def get_file_content(self, file_name:str):
        return self.files[file_name]    
        

    def get_info_text(self) -> str: 
        my_text =  self.context_formated_text()   
        return my_text
    
    def context_formated_text(self) -> str:
        #response_text = yaml.dump(self, default_flow_style=False)
        response_text = self.context_formated_text2()

        return response_text
    
    def update_from_results(self, handler_response:list):
        # intended to update from QuokkaLoki results list
        for response in handler_response:
            #handler_name = QuokkaLoki.get_field_value(response, 'handler')
            #response_text += handler_name + '\n'
            if response == None:
                continue
            result = QuokkaLoki.get_field_value(response, 'result')
            for item in response:
                for key, value in item.items():
                    if key == 'action_name':
                        if value == 'action_load_file':
                            file_name = item['file_name']
                            file_content = result
                            self.add_replace_file(file_name, file_content)
                        if value == 'action_save_file':
                            file_name = item['file_name']
                            file_content = item['file_content']
                            self.add_replace_file(file_name, file_content)
                        if value == 'action_execute_command':                            
                            command = item['command']
                            self.add_action(command, result, '')
                        if value == 'action_websearch':
                            query = item['query']
                            self.add_action(f"web seach: {query} ", result, '')  


    
    def context_formated_text2(self, detail_level:str="full") -> str:

        response_text = 'Context: ' + '\n'
        response_text += 'name: ' + self.name + '\n' 
        response_text += 'description: ' + self.description + '\n'

        if len(self.transcript) > 0:
            for string in self.transcript:
                response_text += 'transcript: ' + string + '\n'

        if detail_level != "full":
            if self.recomendations != '':
                response_text += 'recomendations: ' + self.recomendations + '\n'
            if self.conversation_state != '':
                response_text += 'conversation state: ' + self.conversation_state + '\n'
            return response_text

        
        if self.retry_information != '':
            response_text += 'retry_information: ' + self.retry_information + '\n'

 
        response_text += 'state: ' + self.state + '\n'
        response_text += 'current_node_id: ' + self.current_node_id + '\n'
        response_text += 'output_directory: ' + self.output_directory + '\n'
        response_text += 'input_directory: ' + self.input_directory + '\n'
        response_text += 'info: ' + '\n'

        for info in self.info:
            response_text += '  - ' + info + '\n'

        response_text += 'actions: ' + '\n'
        for action in self.actions:
            response_text += '  - ' + 'request:' +  action['request:'] + '\n'
            my_action_response = action['response:']
            my_response_text = self.format_action_reponse(my_action_response)
            response_text += '    ' + 'response:' +  my_response_text + '\n'
            response_text += '    ' + 'interpretation:' +  action['interpretation:'] + '\n'

        response_text += 'environment: ' + '\n'
        for env in self.environment:
            for key, value in env.items():
                response_text += '  - ' + key + ' ' + value + '\n'

        response_text += 'Files section, source code and other data: ' + '\n'
        for key, value in self.files.items():
            response_text += f"  - file_name: {key}\n"
            response_text += f"``` {value} ```\n\n"



        return response_text
    
    def format_action_reponse(self, response)-> str:

        if type(response) == dict:
            return yaml.dump(response, default_flow_style=False)
        elif type(response) == list:
            my_text = ''
            for item in response:
                my_text += yaml.dump(item, default_flow_style=False)
                my_text += '\n'
            return my_text
        else:
            return response
        

