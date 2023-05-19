import yaml
from typing import List
from src.hierarchical_node import HierarchicalNode
from src.node_manager import NodeManager

class TaskGenerator:
    def __init__(self, node_manager):
        self.node_manager = node_manager

    def new_node(self, name: str, conversation_id: str, info: str = "", parent_id: str = "", children: List[str] = None):
        return HierarchicalNode(name, conversation_id, info, parent_id, children)
    

    def new_node_minimal(self, name: str, conversation_id: str, description: str = "", state: str = "none"):    
        return HierarchicalNode(name, conversation_id, description, state=state)
    
    def generate_tasks(self, goal):
        if goal == "create and test the python code for hello world":
            top_node = self.new_node_minimal("top", "conv1", "Create and test the python code for hello world.")
            self.node_manager.add_node(top_node) 

            node1 = self.new_node_minimal("Create Python file", "conv1", "Create a new Python file named 'hello_world.py' that outputs 'hello world!'.")
            top_node.add_child(node1.id)
            node1.parent_id = top_node.id
            self.node_manager.add_node(node1)

            node2 = self.new_node_minimal("Run Python file", "conv1", "Run the Python file using the command 'python hello_world.py'.")
            top_node.add_child(node2.id)
            node2.parent_id = top_node.id
            self.node_manager.add_node(node2)

            node3 = self.new_node_minimal("Check output", "conv1", "Check that the output of the Python file is 'Hello, World!'.")
            top_node.add_child(node3.id)
            node3.parent_id = top_node.id
            self.node_manager.add_node(node3)

            my_nodes = self.node_manager.get_nodes_conversation_id("conv1")
            return my_nodes
        



    
    def generate_tasks2(self, goal):
        if goal == "create and test the python code for hello world":
            return """
steps:
  - id: 1
    name: "Create Python file"
    description: "Create a new Python file named 'hello_world.py' that outputs 'hello world!'."
    state: "none"
  - id: 2
    name: "Run Python file"
    description: "Run the Python file using the command 'python hello_world.py'."
    state: "none"
  - id: 3
    name: "Check output"
    description: "Check that the output of the Python file is 'Hello, World!'."
    state: "none"
"""
