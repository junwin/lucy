# tests/test_json_file_storage_contexts.py

import pytest
from src.storage.json_file_storage import JsonFileStorage
@pytest.fixture
def storage(tmp_path):
    """
    Create a JsonFileStorage rooted in a temporary directory.

    tmp_path is a pytest built-in fixture that gives you an
    empty temp directory that is automatically cleaned up.
    """
    root = tmp_path / "lucy_storage"
    root.mkdir()
    return JsonFileStorage(base_path=str(root))

def test_save_and_load_context(storage):
    context_data = {
        "goal": "guided conversation",
        "facts_collected": ["retired", "moved to Evanston"],
        "notes": "Client appears reflective"
    }

    storage.save_context("junwin", "therapy_context", context_data)
    loaded = storage.load_context("junwin", "therapy_context")

    assert loaded["goal"] == "guided conversation"
    assert "retired" in loaded["facts_collected"]
