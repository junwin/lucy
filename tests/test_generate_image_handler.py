"""Tests for GenerateImageHandler."""

from __future__ import annotations

import base64
import pytest
from unittest.mock import MagicMock

from src.handlers.generate_image_handler import GenerateImageHandler


@pytest.fixture
def handler():
    mock_config = MagicMock()
    return GenerateImageHandler(mock_config)


class TestSuccessfulGeneration:
    def test_generates_image_with_defaults(self, handler):
        result = handler.execute({"description": "Hello World"})
        assert result["ok"] is True
        assert result["image"]["url"].startswith("data:image/png;base64,")
        assert result["image"]["alt"] == "Hello World"

    def test_custom_dimensions_and_color(self, handler):
        result = handler.execute({
            "description": "Custom",
            "width": 600,
            "height": 300,
            "color": "#ff0000",
        })
        assert result["ok"] is True
        assert result["image"]["url"].startswith("data:image/png;base64,")
        assert result["image"]["alt"] == "Custom"

    def test_empty_description_defaults(self, handler):
        result = handler.execute({"description": "   "})
        assert result["ok"] is True
        assert result["image"]["alt"] == "Generated image"

    def test_result_is_valid_base64_png(self, handler):
        result = handler.execute({"description": "Test"})
        b64_data = result["image"]["url"].split(",", 1)[1]
        decoded = base64.b64decode(b64_data)
        # PNG signature: first 8 bytes
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"


class TestToolDefinition:
    def test_tool_def_has_required_fields(self, handler):
        td = handler.tool_def()
        assert td["name"] == "generate_image"
        assert td["type"] == "function"
        assert "description" in td["parameters"]["properties"]
        assert "width" in td["parameters"]["properties"]
        assert "height" in td["parameters"]["properties"]
        assert "color" in td["parameters"]["properties"]

    def test_result_schema_has_image_field(self, handler):
        rs = handler.result_schema()
        assert "image" in rs["properties"]
        assert "ok" in rs["properties"]
