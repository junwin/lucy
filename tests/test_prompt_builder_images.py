"""Tests for PromptBuilder image/file attachment resolution."""

from __future__ import annotations

import base64
import os
import tempfile
from unittest.mock import Mock

import pytest

from src.prompt_builders.prompt_builder import PromptBuilder


@pytest.fixture
def temp_images_root():
    with tempfile.TemporaryDirectory() as td:
        yield td


def _make_prompt_builder(images_root, allowed_tools=None):
    agent_manager = Mock()
    mock_agent = Mock()
    mock_agent.max_prompt_conversations = 0
    mock_agent.system_prompt = None
    mock_agent.persona = None
    mock_agent.style_prompt = None
    mock_agent.allowed_tools = allowed_tools
    agent_manager.get_agent.return_value = mock_agent

    config = Mock()
    config.get.side_effect = lambda key, default=None: {
        "storage_root_path": images_root,
        "storage_namespace": "data",
    }.get(key, default)

    return PromptBuilder(
        agent_manager=agent_manager,
        config=config,
        storage=Mock(),
    )


@pytest.fixture
def pb_with_temp_dir(temp_images_root):
    return _make_prompt_builder(temp_images_root)


def _create_image_file(base_dir: str, account_name: str, img_id: str, filename: str, content: bytes):
    account_dir = os.path.join(base_dir, "data", "images", account_name)
    os.makedirs(account_dir, exist_ok=True)
    full_name = f"{img_id}.{filename.split('.')[-1]}" if "." in filename else f"{img_id}.png"
    full_path = os.path.join(account_dir, full_name)
    with open(full_path, "wb") as f:
        f.write(content)
    return full_path


def _create_text_file(base_dir: str, account_name: str, file_id: str, filename: str, content: str):
    account_dir = os.path.join(base_dir, "data", "images", account_name)
    os.makedirs(account_dir, exist_ok=True)
    full_name = f"{file_id}.{filename.split('.')[-1]}" if "." in filename else f"{file_id}.txt"
    full_path = os.path.join(account_dir, full_name)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    return full_path


class TestGuessMimeFromPath:
    def test_png(self, pb_with_temp_dir):
        assert pb_with_temp_dir._guess_mime_from_path("screenshot.png") == "image/png"

    def test_jpg(self, pb_with_temp_dir):
        assert pb_with_temp_dir._guess_mime_from_path("photo.jpg") == "image/jpeg"

    def test_jpeg(self, pb_with_temp_dir):
        assert pb_with_temp_dir._guess_mime_from_path("photo.jpeg") == "image/jpeg"

    def test_gif(self, pb_with_temp_dir):
        assert pb_with_temp_dir._guess_mime_from_path("animation.gif") == "image/gif"

    def test_webp(self, pb_with_temp_dir):
        assert pb_with_temp_dir._guess_mime_from_path("image.webp") == "image/webp"

    def test_unknown_extension(self, pb_with_temp_dir):
        assert pb_with_temp_dir._guess_mime_from_path("data.bin") == "application/octet-stream"

    def test_no_extension(self, pb_with_temp_dir):
        assert pb_with_temp_dir._guess_mime_from_path("README") == "application/octet-stream"


class TestFindImageFile:
    def test_finds_matching_file(self, temp_images_root, pb_with_temp_dir):
        account_dir = os.path.join(temp_images_root, "data", "images", "testuser")
        os.makedirs(account_dir, exist_ok=True)
        expected = os.path.join(account_dir, "abc123.png")
        with open(expected, "wb") as f:
            f.write(b"fake image data")
        assert pb_with_temp_dir._find_image_file(
            os.path.join(temp_images_root, "data", "images"), "testuser", "abc123"
        ) == expected

    def test_finds_jpg_variant(self, temp_images_root, pb_with_temp_dir):
        account_dir = os.path.join(temp_images_root, "data", "images", "testuser")
        os.makedirs(account_dir, exist_ok=True)
        expected = os.path.join(account_dir, "abc123.jpeg")
        with open(expected, "wb") as f:
            f.write(b"jpeg data")
        assert pb_with_temp_dir._find_image_file(
            os.path.join(temp_images_root, "data", "images"), "testuser", "abc123"
        ) == expected

    def test_skips_json_sidecar(self, temp_images_root, pb_with_temp_dir):
        account_dir = os.path.join(temp_images_root, "data", "images", "testuser")
        os.makedirs(account_dir, exist_ok=True)
        with open(os.path.join(account_dir, "abc123.json"), "w") as f:
            f.write('{"original_name": "test.png"}')
        assert pb_with_temp_dir._find_image_file(
            os.path.join(temp_images_root, "data", "images"), "testuser", "abc123"
        ) is None

    def test_prefers_image_over_json_when_both_exist(self, temp_images_root, pb_with_temp_dir):
        account_dir = os.path.join(temp_images_root, "data", "images", "testuser")
        os.makedirs(account_dir, exist_ok=True)
        expected = os.path.join(account_dir, "abc123.png")
        with open(expected, "wb") as f:
            f.write(b"image")
        with open(os.path.join(account_dir, "abc123.json"), "w") as f:
            f.write("{}")
        assert pb_with_temp_dir._find_image_file(
            os.path.join(temp_images_root, "data", "images"), "testuser", "abc123"
        ) == expected

    def test_returns_none_when_nonexistent(self, temp_images_root, pb_with_temp_dir):
        images_dir = os.path.join(temp_images_root, "data", "images")
        assert pb_with_temp_dir._find_image_file(images_dir, "testuser", "nonexistent123") is None


