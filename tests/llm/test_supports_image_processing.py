"""Tests for supports_image_processing across the LLM stack.

Covers:
  - OpenAIResponsesApi → True
  - MistralApi → True
  - DeepSeekApi → False
  - RouterApi → routes correctly to each provider
  - RouterApi → raises ValueError for unknown model prefix
"""

from __future__ import annotations

import pytest

from src.llm.openai_responses import OpenAIResponsesApi
from src.llm.mistral_api import MistralApi
from src.llm.deepseek_responses import DeepSeekApi
from src.llm.router_api import RouterApi


# ---------------------------------------------------------------------------
# OpenAIResponsesApi
# ---------------------------------------------------------------------------

def test_supports_image_processing_openai() -> None:
    api = OpenAIResponsesApi()
    assert api.supports_image_processing("gpt-4o") is True
    assert api.supports_image_processing("gpt-5") is True
    assert api.supports_image_processing("o1") is True
    assert api.supports_image_processing("o3-mini") is True


# ---------------------------------------------------------------------------
# MistralApi
# ---------------------------------------------------------------------------

def test_supports_image_processing_mistral() -> None:
    api = MistralApi()
    assert api.supports_image_processing("mistral-large") is True
    assert api.supports_image_processing("mistral-small") is True
    assert api.supports_image_processing("pixtral-large-latest") is True


# ---------------------------------------------------------------------------
# DeepSeekApi
# ---------------------------------------------------------------------------

def test_supports_image_processing_deepseek() -> None:
    api = DeepSeekApi()
    assert api.supports_image_processing("deepseek-chat") is False
    assert api.supports_image_processing("deepseek-reasoner") is False


# ---------------------------------------------------------------------------
# RouterApi
# ---------------------------------------------------------------------------

def test_router_deepseek_returns_false() -> None:
    router = RouterApi()
    assert router.supports_image_processing("deepseek-chat") is False
    assert router.supports_image_processing("deepseek-reasoner") is False


def test_router_mistral_returns_true() -> None:
    router = RouterApi()
    assert router.supports_image_processing("mistral-large") is True
    assert router.supports_image_processing("mistral-small") is True


def test_router_openai_returns_true() -> None:
    router = RouterApi()
    assert router.supports_image_processing("gpt-4o") is True
    assert router.supports_image_processing("gpt-5") is True
    assert router.supports_image_processing("o1") is True
    assert router.supports_image_processing("o3") is True


def test_router_unknown_model_raises_valueerror() -> None:
    router = RouterApi()
    with pytest.raises(ValueError, match="Unknown model prefix"):
        router.supports_image_processing("claude-3-opus")

    with pytest.raises(ValueError, match="Unknown model prefix"):
        router.supports_image_processing("gemini-pro")


def test_router_unknown_model_error_message_helpful() -> None:
    """The error message should tell the user what prefixes are valid."""
    router = RouterApi()
    with pytest.raises(ValueError) as exc_info:
        router.supports_image_processing("llama-3")
    msg = str(exc_info.value)
    assert "gpt" in msg
    assert "deepseek" in msg
    assert "mistral" in msg
