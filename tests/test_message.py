import pytest
from typing import List, Dict
from src.completion.utils import get_id, get_complete_path

from src.completion.message import Message

@pytest.fixture
def sample_message():
    return Message("Admin", "Hello world")

def test_message_constructor(sample_message):
    assert sample_message.role == "Admin"
    assert sample_message.content == "Hello world"

def test_message_from_dict():
    message_dict = {"role": "User", "content": "Test message"}
    message = Message.from_dict(message_dict)
    assert message.role == "User"
    assert message.content == "Test message"

def test_message_from_list_dict():
    message_list = [
        {"role": "User", "content": "Message 1"},
        {"role": "Admin", "content": "Message 2"}
    ]
    messages = Message.from_list_dict(message_list)
    assert len(messages) == 2

    assert messages[0].role == "User"
    assert messages[0].content == "Message 1"

    assert messages[1].role == "Admin"
    assert messages[1].content == "Message 2"
