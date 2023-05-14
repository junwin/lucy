import pytest
from src.completion.completion import Completion
from src.completion.message import Message
from src.completion.completion_manager import CompletionManager

@pytest.fixture
def completion_manager():
    manager = CompletionManager("c:/temp/", "agent_name", "account_name")
    completions = [
        Completion("id1", "time", 10, [Message("user", "Hello")], ["Hello"], "conversation_id1"),
        Completion("id2", "time", 15, [Message("user", "Hello World")], ["Hello", "World"], "conversation_id2"),
        Completion("id3", "time", 20, [Message("user", "Hello OpenAI")], ["Hello", "OpenAI"], "conversation_id3"),
    ]
    for completion in completions:
        manager.store_completion(completion)
    return manager

def test_store_completion(completion_manager):
    new_completion = Completion("id4", "time", 25, [Message("user", "Hello GPT4")], ["Hello", "GPT4"], "conversation_id4")
    assert completion_manager.store_completion(new_completion) == True
    assert len(completion_manager.completions) == 4
    completion_manager.save()

def test_get_completion(completion_manager):
    completion = completion_manager.get_completion("id2")
    assert completion is not None
    assert completion.id == "id2"

def test_get_completion_byId(completion_manager):
    completions = completion_manager.get_completion_byId(["id1", "id3"])
    assert len(completions) == 2
    assert completions[0].id == "id1"
    assert completions[1].id == "id3"

def test_update_completion(completion_manager):
    updated_completion = Completion("id1", "new_time", 30, [Message("user", "Updated")], ["Updated"], "conversation_id1")
    assert completion_manager.update_completion(updated_completion) == True
    completion = completion_manager.get_completion("id1")
    assert completion.total_chars == 30

def test_delete_completion(completion_manager):
    assert completion_manager.delete_completion("id3") == True
    assert len(completion_manager.completions) == 2
    assert completion_manager.get_completion("id3") is None
