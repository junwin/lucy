import json
import datetime
import time
from typing import List, Dict, Set

class HierarchicalNode:
    def __init__(self, name: str, conversation_id: str, info: str = "", parent_id: str = "", children: List[str] = None):
        self.name = name
        self.conversation_id = conversation_id
        self.info = info
        self.parent_id = parent_id
        self.utc_timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        self.id = str(time.time())
        self.children = children if children else []
        self.tags: List[str] = []
        self.state: str = "none"

    def add_child(self, child_id: str):
        self.children.append(child_id)

    def remove_child(self, child_id: str):
        if child_id in self.children:
            self.children.remove(child_id)

    def __repr__(self):
        return f"HierarchicalNode(name={self.name}, children={self.children})"

    def as_dict(self) -> Dict[str, any]:
        return {
            "name": self.name,
            "conversation_id": self.conversation_id,
            "info": self.info,
            "parent_id": self.parent_id,
            "utc_timestamp": self.utc_timestamp,
            "id": self.id,
            "tags": self.tags,
            "children": self.children,
            "state": self.state
        }

    @classmethod
    def from_dict(cls, node_dict: Dict[str, any]) -> 'HierarchicalNode':
        node = cls(
            name=node_dict["name"],
            conversation_id=node_dict["conversation_id"],
            info=node_dict.get("info", ""),
            parent_id=node_dict.get("parent_id", ""),
            children=node_dict.get("children", [])
        )
        node.utc_timestamp = node_dict.get("utc_timestamp", datetime.datetime.utcnow().isoformat() + "Z")
        node.id = node_dict.get("id", str(time.time()))
        node.tags = node_dict.get("tags", [])
        node.state = node_dict.get("state", "none")
        return node