class TestResolveAttachments:
    def test_image_ids_resolved_to_base64(self, temp_images_root):
        img_id = "img001"
        img_content = b"\x89PNG\r\n\x1a\nfake png body"
        _create_image_file(temp_images_root, "junwin", img_id, "photo.png", img_content)
        parts = _make_prompt_builder(temp_images_root)._resolve_attachments(
            account_name="junwin", image_ids=[img_id], file_ids=None
        )
        assert len(parts) == 1
        assert parts[0]["type"] == "image"
        assert parts[0]["source"]["mime_type"] == "image/png"
        assert base64.b64decode(parts[0]["source"]["data"]) == img_content

    def test_missing_image_id_skipped(self, temp_images_root):
        parts = _make_prompt_builder(temp_images_root)._resolve_attachments(
            account_name="junwin", image_ids=["nonexistent"], file_ids=None
        )
        assert parts == []

    def test_multiple_image_ids(self, temp_images_root):
        img1 = b"image one content"
        img2 = b"image two content"
        _create_image_file(temp_images_root, "junwin", "img001", "a.png", img1)
        _create_image_file(temp_images_root, "junwin", "img002", "b.jpg", img2)
        parts = _make_prompt_builder(temp_images_root)._resolve_attachments(
            account_name="junwin", image_ids=["img001", "img002"], file_ids=None
        )
        assert len(parts) == 2
        assert base64.b64decode(parts[0]["source"]["data"]) == img1
        assert base64.b64decode(parts[1]["source"]["data"]) == img2
        assert parts[0]["source"]["mime_type"] == "image/png"
        assert parts[1]["source"]["mime_type"] == "image/jpeg"


class TestResolveFileAttachments:
    def test_file_id_resolved_to_text(self, temp_images_root):
        _create_text_file(temp_images_root, "junwin", "file001", "report.txt", "Hello from file.txt")
        parts = _make_prompt_builder(temp_images_root)._resolve_attachments(
            account_name="junwin", image_ids=None, file_ids=["file001"]
        )
        assert len(parts) == 1
        assert "Hello from file.txt" in parts[0]["text"]
        assert "file001.txt" in parts[0]["text"]

    def test_binary_file_shows_placeholder(self, temp_images_root):
        account_dir = os.path.join(temp_images_root, "data", "images", "junwin")
        os.makedirs(account_dir, exist_ok=True)
        with open(os.path.join(account_dir, "bin001.bin"), "wb") as f:
            f.write(b"\x00\x01\x02\xff\xfe")
        parts = _make_prompt_builder(temp_images_root)._resolve_attachments(
            account_name="junwin", image_ids=None, file_ids=["bin001"]
        )
        assert "Binary file" in parts[0]["text"]


class TestResolveMixedAttachments:
    def test_image_and_file_together(self, temp_images_root):
        _create_image_file(temp_images_root, "junwin", "imgmix1", "pic.png", b"mixed image")
        _create_text_file(temp_images_root, "junwin", "filemix1", "doc.txt", "mixed file content")
        parts = _make_prompt_builder(temp_images_root)._resolve_attachments(
            account_name="junwin", image_ids=["imgmix1"], file_ids=["filemix1"]
        )
        assert len(parts) == 2
        assert parts[0]["type"] == "image"
        assert "mixed file content" in parts[1]["text"]

    def test_empty_ids_produces_empty_list(self, temp_images_root):
        assert _make_prompt_builder(temp_images_root)._resolve_attachments(
            account_name="junwin", image_ids=[], file_ids=[]
        ) == []

    def test_none_ids_produces_empty_list(self, temp_images_root):
        assert _make_prompt_builder(temp_images_root)._resolve_attachments(
            account_name="junwin", image_ids=None, file_ids=None
        ) == []

    def test_png_with_uppercase_extension(self, temp_images_root):
        path = os.path.join(temp_images_root, "UPPER.PNG")
        with open(path, "wb") as f:
            f.write(b"uppercase png")
        assert _make_prompt_builder(temp_images_root)._guess_mime_from_path(path) == "image/png"


class TestBuildPromptWithAttachments:
    def test_attachments_produce_content_parts_array(self, temp_images_root):
        _create_image_file(temp_images_root, "junwin", "imgbp1", "photo.png", b"build prompt test")
        messages = _make_prompt_builder(temp_images_root).build_prompt(
            content_text="Look at this image",
            conversation_id="new",
            agent_name="test-agent",
            account_name="junwin",
            context_type="none",
            image_ids=["imgbp1"],
        )
        user_msg = messages[-1]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)
        assert len([p for p in user_msg["content"] if p["type"] == "image"]) == 1

    def test_no_attachments_produces_string_content(self, temp_images_root):
        messages = _make_prompt_builder(temp_images_root).build_prompt(
            content_text="Hello",
            conversation_id="new",
            agent_name="test-agent",
            account_name="junwin",
            context_type="none",
        )
        assert messages[-1] == {"role": "user", "content": "Hello"}


