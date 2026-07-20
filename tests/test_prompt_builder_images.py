"""Tests for PromptBuilder image/file attachment resolution (Step 2).

Covers:
  - _guess_mime_from_path()  — MIME type detection from extensions
  - _find_image_file()       — glob-based file discovery, .json filtering
  - _resolve_attachments()   — image_ids → base64 content parts, file_ids → text parts
  - build_prompt()           — content-part array construction when attachments present
  - Edge cases               — missing IDs, mixed attachments, binary files
"""

from __future__ import annotations

import base64
import os
import tempfile
from unittest.mock import Mock

import pytest

from src.prompt_builders.prompt_builder import PromptBuilder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_images_root():
    """Create a temp directory to serve as the images storage root."""
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def pb_with_temp_dir(temp_images_root):
    """Return a PromptBuilder configured with a temp images directory."""
    agent_manager = Mock()
    mock_agent = Mock()
    mock_agent.max_prompt_conversations = 0
    mock_agent.system_prompt = None
    mock_agent.persona = None
    mock_agent.style_prompt = None
    agent_manager.get_agent.return_value = mock_agent

    config = Mock()
    config.get.side_effect = lambda key, default=None: {
        "storage_root_path": temp_images_root,
        "storage_namespace": "data",
    }.get(key, default)

    storage = Mock()

    return PromptBuilder(
        agent_manager=agent_manager,
        config=config,
        storage=storage,
        chat2_store=None,
    )


def _write_test_image(images_root: str, account: str, img_id: str, ext: str, content: bytes) -> str:
    """Write a test image file and return its full path."""
    account_dir = os.path.join(images_root, "data", "images", account)
    os.makedirs(account_dir, exist_ok=True)
    path = os.path.join(account_dir, f"{img_id}{ext}")
    with open(path, "wb") as f:
        f.write(content)
    return path


def _write_test_file(images_root: str, account: str, file_id: str, ext: str, content: str) -> str:
    """Write a test text file and return its full path."""
    account_dir = os.path.join(images_root, "data", "images", account)
    os.makedirs(account_dir, exist_ok=True)
    path = os.path.join(account_dir, f"{file_id}{ext}")
    with open(path, "w") as f:
        f.write(content)
    return path


# ---------------------------------------------------------------------------
# Tests: _guess_mime_from_path
# ---------------------------------------------------------------------------


def test_guess_mime_png():
    assert PromptBuilder._guess_mime_from_path("/some/path/img.png") == "image/png"


def test_guess_mime_jpg():
    assert PromptBuilder._guess_mime_from_path("/some/path/img.jpg") == "image/jpeg"


def test_guess_mime_jpeg():
    assert PromptBuilder._guess_mime_from_path("/some/path/img.jpeg") == "image/jpeg"


def test_guess_mime_gif():
    assert PromptBuilder._guess_mime_from_path("/some/path/img.gif") == "image/gif"


def test_guess_mime_webp():
    assert PromptBuilder._guess_mime_from_path("/some/path/img.webp") == "image/webp"


def test_guess_mime_unknown():
    assert PromptBuilder._guess_mime_from_path("/some/path/file.bin") == "application/octet-stream"


def test_guess_mime_no_extension():
    assert PromptBuilder._guess_mime_from_path("/some/path/README") == "application/octet-stream"


def test_guess_mime_case_insensitive():
    assert PromptBuilder._guess_mime_from_path("/some/path/img.PNG") == "image/png"


# ---------------------------------------------------------------------------
# Tests: _find_image_file
# ---------------------------------------------------------------------------


def test_find_image_file_finds_png(temp_images_root, pb_with_temp_dir):
    img_id = "abc-123"
    _write_test_image(temp_images_root, "junwin", img_id, ".png", b"fake-png-data")
    _write_test_image(temp_images_root, "junwin", img_id, ".json", b"{}")  # sidecar

    images_dir = pb_with_temp_dir._build_images_dir()
    result = pb_with_temp_dir._find_image_file(images_dir, "junwin", img_id)

    assert result is not None
    assert result.endswith(".png")
    assert not result.endswith(".json")


