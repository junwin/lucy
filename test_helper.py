    def setup_demo_steps(self, goal:str, conversation_id:str = 'conv1') :
        self.setup_top_node(goal, conversation_id)
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
       
        results = self.handler.process_request(add_tasks)
        print(QuokkaLoki.handler_repsonse_formated_text(results))

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

        request2 = ''' <action_execute_command> command: ```python hello_world.py``` command_path: ```auto/ ``` </action> '''
        result = self.handler.process_request(request2)
        zz = QuokkaLoki.handler_repsonse_formated_text(result) 
        print(result)

     