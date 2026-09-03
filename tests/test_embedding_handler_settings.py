from unittest.mock import patch

from galet.settings import Settings

from src.handlers.embedding_handler import EmbeddingHandler


class FakeConfig:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def _api_with_settings(mock_api):
    def _factory(settings):
        api = mock_api.return_value
        api._settings = settings
        return api

    return _factory


def _make_handler(config):
    with (
        patch("src.handlers.embedding_handler.EmbeddingRouter") as mock_router,
        patch("src.handlers.embedding_handler.OpenAIEmbeddingApi") as mock_openai,
        patch("src.handlers.embedding_handler.MistralEmbeddingApi") as mock_mistral,
    ):
        mock_openai.side_effect = _api_with_settings(mock_openai)
        mock_mistral.side_effect = _api_with_settings(mock_mistral)
        handler = EmbeddingHandler(config)
    return handler, mock_router, mock_openai, mock_mistral


def test_embedding_router_receives_openai_and_mistral_settings_from_config():
    credential_path = "/home/junwin/credential"
    ollama_base_url = "http://192.168.87.40:11434/v1"
    config = FakeConfig(
        {"credential_path": credential_path, "ollama_base_url": ollama_base_url}
    )
    handler, mock_router, mock_openai, mock_mistral = _make_handler(config)

    expected = Settings(credential_path=credential_path, ollama_base_url=ollama_base_url)
    mock_openai.assert_called_once_with(settings=expected)
    mock_mistral.assert_called_once_with(settings=expected)
    mock_router.assert_called_once_with(
        openai_api=mock_openai.return_value,
        mistral_api=mock_mistral.return_value,
    )
    assert mock_openai.return_value._settings == expected
    assert mock_mistral.return_value._settings == expected
    assert handler.facade._api is mock_router.return_value


def test_embedding_router_settings_none_when_config_keys_missing():
    handler, mock_router, mock_openai, mock_mistral = _make_handler(FakeConfig({}))

    expected = Settings(credential_path=None, ollama_base_url=None)
    mock_openai.assert_called_once_with(settings=expected)
    mock_mistral.assert_called_once_with(settings=expected)
    mock_router.assert_called_once_with(
        openai_api=mock_openai.return_value,
        mistral_api=mock_mistral.return_value,
    )
    assert mock_openai.return_value._settings == expected
    assert mock_mistral.return_value._settings == expected
    assert handler.facade._api is mock_router.return_value
