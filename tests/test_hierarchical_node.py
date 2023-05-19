import pytest
from src.hierarchical_node import HierarchicalNode

class TestHierarchicalNode:
    def test_init(self):
        node = HierarchicalNode("test", "123")
        assert node.name == "test"
        assert node.conversation_id == "123"
        assert node.description == ""
        assert node.info == ""
        assert node.parent_id == ""
        assert node.children == []
        assert node.tags == []
        assert node.state == "none"

    def test_add_child(self):
        node = HierarchicalNode("test", "123")
        node.add_child("456")
        assert "456" in node.children

    def test_remove_child(self):
        node = HierarchicalNode("test", "123", children=["456"])
        node.remove_child("456")
        assert "456" not in node.children

    def test_as_dict(self):
        node = HierarchicalNode("test", "123")
        node_dict = node.as_dict()
        assert node_dict["name"] == "test"
        assert node_dict["conversation_id"] == "123"
        assert node_dict["description"] == ""
        assert node_dict["info"] == ""
        assert node_dict["parent_id"] == ""
        assert node_dict["children"] == []
        assert node_dict["tags"] == []
        assert node_dict["state"] == "none"

    def test_from_dict(self):
        node_dict = {
            "name": "test",
            "conversation_id": "123",
            "description": "mynode",
            "info": "",
            "parent_id": "",
            "children": [],
            "tags": [],
            "state": "none"
        }
        node = HierarchicalNode.from_dict(node_dict)
        assert node.name == "test"
        assert node.conversation_id == "123"
        assert node.description == "mynode"
        assert node.info == ""
        assert node.parent_id == ""
        assert node.children == []
        assert node.tags == []
        assert node.state == "none"

    def test_invalid_cases(self):
        with pytest.raises(TypeError):
            HierarchicalNode(None, "123")

        with pytest.raises(TypeError):
            HierarchicalNode("test", None)

        node = HierarchicalNode("test", "123")
        with pytest.raises(TypeError):
            node.add_child(None)

        with pytest.raises(TypeError):
            node.remove_child(None)

        with pytest.raises(TypeError):
            HierarchicalNode.from_dict(None)

        with pytest.raises(KeyError):
            HierarchicalNode.from_dict({"name": "test"})

        with pytest.raises(KeyError):
            HierarchicalNode.from_dict({"conversation_id": "123"})