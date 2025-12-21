# tests/test_json_file_storage_chats.py

import pytest
from src.storage.json_file_storage import JsonFileStorage


@pytest.fixture
def storage(tmp_path):
    """
    Create a JsonFileStorage rooted in a temporary directory.

    tmp_path is a pytest built-in fixture that gives you an
    empty temp directory that is automatically cleaned up.
    """
    root = tmp_path / "lucy_storage"
    root.mkdir()
    return JsonFileStorage(base_path=str(root))


def test_create_chat_and_list(storage):
    chat_id = storage.create_chat(
        account_name="junwin",
        friendly_name="Therapy session",
    )

    chats = storage.list_chats("junwin")

    assert chat_id in chats
    assert chats[chat_id] == "Therapy session"


def test_append_and_load_chat_messages(storage):
    chat_id = storage.create_chat("junwin")

    storage.append_chat_message(
        account_name="junwin",
        chat_id=chat_id,
        role="user",
        content="Hello Lucy",
    )

    storage.append_chat_message(
        account_name="junwin",
        chat_id=chat_id,
        role="assistant",
        content="Hello John",
    )

    chat = storage.load_chat("junwin", chat_id)

    assert len(chat["messages"]) == 2
    assert chat["messages"][0]["role"] == "user"
    assert chat["messages"][0]["content"] == "Hello Lucy"
    assert chat["messages"][1]["role"] == "assistant"
    assert chat["messages"][1]["content"] == "Hello John"
