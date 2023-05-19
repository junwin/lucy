from typing import List, Dict


class Context:
    def __init__(self):
        self.info = [ ]

    def add_info(self, info: dict):     
        self.info.append(info)

    def get_info_text(self) -> str: 
        my_text =  self.context_formated_text(self.info)   
        return my_text
    
    def context_formated_text(self, response) -> str:
        response_text = ''
        for handler_response in response:
                key = list(handler_response.keys())[0]
                value = list(handler_response.values())[0]
                response_text += key + ': ' + value + '\n'

        return response_text