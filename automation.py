import os
import yaml
import logging

from src.message_processor import MessageProcessor
from src.container_config import container
from src.config_manager import ConfigManager
from src.agent_manager import AgentManager


from src.handlers.quokka_loki import QuokkaLoki
from src.handlers.task_update_handler import TaskUpdateHandler
from src.handlers.file_save_handler import FileSaveHandler
from src.handlers.command_execution_handler import CommandExecutionHandler  
from src.handlers.user_action_required_handler import UserActionRequiredHandler
from src.handlers.file_load_handler import FileLoadHandler

from task_generator import TaskGenerator
from context import Context
from src.hierarchical_node import HierarchicalNode
from src.node_manager import NodeManager



config = ConfigManager('config.json')


# Configure logging
logging.basicConfig(filename='logs/my_log_file.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')



task_prompt_part = """\nPerform the description: field in the backticks below\n use only the actions described in your prompt to do the task. Do not be verbose, 
do not provide any other commentary\n\n
Use a script to perform the task, do not do it manually\n\n
Avoid user interaction\n\n
User scrits to access the internet\n\n
output format: only output actions from the list above there is no need to provide any other comentary do not be verbose!\n
IMPORTANT: If the state is 'retry' consult the info: field, if you cannot resolve the issue return ERROR \n"""

task_prompt_part_goal = """\nYour mission is to break down the requirement found in the description: below into a list of steps that other assisaatant or humans will then
perform using the following primatives(action_save_file,action_load_file, action_execute_command, action_request_user_action) You will ONLY use the 'action_add_steps' primative to
have then external system prepare a task list. You should aim to break the task into manageble tasks and provide sufficent detail. 

When you have got the list of tasks you then need return one 'action_add_steps' per task in the response. You will:
* put a short name in the name field,
* put the detaied deascription of the task in the description field in the 'action_add_steps'
* the status is set to none
* most important is that you will take the node_id given in the context:  this must go in the current_node_id field of the action
* you must adhere to the EXACT format shown in the previous system prompt

Output format example (assuming you had 2 tasks to add):
action_add_steps: current_node_id: ``` 999999.9999  ``` name: ``` example name ``` description: ``` exampleyour description ``` state: ``` none ```  \n
action_add_steps: current_node_id: ``` 123456.1234  ``` name: ``` example name 2 ``` description: ``` exampleyour description2 ``` state: ``` none ``` \n

Do not be verbose, do not provide any other commentary - just the action_add_steps primative in the format shown in the previous system prompt\n\n
IMPORTANT: If the state is 'retry' consult the info: field, if you cannot resolve the issue return ERROR \n"""

