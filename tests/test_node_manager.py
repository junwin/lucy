import pytest
from src.hierarchical_node import HierarchicalNode
from src.node_manager import NodeManager

class TestNodeManager:
    @pytest.fixture
    def node_manager(self):
        return NodeManager()

    def test_get_node(self, node_manager):
        node = HierarchicalNode("test", "conv1")
        node_manager.add_node(node)

        assert node_manager.get_node(node.id) == node
        assert node_manager.get_node("non_existent_id") is None

    def test_add_node(self, node_manager):
        node = HierarchicalNode("test", "conv1")
        node_manager.add_node(node)

        assert node_manager.nodes[node.id] == node

    def test_update_node(self, node_manager):
        node1 = HierarchicalNode("test1", "conv1")
        node2 = HierarchicalNode("test2", "conv1", parent_id=node1.id)
        node1.children.append(node2.id)
        node_manager.add_node(node1)
        node_manager.add_node(node2)

        updated_node1 = HierarchicalNode("updated_test1", "conv1")
        node_manager.update_node(node1.id, updated_node1)

        assert node_manager.get_node(node1.id) == updated_node1
        assert node_manager.get_node(node2.id) is None

    def test_delete_node(self, node_manager):
        node1 = HierarchicalNode("test1", "conv1")
        node2 = HierarchicalNode("test2", "conv1", parent_id=node1.id)
        node1.children.append(node2.id)
        node_manager.add_node(node1)
        node_manager.add_node(node2)

        node_manager.delete_node(node1.id)

        assert node_manager.get_node(node1.id) is None
        assert node_manager.get_node(node2.id) is None

    def test_repr(self, node_manager):
        node = HierarchicalNode("test", "conv1")
        node_manager.add_node(node)

        assert repr(node_manager) == f"NodeManager(nodes={{'{node.id}': {node}}})"