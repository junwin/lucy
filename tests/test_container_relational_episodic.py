from unittest.mock import Mock, patch

import galet_memory
import pytest

from src import container_config


def _config(values):
    return lambda key, default=None: values.get(key, default)


def test_relational_episodic_backend_uses_separate_default_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        container_config.config, "get",
        _config({
            "storage_root_path": str(tmp_path),
            "storage_namespace": "data",
            "episodic_memory_backend": "relational_sqlite",
        }),
    )
    relational = Mock()
    monkeypatch.setattr(galet_memory, "RelationalSqliteEpisodicMemory", relational, raising=False)
    with patch.object(container_config, "EmbeddingDigestRecall", return_value=Mock()):
        container_config.CoALAMemoryModule().provide_episodic_memory(Mock(), Mock())
    assert relational.call_args.args == (tmp_path / "data" / "chat2-relational.sqlite",)


def test_unknown_episodic_backend_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(
        container_config.config, "get",
        _config({
            "storage_root_path": str(tmp_path),
            "episodic_memory_backend": "typo",
        }),
    )
    with pytest.raises(ValueError, match="Unknown episodic_memory_backend"):
        container_config.CoALAMemoryModule().provide_episodic_memory(Mock(), Mock())
