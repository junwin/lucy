import pytest
from pathlib import Path

from src.http_endpoints.documents_endpoints import search_documents_impl


class SemanticDocument:
    def __init__(self, source_id: str, source_type: str = "external", path: str = "",
                 title: str = "", tags=None, snippet: str = "", score: float = 1.0,
                 truncated: bool = False, metadata=None):
        self.source_id = source_id
        self.source_type = source_type
        self.path = path
        self.title = title
        self.tags = tags or []
        self.snippet = snippet
        self.score = score
        self.truncated = truncated
        self.metadata = metadata or {}


class SemanticMemoryResult:
    def __init__(self, documents):
        self.documents = documents


class FakeSemanticMemory:
    def __init__(self, result: SemanticMemoryResult = None, exc: Exception = None):
        self.result = result or SemanticMemoryResult([])
        self.exc = exc
        self.requests = []

    def recall(self, req):
        self.requests.append(req)
        if self.exc:
            raise self.exc
        return self.result


def _make_doc(stem="doc1"):
    sid = f"/some/path/{stem}.md"
    return SemanticDocument(
        source_id=sid,
        source_type="external",
        path=sid,
        title=stem,
        tags=["a", "b"],
        snippet="snippet text",
        score=0.85,
        truncated=False,
        metadata={"k": "v"},
    )


def test_ok_shape():
    fake = FakeSemanticMemory(result=SemanticMemoryResult([_make_doc("alpha")]))
    data = {"account_name": "junwin", "question": "what is this?"}
    body, status = search_documents_impl(fake, data)
    assert status == 200
    assert isinstance(body, list)
    assert len(body) == 1
    item = body[0]
    expected_keys = {"id", "source_id", "account_name", "path", "source_type", "title", "tags", "snippet", "score", "truncated", "metadata"}
    assert set(item.keys()) == expected_keys
    assert item["id"] == Path(_make_doc("alpha").source_id).stem
    assert "kind" not in item


def test_default_param_mapping():
    fake = FakeSemanticMemory(result=SemanticMemoryResult([_make_doc()]))
    data = {"account_name": "junwin", "question": "hello"}
    _ = search_documents_impl(fake, data)
    assert len(fake.requests) == 1
    req = fake.requests[0]
    assert getattr(req, "account_name") == "junwin"
    assert getattr(req, "use_embeddings") is True
    assert getattr(req, "namespaces") == ["external"]
    assert getattr(req, "top_k") == 10
    assert getattr(req, "max_chars") == 9000
    assert getattr(req, "score_threshold") == 0.25
    assert getattr(req, "source_type") is None


def test_limit_maps_to_top_k():
    fake = FakeSemanticMemory(result=SemanticMemoryResult([]))
    data = {"account_name": "junwin", "question": "hi", "limit": 3}
    _ = search_documents_impl(fake, data)
    assert len(fake.requests) == 1
    req = fake.requests[0]
    assert getattr(req, "top_k") == 3


def test_namespaces_param_variants():
    cases = [
        ("zen,books", ["zen", "books"]),
        ("zen", ["zen"]),
        ("external,documents,vol_3", ["external", "documents", "vol_3"]),
        ("", ["external"]),
    ]
    for raw, expected in cases:
        fake = FakeSemanticMemory(result=SemanticMemoryResult([]))
        data = {"account_name": "junwin", "question": "q", "namespaces": raw}
        _ = search_documents_impl(fake, data)
        assert len(fake.requests) == 1
        req = fake.requests[0]
        assert getattr(req, "namespaces") == expected


def test_source_type_passthrough():
    fake = FakeSemanticMemory(result=SemanticMemoryResult([]))
    data = {"account_name": "junwin", "question": "q", "source_type": "books"}
    _ = search_documents_impl(fake, data)
    assert len(fake.requests) == 1
    req = fake.requests[0]
    assert getattr(req, "source_type") == "books"


def test_missing_account_name_400():
    fake = FakeSemanticMemory(result=SemanticMemoryResult([]))
    data = {"question": "q"}
    body, status = search_documents_impl(fake, data)
    assert status == 400
    assert body == {"error": "Missing account_name"}


def test_missing_query_400():
    fake = FakeSemanticMemory(result=SemanticMemoryResult([]))
    data = {"account_name": "junwin"}
    body, status = search_documents_impl(fake, data)
    assert status == 400
    assert body == {"error": "Missing query"}


def test_recall_exception_500():
    fake = FakeSemanticMemory(exc=RuntimeError("boom"))
    data = {"account_name": "junwin", "question": "q"}
    body, status = search_documents_impl(fake, data)
    assert status == 500
    assert "error" in body


def test_empty_results_200():
    fake = FakeSemanticMemory(result=SemanticMemoryResult([]))
    data = {"account_name": "junwin", "question": "q"}
    body, status = search_documents_impl(fake, data)
    assert status == 200
    assert body == []
