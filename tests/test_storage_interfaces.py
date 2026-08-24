import inspect
from datetime import datetime, timezone

import pytest

from src.storage import JsonFileStorage, Storage
from src.storage.interfaces import ContextStore, HealthCheckable
from src.storage.models import Context, Skill
from src.storage_paths.storage_paths import StoragePaths

CONTEXT_STORE_METHODS = {
    "get_context",
    "get_or_create_context",
    "save_context",
    "list_context_names",
    "get_skill",
    "get_skill_text",
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
        assert issubclass(JsonFileStorage, ContextStore)
        assert issubclass(JsonFileStorage, HealthCheckable)

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
        for method in DEAD_V1_METHODS:
            assert not hasattr(ContextStore, method)
            assert not hasattr(Storage, method)
            assert not hasattr(JsonFileStorage, method)


class TestInterfaces(InterfacesTestCase):
    pass
