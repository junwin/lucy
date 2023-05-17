import json
from typing import List, Dict, Set
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

    def add_node(self, node: HierarchicalNode) -> None:
        self.nodes[node.id] = node

    def update_node(self, node_id: str, updated_node: HierarchicalNode) -> None:
        existing_node = self.get_node(node_id)
        if existing_node:
            orphan_ids = set(existing_node.children) - set(updated_node.children)
            for orphan_id in orphan_ids:
                self.delete_node(orphan_id)
            self.nodes[node_id] = updated_node

    def delete_node(self, node_id: str) -> None:
        node = self.get_node(node_id)
        if node:
            node.state = "deleted"
            for child_id in node.children:
                self.delete_node(child_id)

    def __repr__(self):
        return f"NodeManager(nodes={self.nodes})"
