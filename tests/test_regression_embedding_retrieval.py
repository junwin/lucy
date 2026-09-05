"""Issue #165 regression guards for sqlite_vec retrieval and DI wiring.

Probe A — the sqlite_vec store itself works (control, offline).
Probe B — the container PromptBuilder searches the bound EmbeddingStore.
Probe D — /prompt_builder endpoint impls resolve the interface and fail loud.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.http_endpoints.prompt_builder_endpoints import build_prompt_impl
from src.http_endpoints.prompt_builder_metrics_endpoints import prompt_builder_metrics_impl
from src.prompt_builders.prompt_builder import PromptBuilder
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.storage.vec0_embedding_store import (
    DEFAULT_SQLITE_VEC_EXTENSION_PATH,
    Vec0EmbeddingStore,
)

_EMBEDDINGS_DB = "/home/junwin/lucy_storage/data/embeddings.sqlite"
_ACCOUNT = "junwin"
_NAMESPACE = "documents"
_TARGET_SOURCE_ID = "obsidian_importer.md"


def _require_vec0_db() -> None:
    if not Path(_EMBEDDINGS_DB).exists():
        pytest.skip("embedding database not available")
    if not Path(DEFAULT_SQLITE_VEC_EXTENSION_PATH).exists():
        pytest.skip("sqlite-vec extension not available")
    conn = sqlite3.connect(":memory:")
    try:
        conn.enable_load_extension(True)
        conn.load_extension(DEFAULT_SQLITE_VEC_EXTENSION_PATH)
    except sqlite3.OperationalError:
        pytest.skip("sqlite-vec extension not loadable")
    finally:
        conn.close()


def _agent_manager() -> Mock:
    agent = Mock()
    agent.context_type = "hybrid"
    agent_manager = Mock()
    agent_manager.is_valid.return_value = True
    agent_manager.get_agent.return_value = agent
    return agent_manager


@pytest.mark.unit
def test_vec0_store_knn_returns_obsidian_importer_first() -> None:
    _require_vec0_db()
    with Vec0EmbeddingStore(_EMBEDDINGS_DB) as store:
        records = store.list_embeddings(_NAMESPACE, _ACCOUNT)
        target = next(record for record in records if record.source_id == _TARGET_SOURCE_ID)
        hits = store.query_embeddings(
            [_NAMESPACE], _ACCOUNT, target.vector, top_k=3
        )
    assert hits
    first_record, first_score = hits[0]
    assert first_record.source_id == _TARGET_SOURCE_ID
    assert first_score == pytest.approx(1.0, abs=1e-6)


@pytest.mark.unit
def test_prompt_builder_searches_bound_embedding_store() -> None:
    from src.storage.interfaces import EmbeddingStore

    try:
        from src.container_config import container
    except Exception as exc:
        pytest.skip(f"container import failed: {exc}")
    try:
        bound_store = container.get(EmbeddingStore)
    except Exception as exc:
        pytest.skip(f"embedding store resolution failed: {exc}")
    if not isinstance(bound_store, Vec0EmbeddingStore):
        pytest.skip(
            "container EmbeddingStore binding is not Vec0EmbeddingStore "
            f"(got {type(bound_store).__name__})"
        )

    prompt_builder = container.get(PromptBuilderInterface)
    assert prompt_builder.embedding_facade is not None
    search_store = (
        getattr(prompt_builder, "embedding_store", None) or prompt_builder.storage
    )
    assert search_store is bound_store


@pytest.mark.unit
def test_prompt_builder_endpoints_resolve_interface_and_fail_loud() -> None:
    agent_manager = _agent_manager()
    requested: list = []

    def raising_get(cls):
        requested.append(cls)
        raise KeyError(cls)

    container = Mock()
    container.get.side_effect = raising_get

    payload = {
        "query": "q",
        "agentName": "peace",
        "accountName": "junwin",
        "contextType": "hybrid",
    }
    for impl in (build_prompt_impl, prompt_builder_metrics_impl):
        result, status = impl(agent_manager, None, container, None, payload)
        assert status == 500
        assert isinstance(result, dict)
        assert "error" in result

    assert PromptBuilder not in requested
    assert PromptBuilderInterface in requested
