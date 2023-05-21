import os
import re
import yaml
import shlex
import subprocess
from typing import List, Tuple
from src.handlers.handler import Handler
from src.node_manager import NodeManager
from src.hierarchical_node import HierarchicalNode 
from src.container_config import container
from src.config_manager import ConfigManager
from src.handlers.quokka_loki import QuokkaLoki 

class TaskUpdateHandler(Handler):
    def __init__(self, node_manager: NodeManager):
        self.node_manager = node_manager

    def handle(self, request:str) :

        if not "action_add_steps:" in request:
            return None
        
        results = []
        next_action_index = 0
        request_len = len(request)
        lines = request.split('\n')

        # Remove any lines that are only whitespace
        lines = [line for line in lines if line.strip()]

        for line in lines:

            my_action = QuokkaLoki.extract_action(line, "action_add_steps:", ['current_node_id', 'name', 'description', 'state'] )
            my_action_name = my_action['action']
            #next_action_index = my_action[my_action_name]
            #next_action_index = next_action_index

            if my_action_name != "action_add_steps:":
                return [ { "handler": self.__class__.__name__}, {"result": 'Error: Invalid action name for save a file command.'}]

            node_id = my_action['current_node_id']
            name = my_action['name']
            description = my_action['description']
            state = my_action['state']

            # get the currtent node using the  id
            my_node = self.node_manager.get_node(node_id)
            if my_node is None:
                return [ { "handler": self.__class__.__name__}, {"result": f"Error: Invalid node id {node_id}"}]

            new_node = HierarchicalNode.new_node_minimal(name, my_node.conversation_id, description, state)
            my_node.add_child(new_node.id)
            new_node.parent_id = my_node.id
            self.node_manager.add_node(new_node) 

            results = results + [{ "handler": self.__class__.__name__}, {"result": f"Node added {name}"}]

        return results
   
