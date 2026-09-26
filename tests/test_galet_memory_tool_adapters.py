"""Contract checks for Lucy's galet-tools memory adapters."""

from types import SimpleNamespace
from unittest.mock import Mock

from galet_tools.tools.curate_chat_handler import CurateChatHandler as GaletCurateChatHandler
from galet_tools.tools.episodic_memory_handler import EpisodicMemoryHandler as GaletEpisodicMemoryHandler
from galet_tools.tools.reset_session_handler import ResetSessionHandler as GaletResetSessionHandler
from galet_tools.tools.semantic_memory_handler import SemanticMemoryHandler as GaletSemanticMemoryHandler

from src.handlers.curate_chat_handler import CurateChatHandler
from src.handlers.episodic_memory_handler import EpisodicMemoryHandler
from src.handlers.reset_session_handler import ResetSessionHandler
from src.handlers.semantic_memory_handler import SemanticMemoryHandler


class Config:
    def get(self, key, default=None):
        return default


class Curation:
    def __init__(self):
        self.calls = []

    def produce_digest(self, **kwargs):
        self.calls.append(("digest", kwargs))
        return SimpleNamespace(
            session_id=kwargs["session_id"], digest="a digest", boundary_event=None
        )

    def archive(self, **kwargs):
        self.calls.append(("archive", kwargs))
        return SimpleNamespace(
            session_id=kwargs["session_id"], digest="a digest",
            boundary_event=SimpleNamespace(event_id="boundary-1"),
        )


def test_adapters_subclass_canonical_handlers():
    assert issubclass(CurateChatHandler, GaletCurateChatHandler)
    assert issubclass(EpisodicMemoryHandler, GaletEpisodicMemoryHandler)
    assert issubclass(ResetSessionHandler, GaletResetSessionHandler)
    assert issubclass(SemanticMemoryHandler, GaletSemanticMemoryHandler)


def test_curate_chat_uses_galet_service_for_digest_and_archive():
    service = Curation()
    handler = CurateChatHandler(Config(), service=service)
    digest = handler.execute(
        {"mode": "digest", "session_id": "session-1"}, account_name="acct"
    )
    archived = handler.execute(
        {"mode": "archive", "session_id": "session-1",
         "idempotency_key": "operation-1"},
        account_name="acct",
    )
    assert digest["ok"] and digest["status"] == "preview"
    assert digest["note_text"] == "a digest"
    assert archived["ok"] and archived["boundary_event_id"] == "boundary-1"
    assert service.calls[0][0] == "digest"
    assert service.calls[1][1]["idempotency_key"] == "operation-1"


def test_legacy_filter_uses_lucy_engine():
    engine = Mock()
    engine.curate.return_value = {"status": "published", "summary": {"kept_count": 2}}
    result = CurateChatHandler(Config(), engine=engine).execute(
        {"mode": "filter", "session_id": "session-1"},
        account_name="acct",
    )
    assert result["ok"] is True
    engine.curate.assert_called_once()
