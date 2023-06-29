import yaml

from src.node_manager import NodeManager
from src.handlers.task_update_handler import TaskUpdateHandler
from src.hierarchical_node import HierarchicalNode
from src.context.context_manager import ContextManager 
from src.context.context import Context 
from src.handlers.quokka_loki import QuokkaLoki
from src.container_config import container

class TaskBuilder:
    def __init__(self ):
        self.node_manager = container.get(NodeManager)
        self.quokka_loki = QuokkaLoki()
        self.quokka_loki.add_handler(TaskUpdateHandler(self.node_manager))
        self.top_node = None

    def create_task_nodes(self, goal:str, account_name: str, conversation_id:str = 'conv1') :
        self.process_yaml_spec(goal, account_name, conversation_id)
        #self.setup_demo_steps(goal, account_name, conversation_id)


    def setup_demo_steps(self, goal:str, account_name:str, conversation_id:str = 'conv1') :
        self.setup_top_node(goal, account_name, conversation_id)
        current_node_id = self.top_node.id
        add_tasks = ''

  
        #add_tasks += f" <action_add_steps> current_node_id: ```{current_node_id}``` name: ```find etfs ``` description: ``` search the web for the top 5 high yield ETFs ``` state: ```none``` </action>\n"

        #add_tasks += f" <action_add_steps> current_node_id: ```{current_node_id}``` name: ```read extract.txt ``` description: ``` read the file extract.txt ``` state: ```none``` </action>\n"

        #add_tasks += f" <action_add_steps> current_node_id: ```{current_node_id}``` name: ```write a new function``` description: ``` 1) write the python code  grab_text.py that a web url as a parameter then uses beautifulSoup to scrape the web page's text and prints the text. 2) then save it``` state: ```none``` </action>\n"
        #add_tasks += f" <action_add_steps> current_node_id: ```{current_node_id}``` name: ```run grab_text.py ``` description: ``` run grab_text.py to scrape https://seekingalpha.com/article/4601929-the-10-best-high-yield-monthly-paying-etfs-youve-never-heard-of and redirect the output to a file extract.txt ``` state: ```none``` </action>\n"
        #add_tasks += f" <action_add_steps> current_node_id: ```{current_node_id}``` name: ```get the extract file ``` description: ``` get the file extract.txt from the working folder ``` state: ```none``` </action>\n"
        
        #add_tasks += f" <action_add_steps> current_node_id: ```{current_node_id}``` name: ```load files  ``` description: ``` load hierarchical_node.py and node_manager.py into the context ``` state: ```none``` </action>\n"
        #add_tasks += f" <action_add_steps> current_node_id: ```{current_node_id}``` name: ```write test code 1 ``` description: ``` write a pytest for  hierarchical_node.py and save the file``` state: ```none``` </action>\n"
        #add_tasks += f" <action_add_steps> current_node_id: ```{current_node_id}``` name: ```write test code 2 ``` description: ``` write a pytest for  node_manager.py and save the file``` state: ```none``` </action>\n"

        add_tasks += f" <action_add_steps> current_node_id: ```{current_node_id}``` name: ```load files  ``` description: ``` load hierarchical_node.py and test_hierarchical_node.py into the context ``` state: ```none``` </action>\n"
        add_tasks += f" <action_add_steps> current_node_id: ```{current_node_id}``` name: ```run test ``` description: ``` run pytest for test_hierarchical_node.py ``` state: ```none``` </action>\n"
       

        results = self.quokka_loki.process_request(add_tasks)
        print(QuokkaLoki.handler_repsonse_formated_text(results))

    def setup_top_node(self, goal:str, account_name:str, conversation_id:str) :
        self.top_node = HierarchicalNode("top", conversation_id, goal)
        self.top_node.account_name = account_name
        self.node_manager.add_node(self.top_node) 
        self.goal_context = self.get_context_from_node(self.top_node)

    def get_context_from_node(self, node):
        context = Context(name=node.name, description=node.description, current_node_id=node.id, state=node.state, account_name=node.account_name, conversation_id=node.conversation_id)
        context.add_info(node.info)

        return context
    

 

    def process_yaml_spec(self, goal:str, account_name:str, conversation_id:str = 'conv1'):
        
        self.setup_top_node(goal, account_name, conversation_id)

        current_node_id = self.top_node.id

        results = self.quokka_loki.process_yaml_goals(goal, current_node_id, account_name, conversation_id, working_directory='')
        
        print(QuokkaLoki.handler_repsonse_formated_text(results))

    

    my_spec = """- name: Project Setup
  description: Set up a new Vue 3 project using Vite, named 'fpe_assembly'.

- name: run npm install
  description: run npm install to install the project dependencies.

- name: Install Axios
  description: Install Axios for performing HTTP requests.

- name: Services Setup and Error Handling
  description: Write the code for a 'DataService' class with two asynchronous methods, 'getAssemblyById(d_id)' and 'getScMaster()'. Implement basic error handling for the axios calls in the 'DataService', with any caught errors being logged to the console - Save the code in the 'src/services' directory releative to the output_directory

- name: Define Data Structures
  description: Define the data structures for the 'assemblies' and 'sc_master' objects based on the provided sample return data.

- name: Create Vue Component and Apply Styling
  description: |
    Create a Vue 3 component 'EditAssembly.vue' that will display and edit assembly data fetched by using 'DataService'. The component's template will include the following fields:
      - Heading: Edit Assembly ID 999999 (field name: d_id)
      - Assembly ID: read only text (field name: d_id)
      - ACME Drawing Number: readonly text (field name: drawnum)
      - Description: Text Area (field name: assemblydesc)
      - Client P/N: input field, text (field name: custpn)
      - Revision: input field, text (field name: revision)
      - Client: Dropdown (uses the sc_company field returned in dataService getScMaster() method)
      - Type: Dropdown (values AA, BB, CC, DD)
    Data returned from the DataService will be as per the provided example.
    Apply minimal styling to the application, with all elements left-justified.

- name: Integration of Vue Component
  description: Integrate 'EditAssembly.vue' component into 'App.vue'.

- name: Implement Testing
  description: Implement unit tests for the application using Vitest, Vite's built-in testing tool. """