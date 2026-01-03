import importlib
import sys
from pathlib import Path

import pytest


def _reload_container_config(monkeypatch, config_dict):
    """Reload src.container_config with a patched module-level `config` object."""

    class FakeConfig:
        def get(self, key, default=None):
            return config_dict.get(key, default)

    # Ensure a clean import so module-level objects are rebuilt
    sys.modules.pop("src.container_config", None)
    import src.container_config as container_config

    # Patch the already-created module-level `config` instance
    monkeypatch.setattr(container_config, "config", FakeConfig(), raising=True)

    return importlib.reload(container_config)


def test_storage_effective_path_is_root_plus_base(monkeypatch, tmp_path):
    cfg = {
        "storage_root_path": str(tmp_path / "root"),
        "storage_base_path": "mydata",
        "agents_path": "agents",  # required by AgentManagerModule
    }

    container_config = _reload_container_config(monkeypatch, cfg)

    # IMPORTANT: StorageModule reads the module-level `config` at call time.
    # After reload(), the module-level `config` is reset, so patch again.
    monkeypatch.setattr(container_config, "config", type("C", (), {"get": lambda _self, k, d=None: cfg.get(k, d)})(), raising=True)

    storage = container_config.StorageModule().provide_storage()

    expected = Path(cfg["storage_root_path"]) / cfg["storage_base_path"]
    assert Path(storage.base_path) == expected


@pytest.mark.parametrize(
    "bad_base",
    [
        "/abs/path",
        "../escape",
        "mydata/../escape",
    ],
)
def test_storage_base_path_rejects_absolute_or_traversal(monkeypatch, tmp_path, bad_base):
    cfg = {
        "storage_root_path": str(tmp_path / "root"),
        "storage_base_path": bad_base,
        "agents_path": "agents",
    }

    container_config = _reload_container_config(monkeypatch, cfg)
    monkeypatch.setattr(container_config, "config", type("C", (), {"get": lambda _self, k, d=None: cfg.get(k, d)})(), raising=True)

    with pytest.raises(ValueError):
        container_config.StorageModule().provide_storage()
