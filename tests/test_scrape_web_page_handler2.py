"""Tests for ScrapeWebPageHandler2."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from src.handlers.scrape_web_page_handler2 import ScrapeWebPageHandler2


@pytest.fixture
def handler():
    mock_config = MagicMock()
    return ScrapeWebPageHandler2(mock_config)


class TestInputValidation:
    def test_missing_page_url_returns_error(self, handler):
        result = handler.execute({})
        assert result["ok"] is False
        assert "page_url is required" in result["error"]

    def test_empty_page_url_returns_error(self, handler):
        result = handler.execute({"page_url": "   "})
        assert result["ok"] is False
        assert "page_url is required" in result["error"]


class TestSuccessfulScrape:
    def test_valid_url_scrape(self, handler):
        with patch("src.handlers.scrape_web_page_handler2.execute_script") as mock_exec:
            mock_exec.return_value = "<html>Hello world</html>"
            result = handler.execute({"page_url": "https://example.com"})
            assert result["ok"] is True
            assert result["tool"] == "scrape_web_page"
            assert result["page_url"] == "https://example.com"
            assert result["result"] == "<html>Hello world</html>"

    def test_execute_script_failure(self, handler):
        with patch("src.handlers.scrape_web_page_handler2.execute_script") as mock_exec:
            mock_exec.side_effect = RuntimeError("Connection refused")
            result = handler.execute({"page_url": "https://example.com"})
            assert result["ok"] is False
            assert "Connection refused" in result["error"]


class TestToolDefinition:
    def test_tool_def_has_required_fields(self, handler):
        td = handler.tool_def()
        assert td["name"] == "scrape_web_page"
        assert td["type"] == "function"
        assert "page_url" in td["parameters"]["properties"]
        assert "page_url" in td["parameters"]["required"]

    def test_result_schema_has_required_fields(self, handler):
        rs = handler.result_schema()
        assert "ok" in rs["properties"]
        assert "tool" in rs["properties"]
        assert "result" in rs["properties"]
