"""Focused unit tests for CurateChatHandler galet Settings injection.

Regression test: the handler used to build ``RouterApi()`` with no settings,
so galet fell back to its default Settings (no credential_path) and curation
summaries silently degraded to non-LLM template digests. This verifies the
handler now injects ``Settings(credential_path=..., ollama_base_url=...)``
from config, matching the ``container_config.LLMModule`` pattern.
"""

from unittest.mock import patch

from galet.settings import Settings

from src.handlers.curate_chat_handler import CurateChatHandler


class FakeConfig:
    """Minimal config object exposing the .get() surface the handler uses."""

    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def _make_handler(config):
    """Build CurateChatHandler with storage/engine construction stubbed out.

    The test targets __init__ wiring only; patching _build_store and
    _build_engine keeps it hermetic (no config.json on disk, no embedding
    or storage machinery) and isolates the RouterApi construction.
    """
    with (
        patch.object(CurateChatHandler, "_build_store"),
        patch.object(CurateChatHandler, "_build_engine"),
        patch("src.handlers.curate_chat_handler.RouterApi") as mock_router,
    ):
        handler = CurateChatHandler(config)
    return handler, mock_router


def test_router_api_injected_with_settings_from_config():
    cfg = FakeConfig(
        {
            "credential_path": "/home/junwin/credential",
            "ollama_base_url": "http://192.168.87.40:11434/v1",
        }
    )
    handler, mock_router = _make_handler(cfg)

    mock_router.assert_called_once_with(
        settings=Settings(
            credential_path="/home/junwin/credential",
            ollama_base_url="http://192.168.87.40:11434/v1",
        )
    )
    # The same RouterApi instance is what the curation engine receives.
    assert handler.llm_api is mock_router.return_value


def test_router_api_settings_none_when_config_keys_missing():
    handler, mock_router = _make_handler(FakeConfig({}))

    mock_router.assert_called_once_with(
        settings=Settings(credential_path=None, ollama_base_url=None)
    )
    assert handler.llm_api is mock_router.return_value