def test_find_image_file_filters_json_sidecar(temp_images_root, pb_with_temp_dir):
    """Only the .json sidecar exists — should return None."""
    img_id = "json-only"
    _write_test_image(temp_images_root, "junwin", img_id, ".json", b"{}")

    images_dir = pb_with_temp_dir._build_images_dir()
    result = pb_with_temp_dir._find_image_file(images_dir, "junwin", img_id)

    assert result is None


def test_find_image_file_missing_id(temp_images_root, pb_with_temp_dir):
    images_dir = pb_with_temp_dir._build_images_dir()
    result = pb_with_temp_dir._find_image_file(images_dir, "junwin", "nonexistent")

    assert result is None


def test_find_image_file_missing_account_dir(temp_images_root, pb_with_temp_dir):
    images_dir = pb_with_temp_dir._build_images_dir()
    result = pb_with_temp_dir._find_image_file(images_dir, "no-such-account", "abc-123")

    assert result is None


# ---------------------------------------------------------------------------
# Tests: _resolve_attachments — images
# ---------------------------------------------------------------------------


def test_resolve_single_image(temp_images_root, pb_with_temp_dir):
    img_id = "img-001"
    raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    _write_test_image(temp_images_root, "junwin", img_id, ".png", raw)

    parts = pb_with_temp_dir._resolve_attachments(
        account_name="junwin",
        image_ids=[img_id],
        file_ids=None,
    )

    assert len(parts) == 1
    assert parts[0]["type"] == "image"
    assert parts[0]["source"]["mime_type"] == "image/png"

    decoded = base64.b64decode(parts[0]["source"]["data"])
    assert decoded == raw


def test_resolve_multiple_images(temp_images_root, pb_with_temp_dir):
    raw1 = b"png-data-1"
    raw2 = b"jpeg-data-2"

    _write_test_image(temp_images_root, "junwin", "img-a", ".png", raw1)
    _write_test_image(temp_images_root, "junwin", "img-b", ".jpg", raw2)

    parts = pb_with_temp_dir._resolve_attachments(
        account_name="junwin",
        image_ids=["img-a", "img-b"],
        file_ids=None,
    )

    assert len(parts) == 2
    assert parts[0]["source"]["mime_type"] == "image/png"
    assert parts[1]["source"]["mime_type"] == "image/jpeg"

    assert base64.b64decode(parts[0]["source"]["data"]) == raw1
    assert base64.b64decode(parts[1]["source"]["data"]) == raw2


def test_resolve_image_missing_id_skipped(temp_images_root, pb_with_temp_dir):
    """Missing image IDs are silently skipped."""
    raw = b"real-data"
    _write_test_image(temp_images_root, "junwin", "real-id", ".png", raw)

    parts = pb_with_temp_dir._resolve_attachments(
        account_name="junwin",
        image_ids=["fake-id", "real-id"],
        file_ids=None,
    )

    assert len(parts) == 1
    assert base64.b64decode(parts[0]["source"]["data"]) == raw


def test_resolve_image_different_account_not_found(temp_images_root, pb_with_temp_dir):
    """An image uploaded by 'alice' is not found when querying as 'bob'."""
    _write_test_image(temp_images_root, "alice", "img-x", ".png", b"alice-data")

    parts = pb_with_temp_dir._resolve_attachments(
        account_name="bob",
        image_ids=["img-x"],
        file_ids=None,
    )

    assert len(parts) == 0


def test_resolve_image_webp(temp_images_root, pb_with_temp_dir):
    img_id = "webp-img"
    raw = b"RIFF....WEBP"
    _write_test_image(temp_images_root, "junwin", img_id, ".webp", raw)

    parts = pb_with_temp_dir._resolve_attachments(
        account_name="junwin",
        image_ids=[img_id],
        file_ids=None,
    )

    assert len(parts) == 1
    assert parts[0]["source"]["mime_type"] == "image/webp"


