import sys
import types

# Provide a fake 'galet' package and submodules to avoid import errors during tests
galet = types.ModuleType("galet")
embedding_router = types.ModuleType("galet.embedding_router")
setattr(embedding_router, "EmbeddingRouter", type("EmbeddingRouter", (), {}))
setattr(galet, "embedding_router", embedding_router)

mistral_embedding = types.ModuleType("galet.mistral_embedding")
setattr(mistral_embedding, "MistralEmbeddingApi", type("MistralEmbeddingApi", (), {}))
setattr(galet, "mistral_embedding", mistral_embedding)

openai_embedding = types.ModuleType("galet.openai_embedding")
setattr(openai_embedding, "OpenAIEmbeddingApi", type("OpenAIEmbeddingApi", (), {}))
setattr(galet, "openai_embedding", openai_embedding)

settings = types.ModuleType("galet.settings")
setattr(settings, "Settings", type("Settings", (), {"__init__": lambda self, *a, **k: None}))
setattr(galet, "settings", settings)

embedding_dto = types.ModuleType("galet.embedding_dto")
setattr(embedding_dto, "EmbeddingResponse", type("EmbeddingResponse", (), {"__init__": lambda self, embeddings=None: setattr(self, "embeddings", embeddings or [])}))
setattr(galet, "embedding_dto", embedding_dto)

embedding_interface = types.ModuleType("galet.embedding_interface")
setattr(embedding_interface, "EmbeddingApi", type("EmbeddingApi", (), {}))
setattr(galet, "embedding_interface", embedding_interface)

sys.modules["galet"] = galet
sys.modules["galet.embedding_router"] = embedding_router
sys.modules["galet.mistral_embedding"] = mistral_embedding
sys.modules["galet.openai_embedding"] = openai_embedding
sys.modules["galet.settings"] = settings
sys.modules["galet.embedding_dto"] = embedding_dto
sys.modules["galet.embedding_interface"] = embedding_interface

from src.coala_memory.semantic import (
    SemanticDocument,
    SemanticMemoryResult,
)
from src.embeddings.facade import EmbeddingFacade
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
    # Contract updated to include utility actions
    assert tool["parameters"]["properties"]["action"]["enum"] == [
        "recall",
        "embed",
        "compare",
        "rank",
        "models",
        "namespaces",
    ]

    # Schema should not include a 'search' action and union selector named 'embedding_model'
    assert "search" not in tool["parameters"]["properties"]["action"]["enum"]
    assert "embedding_model" in tool["parameters"]["properties"]
    required = tool["parameters"].get("required", [])
    # union properties must be listed in required
    for prop in [
        "action",
        "query",
        "account_name",
        "namespaces",
        "top_k",
        "max_chars",
        "score_threshold",
        "embedding_model",
        "source_type",
    ]:
        assert prop in required


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


def test_constructor_injected_path_builds_no_router_or_store():
    memory = FakeSemanticMemory()
    handler = SemanticMemoryHandler(DummyConfig(), memory=memory)

    assert handler.memory is memory
    # Ensure it's not the default SqliteVecSemanticMemory
    from src.coala_memory.semantic.sqlite_vec_memory import SqliteVecSemanticMemory

    assert not isinstance(handler.memory, SqliteVecSemanticMemory)


def test_unknown_action_error_lists_allowed_actions():
    handler = SemanticMemoryHandler(DummyConfig(), memory=FakeSemanticMemory())
    result = handler.execute({"action": "search", "query": "x"}, account_name="a")
    # Error message must list the allowed actions exactly
    assert result["ok"] is False
    assert "Unknown action" in result["error"]
    assert "recall" in result["error"]
    assert "embed" in result["error"]
    assert "compare" in result["error"]
    assert "rank" in result["error"]
    assert "models" in result["error"]
    assert "namespaces" in result["error"]


class FakeMemoryWithFacade:
    def __init__(self, facade):
        self.embedding_facade = facade

    def recall(self, request):
        raise AssertionError("recall should not be called")


def test_models_action_returns_registry_models_via_facade():
    facade = EmbeddingFacade(embedding_api=object())
    handler = SemanticMemoryHandler(DummyConfig(), memory=FakeMemoryWithFacade(facade))

    result = handler.execute({"action": "models"}, account_name="junwin")

    assert result["ok"] is True
    assert result["action"] == "models"
    assert isinstance(result["models"], list)
    names = {model["name"] for model in result["models"]}
    assert "text-embedding-3-small" in names
    assert "text-embedding-3-large" in names
    assert "text-embedding-ada-002" in names
    assert "mistral-embed" in names
    for model in result["models"]:
        assert {"name", "provider", "dimensions"} <= set(model)


def test_models_action_reports_error_when_no_capability():
    handler = SemanticMemoryHandler(DummyConfig(), memory=FakeSemanticMemory())

    result = handler.execute({"action": "models"}, account_name="junwin")

    assert result["ok"] is False
    assert "models" in result["error"]


class FakeEmbeddingStoreWithNamespaces:
    def __init__(self, namespaces):
        self._namespaces = list(namespaces)
        self.calls = []

    def list_embedding_namespaces(self, account_name):
        self.calls.append(account_name)
        return list(self._namespaces)


class FakeMemoryWithStore:
    def __init__(self, store):
        self.embedding_store = store

    def recall(self, request):
        raise AssertionError("recall should not be called")


def test_namespaces_action_lists_namespaces_via_embedding_store():
    store = FakeEmbeddingStoreWithNamespaces(["books", "zen"])
    handler = SemanticMemoryHandler(DummyConfig(), memory=FakeMemoryWithStore(store))

    result = handler.execute(
        {"action": "namespaces", "account_name": ""}, account_name="junwin"
    )

    assert result["ok"] is True
    assert result["action"] == "namespaces"
    assert result["account_name"] == "junwin"
    assert result["namespaces"] == ["books", "zen"]
    assert store.calls == ["junwin"]


def test_namespaces_action_explicit_account_overrides_caller():
    store = FakeEmbeddingStoreWithNamespaces(["books"])
    handler = SemanticMemoryHandler(DummyConfig(), memory=FakeMemoryWithStore(store))

    result = handler.execute(
        {"action": "namespaces", "account_name": "other"}, account_name="junwin"
    )

    assert result["ok"] is True
    assert store.calls == ["other"]
    assert result["account_name"] == "other"


def test_namespaces_action_prefers_memory_list_namespaces():
    class MemoryWithListNamespaces:
        def __init__(self):
            self.calls = []

        def list_namespaces(self, account_name):
            self.calls.append(account_name)
            return ["a", "b"]

    handler = SemanticMemoryHandler(DummyConfig(), memory=MemoryWithListNamespaces())

    result = handler.execute(
        {"action": "namespaces", "account_name": ""}, account_name="junwin"
    )

    assert result["ok"] is True
    assert result["namespaces"] == ["a", "b"]


def test_namespaces_action_requires_account():
    store = FakeEmbeddingStoreWithNamespaces(["books"])
    handler = SemanticMemoryHandler(DummyConfig(), memory=FakeMemoryWithStore(store))

    result = handler.execute({"action": "namespaces"}, account_name="auto")

    assert result["ok"] is False
    assert "account_name is required" in result["error"]


def test_namespaces_action_reports_error_when_no_capability():
    handler = SemanticMemoryHandler(DummyConfig(), memory=FakeSemanticMemory())

    result = handler.execute({"action": "namespaces"}, account_name="junwin")

    assert result["ok"] is False
    assert "capability" in result["error"]
