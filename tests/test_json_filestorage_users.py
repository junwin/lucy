# tests/test_json_file_storage_users.py

def test_save_and_load_user(storage):
    profile = {
        "name": "John Unwin",
        "preferences": {
            "editor": "vim",
            "tone": "calm"
        }
    }

    storage.save_user("junwin", profile)
    loaded = storage.load_user("junwin")

    assert loaded == profile


def test_load_missing_user_returns_none(storage):
    assert storage.load_user("does-not-exist") is None
