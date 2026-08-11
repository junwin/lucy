import pytest

from src.llm.provider_registry import ProviderRegistry


def test_explicit_provider_overrides_prefix():
    # model looks like deepseek but explicit provider openai should win
    name, inst = ProviderRegistry.resolve("deepseek-xyz", provider="openai")
    assert name == "openai"
    assert inst is not None


def test_prefix_fallback_works():
    name, _ = ProviderRegistry.resolve("deepseek-something")
    assert name == "deepseek"

    name2, _ = ProviderRegistry.resolve("mistral-foo")
    assert name2 == "mistral"


def test_ollama_prefix_resolution():
    """Model names starting with 'ollama' route to the ollama provider."""
    name, _ = ProviderRegistry.resolve("ollama/llama3.1")
    assert name == "ollama"

    name2, _ = ProviderRegistry.resolve("ollama-qwen3")
    assert name2 == "ollama"


def test_ollama_explicit_provider():
    """Explicit provider=ollama routes correctly."""
    name, inst = ProviderRegistry.resolve("llama3.1", provider="ollama")
    assert name == "ollama"
    assert inst is not None


def test_unknown_model_falls_through_to_openai():
    name, _ = ProviderRegistry.resolve("some-unknown-model")
    assert name == "openai"


def test_unknown_explicit_provider_raises():
    with pytest.raises(ValueError):
        ProviderRegistry.resolve_name("gpt-4o", provider="not-a-provider")
