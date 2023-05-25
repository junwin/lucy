import os
import re
import yaml
import shlex
import subprocess
import logging
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

    def handle(self, action: dict, account_name:str = "auto") -> List[dict]:
        action_name = action['action_name']
        if action_name != "action_add_steps":
            return None
        
        logging.info(self.__class__.__name__ )
        
        current_node_id = action['current_node_id']
        description = action['description']
        state = action['state']

        name = action['name']
        node_type = 'task'
        if 'node_type' in action:
            node_type = action['node_type']
  
        config = container.get(ConfigManager) 

        my_current_node = self.node_manager.get_node(current_node_id)

        if my_current_node is None:
            return [{"result": f"Error: Invalid node id {current_node_id}"},{ "handler": self.__class__.__name__} ]

        new_node = HierarchicalNode.new_node_minimal(name, my_current_node.conversation_id, description, state)
        new_node.node_type = node_type

        my_current_node.add_child(new_node.id)
        new_node.parent_id = current_node_id
        self.node_manager.add_node(new_node) 

        my_result=[{"result": f"Node added sucess {name}"},{ "handler": self.__class__.__name__} ]

        return my_result


    