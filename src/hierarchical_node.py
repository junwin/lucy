import json
import datetime
import time
from typing import List, Dict, Set

class HierarchicalNode:
    incrementing_id = 0
    def __init__(self, name: str, conversation_id: str, description: str = "",  info: str = "", parent_id: str = "", children: List[str] = None, state: str = "none", node_type: str = "node"):
        self.name = name
        self.description = description
        self.conversation_id = conversation_id
        self.info = info
        self.parent_id = parent_id
        self.utc_timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        self.id = self.get_id()
        self.children = children if children else []
        self.tags: List[str] = []
        self.state: str = state
        self.node_type: str = "node"

    @classmethod
    def as_dict(self) -> Dict[str, any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description, 
            "conversation_id": self.conversation_id,
            "info": self.info,
            "parent_id": self.parent_id,
            "utc_timestamp": self.utc_timestamp,
            "id": self.id,
            "tags": self.tags,
            "children": self.children,
            "state": self.state,
            "node_type": self.node_type
        }

    @classmethod
    def from_dict(cls, node_dict: Dict[str, any]) -> 'HierarchicalNode':
        node = cls(
            name=node_dict["name"],
            description=node_dict["description"],
            conversation_id=node_dict["conversation_id"],
            info=node_dict.get("info", ""),
            parent_id=node_dict.get("parent_id", ""),
            children=node_dict.get("children", [])
        )
        node.utc_timestamp = node_dict.get("utc_timestamp", datetime.datetime.utcnow().isoformat() + "Z")
        node.id = node_dict.get("id", str(time.time()))
        node.tags = node_dict.get("tags", [])
        node.state = node_dict.get("state", "none")
        node.node_type = node_dict.get("node_type", "node") 
        return node
    

    @classmethod
    def new_node_minimal(cls, name: str, conversation_id: str, description: str = "", state: str = "none"):    
        return cls(name, conversation_id, description, state=state)

    def get_id(self) -> str:
        id =  str(time.time()) + str(HierarchicalNode.incrementing_id)
        HierarchicalNode.incrementing_id += 1
        return id

    def add_child(self, child_id: str):
        self.children.append(child_id)

    def remove_child(self, child_id: str):
        if child_id in self.children:
            self.children.remove(child_id)

    def __repr__(self):
        return f"HierarchicalNode(name={self.name}, children={self.children})"


    
    def get_node_field_names(self) -> List[str]:
        return ["name", "description", "conversation_id", "info", "parent_id", "utc_timestamp", "id", "tags", "children", "state"]
    
    def check_string_elements_present(self, list1, list2):
        for element in list1:
            if element not in list2:
                return False     
        return True
    
    def get_formatted_text(self, fields: List[str]) -> str:
        if not self.check_string_elements_present(fields, self.get_node_field_names()):
            return "Invalid fields provided"
        
        response = ""
        for element in fields:
            response += element + ": " + str(getattr(self, element)) + "\n"

        return response

        
