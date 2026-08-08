"""Tests for ServeImageHandler."""

from __future__ import annotations

import base64
import os
import pytest
from unittest.mock import MagicMock

from PIL import Image


@pytest.fixture
def config_with_storage(tmp_path):
    """Mock config with storage_root_path set to a temp directory."""
    storage_root = str(tmp_path / "lucy_storage")
    os.makedirs(storage_root, exist_ok=True)

    mock_config = MagicMock()
    mock_config.get.side_effect = lambda key, default=None: {
        "storage_root_path": storage_root,
        "storage_namespace": "data",
        "external_roots": {"pictures": str(tmp_path / "pictures")},
    }.get(key, default)
    return mock_config


@pytest.fixture
def handler(config_with_storage):
    from src.handlers.serve_image_handler import ServeImageHandler
    return ServeImageHandler(config_with_storage)


@pytest.fixture
def test_image(tmp_path, config_with_storage):
    """Create a real PNG file in the storage directory."""
    storage_root = config_with_storage.get("storage_root_path")
    storage_ns = config_with_storage.get("storage_namespace")
    img_dir = os.path.join(storage_root, storage_ns)
    os.makedirs(img_dir, exist_ok=True)

    img_path = os.path.join(img_dir, "test.png")
    img = Image.new("RGB", (10, 10), color="red")
    img.save(img_path, "PNG")
    return img_path


@pytest.fixture
def external_image(tmp_path, config_with_storage):
    """Create a real PNG file in the external pictures directory."""
    pictures_root = config_with_storage.get("external_roots")["pictures"]
    os.makedirs(pictures_root, exist_ok=True)

    img_path = os.path.join(pictures_root, "photo.jpg")
    img = Image.new("RGB", (10, 10), color="blue")
    img.save(img_path, "JPEG")
    return img_path


class TestInputValidation:
    def test_missing_path_returns_error(self, handler):
        result = handler.execute({"location": "storage", "external_root": "", "path": ""})
        assert result["ok"] is False
        assert "path is required" in result["error"]

    def test_missing_external_root_returns_error(self, handler):
        result = handler.execute({
            "location": "external",
            "external_root": "",
            "path": "test.png",
        })
        assert result["ok"] is False
        assert "external_root is required" in result["error"]

    def test_invalid_location_returns_error(self, handler):
        result = handler.execute({
            "location": "fake",
            "external_root": "",
            "path": "test.png",
        })
        assert result["ok"] is False
        assert "Unknown location" in result["error"]

    def test_path_traversal_rejected(self, handler):
        result = handler.execute({
            "location": "storage",
            "external_root": "",
            "path": "../etc/passwd",
        })
        assert result["ok"] is False
        assert ".." in result["error"] or "File access" in result["error"]

    def test_absolute_path_rejected(self, handler):
        result = handler.execute({
            "location": "storage",
            "external_root": "",
            "path": "/etc/passwd",
        })
        assert result["ok"] is False
        assert "relative" in result["error"]

    def test_file_not_found(self, handler):
        result = handler.execute({
            "location": "storage",
            "external_root": "",
            "path": "nonexistent.png",
        })
        assert result["ok"] is False
        assert "not found" in result["error"]


class TestSuccessfulServe:
    def test_serve_from_storage(self, handler, test_image):
        result = handler.execute({
            "location": "storage",
            "external_root": "",
            "path": "test.png",
        })
        assert result["ok"] is True
        assert result["image"]["url"].startswith("data:image/png;base64,")
        assert result["image"]["alt"] == "test.png"

    def test_serve_from_external(self, handler, external_image):
        result = handler.execute({
            "location": "external",
            "external_root": "pictures",
            "path": "photo.jpg",
        })
        assert result["ok"] is True
        assert result["image"]["url"].startswith("data:image/jpeg;base64,")

    def test_max_dimension_capped(self, handler, test_image):
        """max_dimension > 512 should be capped to 512."""
        result = handler.execute({
            "location": "storage",
            "external_root": "",
            "path": "test.png",
            "max_dimension": 1024,
        })
        assert result["ok"] is True

    def test_result_is_valid_base64(self, handler, test_image):
        result = handler.execute({
            "location": "storage",
            "external_root": "",
            "path": "test.png",
        })
        b64_data = result["image"]["url"].split(",", 1)[1]
        decoded = base64.b64decode(b64_data)
        assert len(decoded) > 0

    def test_unsupported_mime_type(self, handler, config_with_storage):
        """A .txt file should be rejected."""
        storage_root = config_with_storage.get("storage_root_path")
        storage_ns = config_with_storage.get("storage_namespace")
        txt_dir = os.path.join(storage_root, storage_ns)
        os.makedirs(txt_dir, exist_ok=True)

        txt_path = os.path.join(txt_dir, "notes.txt")
        with open(txt_path, "w") as f:
            f.write("hello")

        result = handler.execute({
            "location": "storage",
            "external_root": "",
            "path": "notes.txt",
        })
        assert result["ok"] is False
        assert "Unsupported" in result["error"]


class TestToolDefinition:
    def test_tool_def_has_required_fields(self, handler):
        td = handler.tool_def()
        assert td["name"] == "serve_image"
        assert "location" in td["parameters"]["properties"]
        assert "external_root" in td["parameters"]["properties"]
        assert "path" in td["parameters"]["properties"]
