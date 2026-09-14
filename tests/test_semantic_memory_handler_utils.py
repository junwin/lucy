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
