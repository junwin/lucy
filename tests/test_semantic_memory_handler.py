from src.coala_memory.semantic import (
    SemanticDocument,
    SemanticMemoryResult,
)
from src.handlers.semantic_memory_handler import SemanticMemoryHandler


class DummyConfig:
    def get(self, key, default=None):
        return default


class FakeSemanticMemory:
    def __init__(self):
        self.requests = []

    def recall(self, request):
        self.requests.append(request)
        return SemanticMemoryResult(
            documents=[
                SemanticDocument(
                    source_id="note-1",
                    source_type="obsidian_note",
                    title="CoALA memory",
                    snippet="Semantic memory integration test",
                    tags=["lucy", "memory"],
                    score=0.73,
                    path="/tmp/note-1.md",
                )
            ],
            metadata={"backend": "sqlite_vec", "selected_count": 1},
        )


def _args(**overrides):
    args = {
        "action": "recall",
        "query": "what do we know about CoALA memory?",
        "account_name": "",
        "namespaces": ["external"],
        "top_k": 3,
        "max_chars": 9000,
        "score_threshold": 0.25,
        "embedding_model": "text-embedding-3-small",
        "source_type": "obsidian_note",
    }
    args.update(overrides)
    return args


def test_semantic_memory_handler_exposes_handler_v2_tool_contract():
    tool = SemanticMemoryHandler.tool_def()

    assert SemanticMemoryHandler.name() == "semantic_memory"
    assert tool["name"] == "semantic_memory"
    assert tool["strict"] is True
    assert tool["parameters"]["properties"]["action"]["enum"] == ["recall"]


def test_semantic_memory_handler_uses_caller_account_and_returns_documents():
    memory = FakeSemanticMemory()
    handler = SemanticMemoryHandler(DummyConfig(), memory=memory)

    result = handler.execute(_args(), account_name="junwin")

    assert result["ok"] is True
    assert result["tool"] == "semantic_memory"
    assert result["count"] == 1
    assert result["documents"][0]["source_id"] == "note-1"
    assert result["documents"][0]["score"] == 0.73

    request = memory.requests[0]
    assert request.account_name == "junwin"
    assert request.namespaces == ["external"]
    assert request.top_k == 3
    assert request.source_type == "obsidian_note"


def test_semantic_memory_handler_explicit_account_overrides_caller_account():
    memory = FakeSemanticMemory()
    handler = SemanticMemoryHandler(DummyConfig(), memory=memory)

    result = handler.execute(_args(account_name="other"), account_name="junwin")

    assert result["ok"] is True
    assert memory.requests[0].account_name == "other"


def test_semantic_memory_handler_reports_recall_errors():
    class FailingMemory:
        def recall(self, request):
            raise RuntimeError("embedding store unavailable")

    handler = SemanticMemoryHandler(DummyConfig(), memory=FailingMemory())
    result = handler.execute(_args(), account_name="junwin")

    assert result["ok"] is False
    assert "embedding store unavailable" in result["error"]
