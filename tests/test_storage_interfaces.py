import inspect
from datetime import datetime, timezone

import pytest

from src.storage import JsonFileStorage, Storage
from src.storage.interfaces import (
    ContextStore,
    DocumentStore,
    EmbeddingStore,
    HealthCheckable,
    TasklistStore,
)
from src.storage.models import Context, DocumentRef, EmbeddingRecord, Skill
from src.storage_paths.storage_paths import StoragePaths
from src.tasklists.task_list import TaskList

CONTEXT_STORE_METHODS = {
    "get_context",
    "get_or_create_context",
    "save_context",
    "list_context_names",
    "get_skill",
    "get_skill_text",
}

TASKLIST_STORE_METHODS = {
    "list_tasklists",
    "get_tasklist",
    "save_tasklist",
    "delete_tasklist",
    "append_task_execution_record",
    "get_task_result",
}

DOCUMENT_STORE_METHODS = {
    "list_documents",
    "get_document",
    "upsert_document",
}

EMBEDDING_STORE_METHODS = {
    "upsert_embedding",
    "query_embeddings",
    "delete_embeddings",
    "list_embeddings",
    "list_embedding_namespaces",
}

DEAD_V1_METHODS = {
    "get_chat_session",
    "list_chat_sessions",
    "rename_chat_session",
    "update_chat_session",
    "delete_chat_session",
    "upsert_user_profile",
    "save_user",
    "load_user",
    "get_agent_profile",
    "upsert_agent_profile",
}


@pytest.fixture
def storage_paths(tmp_path) -> StoragePaths:
    root = tmp_path / "lucy_storage"
    root.mkdir()
    return StoragePaths(str(root), "data")


@pytest.fixture
def json_storage(storage_paths) -> JsonFileStorage:
    return JsonFileStorage(storage_paths)


