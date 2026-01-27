from src.agent.agent import Agent


def test_allowed_tools_missing_means_allow_none():
    a = Agent.from_dict({"name": "a"})
    assert a.allowed_tools is None
    assert a.allows_tool("anything") is False


def test_allowed_tools_empty_list_means_allow_none():
    a = Agent.from_dict({"name": "a", "allowed_tools": []})
    assert a.allowed_tools == []
    assert a.allows_tool("anything") is False


def test_allowed_tools_non_empty_list_is_allow_list():
    a = Agent.from_dict({"name": "a", "allowed_tools": ["t1", "t2"]})
    assert a.allows_tool("t1") is True
    assert a.allows_tool("t2") is True
    assert a.allows_tool("t3") is False
