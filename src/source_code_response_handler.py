import os
import re
import json
from typing import Dict, Any
import logging
from src.response_handler import ResponseHandler

class SourceCodeResponseHandler(ResponseHandler):
    def __init__(self, account_output_path:str, max_length=500):
        self.max_length = max_length
        self.output_folder = account_output_path

    def handle_response(self, account_name:str, response: str) ->str:
        my_folder_path = os.path.join(self.output_folder, account_name)
        self.save_test_code(response, my_folder_path)
        response = "files saved to " + self.output_folder
        return response

    def extract_json_object(self, text: str) -> Dict[str, Any]:
        start = text.index('{')
        end = text.index('}') + 1
        json_object = text[start:end]
        return json.loads(json_object)

    def extract_source_code(self, text: str) -> str:
        try:
            if text:
                start = text.index('}') + 1
                extracted_text = text[start:].strip()
                return extracted_text if extracted_text else None
            else:
                return None
        except ValueError:
            logging.error("No closing brace '}' found in the text.")
            return None
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            return None


    def save_test_code(self, response: str, base_folder: str) -> str:
        code_info  = self. extract_json_object(response) 
        source_code = self.extract_source_code(response)

        # Extract filename
        filename = code_info["output_file_path"]


        if filename is None:        
            return "Error: Filename not found."

        if source_code is None:
            print (f"Error: Source code not found.")
            return "Error: Source code not found." 

        print (f"source_code is '{source_code}'")   

        # Save the code to the base folder
        tests_folder = os.path.join(base_folder, 'tests')
        if not os.path.exists(tests_folder):
            os.makedirs(tests_folder)

        file_path = os.path.join(tests_folder, filename)
        with open(file_path, 'w') as file:
            file.write(source_code)

        return f"File '{filename}' saved to '{tests_folder}'."

    
    