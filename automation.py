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



task_prompt_part = """Your task is to provide automantion. Examine the context: provided below, the description: field describe what needs to be done - you will do your best to 
provide a solution\nYou must not ask for user or human intervantion\nWhen the state: is 'retry' the last solution proposed by the AI (you) was not satisfactory so remedial action is required, the context provides the information to resolve things, request shows the request that failed, response: shows the result to running the request and the interpretation: shows why the request failed. Do not forget that any action_ must not be split over muliple lines and must be complete on a single line. 
Check the environment os before using action_execute_command: to run a command. You must only respond with actions - do not provide comentary or update the context, 
ALL paths and folders must be relative and added to the the output_folder: provided in the context.
When developing code use action_save_file: to save the code to the output_folder: provided in the context.
When running a .bat .cmd .exe use action_execute_command: to run the command in the output_folder: provided in the context.
do not install components e.g. pip install - assume they are installed.
You MUST NOT request user input for example, you should not ask the user to provide a file path or file name or browse the internet for information. Use scripts or curl to access the internet
"""

task_prompt_part_goal = """The purpose of this request is to break down a given requirement/goal into a set of steps using the 
provided action primitives (action_save_file, action_load_file, action_execute_command). 
The assistant should use the 'action_add_steps' primitive to prepare a task list for external systems or other assistants. 
The goal is to divide the goal into manageable tasks
You MUST avoid tasks that require human intervention for example, you should not ask the user to provide a file path or file name or browse the internet for information.

To accomplish this, please follow these guidelines:

1. Use the 'action_add_steps' primitive to return one action per task in the response.
2. In the 'name' field, provide a short name for the task.
3. In the 'description' field of the 'action_add_steps', provide a detailed description of the task.
4. Set the 'state' to 'none' for each task.
5. Most importantly, take the 'node_id' provided in the context and include it in the 'current_node_id' field of the action.
6. Adhere precisely to the format shown in the previous system prompt.

Please ensure the following format is used for the 'action_add_steps' action:

Here are output examples:
action_add_steps: current_node_id: ```999999.9999```  name: ```example name``` description: ```example description```  state: ```none``` 
action_request_user_action: message: ```your message```

YOU MUST!!! use the triple backticks as shown in the examples and have a complete action_ per line DO NOT SPLIT AN ACTION OVER MULTIPLE LINES FOLLOW THE EXAMPLE !!!!! !!!!!

Avoid being verbose and providing any other commentary. 
"""





class Automation:

    def __init__(self ):
        base_path = os.path.dirname(os.path.realpath('sandpit'))
        self.goal = None
        self.steps_yaml = None
        self.steps = None
        self.goal_context = None
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

        self.workout_steps(user_goal)

        self.top_node = self.node_manager.get_nodes_conversation_id("conv1", "top")
        self.top_node = self.top_node[0]

        self.task_nodes = self.node_manager.get_nodes_parent_id(self.top_node.id) 

   
        self.top_context = self.get_context_from_node(self.top_node)

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

            if step.state == 'none':
                step.state = 'in_progress'
                self.step_context = self.get_context_from_node(step)


            context_text = self.step_context.get_info_text()  

            my_step_text = step.get_formatted_text(["name", "description", "info", "state"])
 
            message = task_prompt_part + "  " + 'context_info:'  + context_text + " " 

            response = self.ask(message)
            
            rh_repsonse = self.handler.process_request(response)
            response_text = self.handler_repsonse_formated_text(rh_repsonse)
   

            prompt2 = "Did these requests complete correctly - see response ? first always answer (yes/no)  then and recomend remedial action  request: " + response + " response: " + response_text


            critic_response = self.ask(prompt2)
            critic_response = critic_response.lower()
            if "yes" in critic_response:
                step.state = 'completed'
            else:
                step.state = 'retry'

            self.step_context.add_action(response, response_text, 'ERROR -' + critic_response)





    def workout_steps(self, goal:str, conversation_id:str = 'conv1'):
        
        top_node = HierarchicalNode("top", conversation_id, goal)
        #top_node.id= '1684550657.07442864'  #testing aid
        self.node_manager.add_node(top_node) 

        self.goal_context = self.get_context_from_node(top_node)
        context_text = self.goal_context.context_formated_text()

        #my_step_text = top_node.get_formatted_text(["name", "description", "info", "state"])
 
        message = task_prompt_part_goal + " ```"  + 'context_info:'  + context_text + "``` " 

        response = self.ask(message)
        #response = ''' action_add_steps: current_node_id: ``` 1684550657.07442864 ``` name: ``` Identify high yield stocks ``` description: ``` Use a stock analysis tool to identify the top 5 high yield stocks based on the given criteria. ``` state: ``` none ```  \n\naction_add_steps: current_node_id: ``` 1684550657.07442864 ``` name: ``` Save high yield stocks as CSV ``` description: ``` Save the identified high yield stocks as a CSV file with the given file name and path. ``` state: ``` none ``` '''
            
        repsonse_handler = self.handler.process_request(response)
        response_text = self.handler_repsonse_formated_text(repsonse_handler)

        self.goal_context.add_action(response, response_text, 'none')




  


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
    
    
    def get_context_from_node(self, node):
        context = Context(name=node.name, description=node.description, current_node_id=node.id, state=node.state)
        context.add_info(node.info)

        return context


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
#my_auto.run("create and test the python to print the first 5 prime numbers")
#my_auto.run("whats on the first page of www.unwin.com")
#my_auto.run('read then store text form this webpage https://echoblang.wordpress.com/2015/08/09/fast-introduction-to-scrum/  into a file called scrum.txt, then load the file and have an AI assitant summarize it and save the summary to a file called scrum_summary.txt')
my_auto.run("load file scrum.txt and then tell the assistant to summarize it")