class InterfacesTestCase:
    def test_storage_is_context_store_and_health_checkable(self):
        assert issubclass(Storage, ContextStore)
        assert issubclass(Storage, HealthCheckable)
        assert issubclass(Storage, TasklistStore)
        assert issubclass(Storage, DocumentStore)
        assert issubclass(Storage, EmbeddingStore)
        assert issubclass(JsonFileStorage, ContextStore)
        assert issubclass(JsonFileStorage, HealthCheckable)
        assert issubclass(JsonFileStorage, TasklistStore)
        assert issubclass(JsonFileStorage, DocumentStore)
        assert issubclass(JsonFileStorage, EmbeddingStore)

    def test_storage_aggregate_is_abstract_json_file_storage_concrete(self):
        assert inspect.isabstract(Storage)
        assert not inspect.isabstract(JsonFileStorage)

    def test_json_file_storage_implements_every_context_store_method(self, json_storage):
        assert isinstance(json_storage, ContextStore)
        assert isinstance(json_storage, HealthCheckable)
        assert json_storage.get_context("junwin", "missing") is None
        created = json_storage.get_or_create_context("junwin", "c1")
        assert isinstance(created, Context)
        assert created.id == "c1"
        assert created.account_name == "junwin"
        loaded = json_storage.get_context("junwin", "c1")
        assert loaded is not None
        assert loaded.id == "c1"
        ctx = Context(
            id="rt",
            account_name="junwin",
            text="Body",
            updated_at=datetime.now(timezone.utc),
        )
        json_storage.save_context(ctx)
        loaded = json_storage.get_context("junwin", "rt")
        assert loaded is not None
        assert loaded.text == "Body"
        assert json_storage.list_context_names("junwin") == ["c1", "rt"]
        assert json_storage.get_skill("junwin", "missing") is None
        assert json_storage.get_skill_text("junwin", "missing") is None
        assert json_storage.health_check() is True

    def test_json_file_storage_implements_every_tasklist_store_method(self, json_storage):
        assert isinstance(json_storage, TasklistStore)
        store: TasklistStore = json_storage
        tasklist = TaskList(id="tl1", name="My Tasks", description="d", tasks=[])
        store.save_tasklist("alice", "tl1", tasklist)
        assert store.list_tasklists("alice") == ["tl1"]
        tl = store.get_tasklist("alice", "tl1")
        assert isinstance(tl, TaskList)
        assert tl.id == "tl1"
        assert tl.schema_version == 1
        assert tl.name == "My Tasks"
        assert tl.description == "d"
        assert tl.tasks == []
        store.delete_tasklist("alice", "tl1")
        assert store.list_tasklists("alice") == []
        store.delete_tasklist("alice", "tl1")
        assert store.list_tasklists("alice") == []

    def test_json_file_storage_implements_every_document_store_method(self, json_storage):
        assert isinstance(json_storage, DocumentStore)
        store: DocumentStore = json_storage
        doc = DocumentRef(
            id="d1",
            account_name="alice",
            path="/tmp/d1.md",
            kind="obsidian_note",
            title="Doc One",
            tags=["alpha"],
            metadata={"source": "test"},
        )
        store.upsert_document(doc)
        loaded = store.get_document("d1")
        assert isinstance(loaded, DocumentRef)
        assert loaded.id == "d1"
        assert loaded.account_name == "alice"
        assert loaded.path == "/tmp/d1.md"
        assert loaded.kind == "obsidian_note"
        assert loaded.title == "Doc One"
        assert loaded.tags == ["alpha"]
        assert loaded.metadata == {"source": "test"}
        assert store.get_document("missing") is None
        assert [d.id for d in store.list_documents("alice")] == ["d1"]
        assert [d.id for d in store.list_documents("alice", kind="obsidian_note", tag="alpha")] == ["d1"]
        assert store.list_documents("alice", kind="other") == []
        assert store.list_documents("nobody") == []

    def test_json_file_storage_implements_every_embedding_store_method(self, json_storage):
        assert isinstance(json_storage, EmbeddingStore)
        store: EmbeddingStore = json_storage
        store.upsert_embedding(
            EmbeddingRecord(
                id="e1",
                namespace="digests",
                account_name="alice",
                vector=[1.0, 0.0, 0.0],
                source_type="chat_session",
                source_id="s1",
            )
        )
        store.upsert_embedding(
            EmbeddingRecord(
                id="e2",
                namespace="digests",
                account_name="alice",
                vector=[0.9, 0.1, 0.0],
                source_type="chat_session",
                source_id="s2",
            )
        )
        store.upsert_embedding(
            EmbeddingRecord(
                id="e3",
                namespace="documents",
                account_name="alice",
                vector=[0.0, 1.0, 0.0],
                source_type="document",
                source_id="d1",
            )
        )
        assert store.list_embedding_namespaces("alice") == ["digests", "documents"]
        assert store.list_embedding_namespaces("nobody") == []
        hits = store.query_embeddings(["digests"], "alice", [1.0, 0.0, 0.0], top_k=1)
        assert len(hits) == 1
        assert hits[0][0].id == "e1"
        assert hits[0][1] > 0.99
        hits = store.query_embeddings(
            ["digests", "documents"], "alice", [1.0, 0.0, 0.0], top_k=3
        )
        assert [r.id for r, _ in hits] == ["e1", "e2", "e3"]
        hits = store.query_embeddings(
            ["digests", "documents"],
            "alice",
            [1.0, 0.0, 0.0],
            top_k=10,
            filter={"source_type": "document"},
        )
        assert [r.id for r, _ in hits] == ["e3"]
        assert store.delete_embeddings("digests", "alice", source_type="chat_session") == 2
        assert store.delete_embeddings("digests", "alice", source_id="e1") == 0
        assert store.delete_embeddings("missing", "alice") == 0
        assert store.delete_embeddings("documents", "alice", source_id="d1") == 1
        assert store.query_embeddings(["digests"], "alice", [1.0, 0.0, 0.0]) == []

    def test_methods_callable_with_documented_signatures(self, json_storage):
        assert list(inspect.signature(json_storage.get_context).parameters) == [
            "account_name",
            "context_id",
        ]
        sig = inspect.signature(json_storage.get_or_create_context)
        params = list(sig.parameters.values())
        assert [p.name for p in params[:2]] == ["account_name", "context_id"]
        assert all(p.default is not inspect.Parameter.empty for p in params[2:])
        assert list(inspect.signature(json_storage.save_context).parameters) == ["context"]
        assert list(inspect.signature(json_storage.list_context_names).parameters) == [
            "account_name"
        ]
        assert list(inspect.signature(json_storage.get_skill).parameters) == [
            "account_name",
            "skill_name",
        ]
        assert list(inspect.signature(json_storage.get_skill_text).parameters) == [
            "account_name",
            "skill_name",
        ]
        assert list(inspect.signature(json_storage.health_check).parameters) == []

    def test_get_skill_returns_skill_and_text(self, json_storage):
        skill_dir = json_storage.storage_paths.skills / "junwin"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "alpha.md").write_text(
            "---\nmandatory_tools:\n  - file_load\n---\nSKILL BODY\n",
            encoding="utf-8",
        )
        skill = json_storage.get_skill("junwin", "alpha")
        assert isinstance(skill, Skill)
        assert skill.text == "SKILL BODY\n"
        assert skill.mandatory_tools == ["file_load"]
        assert json_storage.get_skill_text("junwin", "alpha") == "SKILL BODY\n"

    def test_narrow_interface_subset_holds(self):
        own = {
            name
            for name, member in vars(ContextStore).items()
            if callable(member) and not name.startswith("_")
        }
        assert own == CONTEXT_STORE_METHODS
        for method in CONTEXT_STORE_METHODS:
            assert hasattr(Storage, method)
            assert hasattr(JsonFileStorage, method)
        assert hasattr(Storage, "health_check")
        assert hasattr(JsonFileStorage, "health_check")
        tasklist_own = {
            name
            for name, member in vars(TasklistStore).items()
            if callable(member) and not name.startswith("_")
        }
        assert tasklist_own == TASKLIST_STORE_METHODS
        for method in TASKLIST_STORE_METHODS:
            assert hasattr(Storage, method)
            assert hasattr(JsonFileStorage, method)
        document_own = {
            name
            for name, member in vars(DocumentStore).items()
            if callable(member) and not name.startswith("_")
        }
        assert document_own == DOCUMENT_STORE_METHODS
        for method in DOCUMENT_STORE_METHODS:
            assert hasattr(Storage, method)
            assert hasattr(JsonFileStorage, method)
        embedding_own = {
            name
            for name, member in vars(EmbeddingStore).items()
            if callable(member) and not name.startswith("_")
        }
        assert embedding_own == EMBEDDING_STORE_METHODS
        for method in EMBEDDING_STORE_METHODS:
            assert hasattr(Storage, method)
            assert hasattr(JsonFileStorage, method)
        for method in DEAD_V1_METHODS:
            assert not hasattr(ContextStore, method)
            assert not hasattr(TasklistStore, method)
            assert not hasattr(DocumentStore, method)
            assert not hasattr(EmbeddingStore, method)
            assert not hasattr(Storage, method)
            assert not hasattr(JsonFileStorage, method)


class TestInterfaces(InterfacesTestCase):
    pass
