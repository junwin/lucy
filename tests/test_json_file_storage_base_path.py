import os
from pathlib import Path

from src.storage.json_file_storage import JsonFileStorage


def test_base_path_can_be_absolute(tmp_path):
    base = tmp_path / "lucydata"
    storage = JsonFileStorage(base_path=str(base))

    # Constructor should create the directory
    assert base.exists()
    assert base.is_dir()

    # And writes should land under that base
    storage.save_user("junwin", {"name": "John", "preferences": {"x": 1}})
    assert (base / "users" / "junwin.json").exists()


def test_base_path_can_be_relative(tmp_path, monkeypatch):
    # Simulate running from an arbitrary working directory
    monkeypatch.chdir(tmp_path)

    storage = JsonFileStorage(base_path="lucydata")

    base = tmp_path / "lucydata"
    assert base.exists()
    assert base.is_dir()

    storage.save_user("junwin", {"name": "John", "preferences": {"x": 1}})
    assert (base / "users" / "junwin.json").exists()


def test_base_path_can_be_tilde_expanded(tmp_path, monkeypatch):
    # Make ~ resolve to our temp dir for the test
    monkeypatch.setenv("HOME", str(tmp_path))

    storage = JsonFileStorage(base_path="~/lucydata")

    base = tmp_path / "lucydata"
    assert base.exists()
    assert base.is_dir()

    storage.save_user("junwin", {"name": "John", "preferences": {"x": 1}})
    assert (base / "users" / "junwin.json").exists()
