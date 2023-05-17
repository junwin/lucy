## Presets
 /conjugate, spanish, conocer

## processes
!folder_summarize, input_path="test_data\in",output_path="test_data\out",file_type=".py"

## Example of Agent Write Code
request keywords: ```produce_test_code```
program language: python
output file name: hello_world.py

spec: 

write a python function that
* takes a string parameter called name
* have the function return Hello world + name !
* Make sure to use type hints
* show usage with name Binky

produces ```import os
import unittest

def hello_world(name: str) -> str:
    return f"Hello world {name}!"

class TestHelloWorld(unittest.TestCase):
    def test_hello_world(self):
        self.assertEqual(hello_world("Binky"), "Hello world Binky!")

if __name__ == "__main__":
    unittest.main()```


## Example of having an agent generate test code
request keywords: ```produce_test_code```
input file name: source_code_response_handler.py
test framework: pytest
program language: python
output file name: test_source_code_response_handler.py

code: 

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

    def handle_response(self, agent_name:str, response: str) ->str:
        self.save_test_code(response, self.output_folder)
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

   ## inline files 
  good morning !inline_file_path:"C:\temp\sandbox\Whiteboard.txt"   need to work what is next  
