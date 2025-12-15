# tests/test_completions_manager.py

import pytest
from src.completion.completion import Completion
from src.completion.message import Message
from src.completion.completion_manager import CompletionManager
from src.storage.json_file_storage import JsonFileStorage


@pytest.fixture
def storage(tmp_path):
    # Each test gets its own fresh storage directory
    return JsonFileStorage(str(tmp_path))


@pytest.fixture
def completion_manager(storage):
    # New-style CompletionManager: first arg is a Storage
    manager = CompletionManager(storage, "agent_name", "account_name")
    # At this point manager.load() will see an empty Storage

    base_completions = [
        Completion("id1", "time", 10, [Message("user", "Hello")], ["Hello"], "conversation_id1"),
        Completion("id2", "time", 15, [Message("user", "Hello World")], ["Hello", "World"], "conversation_id2"),
        Completion("id3", "time", 20, [Message("user", "Hello OpenAI")], ["Hello", "OpenAI"], "conversation_id3"),
    ]
    for completion in base_completions:
        manager.store_completion(completion)

    return manager


def test_store_completion(completion_manager):
    completion = completion_manager.get_completion("id2")
    assert completion is not None
    
    new_completion = Completion(
        "id4",
        "time",
        25,
        [Message("user", "Hello GPT4")],
        ["Hello", "GPT4"],
        "conversation_id4",
    )
    assert completion_manager.store_completion(new_completion) is True
    assert len(completion_manager.completions) == 4

    # Optional: verify that save does not blow up
    completion_manager.save()


def test_get_completion(completion_manager):
    completion = completion_manager.get_completion("id2")
    assert completion is not None
    assert completion.id == "id2"


def test_get_completion_byId(completion_manager):
    completions = completion_manager.get_completion_byId(["id1", "id3"])
    assert len(completions) == 2
    # get_completion_byId sorts by id, so this should be deterministic
    assert completions[0].id == "id1"
    assert completions[1].id == "id3"


def test_update_completion(completion_manager):
    updated_completion = Completion(
        "id1",
        "new_time",
        30,
        [Message("user", "Updated")],
        ["Updated"],
        "conversation_id1",
    )
    assert completion_manager.update_completion(updated_completion) is True
    completion = completion_manager.get_completion("id1")
    assert completion.total_chars == 30


def test_delete_completion(completion_manager):
    assert completion_manager.delete_completion("id3") is True
    # Started with 3, deleted 1 → 2 left
    assert len(completion_manager.completions) == 2
    assert completion_manager.get_completion("id3") is None
