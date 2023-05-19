import os
import yaml
import logging

from src.message_processor import MessageProcessor
from src.container_config import container
from src.config_manager import ConfigManager
from src.agent_manager import AgentManager
from src.handlers.quokka_loki import QuokkaLoki
from task_generator import TaskGenerator
from context import Context
from src.hierarchical_node import HierarchicalNode
from src.node_manager import NodeManager



config = ConfigManager('config.json')


# Configure logging
logging.basicConfig(filename='logs/my_log_file.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')



task_prompt_part = """\nPerform the description: field in the  yaml in backticks below\n use onlt the actions described in your prompt to do the task do not provide any other commentary\n\n
output format: only output actions from the list above there is no need to provide any other comentary"""

class Automation:

    def __init__(self ):
        base_path = os.path.dirname(os.path.realpath('sandpit'))
        self.goal = None
        self.handler = QuokkaLoki()
        self.steps_yaml = None
        self.steps = None
        self.context = Context()
        self.node_manager = NodeManager()
        self.task_generator = TaskGenerator(self.node_manager)

    def run(self, user_goal: str) -> str:
        max_iterations = 10
        self.task_generator.generate_tasks(user_goal)
        self.top_node = self.node_manager.get_nodes_conversation_id("conv1", "top")
        self.task_nodes = self.node_manager.get_nodes_parent_id(self.top_node[0].id) 

        #self.steps = yaml.safe_load(self.steps_yaml)

        itr = 0
        while itr < max_iterations:

            next_step = self.find_next_step(self.steps)
            if next_step:
                self.process_step(next_step)
            itr += 1

    def process_step(self, step):
        if step:
            my_step = yaml.dump(step)

            #message = seed_message + "```" + my_steps + "```" 
            message = task_prompt_part + "```" + my_step + "```" 
            response = self.ask(message)
            
            rh_repsonse = self.handler.process_request(response)
            my_class = rh_repsonse[0]
            my_content = rh_repsonse[1]

            prompt2 = "Did these requests complete correctly - see response ? (yes/no)  request: " + response + " response: " + my_content[0][1]


            response2 = self.ask(prompt2)
            response2 = response2.lower()
            if "yes" in response2:
                step.state = 'completed'

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

    def ask(self, question: str) -> str:
        agentName = "doris"
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