class Automation:

    def __init__(self ):
        base_path = os.path.dirname(os.path.realpath('sandpit'))
        self.goal = None
        self.steps_yaml = None
        self.steps = None
        self.context = Context()
        self.node_manager = NodeManager()
        task_update_handler = TaskUpdateHandler(self.node_manager) 
        file_save_handler = FileSaveHandler()
        command_execution_handler = CommandExecutionHandler()
        user_action_required_handler = UserActionRequiredHandler()
        file_load_handler = FileLoadHandler()
        self.handler = QuokkaLoki()
        self.handler.add_handler(file_save_handler)
        self.handler.add_handler(command_execution_handler)
        self.handler.add_handler(user_action_required_handler)
        self.handler.add_handler(file_load_handler)
        self.handler.add_handler(task_update_handler)
        self.task_generator = TaskGenerator(self.node_manager)

    def test_extract_action(self):
        request = ''' hello zzz ddd fgg 123 ```action_save_file: file_path: ``` insert your path ``` file_name: ```hello_world.py``` file_content:```print("hello world!")``` ``` 
    99 myohmy code: blah ```action_add_steps: current_node_id: ```node id``` name: ```Create Python file``` description: ```Create a new Python file named 'hello_world.py' that outputs 'hello world!'``` state: ```none``` ```'''
        action_name = 'action_save_file'
        parameter_names = ['file_path', 'file_name', 'file_content']
        result = QuokkaLoki.extract_action(request, action_name, parameter_names)
        print(result)

        action_name = 'action_add_steps'
        parameter_names = ['current_node_id', 'name', 'description', 'state']
        result = QuokkaLoki.extract_action(request, action_name, parameter_names)
        print(result)

    def test_extract_action2(self):
        request = ''' Processing code response: ```action_save_file: file_path: ```insert your path``` file_name: ```hello_world.py``` file_content:```print("hello world!")``` ```
```action_add_steps: current_node_id: ```node id``` name: ```Create Python file``` description: ```Create a new Python file named 'hello_world.py' that outputs 'hello world!'``` state: ```none``` ```context_info:```'''

        request2 = ''' '```action_execute_command: command: ```python hello_world.py``` command_path: ```insert your path``` ```' '''
        result = self.handler.process_request(request2)
        zz = self.handler_repsonse_formated_text(result) 
        print(result)

     

    def handler_repsonse_formated_text(self, response) -> str:
        response_text = ''
        for handler_response in response:
            for respnose_element in handler_response:
                xx = respnose_element.keys()
                key = list(respnose_element.keys())[0]
                value = list(respnose_element.values())[0]
                response_text += key + ': ' + value + '\n'

        return response_text

        


    def run(self, user_goal: str) -> str:
        max_iterations = 10
        #self.task_generator.generate_tasks(user_goal)

        self.workout_steps('search internet for hot cross buns, then prepare a blog entry about them')

        self.top_node = self.node_manager.get_nodes_conversation_id("conv1", "top")

        self.task_nodes = self.node_manager.get_nodes_parent_id(self.top_node[0].id) 

        #self.test_extract_action2()
        self.context = Context()

        itr = 0
        while itr < max_iterations:

            next_step = self.find_next_step(self.steps)
            if next_step:
                self.process_step(next_step)
            else:
                print("No more steps to process")
                break

            itr += 1

    def process_step(self, step):
        if step:

            context_text = self.context.get_info_text()  

            my_step_text = step.get_formatted_text(["name", "description", "info", "state"])
 
            message = task_prompt_part + " ```" + my_step_text + " ```" + " ```" + 'context_info:'  + context_text + "``` " 

            response = self.ask(message)
            
            rh_repsonse = self.handler.process_request(response)
            response_text = self.handler_repsonse_formated_text(rh_repsonse)
   

            prompt2 = "Did these requests complete correctly - see response ? (yes/no)  request: " + response + " response: " + response_text


            response2 = self.ask(prompt2)
            response2 = response2.lower()
            if "yes" in response2:
                step.state = 'completed'
                context_info = {"response": step.id + ': ' + response}
                self.context.add_info(context_info)
                context_info = {"handler_result:": response_text}
                self.context.add_info(context_info)
            else:
                context_info = {"response": step.id + ': ' + f"ERROR - this method did not work: {response}  You must try some other appraoch"}
                self.context.add_info(context_info)
                context_info = {"handler_result:": f"ERROR - here is the response when running your request : {response_text}  You must try some other appraoch"}
                self.context.add_info(context_info)
                step.state = 'retry'
                step.info = response2

            #self.context.add_info(context_info)



    def workout_steps(self, goal):
        
        top_node = HierarchicalNode("top", "conv1", goal)
        #top_node.id= '1684550657.07442864'  #testing aid
        self.node_manager.add_node(top_node) 

        self.context.add_info({"parent_node_id": top_node.id})
        context_text = self.context.get_info_text()  

        my_step_text = top_node.get_formatted_text(["name", "description", "info", "state"])
 
        message = task_prompt_part_goal + " ```" + my_step_text + " ```" + " ```" + 'context_info:'  + context_text + "``` " 

        response = self.ask(message)
        #response = ''' action_add_steps: current_node_id: ``` 1684550657.07442864 ``` name: ``` Identify high yield stocks ``` description: ``` Use a stock analysis tool to identify the top 5 high yield stocks based on the given criteria. ``` state: ``` none ```  \n\naction_add_steps: current_node_id: ``` 1684550657.07442864 ``` name: ``` Save high yield stocks as CSV ``` description: ``` Save the identified high yield stocks as a CSV file with the given file name and path. ``` state: ``` none ``` '''
            
        rh_repsonse = self.handler.process_request(response)
        response_text = self.handler_repsonse_formated_text(rh_repsonse)


  


    def find_next_step(self, steps):
        # Check if there's an "in progress" step
        for node in self.task_nodes:
            if node.state == 'in_progress':
                print('A step is currently in progress.')
                return None

        # If there's no "in progress" step, find the next available step
        for node in self.task_nodes:
            if node.state == 'none':
                return node
            if node.state == 'retry':
                return node

        # If no next step is found, return None
        return None
    
    
    
    def find_next_step2(self, steps):
        # Check if there's an "in progress" step
        for step in steps['steps']:
            if step['state'] == 'in_progress':
                print('A step is currently in progress.')
                return None

        # If there's no "in progress" step, find the next available step
        for step in steps['steps']:
            if step['state'] == 'none':
                return step

        # If no next step is found, return None
        return None

    def ask(self, question: str, agentName:str = 'doris') -> str:
        agentName = agentName
        accountName = "auto"
        #select_type = request.json.get('selectType', '')
        conversationId = "auto"
        agent_manager = container.get(AgentManager)
        my_agent = agent_manager.get_agent(agentName)
        select_type = my_agent['select_type']

        processor = MessageProcessor()

        processor.context_type = select_type
        # Modify the process_message method in the MessageProcessor class if needed
        #process_message(self, agent_name:str, account_name:str, message, conversationId="0"):
        response = processor.process_message(agentName, accountName, question, conversationId)
        # processor.save_conversations()
        return response

    

my_auto = Automation()
my_auto.run("create and test the python code for hello world")