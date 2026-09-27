from galet_memory import FileProceduralMemory, ProceduralLayout

from src.handlers.context_handler import ContextHandler


def test_context_handler_uses_galet_memory_for_context_lifecycle(tmp_path):
    memory = FileProceduralMemory(tmp_path, ProceduralLayout.lucy())
    memory.repository.save_skill(account_name="alice", skill_name="filepaths",
                                 text="Use absolute paths.",
                                 frontmatter={"mandatory_tools": ["file_load"]})
    handler = ContextHandler(None)
    context = {"procedural_memory": memory, "context_name": "skinny"}

    saved = handler.execute({"action": "save", "context_name": "skinny",
                             "text": "Short project context.",
                             "data": {"imports": ["filepaths"],
                                      "allowed_tools": ["file_load"]}},
                            account_name="alice", **context)
    assert saved["ok"] is True
    assert saved["data"]["extra"]["allowed_tools"] == ["file_load"]
    assert handler.execute({"action": "list"}, account_name="alice", **context)["context_names"] == ["skinny"]

    loaded = handler.execute({"action": "load"}, account_name="alice", **context)
    assert loaded["skills"] == ["filepaths"]
    assert "## skill: filepaths\nUse absolute paths." in loaded["resolved_text"]
    assert loaded["required_tools"] == ["file_load"]

    changed = handler.execute({"action": "set_mandatory_tools", "tool_names": ["inspect", "inspect"]},
                              account_name="alice", **context)
    assert changed["mandatory_tools"] == ["inspect"]
    reloaded = handler.execute({"action": "load"}, account_name="alice", **context)
    assert reloaded["data"]["text"].strip() == "Short project context."
    assert reloaded["data"]["extra"]["allowed_tools"] == ["file_load"]
    assert reloaded["required_tools"] == ["inspect", "file_load"]