def test_resolve_image_gif(temp_images_root, pb_with_temp_dir):
    img_id = "gif-img"
    raw = b"GIF89a...."
    _write_test_image(temp_images_root, "junwin", img_id, ".gif", raw)

    parts = pb_with_temp_dir._resolve_attachments(
        account_name="junwin",
        image_ids=[img_id],
        file_ids=None,
    )

    assert len(parts) == 1
    assert parts[0]["source"]["mime_type"] == "image/gif"


def test_resolve_image_none_ids(temp_images_root, pb_with_temp_dir):
    """image_ids=None returns empty list."""
    parts = pb_with_temp_dir._resolve_attachments(
        account_name="junwin",
        image_ids=None,
        file_ids=None,
    )
    assert parts == []


def test_resolve_image_empty_ids(temp_images_root, pb_with_temp_dir):
    """image_ids=[] returns empty list."""
    parts = pb_with_temp_dir._resolve_attachments(
        account_name="junwin",
        image_ids=[],
        file_ids=None,
    )
    assert parts == []


# ---------------------------------------------------------------------------
# Tests: _resolve_attachments — files
# ---------------------------------------------------------------------------


def test_resolve_single_text_file(temp_images_root, pb_with_temp_dir):
    file_id = "file-001"
    _write_test_file(temp_images_root, "junwin", file_id, ".txt", "Hello world")

    parts = pb_with_temp_dir._resolve_attachments(
        account_name="junwin",
        image_ids=None,
        file_ids=[file_id],
    )

    assert len(parts) == 1
    assert parts[0]["type"] == "text"
    assert "[File: file-001.txt]" in parts[0]["text"]
    assert "Hello world" in parts[0]["text"]


def test_resolve_file_missing_id_skipped(temp_images_root, pb_with_temp_dir):
    _write_test_file(temp_images_root, "junwin", "real-file", ".md", "# Title")

    parts = pb_with_temp_dir._resolve_attachments(
        account_name="junwin",
        image_ids=None,
        file_ids=["fake-file", "real-file"],
    )

    assert len(parts) == 1
    assert "[File: real-file.md]" in parts[0]["text"]


def test_resolve_binary_file_fallback(temp_images_root, pb_with_temp_dir):
    """Binary file that can't be decoded as UTF-8 gets a fallback message."""
    file_id = "bin-file"
    path = os.path.join(temp_images_root, "data", "images", "junwin", f"{file_id}.bin")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x80\x81\x82\x83")

    parts = pb_with_temp_dir._resolve_attachments(
        account_name="junwin",
        image_ids=None,
        file_ids=[file_id],
    )

    assert len(parts) == 1
    assert "[Binary file: bin-file.bin]" in parts[0]["text"]


def test_resolve_mixed_images_and_files(temp_images_root, pb_with_temp_dir):
    _write_test_image(temp_images_root, "junwin", "img-1", ".png", b"png-data")
    _write_test_file(temp_images_root, "junwin", "file-1", ".md", "# Notes")

    parts = pb_with_temp_dir._resolve_attachments(
        account_name="junwin",
        image_ids=["img-1"],
        file_ids=["file-1"],
    )

    assert len(parts) == 2
    assert parts[0]["type"] == "image"
    assert parts[1]["type"] == "text"


# ---------------------------------------------------------------------------
# Tests: build_prompt() with attachments
# ---------------------------------------------------------------------------


def _find_user_content_part(messages, role="user"):
    """Find the first user message that has a content-part list."""
    for m in messages:
        if m["role"] == role and isinstance(m["content"], list):
            return m["content"]
    return None