class TestSupportsImages:
    def test_supports_images_false_emits_markers_with_instruction(self, temp_images_root):
        img_path = _create_image_file(temp_images_root, "junwin", "imgdel1", "screenshot.png", b"delegation test")
        parts = _make_prompt_builder(temp_images_root, allowed_tools=["file_load", "file_save"])._resolve_attachments(
            account_name="junwin",
            image_ids=["imgdel1"],
            file_ids=None,
            agent_allowed_tools=["file_load", "file_save"],
            supports_images=False,
        )
        assert len(parts) == 2
        assert "imgdel1" in parts[0]["text"]
        assert os.path.basename(img_path) in parts[0]["text"]
        assert "tasklists_manage" in parts[1]["text"]
        assert "tasklists_run" in parts[1]["text"]
        assert "colin" in parts[1]["text"]

    def test_supports_images_false_emits_instruction_regardless_of_tools(self, temp_images_root):
        img_path = _create_image_file(temp_images_root, "junwin", "imgdel2", "screenshot.png", b"marker test")
        parts = _make_prompt_builder(temp_images_root, allowed_tools=[])._resolve_attachments(
            account_name="junwin", image_ids=["imgdel2"], file_ids=None,
            agent_allowed_tools=[], supports_images=False,
        )
        assert len(parts) == 2
        assert os.path.basename(img_path) in parts[0]["text"]
        assert "tasklists_manage" in parts[1]["text"]

    def test_supports_images_false_multiple_images(self, temp_images_root):
        p1 = _create_image_file(temp_images_root, "junwin", "img001", "a.png", b"img1")
        p2 = _create_image_file(temp_images_root, "junwin", "img002", "b.jpg", b"img2")
        parts = _make_prompt_builder(temp_images_root, allowed_tools=["tasklists_manage"])._resolve_attachments(
            account_name="junwin", image_ids=["img001", "img002"], file_ids=None,
            agent_allowed_tools=["tasklists_manage"], supports_images=False,
        )
        assert len(parts) == 3
        assert any(os.path.basename(p1) in m["text"] for m in parts[:2])
        assert any(os.path.basename(p2) in m["text"] for m in parts[:2])
        assert "tasklists_manage" in parts[2]["text"]

    def test_supports_images_true_still_inlines_base64(self, temp_images_root):
        img_content = b"fallback test image"
        _create_image_file(temp_images_root, "junwin", "imgfallback1", "pic.png", img_content)
        parts = _make_prompt_builder(temp_images_root)._resolve_attachments(
            account_name="junwin", image_ids=["imgfallback1"], file_ids=None,
            supports_images=True,
        )
        assert len(parts) == 1
        assert parts[0]["type"] == "image"
        assert base64.b64decode(parts[0]["source"]["data"]) == img_content

    def test_supports_images_true_no_instruction(self, temp_images_root):
        img_content = b"vision model test"
        _create_image_file(temp_images_root, "junwin", "imgvision001", "photo.png", img_content)
        parts = _make_prompt_builder(temp_images_root)._resolve_attachments(
            account_name="junwin", image_ids=["imgvision001"], file_ids=None,
            supports_images=True,
        )
        assert len(parts) == 1
        assert parts[0]["type"] == "image"

    def test_supports_images_false_mixed_attachments(self, temp_images_root):
        img_path = _create_image_file(temp_images_root, "junwin", "imgmixdel", "photo.png", b"mixed image")
        _create_text_file(temp_images_root, "junwin", "filemixdel", "doc.txt", "file content here")
        parts = _make_prompt_builder(temp_images_root)._resolve_attachments(
            account_name="junwin", image_ids=["imgmixdel"], file_ids=["filemixdel"],
            supports_images=False,
        )
        assert len(parts) == 3
        assert os.path.basename(img_path) in parts[0]["text"]
        assert "tasklists_manage" in parts[1]["text"]
        assert "file content here" in parts[2]["text"]

    def test_supports_images_false_no_instruction_without_images(self, temp_images_root):
        _create_text_file(temp_images_root, "junwin", "fileonly001", "readme.txt", "just a file")
        parts = _make_prompt_builder(temp_images_root)._resolve_attachments(
            account_name="junwin", image_ids=None, file_ids=["fileonly001"], supports_images=False,
        )
        assert len(parts) == 1
        assert "just a file" in parts[0]["text"]
        assert "tasklists_manage" not in parts[0]["text"]

    def test_supports_images_default_backward_compat(self, temp_images_root):
        img_content = b"backward compat test"
        _create_image_file(temp_images_root, "junwin", "imgold001", "old.png", img_content)
        parts = _make_prompt_builder(temp_images_root)._resolve_attachments(
            account_name="junwin", image_ids=["imgold001"], file_ids=None
        )
        assert len(parts) == 1
        assert parts[0]["type"] == "image"
        assert base64.b64decode(parts[0]["source"]["data"]) == img_content
