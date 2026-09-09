from src.config_manager import ConfigManager
from src.container_config import EmbeddingModule


def test_embedding_facade_wiring_credential_path():
    facade = EmbeddingModule().provide_embedding_facade()
    expected = ConfigManager("config.json").get("credential_path")
    assert expected == "/home/junwin/credential"
    assert facade._api._openai._settings.credential_path == expected
    assert facade._api._mistral._settings.credential_path == expected


def test_embedding_facade_models_returns_known_model_metadata():
    facade = EmbeddingModule().provide_embedding_facade()

    models = facade.models()

    names = {model["name"] for model in models}
    assert "text-embedding-3-small" in names
    assert "text-embedding-3-large" in names
    assert "text-embedding-ada-002" in names
    assert "mistral-embed" in names
    assert all({"name", "provider", "dimensions"} <= set(model) for model in models)
