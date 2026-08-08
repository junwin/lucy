"""Tests for PromptBuilder image/file attachment resolution (Step 2).

Covers:
  - _guess_mime_from_path()  — MIME type detection from extensions
  - _find_image_file()       — glob-based file discovery, .json filtering
  - _resolve_attachments()   — image_ids → base64 content parts, file_ids → text parts
  - build_prompt()           — content-part array construction when attachments present
  - Edge cases               — missing IDs, mixed attachments, binary files
  - Delegation mode          — text markers when supports_images=False
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


def _make_prompt_builder(images_root, allowed_tools=None):
    """Factory for a PromptBuilder with a temp images directory.

    allowed_tools: list of tool names to set on the mock agent, or None
    (which means allowed_tools is not set — backward compat).
    """
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

    storage = Mock()

    return PromptBuilder(
        agent_manager=agent_manager,
        config=config,
        storage=storage,
        chat2_store=None,
    )


@pytest.fixture
def pb_with_temp_dir(temp_images_root):
    """Return a PromptBuilder configured with a temp images directory."""
    return _make_prompt_builder(temp_images_root)


def _create_image_file(base_dir: str, account_name: str, img_id: str, filename: str, content: bytes):
    """Create a fake image file under the temp images directory."""
    account_dir = os.path.join(base_dir, "data", "images", account_name)
    os.makedirs(account_dir, exist_ok=True)
    path = os.path.join(account_dir, filename)
    # use the img_id as part of the name so glob finds it
    full_name = f"{img_id}.{filename.split('.')[-1]}" if "." in filename else f"{img_id}.png"
    full_path = os.path.join(account_dir, full_name)
    with open(full_path, "wb") as f:
        f.write(content)
    return full_path


def _create_text_file(base_dir: str, account_name: str, file_id: str, filename: str, content: str):
    """Create a fake text file under the temp images directory."""
    account_dir = os.path.join(base_dir, "data", "images", account_name)
    os.makedirs(account_dir, exist_ok=True)
    full_name = f"{file_id}.{filename.split('.')[-1]}" if "." in filename else f"{file_id}.txt"
    full_path = os.path.join(account_dir, full_name)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    return full_path


# ---------------------------------------------------------------------------
# _guess_mime_from_path
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _find_image_file
# ---------------------------------------------------------------------------


class TestFindImageFile:
    def test_finds_matching_file(self, temp_images_root, pb_with_temp_dir):
        account_dir = os.path.join(temp_images_root, "data", "images", "testuser")
        os.makedirs(account_dir, exist_ok=True)
        expected = os.path.join(account_dir, "abc123.png")
        with open(expected, "wb") as f:
            f.write(b"fake image data")

        result = pb_with_temp_dir._find_image_file(
            os.path.join(temp_images_root, "data", "images"),
            "testuser",
            "abc123",
        )
        assert result == expected

    def test_finds_jpg_variant(self, temp_images_root, pb_with_temp_dir):
        account_dir = os.path.join(temp_images_root, "data", "images", "testuser")
        os.makedirs(account_dir, exist_ok=True)
        expected = os.path.join(account_dir, "abc123.jpeg")
        with open(expected, "wb") as f:
            f.write(b"jpeg data")

        result = pb_with_temp_dir._find_image_file(
            os.path.join(temp_images_root, "data", "images"),
            "testuser",
            "abc123",
        )
        assert result == expected

    def test_skips_json_sidecar(self, temp_images_root, pb_with_temp_dir):
        account_dir = os.path.join(temp_images_root, "data", "images", "testuser")
        os.makedirs(account_dir, exist_ok=True)
        # Only a .json sidecar — no image file
        json_path = os.path.join(account_dir, "abc123.json")
        with open(json_path, "w") as f:
            f.write('{"original_name": "test.png"}')

        result = pb_with_temp_dir._find_image_file(
            os.path.join(temp_images_root, "data", "images"),
            "testuser",
            "abc123",
        )
        assert result is None

    def test_prefers_image_over_json_when_both_exist(self, temp_images_root, pb_with_temp_dir):
        account_dir = os.path.join(temp_images_root, "data", "images", "testuser")
        os.makedirs(account_dir, exist_ok=True)
        expected = os.path.join(account_dir, "abc123.png")
        with open(expected, "wb") as f:
            f.write(b"image")
        json_path = os.path.join(account_dir, "abc123.json")
        with open(json_path, "w") as f:
            f.write("{}")

        result = pb_with_temp_dir._find_image_file(
            os.path.join(temp_images_root, "data", "images"),
            "testuser",
            "abc123",
        )
        assert result == expected

    def test_returns_none_when_nonexistent(self, temp_images_root, pb_with_temp_dir):
        images_dir = os.path.join(temp_images_root, "data", "images")
        result = pb_with_temp_dir._find_image_file(images_dir, "testuser", "nonexistent123")
        assert result is None


# ---------------------------------------------------------------------------
# _resolve_attachments — images
# ---------------------------------------------------------------------------


class TestResolveAttachments:
    def test_image_ids_resolved_to_base64(self, temp_images_root):
        img_id = "img001"
        img_content = b"\x89PNG\r\n\x1a\nfake png body"
        _create_image_file(temp_images_root, "junwin", img_id, "photo.png", img_content)

        pb = _make_prompt_builder(temp_images_root)
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=[img_id],
            file_ids=None,
        )

        assert len(parts) == 1
        part = parts[0]
        assert part["type"] == "image"
        assert part["source"]["mime_type"] == "image/png"
        decoded = base64.b64decode(part["source"]["data"])
        assert decoded == img_content

    def test_missing_image_id_skipped(self, temp_images_root):
        pb = _make_prompt_builder(temp_images_root)
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=["nonexistent"],
            file_ids=None,
        )
        assert parts == []

    def test_multiple_image_ids(self, temp_images_root):
        r"""
        ┌──────────────────────────────────────────────────────────────┐
        │  image_ids: [img001, img002]  →  two base64 image parts      │
        │  Each part: {type: image, source: {data, mime_type}}         │
        └──────────────────────────────────────────────────────────────┘
        """
        img1 = b"image one content"
        img2 = b"image two content"
        _create_image_file(temp_images_root, "junwin", "img001", "a.png", img1)
        _create_image_file(temp_images_root, "junwin", "img002", "b.jpg", img2)

        pb = _make_prompt_builder(temp_images_root)
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=["img001", "img002"],
            file_ids=None,
        )

        assert len(parts) == 2
        assert parts[0]["type"] == "image"
        assert parts[1]["type"] == "image"
        assert base64.b64decode(parts[0]["source"]["data"]) == img1
        assert base64.b64decode(parts[1]["source"]["data"]) == img2
        assert parts[0]["source"]["mime_type"] == "image/png"
        assert parts[1]["source"]["mime_type"] == "image/jpeg"


# ---------------------------------------------------------------------------
# _resolve_attachments — files
# ---------------------------------------------------------------------------


class TestResolveFileAttachments:
    def test_file_id_resolved_to_text(self, temp_images_root):
        file_id = "file001"
        content = "Hello from file.txt"
        _create_text_file(temp_images_root, "junwin", file_id, "report.txt", content)

        pb = _make_prompt_builder(temp_images_root)
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=None,
            file_ids=[file_id],
        )

        assert len(parts) == 1
        part = parts[0]
        assert part["type"] == "text"
        assert content in part["text"]
        assert "file001.txt" in part["text"]

    def test_binary_file_shows_placeholder(self, temp_images_root):
        file_id = "bin001"
        account_dir = os.path.join(temp_images_root, "data", "images", "junwin")
        os.makedirs(account_dir, exist_ok=True)
        path = os.path.join(account_dir, f"{file_id}.bin")
        with open(path, "wb") as f:
            f.write(b"\x00\x01\x02\xff\xfe")

        pb = _make_prompt_builder(temp_images_root)
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=None,
            file_ids=[file_id],
        )

        assert len(parts) == 1
        assert "Binary file" in parts[0]["text"]


# ---------------------------------------------------------------------------
# _resolve_attachments — mixed
# ---------------------------------------------------------------------------


class TestResolveMixedAttachments:
    def test_image_and_file_together(self, temp_images_root):
        """
        Mixed attachments produce both image part and text part.
        """
        img_id = "imgmix1"
        file_id = "filemix1"
        _create_image_file(temp_images_root, "junwin", img_id, "pic.png", b"mixed image")
        _create_text_file(temp_images_root, "junwin", file_id, "doc.txt", "mixed file content")

        pb = _make_prompt_builder(temp_images_root)
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=[img_id],
            file_ids=[file_id],
        )

        assert len(parts) == 2
        assert parts[0]["type"] == "image"
        assert parts[1]["type"] == "text"
        assert "mixed file content" in parts[1]["text"]

    def test_empty_ids_produces_empty_list(self, temp_images_root):
        pb = _make_prompt_builder(temp_images_root)
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=[],
            file_ids=[],
        )
        assert parts == []

    def test_none_ids_produces_empty_list(self, temp_images_root):
        pb = _make_prompt_builder(temp_images_root)
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=None,
            file_ids=None,
        )
        assert parts == []

    def test_png_with_uppercase_extension(self, temp_images_root):
        account_dir = os.path.join(temp_images_root, "data", "images", "junwin")
        os.makedirs(account_dir, exist_ok=True)
        path = os.path.join(account_dir, "UPPER.PNG")
        with open(path, "wb") as f:
            f.write(b"uppercase png")

        pb = _make_prompt_builder(temp_images_root)
        # _find_image_file uses glob — on Linux, glob is case-sensitive,
        # so "upper" won't match "UPPER.PNG". Skip the glob and test _guess_mime.
        mime = pb._guess_mime_from_path(path)
        assert mime == "image/png"


# ---------------------------------------------------------------------------
# build_prompt — content-part array
# ---------------------------------------------------------------------------


class TestBuildPromptWithAttachments:
    def test_attachments_produce_content_parts_array(self, temp_images_root):
        img_id = "imgbp1"
        _create_image_file(temp_images_root, "junwin", img_id, "photo.png", b"build prompt test")

        pb = _make_prompt_builder(temp_images_root)
        messages = pb.build_prompt(
            content_text="Look at this image",
            conversation_id="new",
            agent_name="test-agent",
            account_name="junwin",
            context_type="none",
            image_ids=[img_id],
        )

        user_msg = messages[-1]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)

        text_parts = [p for p in user_msg["content"] if p["type"] == "text"]
        image_parts = [p for p in user_msg["content"] if p["type"] == "image"]
        assert len(text_parts) >= 1  # the query text
        assert len(image_parts) == 1

    def test_no_attachments_produces_string_content(self, temp_images_root):
        pb = _make_prompt_builder(temp_images_root)
        messages = pb.build_prompt(
            content_text="Hello",
            conversation_id="new",
            agent_name="test-agent",
            account_name="junwin",
            context_type="none",
        )

        user_msg = messages[-1]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], str)
        assert user_msg["content"] == "Hello"


# ===========================================================================
# supports_images parameter tests (triggers marker vs inline behavior)
# ===========================================================================


class TestSupportsImages:
    """Tests for the supports_images parameter controlling marker vs inline."""

    def test_supports_images_false_emits_markers_with_instruction(self, temp_images_root):
        """When supports_images=False, images become text markers + delegation instruction.

        Marker format: [Attached image: <uuid> — <filename>]
        Instruction: concise step-by-step delegation text using tasklists_manage.
        """
        img_id = "imgdel1"
        img_path = _create_image_file(temp_images_root, "junwin", img_id, "screenshot.png", b"delegation test")
        filename = os.path.basename(img_path)

        pb = _make_prompt_builder(temp_images_root, allowed_tools=["file_load", "file_save"])
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=[img_id],
            file_ids=None,
            agent_allowed_tools=["file_load", "file_save"],
            supports_images=False,
        )

        # 2 parts: marker + instruction text
        assert len(parts) == 2

        # First part: text marker with UUID and filename
        assert parts[0]["type"] == "text"
        assert img_id in parts[0]["text"]
        assert filename in parts[0]["text"]

        # Second part: mandatory delegation instruction
        assert parts[1]["type"] == "text"
        assert "tasklists_manage" in parts[1]["text"]
        assert "tasklists_run" in parts[1]["text"]
        assert "colin" in parts[1]["text"]

        # No image parts at all
        image_parts = [p for p in parts if p["type"] == "image"]
        assert len(image_parts) == 0

    def test_supports_images_false_emits_instruction_regardless_of_tools(self, temp_images_root):
        """When supports_images=False, instruction is always emitted even if
        agent_allowed_tools is empty or missing (not gated on delegate_tasks)."""
        img_id = "imgdel2"
        img_path = _create_image_file(temp_images_root, "junwin", img_id, "screenshot.png", b"marker test")
        filename = os.path.basename(img_path)

        pb = _make_prompt_builder(temp_images_root, allowed_tools=[])
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=[img_id],
            file_ids=None,
            agent_allowed_tools=[],
            supports_images=False,
        )

        # marker + instruction = 2 parts
        assert len(parts) == 2
        assert parts[0]["type"] == "text"
        assert img_id in parts[0]["text"]
        assert filename in parts[0]["text"]
        assert "tasklists_manage" in parts[1]["text"]
        assert "tasklists_run" in parts[1]["text"]

    def test_supports_images_false_multiple_images(self, temp_images_root):
        """Multiple image_ids with supports_images=False: all become text markers."""
        p1 = _create_image_file(temp_images_root, "junwin", "img001", "a.png", b"img1")
        p2 = _create_image_file(temp_images_root, "junwin", "img002", "b.jpg", b"img2")

        pb = _make_prompt_builder(temp_images_root, allowed_tools=["tasklists_manage"])
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=["img001", "img002"],
            file_ids=None,
            agent_allowed_tools=["tasklists_manage"],
            supports_images=False,
        )

        # 2 markers + 1 instruction = 3 parts
        assert len(parts) == 3
        assert all(p["type"] == "text" for p in parts)

        markers = parts[:2]
        assert any(os.path.basename(p1) in m["text"] for m in markers)
        assert any(os.path.basename(p2) in m["text"] for m in markers)

        # Instruction is last
        assert "tasklists_manage" in parts[2]["text"]

    def test_supports_images_true_still_inlines_base64(self, temp_images_root):
        """When supports_images=True (default), images are always base64 inline."""
        img_id = "imgfallback1"
        img_content = b"fallback test image"
        _create_image_file(temp_images_root, "junwin", img_id, "pic.png", img_content)

        pb = _make_prompt_builder(temp_images_root, allowed_tools=["file_load", "file_save"])
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=[img_id],
            file_ids=None,
            agent_allowed_tools=["file_load", "file_save"],
            supports_images=True,
        )

        assert len(parts) == 1
        assert parts[0]["type"] == "image"
        decoded = base64.b64decode(parts[0]["source"]["data"])
        assert decoded == img_content

    def test_supports_images_true_no_instruction(self, temp_images_root):
        """When supports_images=True, images inline base64 — no delegation instruction."""
        img_id = "imgvision001"
        img_content = b"vision model test"
        _create_image_file(temp_images_root, "junwin", img_id, "photo.png", img_content)

        pb = _make_prompt_builder(temp_images_root, allowed_tools=["file_load"])
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=[img_id],
            file_ids=None,
            agent_allowed_tools=["file_load"],
            supports_images=True,
        )

        assert len(parts) == 1
        assert parts[0]["type"] == "image"
        decoded = base64.b64decode(parts[0]["source"]["data"])
        assert decoded == img_content

    def test_supports_images_false_mixed_attachments(self, temp_images_root):
        """Image_ids become markers, file_ids still inlined as text."""
        img_id = "imgmixdel"
        file_id = "filemixdel"
        img_path = _create_image_file(temp_images_root, "junwin", img_id, "photo.png", b"mixed image")
        _create_text_file(temp_images_root, "junwin", file_id, "doc.txt", "file content here")

        pb = _make_prompt_builder(temp_images_root, allowed_tools=["tasklists_manage"])
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=[img_id],
            file_ids=[file_id],
            agent_allowed_tools=["tasklists_manage"],
            supports_images=False,
        )

        # image marker + instruction + file text = 3 parts
        assert len(parts) == 3

        # Image marker
        assert parts[0]["type"] == "text"
        assert os.path.basename(img_path) in parts[0]["text"]

        # Instruction
        assert "tasklists_manage" in parts[1]["text"]

        # File text still inlined
        assert parts[2]["type"] == "text"
        assert "file content here" in parts[2]["text"]

    def test_supports_images_false_no_instruction_without_images(self, temp_images_root):
        """No instruction appended if there are no images (even with supports_images=False)."""
        file_id = "fileonly001"
        _create_text_file(temp_images_root, "junwin", file_id, "readme.txt", "just a file")

        pb = _make_prompt_builder(temp_images_root, allowed_tools=["tasklists_manage"])
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=None,
            file_ids=[file_id],
            agent_allowed_tools=["tasklists_manage"],
            supports_images=False,
        )

        # Only the file text, no delegation instruction
        assert len(parts) == 1
        assert "just a file" in parts[0]["text"]
        assert "tasklists_manage" not in parts[0]["text"]

    def test_supports_images_default_backward_compat(self, temp_images_root):
        """Default supports_images=True (or not passed) falls back to inline base64."""
        img_id = "imgold001"
        img_content = b"backward compat test"
        _create_image_file(temp_images_root, "junwin", img_id, "old.png", img_content)

        pb = _make_prompt_builder(temp_images_root, allowed_tools=None)
        parts = pb._resolve_attachments(
            account_name="junwin",
            image_ids=[img_id],
            file_ids=None,
            agent_allowed_tools=None,
        )

        assert len(parts) == 1
        assert parts[0]["type"] == "image"
        decoded = base64.b64decode(parts[0]["source"]["data"])
        assert decoded == img_content