def test_build_prompt_with_image_ids_uses_content_parts(temp_images_root, pb_with_temp_dir):
    raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    _write_test_image(temp_images_root, "junwin", "img-x", ".png", raw)

    messages = pb_with_temp_dir.build_prompt(
        content_text="What's in this image?",
        conversation_id="new",
        agent_name="lucy",
        account_name="junwin",
        context_type="none",
        image_ids=["img-x"],
    )

    content = _find_user_content_part(messages)
    assert content is not None, "Expected a user message with content parts"

    # First part is the text
    assert content[0]["type"] == "text"
    assert content[0]["text"] == "What's in this image?"

    # Second part is the image
    assert content[1]["type"] == "image"
    assert content[1]["source"]["mime_type"] == "image/png"
    assert base64.b64decode(content[1]["source"]["data"]) == raw


def test_build_prompt_without_attachments_uses_string_content(temp_images_root, pb_with_temp_dir):
    """Without image_ids/file_ids, content stays as a plain string."""
    messages = pb_with_temp_dir.build_prompt(
        content_text="Hello",
        conversation_id="new",
        agent_name="lucy",
        account_name="junwin",
        context_type="none",
    )

    user_msgs = [m for m in messages if m["role"] == "user"]
    last_user = user_msgs[-1]
    assert isinstance(last_user["content"], str)
    assert last_user["content"] == "Hello"


def test_build_prompt_with_file_ids_includes_file_content(temp_images_root, pb_with_temp_dir):
    """build_prompt with file_ids includes the file text in content parts."""
    _write_test_file(temp_images_root, "junwin", "doc-1", ".md", "# Report\n\nContent here")

    messages = pb_with_temp_dir.build_prompt(
        content_text="Summarize this file",
        conversation_id="new",
        agent_name="lucy",
        account_name="junwin",
        context_type="none",
        file_ids=["doc-1"],
    )

    content = _find_user_content_part(messages)
    assert content is not None, "Expected a user message with content parts"

    assert content[0]["type"] == "text"
    assert content[0]["text"] == "Summarize this file"
    assert content[1]["type"] == "text"
    assert "[File: doc-1.md]" in content[1]["text"]
    assert "Content here" in content[1]["text"]


def test_build_prompt_missing_image_produces_text_only(temp_images_root, pb_with_temp_dir):
    """When all image_ids point to missing files, content parts has just the text part."""
    messages = pb_with_temp_dir.build_prompt(
        content_text="What's in this?",
        conversation_id="new",
        agent_name="lucy",
        account_name="junwin",
        context_type="none",
        image_ids=["missing-id"],
    )

    content = _find_user_content_part(messages)
    assert content is not None
    assert len(content) == 1
    assert content[0]["type"] == "text"
    assert content[0]["text"] == "What's in this?"


def test_build_prompt_image_ids_ignored_without_account(temp_images_root, pb_with_temp_dir):
    """When account_name is empty, no images are resolved."""
    _write_test_image(temp_images_root, "junwin", "img-x", ".png", b"data")

    messages = pb_with_temp_dir.build_prompt(
        content_text="Hello",
        conversation_id="new",
        agent_name="lucy",
        account_name="",
        context_type="none",
        image_ids=["img-x"],
    )

    content = _find_user_content_part(messages)
    assert content is not None
    # Only the text part, no image part resolved (empty account -> wrong dir)
    assert len(content) == 1
    assert content[0]["type"] == "text"


def test_build_prompt_base64_is_valid_for_full_byte_range(temp_images_root, pb_with_temp_dir):
    """The base64-encoded data can be decoded to the original bytes (all values 0-255)."""
    raw = bytes(range(256))
    _write_test_image(temp_images_root, "junwin", "full-range", ".png", raw)

    parts = pb_with_temp_dir._resolve_attachments(
        account_name="junwin",
        image_ids=["full-range"],
        file_ids=None,
    )

    decoded = base64.b64decode(parts[0]["source"]["data"])
    assert decoded == raw
