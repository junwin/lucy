import pytest

from galet_memory import ProceduralMemoryRequest
from src.procedural_memory_config import build_procedural_memory
from src.handlers.context_handler import ContextHandler
from src.http_endpoints.context_endpoints import list_context_names_impl


class Config:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def test_shared_configuration_for_recall_tool_listing_and_account_edits(tmp_path):
    config = Config(storage_root_path=str(tmp_path), storage_namespace="data")
    memory = build_procedural_memory(config)
    repo = memory.repository
    repo.save_skill(account_name="alice", skill_name="writing", scope="global", text="Shared writing")
    global_path = repo.save_context(account_name="alice", context_name="shop", scope="global",
                                   text="Shared shop", frontmatter={"imports": ["writing"],
                                   "allowed_tools": ["read"], "mandatory_tools": ["search"]})
    before = global_path.read_bytes()
    handler = ContextHandler(config)
    assert handler.execute({"action": "list"}, account_name="alice")["context_names"] == ["shop"]
    assert list_context_names_impl(None, "alice", procedural_memory=memory) == (["shop"], 200)
    loaded = handler.execute({"action": "load", "context_name": "shop"}, account_name="alice")
    assert loaded["ok"]
    assert loaded["skills"] == ["writing"]
    assert loaded["resolved_text"] == memory.recall(ProceduralMemoryRequest("alice", "shop")).resolved_text
    changed = handler.execute({"action": "set_mandatory_tools", "context_name": "shop",
                               "tool_names": ["inspect"]}, account_name="alice")
    assert changed["ok"]
    assert (tmp_path / "data/contexts/alice/shop.md").is_file()
    assert global_path.read_bytes() == before
    loaded = handler.execute({"action": "load", "context_name": "shop"}, account_name="alice")
    assert loaded["data"]["text"] == "Shared shop"
    assert loaded["data"]["extra"]["allowed_tools"] == ["read"]
    assert loaded["required_tools"] == ["inspect"]
    repo.save_skill(account_name="alice", skill_name="writing", text="Alice writing")
    saved = handler.execute({"action": "save", "context_name": "shop", "text": "Alice shop"},
                            account_name="alice")
    assert saved["ok"]
    assert saved["data"]["imports"] == ["writing"]
    assert memory.recall(ProceduralMemoryRequest("alice", "shop")).skills[0].text == "Alice writing"
    bob = memory.recall(ProceduralMemoryRequest("bob", "shop"))
    assert bob.text == "Shared shop"
    assert bob.skills[0].text == "Shared writing"
    assert bob.required_tools == ["search"]


def test_custom_root_layout_and_legacy_merge_policy(tmp_path):
    config = Config(storage_root_path=str(tmp_path / "unused"), procedural_memory={
        "root": str(tmp_path / "custom"), "context_resolution": "merge",
        "layout": {"global_contexts": "shared/contexts", "global_skills": "shared/skills"}})
    memory = build_procedural_memory(config)
    memory.repository.save_context(account_name="alice", context_name="shop", scope="global", text="Shared")
    memory.repository.save_context(account_name="alice", context_name="shop", text="Account")
    assert (tmp_path / "custom/shared/contexts/shop.md").is_file()
    assert memory.recall(ProceduralMemoryRequest("alice", "shop")).text == "Shared\n\nAccount"
    assert ContextHandler(config).memory.repository.root == memory.repository.root


@pytest.mark.parametrize("options", [{"context_resolution": "typo"}, {"layout": []},
                                     {"layout": {"global_skills": 123}}, {"layout": {"typo": "x"}}])
def test_invalid_config_is_not_silently_ignored(tmp_path, options):
    config = Config(storage_root_path=str(tmp_path), procedural_memory=options)
    with pytest.raises((ValueError, TypeError)):
        build_procedural_memory(config)
    with pytest.raises((ValueError, TypeError)):
        ContextHandler(config)
