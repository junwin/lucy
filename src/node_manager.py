import json
from pathlib import Path
from typing import List, Dict
from src.hierarchical_node import HierarchicalNode


class NodeManager:
    def __init__(self):
        self.nodes: Dict[str, HierarchicalNode] = {}

    def get_node(self, node_id: str) -> HierarchicalNode:
        node = self.nodes.get(node_id)
        if node and node.state != "deleted":
            return node
        else:
            return None

    def get_nodes_conversation_id(self, conversation_id: str, name: str = None) -> List[HierarchicalNode]:
        nodes = []
        for node in self.nodes.values():
            if node.conversation_id == conversation_id and node.state != "deleted":
                if name:
                    if node.name == name:
                        nodes.append(node)
                else:
                    nodes.append(node)
        return nodes

    def get_nodes_parent_id(self, parent_id: str) -> List[HierarchicalNode]:
        nodes = []
        for node in self.nodes.values():
            if node.parent_id == parent_id and node.state != "deleted":
                nodes.append(node)
        return nodes

    def add_node(self, node: HierarchicalNode) -> None:
        self.nodes[node.id] = node

    def update_node(self, node_id: str, updated_node: HierarchicalNode) -> None:
        """Update an existing node in the manager without removing its children."""
        if node_id in self.nodes:
            self.nodes[node_id] = updated_node

    def delete_node(self, node_id: str) -> None:
        node = self.get_node(node_id)
        if node:
            node.state = "deleted"
            for child_id in node.children:
                self.delete_node(child_id)

    def to_dict(self) -> Dict[str, Dict]:
        return {node_id: node.as_dict() for node_id, node in self.nodes.items()}

    @classmethod
    def from_dict(cls, data: Dict[str, Dict]) -> "NodeManager":
        nm = cls()
        for node_id, node_data in data.items():
            nm.nodes[node_id] = HierarchicalNode.from_dict(node_data)
        return nm

    def save_for_conversation(self, conversation_id: str, path: Path) -> None:
        nodes = {
            nid: n.as_dict()
            for nid, n in self.nodes.items()
            if n.conversation_id == conversation_id
        }
        path.write_text(json.dumps(nodes, indent=2))

    @classmethod
    def load_for_conversation(cls, path: Path) -> "NodeManager":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        return cls.from_dict(data)

    def __repr__(self):
        return f"NodeManager(nodes={self.nodes})"