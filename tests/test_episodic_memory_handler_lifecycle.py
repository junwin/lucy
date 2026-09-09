import json
from uuid import uuid4

from src.config_manager import ConfigManager
from src.coala_memory.episodic import EpisodicEvent
from src.handlers.episodic_memory_handler import EpisodicMemoryHandler

from tests.test_episodic_memory_handler import _config, _base_args


def test_create_session_honours_required_and_optionals(tmp_path):
    handler = EpisodicMemoryHandler(_config(tmp_path))
    args = _base_args(action="create_session", agent_name="peace", context_name="lucyproject")
    args.update({
        "session_id": "",
        "friendly_name": "new session",
        "session_type": "user",
        "user_id": "u123",
        "tags": ["t1", "t2"],
        "participants": ["p1"],
        "links": {"related": "s1"},
        "metadata": {"k": "v"},
    })
    result = handler.execute(args, account_name="junwin")
    assert result["ok"] is True
    assert result["tool"] == handler.NAME
    assert "session" in result
    assert result["session"].get("context_name") == "lucyproject"


def test_update_session_patches_allowed_fields_only(tmp_path):
    handler = EpisodicMemoryHandler(_config(tmp_path))
    session = handler.memory.create_session(account_name="junwin", agent_name="peace", friendly_name="orig", context_name="orig_ctx")

    link_id = str(uuid4())
    args = _base_args(action="update_session", session_id=session.session_id, agent_name="peace")
    patch = {
        "friendly_name": "patched",
        "context_name": "patched_ctx",
        "tags": ["x"],
        "session_type": "internal",
        "participants": ["p2"],
        "links": {"internal_session_id": link_id},
        "metadata": {"m": 1},
        # routing/identity args present in the flat namespace must not leak into the patch
        "account_name": "junwin",
        "session_id": session.session_id,
    }
    args.update(patch)
    result = handler.execute(args, account_name="junwin")
    assert result["ok"] is True
    updated = handler.memory.get_session(session.session_id, include_events=False)
    assert updated is not None
    assert updated.friendly_name == "patched"
    assert updated.context_name == "patched_ctx"
    assert "x" in updated.tags
    assert updated.session_type == "internal"
    assert "p2" in updated.participants
    assert updated.links.get("internal_session_id") == link_id
    assert updated.metadata.get("m") == 1
    assert updated.account_name == "junwin"
    assert updated.agent_name == "peace"
    assert updated.session_id == session.session_id


def test_update_session_unknown_session_id_errors_without_touching_others(tmp_path):
    handler = EpisodicMemoryHandler(_config(tmp_path))
    session = handler.memory.create_session(account_name="junwin", agent_name="peace", friendly_name="orig")

    args = _base_args(action="update_session", session_id=str(uuid4()), agent_name="peace")
    args["friendly_name"] = "patched"
    result = handler.execute(args, account_name="junwin")

    assert result["ok"] is False
    assert "Session not found" in result["error"]
    untouched = handler.memory.get_session(session.session_id, include_events=False)
    assert untouched is not None
    assert untouched.friendly_name == "orig"


def test_reset_session_clears_events_keeps_metadata(tmp_path):
    handler = EpisodicMemoryHandler(_config(tmp_path))
    session = handler.memory.create_session(account_name="junwin", agent_name="peace", metadata={"x": 1})
    handler.memory.append_event(session.session_id, EpisodicEvent(role="user", actor="user", kind="user_message", content="c1"))
    handler.memory.append_event(session.session_id, EpisodicEvent(role="assistant", actor="peace", kind="assistant_message", content="c2"))

    args = _base_args(action="reset_session", session_id=session.session_id, agent_name="peace")
    result = handler.execute(args, account_name="junwin")
    assert result["ok"] is True
    assert result.get("session_id") == session.session_id
    s = handler.memory.get_session(session.session_id, include_events=True)
    assert s is not None
    assert len(s.events) == 0
    assert s.metadata.get("x") == 1


def test_delete_session_returns_ok_and_session_id(tmp_path):
    handler = EpisodicMemoryHandler(_config(tmp_path))
    session = handler.memory.create_session(account_name="junwin", agent_name="peace")
    args = _base_args(action="delete_session", session_id=session.session_id, agent_name="peace")
    result = handler.execute(args, account_name="junwin")
    assert result["ok"] is True
    assert result.get("session_id") == session.session_id
    s = handler.memory.get_session(session.session_id, include_events=False)
    assert s is None
