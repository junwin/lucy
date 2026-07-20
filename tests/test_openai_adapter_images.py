"""Tests for OpenAI adapter image content-part normalization (Step 5).

Covers:
  - _normalize_content_parts() — maps intermediate format → OpenAI input_image
  - _normalize_messages() — applies normalization across all messages
  - create_response() — normalizes input before calling the OpenAI client
  - Text parts are renamed to input_text
  - Non-list content passes through unchanged
  - Mixed text + image parts in a single message
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.llm.openai_responses import OpenAIResponsesApi


# ---------------------------------------------------------------------------
# Tests: _normalize_content_parts
# ---------------------------------------------------------------------------


def test_normalize_image_part_to_input_image():
    content = [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image", "source": {"data": "aGVsbG8=", "mime_type": "image/png"}},
    ]

    result = OpenAIResponsesApi._normalize_content_parts(content)

    assert len(result) == 2
    # Text part renamed to input_text
    assert result[0] == {"type": "input_text", "text": "What's in this image?"}
    # Image part mapped to input_image
    assert result[1]["type"] == "input_image"
    assert result[1]["image_url"] == "data:image/png;base64,aGVsbG8="


def test_normalize_image_part_jpeg():
    content = [
        {"type": "image", "source": {"data": "AAAA", "mime_type": "image/jpeg"}},
    ]

    result = OpenAIResponsesApi._normalize_content_parts(content)

    assert result[0]["type"] == "input_image"
    assert result[0]["image_url"] == "data:image/jpeg;base64,AAAA"


def test_normalize_image_part_gif():
    content = [
        {"type": "image", "source": {"data": "R0lG", "mime_type": "image/gif"}},
    ]

    result = OpenAIResponsesApi._normalize_content_parts(content)
    assert result[0]["image_url"] == "data:image/gif;base64,R0lG"


def test_normalize_image_part_webp():
    content = [
        {"type": "image", "source": {"data": "UklG", "mime_type": "image/webp"}},
    ]

    result = OpenAIResponsesApi._normalize_content_parts(content)
    assert result[0]["image_url"] == "data:image/webp;base64,UklG"


def test_normalize_missing_source_defaults_png():
    """When source is missing or not a dict, defaults to image/png."""
    content = [
        {"type": "image", "source": "not-a-dict"},
    ]

    result = OpenAIResponsesApi._normalize_content_parts(content)
    assert "image/png" in result[0]["image_url"]


def test_normalize_empty_source_uses_defaults():
    content = [
        {"type": "image", "source": {}},
    ]

    result = OpenAIResponsesApi._normalize_content_parts(content)
    assert result[0]["image_url"] == "data:image/png;base64,"


def test_normalize_text_parts_renamed_to_input_text():
    content = [
        {"type": "text", "text": "Hello"},
        {"type": "text", "text": "World"},
    ]

    result = OpenAIResponsesApi._normalize_content_parts(content)
    assert result[0]["type"] == "input_text" and result[1]["type"] == "input_text"


def test_normalize_non_list_passes_through_string():
    """String content passes through unchanged."""
    result = OpenAIResponsesApi._normalize_content_parts("plain string")
    assert result == "plain string"


def test_normalize_non_list_passes_through_none():
    result = OpenAIResponsesApi._normalize_content_parts(None)
    assert result is None


def test_normalize_non_dict_part_passes_through():
    content = [
        {"type": "text", "text": "Hello"},
        "bare string in list",
    ]

    result = OpenAIResponsesApi._normalize_content_parts(content)
    assert result[0] == {"type": "input_text", "text": "Hello"}
    assert result[1] == "bare string in list"


def test_normalize_unknown_type_passes_through():
    content = [
        {"type": "custom_thing", "value": 42},
    ]

    result = OpenAIResponsesApi._normalize_content_parts(content)
    assert result == content


def test_normalize_multiple_images():
    content = [
        {"type": "text", "text": "Compare these:"},
        {"type": "image", "source": {"data": "aW1nMQ==", "mime_type": "image/png"}},
        {"type": "image", "source": {"data": "aW1nMg==", "mime_type": "image/jpeg"}},
    ]

    result = OpenAIResponsesApi._normalize_content_parts(content)

    assert len(result) == 3
    assert result[0]["type"] == "input_text"
    assert result[1]["type"] == "input_image"
    assert result[1]["image_url"] == "data:image/png;base64,aW1nMQ=="
    assert result[2]["type"] == "input_image"
    assert result[2]["image_url"] == "data:image/jpeg;base64,aW1nMg=="


# ---------------------------------------------------------------------------
# Tests: _normalize_messages
# ---------------------------------------------------------------------------


def test_normalize_messages_with_content_parts():
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": [
            {"type": "text", "text": "What's this?"},
            {"type": "image", "source": {"data": "AAAA", "mime_type": "image/png"}},
        ]},
    ]

    result = OpenAIResponsesApi._normalize_messages(messages)

    # System message unchanged
    assert result[0] == {"role": "system", "content": "You are helpful."}
    # User message content normalized
    assert isinstance(result[1]["content"], list)
    assert result[1]["content"][0]["type"] == "input_text"
    assert result[1]["content"][1]["type"] == "input_image"


def test_normalize_messages_all_string_content_unchanged():
    messages = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]

    result = OpenAIResponsesApi._normalize_messages(messages)
    assert result == messages


def test_normalize_messages_with_mixed_content_types():
    """Messages with both string content and list content."""
    messages = [
        {"role": "user", "content": "Plain text"},
        {"role": "user", "content": [
            {"type": "image", "source": {"data": "AAAA", "mime_type": "image/png"}},
        ]},
    ]

    result = OpenAIResponsesApi._normalize_messages(messages)

    assert result[0]["content"] == "Plain text"
    assert result[1]["content"][0]["type"] == "input_image"


def test_normalize_messages_non_dict_passes_through():
    messages = [
        {"role": "user", "content": "Hello"},
        "not a dict",
    ]

    result = OpenAIResponsesApi._normalize_messages(messages)
    assert result[0] == {"role": "user", "content": "Hello"}
    assert result[1] == "not a dict"


def test_normalize_messages_non_list_passes_through():
    result = OpenAIResponsesApi._normalize_messages("not a list")
    assert result == "not a list"


def test_normalize_messages_empty_list():
    result = OpenAIResponsesApi._normalize_messages([])
    assert result == []


def test_normalize_messages_preserves_other_message_fields():
    """Non-content fields are preserved."""
    messages = [
        {"role": "user", "content": "Hello", "name": "john", "metadata": {"key": "val"}},
    ]

    result = OpenAIResponsesApi._normalize_messages(messages)
    assert result[0]["role"] == "user"
    assert result[0]["content"] == "Hello"
    assert result[0]["name"] == "john"
    assert result[0]["metadata"] == {"key": "val"}


# ---------------------------------------------------------------------------
# Tests: create_response integration (normalization wired in)
# ---------------------------------------------------------------------------


def _make_mock_openai_client():
    """Build a mock OpenAI client whose responses.create returns a fake response."""
    client = Mock()
    fake_resp = Mock()
    fake_resp.id = "resp-abc-123"
    fake_resp.model = "gpt-4o"
    fake_resp.output_text = "I see a cat in the image."
    fake_resp.tool_calls = None
    fake_resp.output = []
    fake_resp.usage = None
    client.responses.create.return_value = fake_resp
    return client


def test_create_response_normalizes_image_parts():
    """create_response normalizes intermediate image format before calling OpenAI."""
    client = _make_mock_openai_client()
    api = OpenAIResponsesApi(client=client)

    messages = [
        {"role": "system", "content": "You are vision-capable."},
        {"role": "user", "content": [
            {"type": "text", "text": "Describe this:"},
            {"type": "image", "source": {"data": "YWJjZA==", "mime_type": "image/jpeg"}},
        ]},
    ]

    api.create_response(model="gpt-4o", input=messages)

    # Verify client was called with normalized input
    call_kwargs = client.responses.create.call_args.kwargs
    actual_input = call_kwargs["input"]

    assert actual_input[0] == messages[0]  # system message unchanged
    assert actual_input[1]["content"][0] == {"type": "input_text", "text": "Describe this:"}
    assert actual_input[1]["content"][1] == {
        "type": "input_image",
        "image_url": "data:image/jpeg;base64,YWJjZA==",
    }


def test_create_response_passes_through_plain_text():
    """create_response leaves plain text messages unchanged."""
    client = _make_mock_openai_client()
    api = OpenAIResponsesApi(client=client)

    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello world"},
    ]

    api.create_response(model="gpt-4o", input=messages)

    call_kwargs = client.responses.create.call_args.kwargs
    assert call_kwargs["input"] == messages


def test_create_response_handles_string_input():
    """create_response handles a plain string input (non-list)."""
    client = _make_mock_openai_client()
    api = OpenAIResponsesApi(client=client)

    api.create_response(model="gpt-4o", input="Just a string")

    call_kwargs = client.responses.create.call_args.kwargs
    assert call_kwargs["input"] == "Just a string"


def test_create_response_preserves_original_messages():
    """create_response does not mutate the caller's input list."""
    client = _make_mock_openai_client()
    api = OpenAIResponsesApi(client=client)

    messages = [
        {"role": "user", "content": [
            {"type": "image", "source": {"data": "AAAA", "mime_type": "image/png"}},
        ]},
    ]

    original = [
        {"role": "user", "content": [
            {"type": "image", "source": {"data": "AAAA", "mime_type": "image/png"}},
        ]},
    ]

    api.create_response(model="gpt-4o", input=messages)

    # Caller's original is untouched
    assert messages == original
