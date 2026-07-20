"""Tests for DeepSeek vision proxy (Step 7).

Covers:
  - _has_image_content() — detects image parts in messages
  - _strip_image_parts() — removes image parts, keeps text
  - _resolve_images_via_proxy() — replaces images with descriptions
  - Error when proxy is disabled and images present
  - No-op when no images present
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from src.llm.deepseek_responses import DeepSeekApi


# ---------------------------------------------------------------------------
# Tests: _has_image_content
# ---------------------------------------------------------------------------


def test_has_image_content_true():
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": "Hello"},
            {"type": "image", "source": {"data": "AAAA", "mime_type": "image/png"}},
        ]},
    ]
    assert DeepSeekApi._has_image_content(messages) is True


def test_has_image_content_false_text_only():
    messages = [
        {"role": "user", "content": "plain text"},
        {"role": "assistant", "content": "response"},
    ]
    assert DeepSeekApi._has_image_content(messages) is False


def test_has_image_content_false_text_parts_only():
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "World"},
        ]},
    ]
    assert DeepSeekApi._has_image_content(messages) is False


def test_has_image_content_false_empty():
    assert DeepSeekApi._has_image_content([]) is False


def test_has_image_content_false_non_dict_messages():
    messages = [
        "bare string",
        {"role": "user", "content": "text"},
    ]
    assert DeepSeekApi._has_image_content(messages) is False


# ---------------------------------------------------------------------------
# Tests: _strip_image_parts
# ---------------------------------------------------------------------------


def test_strip_image_parts_removes_images():
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": "What's this?"},
            {"type": "image", "source": {"data": "AAAA"}},
        ]},
    ]

    result = DeepSeekApi._strip_image_parts(messages)

    # Single text part collapses to plain string
    assert result[0]["content"] == "What's this?"


def test_strip_image_parts_multiple_text_parts():
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": "Part A"},
            {"type": "text", "text": "Part B"},
        ]},
    ]

    result = DeepSeekApi._strip_image_parts(messages)
    # Multiple text parts stay as list (no image parts to strip)
    assert isinstance(result[0]["content"], list)
    assert len(result[0]["content"]) == 2


def test_strip_image_parts_all_images():
    """When all parts are images, content becomes empty string."""
    messages = [
        {"role": "user", "content": [
            {"type": "image", "source": {"data": "AAAA"}},
            {"type": "image", "source": {"data": "BBBB"}},
        ]},
    ]

    result = DeepSeekApi._strip_image_parts(messages)
    assert result[0]["content"] == ""


def test_strip_image_parts_string_content_unchanged():
    messages = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hello"},
    ]

    result = DeepSeekApi._strip_image_parts(messages)
    assert result == messages


def test_strip_image_parts_non_dict_messages():
    messages = [
        "bare string",
        {"role": "user", "content": "text"},
    ]

    result = DeepSeekApi._strip_image_parts(messages)
    assert result[0] == "bare string"
    assert result[1] == {"role": "user", "content": "text"}


def test_strip_image_parts_mixed():
    """Image parts stripped, text parts kept."""
    messages = [
        {"role": "user", "content": [
            {"type": "image", "source": {"data": "AAAA"}},
            {"type": "text", "text": "Hello"},
        ]},
    ]

    result = DeepSeekApi._strip_image_parts(messages)
    # Single text part after stripping → collapses to string
    assert result[0]["content"] == "Hello"


# ---------------------------------------------------------------------------
# Tests: _resolve_images_via_proxy (with mocked vision client)
# ---------------------------------------------------------------------------


def _make_config(proxy_enabled=True, max_chars=500):
    """Build a mock ConfigManager."""
    config = Mock()
    config.get.side_effect = lambda key, default=None: {
        "vision_proxy": {"enabled": proxy_enabled, "max_description_chars": max_chars, "model": "gpt-4o"},
    }.get(key, default)
    return config


def test_resolve_images_no_images_passes_through():
    messages = [
        {"role": "user", "content": "Hello"},
    ]
    config = _make_config()

    result = DeepSeekApi._resolve_images_via_proxy(messages, config=config)
    assert result == messages


def test_resolve_images_proxy_disabled_raises():
    messages = [
        {"role": "user", "content": [
            {"type": "image", "source": {"data": "AAAA", "mime_type": "image/png"}},
        ]},
    ]
    config = _make_config(proxy_enabled=False)

    with pytest.raises(RuntimeError, match="vision proxy.*disabled"):
        DeepSeekApi._resolve_images_via_proxy(messages, config=config)


def test_resolve_images_replaces_image_with_description():
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": "What's in this?"},
            {"type": "image", "source": {"data": "AAAA", "mime_type": "image/png"}},
        ]},
    ]
    config = _make_config()

    mock_desc = "A screenshot showing a terminal window with code."

    with patch.object(DeepSeekApi, "_describe_image_via_proxy", return_value=mock_desc):
        result = DeepSeekApi._resolve_images_via_proxy(messages, config=config)

    assert len(result) == 1
    content = result[0]["content"]
    assert isinstance(content, str)
    assert "What's in this?" in content
    assert "[Image 1 description:" in content
    assert mock_desc in content


def test_resolve_images_multiple_images():
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": "Compare"},
            {"type": "image", "source": {"data": "AAAA", "mime_type": "image/png"}},
            {"type": "image", "source": {"data": "BBBB", "mime_type": "image/jpeg"}},
        ]},
    ]
    config = _make_config()

    with patch.object(DeepSeekApi, "_describe_image_via_proxy", side_effect=["First image", "Second image"]):
        result = DeepSeekApi._resolve_images_via_proxy(messages, config=config)

    content = result[0]["content"]
    assert "[Image 1 description: First image]" in content
    assert "[Image 2 description: Second image]" in content


def test_resolve_images_no_text_question():
    messages = [
        {"role": "user", "content": [
            {"type": "image", "source": {"data": "AAAA", "mime_type": "image/png"}},
        ]},
    ]
    config = _make_config()

    mock_desc = "A photo of a cat."

    with patch.object(DeepSeekApi, "_describe_image_via_proxy", return_value=mock_desc):
        result = DeepSeekApi._resolve_images_via_proxy(messages, config=config)

    content = result[0]["content"]
    assert content == "[Image 1 description: A photo of a cat.]"


def test_resolve_images_system_message_unchanged():
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": [
            {"type": "image", "source": {"data": "AAAA", "mime_type": "image/png"}},
        ]},
    ]
    config = _make_config()

    with patch.object(DeepSeekApi, "_describe_image_via_proxy", return_value="A chart."):
        result = DeepSeekApi._resolve_images_via_proxy(messages, config=config)

    # System message unchanged
    assert result[0] == {"role": "system", "content": "You are helpful."}
    # User message resolved
    assert "[Image 1 description: A chart.]" in result[1]["content"]


def test_resolve_images_non_dict_messages_preserved():
    messages = [
        "bare string",
        {"role": "user", "content": "Hello"},
    ]
    config = _make_config()

    result = DeepSeekApi._resolve_images_via_proxy(messages, config=config)
    assert result == messages


def test_resolve_images_preserves_non_content_fields():
    messages = [
        {"role": "user", "content": [
            {"type": "image", "source": {"data": "AAAA", "mime_type": "image/png"}},
        ], "name": "john"},
    ]
    config = _make_config()

    with patch.object(DeepSeekApi, "_describe_image_via_proxy", return_value="A diagram."):
        result = DeepSeekApi._resolve_images_via_proxy(messages, config=config)

    assert result[0]["role"] == "user"
    assert result[0]["name"] == "john"
    assert "[Image 1 description: A diagram.]" in result[0]["content"]
