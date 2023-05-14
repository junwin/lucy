import pytest
from typing import List, Dict
from src.completion.completion import Completion
from src.completion.message import Message

@pytest.fixture
def sample_completion():
    messages = [
        Message("User", "Hello"),
        Message("Assistant", "Hi, how can I assist you?")
    ]
    return Completion("1", "2023-05-13", 10, messages, ["tag1", "tag2"], "conversation-1")

def test_completion_constructor(sample_completion):
    assert sample_completion.id == "1"
    assert sample_completion.utc_timestamp == "2023-05-13"
    assert sample_completion.total_chars == 10
    assert len(sample_completion.messages) == 2
    assert sample_completion.tags == ["tag1", "tag2"]
    assert sample_completion.conversation_id == "conversation-1"

def test_completion_repr(sample_completion):
    expected_id = "1"
    expected_utc_timestamp = "2023-05-13"
    expected_total_chars = 10
    expected_messages = [
        Message("User", "Hello"),
        Message("Assistant", "Hi, how can I assist you?")
    ]
    expected_tags = ["tag1", "tag2"]
    expected_conversation_id = "conversation-1"

    assert sample_completion.id == expected_id
    assert sample_completion.utc_timestamp == expected_utc_timestamp
    assert sample_completion.total_chars == expected_total_chars
    assert sample_completion.messages[0].role == expected_messages[0].role
    assert sample_completion.messages[0].content == expected_messages[0].content
    assert sample_completion.tags == expected_tags
    assert sample_completion.conversation_id == expected_conversation_id

def test_completion_is_none_or_empty():
    completion = Completion("", "", 0, [], [], "")
    assert completion.is_none_or_empty("") is True
    assert completion.is_none_or_empty("   ") is True
    assert completion.is_none_or_empty("Hello") is False

def test_completion_add_response_messages(sample_completion):
    request = "Can you help me with this?"
    response = "Sure, what do you need assistance with?"
    sample_completion.add_response_messages(request, response)
    assert len(sample_completion.messages) == 4
    assert sample_completion.messages[-2].role == "assistant"
    assert sample_completion.messages[-2].content == response
    assert sample_completion.messages[-1].role == "user"
    assert sample_completion.messages[-1].content == request

def test_completion_add_response_message(sample_completion):
    message_text = "How can I place an order?"
    message_role = "User"
    sample_completion.add_response_message(message_text, message_role)
    assert len(sample_completion.messages) == 3
    assert sample_completion.messages[-1].role == message_role
    assert sample_completion.messages[-1].content == message_text
