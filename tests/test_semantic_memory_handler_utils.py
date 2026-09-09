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

from src.handlers.semantic_memory_handler import SemanticMemoryHandler


class DummyConfig:
    def get(self, key, default=None):
        return default


class FakeEmbeddingStoreNamespaces:
    def __init__(self, namespaces):
        self._namespaces = list(namespaces)
        self.calls = []

    def list_embedding_namespaces(self, account_name):
        self.calls.append(account_name)
        return list(self._namespaces)


class FakeUtilsMemory:
    def __init__(self):
        self.calls = []
        self.embedding_store = FakeEmbeddingStoreNamespaces(["books", "zen"])

    def embed(self, items, model=None):
        self.calls.append(("embed", items, model))
        return type("Resp", (), {"embeddings": [[0.1, 0.2]]})()

    def compare(self, a, b, model=None):
        self.calls.append(("compare", a, b, model))
        return {"score": 0.9}

    def rank(self, items, model=None):
        self.calls.append(("rank", items, model))
        return {"ranks": list(range(len(items)))}

    def models(self):
        self.calls.append(("models",))
        return {"models": ["text-embedding-3-small"]}


def _args(**overrides):
    args = {
        "action": "embed",
        "query": "irrelevant",
        "account_name": "",
        "namespaces": ["external"],
        "top_k": 3,
        "max_chars": 9000,
        "score_threshold": 0.25,
        "embedding_model": "text-embedding-3-small",
        "source_type": "",
    }
    args.update(overrides)
    return args


def test_embed_action_against_injected_facade_expect_success():
    memory = FakeUtilsMemory()
    handler = SemanticMemoryHandler(DummyConfig(), memory=memory)

    result = handler.execute(_args(action="embed"), account_name="junwin")

    assert result["ok"] is True


def test_compare_action_against_injected_facade_expect_success():
    memory = FakeUtilsMemory()
    handler = SemanticMemoryHandler(DummyConfig(), memory=memory)

    result = handler.execute(_args(action="compare"), account_name="junwin")

    assert result["ok"] is True


def test_rank_action_against_injected_facade_expect_success():
    memory = FakeUtilsMemory()
    handler = SemanticMemoryHandler(DummyConfig(), memory=memory)

    result = handler.execute(_args(action="rank"), account_name="junwin")

    assert result["ok"] is True


def test_models_action_against_injected_facade_expect_success():
    memory = FakeUtilsMemory()
    handler = SemanticMemoryHandler(DummyConfig(), memory=memory)

    result = handler.execute(_args(action="models"), account_name="junwin")

    assert result["ok"] is True
    assert result["models"] == ["text-embedding-3-small"]
    assert result["count"] == 1
    assert memory.calls[-1] == ("models",)


def test_namespaces_action_against_injected_memory_store():
    memory = FakeUtilsMemory()
    handler = SemanticMemoryHandler(DummyConfig(), memory=memory)

    result = handler.execute(
        {"action": "namespaces", "account_name": ""}, account_name="junwin"
    )

    assert result["ok"] is True
    assert result["namespaces"] == ["books", "zen"]
    assert memory.embedding_store.calls == ["junwin"]
