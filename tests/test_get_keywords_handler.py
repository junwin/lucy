"""Tests for GetKeywordsHandler."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from src.handlers.get_keywords_handler import GetKeywordsHandler


@pytest.fixture
def handler():
    mock_config = MagicMock()
    return GetKeywordsHandler(mock_config)


class TestInputValidation:
    def test_missing_content_returns_error(self, handler):
        result = handler.execute({})
        assert result["ok"] is False
        assert "content is required" in result["error"]

    def test_empty_content_returns_error(self, handler):
        result = handler.execute({"content": "   "})
        assert result["ok"] is False
        assert "content is required" in result["error"]


class TestSuccessfulExtraction:
    def test_valid_content_returns_keywords(self, handler):
        with patch("src.handlers.get_keywords_handler.Keywords") as mock_kw_cls:
            mock_kw = MagicMock()
            mock_kw.extract_keywords.return_value = ["alpha", "beta", "gamma"]
            mock_kw_cls.return_value = mock_kw

            result = handler.execute({"content": "some text about alpha beta gamma"})
            assert result["ok"] is True
            assert result["keywords"] == ["alpha", "beta", "gamma"]

    def test_language_code_is_passed_through(self, handler):
        with patch("src.handlers.get_keywords_handler.Keywords") as mock_kw_cls:
            mock_kw = MagicMock()
            mock_kw.extract_keywords.return_value = ["hola"]
            mock_kw_cls.return_value = mock_kw

            handler.execute({"content": "hola mundo", "language_code": "es"})
            mock_kw_cls.assert_called_once_with(language_code="es")

    def test_invalid_top_n_defaults_to_10(self, handler):
        with patch("src.handlers.get_keywords_handler.Keywords") as mock_kw_cls:
            mock_kw = MagicMock()
            mock_kw.extract_keywords.return_value = ["a", "b"]
            mock_kw_cls.return_value = mock_kw

            handler.execute({"content": "test", "top_n": -5})
            mock_kw.extract_keywords.assert_called_once_with("test", top_n=10)

    def test_keywords_class_failure_returns_error(self, handler):
        with patch("src.handlers.get_keywords_handler.Keywords") as mock_kw_cls:
            mock_kw = MagicMock()
            mock_kw.extract_keywords.side_effect = RuntimeError("spaCy model not loaded")
            mock_kw_cls.return_value = mock_kw

            result = handler.execute({"content": "test"})
            assert result["ok"] is False
            assert "spaCy model not loaded" in result["error"]


class TestToolDefinition:
    def test_tool_def_has_required_fields(self, handler):
        td = handler.tool_def()
        assert td["name"] == "get_keywords"
        assert td["type"] == "function"
        assert "content" in td["parameters"]["properties"]
        assert "content" in td["parameters"]["required"]
