
## Message Processors

Message processors are selected based on the agent the end user is interacting with when an inbound message is received. If the chosen agent configuration does not specify a message processor, the default will be used.

### Default Message Processor

The default processor:

* Utilizes the preprocessor to apply presets and processes.
* Employs the prompt builder to enhance the request with short and long term memory.
* Optionally stores completion messages.

### Function Calling Processor

This processor:

* Uses the prompt builder to augment the request with short and long term memory.
* Retrieves function definitions from the available handlers.
* Calls the Completions API with the inbound request and available functions.
* Processes any requested functions.
* Calls the Completions API again to get a response based on the inbound information.
* Optionally stores completion messages.

Associated Agent: Doug

### Automation Processor

This processor:

* Uses a YAML set of goals as input.
* Processes each goal individually.
* Utilizes handlers (similar to function calling) to perform local functions.
* Uses a 'critic' to assess the success of each operation (aka step) and recommends remedial action.
* Uses the context to track the state, e.g., files loaded/saved, messages, etc.

Associated Agents: Doris and Colin

### Guided Conversation Processor

This processor:

* Uses an agent with a role focused on empathy, e.g., Glinda, who is friendly and empathetic.
* Uses an agent (SME) with subject matter expertise, e.g., Dorothy, an expert in life coaching.
* Uses the context to track the progress of the conversation.
* Utilizes the SME to guide the conversation by injecting recommendations along with each user request.
* Has the ability to summarize the session.

Associated Agents: Glinda and Dorothy



## Presets
 /conjugate, spanish, conocer

## processes
!folder_summarize, input_path="test_data\in",output_path="test_data\out",file_type=".py"

## automation
- name: load HelloWorld.vue 
  description: load HelloWorld.vue into the context
  working_directory: ~/src/sandbox/testabc/src/components

- name: describe the code
  description: Carefully examine the code for HelloWorld.vue describe the function and identify potential issues
  working_directory: ~/src/sandbox/testabc/src/components

- name: Save the results
  description: Save the results of examining the code in a file called bbbb.txt
  working_directory: ~/src/sandbox/testabc/src/components



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
