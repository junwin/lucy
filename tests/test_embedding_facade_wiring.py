from src.config_manager import ConfigManager
from src.container_config import EmbeddingModule


def test_embedding_facade_wiring_credential_path():
    facade = EmbeddingModule().provide_embedding_facade()
    expected = ConfigManager("config.json").get("credential_path")
    assert expected == "/home/junwin/credential"
    assert facade._api._openai._settings.credential_path == expected
    assert facade._api._mistral._settings.credential_path == expected
