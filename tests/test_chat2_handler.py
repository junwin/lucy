"""Tests for Chat2Handler."""

from __future__ import annotations

import json
from typing import Any, Dict
from uuid import uuid4

from src.handlers.chat2_handler import Chat2Handler
from src.chat2.facade import Chat2Store
from src.chat2.store_primitives import InMemoryStore


class SimpleConfig:
    """Minimal config for handler construction."""
    def __init__(self, storage_root_path: str = "/tmp", storage_namespace: str = "test"):
        self._m = {
            "storage_root_path": storage_root_path,
            "storage_namespace": storage_namespace,
        }

    def get(self, k: str, default: Any = None) -> Any:
        return self._m.get(k, default)


def _make_handler() -> Chat2Handler:
    """Create a Chat2Handler with an in-memory store for testing."""
    cfg = SimpleConfig()
    handler = Chat2Handler(cfg)
    # Replace the real store with an in-memory one for testing
    handler.chat2_store = Chat2Store(InMemoryStore())
    return handler


def _create_test_session(handler: Chat2Handler, session_id: str | None = None) -> str:
    """Helper: create a session with some events. Returns the session_id."""
    store = handler.chat2_store
    sid = session_id or str(uuid4())
    store.create_session(
        user_id="testuser",
        account_name="testaccount",
        agent_name="lucy",
        session_id=sid,
        friendly_name="Test Session",
    )
    # Add some events
    from src.chat2.models import ChatEvent
    store.add_event(sid, ChatEvent(
        role="user", actor="testuser", kind="user_message", payload="Hello, how are you?"
    ))
    store.add_event(sid, ChatEvent(
        role="assistant", actor="lucy", kind="assistant_message", payload="I'm doing great!"
    ))
    store.add_event(sid, ChatEvent(
        role="user", actor="testuser", kind="user_message", payload="What's the weather?"
    ))
    store.add_event(sid, ChatEvent(
        role="assistant", actor="lucy", kind="assistant_message", payload="It's sunny today."
    ))
    return sid


# ------------------------------------------------------------------
# reset_chat
# ------------------------------------------------------------------

def test_reset_chat_clears_events():
    handler = _make_handler()
    sid = _create_test_session(handler)

    result = handler.execute({"action": "reset_chat", "session_id": sid})
    assert result["ok"] is True
    assert result["action"] == "reset_chat"
    assert result["session_id"] == sid

    # Verify events are cleared
    events = list(handler.chat2_store.stream_events(sid))
    assert len(events) == 0

    # Verify metadata preserved
    meta = handler.chat2_store.get_session(sid)
    assert meta is not None
    assert meta.friendly_name == "Test Session"


def test_reset_chat_missing_session():
    handler = _make_handler()
    result = handler.execute({"action": "reset_chat", "session_id": str(uuid4())})
    assert result["ok"] is False
    assert "not found" in result["error"].lower()


def test_reset_chat_no_session_id():
    handler = _make_handler()
    result = handler.execute({"action": "reset_chat"})
    assert result["ok"] is False
    assert "session_id is required" in result["error"].lower()


# ------------------------------------------------------------------
# search_sessions
# ------------------------------------------------------------------

def test_search_sessions_finds_matches():
    handler = _make_handler()
    _create_test_session(handler)
    _create_test_session(handler)

    result = handler.execute({"action": "search_sessions", "query": "weather"})
    assert result["ok"] is True
    assert result["total_matches"] >= 1
    # At least one session should have matched "weather"
    assert any("weather" in str(s) for s in result["sessions"])


def test_search_sessions_no_match():
    handler = _make_handler()
    _create_test_session(handler)

    result = handler.execute({"action": "search_sessions", "query": "zzz_nonexistent_zzz"})
    assert result["ok"] is True
    assert result["total_matches"] == 0


def test_search_sessions_no_query():
    handler = _make_handler()
    result = handler.execute({"action": "search_sessions"})
    assert result["ok"] is False
    assert "query is required" in result["error"].lower()


# ------------------------------------------------------------------
# get_session
# ------------------------------------------------------------------

def test_get_session():
    handler = _make_handler()
    sid = _create_test_session(handler)

    result = handler.execute({"action": "get_session", "session_id": sid})
    assert result["ok"] is True
    assert result["session_id"] == sid
    assert result["session"]["friendly_name"] == "Test Session"
    assert result["event_count"] == 4
    assert len(result["events"]) == 4


def test_get_session_missing():
    handler = _make_handler()
    result = handler.execute({"action": "get_session", "session_id": str(uuid4())})
    assert result["ok"] is False
    assert "not found" in result["error"].lower()


def test_get_session_no_id():
    handler = _make_handler()
    result = handler.execute({"action": "get_session"})
    assert result["ok"] is False
    assert "session_id is required" in result["error"].lower()


# ------------------------------------------------------------------
# list_sessions
# ------------------------------------------------------------------

def test_list_sessions():
    handler = _make_handler()
    _create_test_session(handler)
    _create_test_session(handler)

    result = handler.execute({"action": "list_sessions"})
    assert result["ok"] is True
    assert result["total"] >= 2


def test_list_sessions_filtered():
    handler = _make_handler()
    _create_test_session(handler)

    result = handler.execute({"action": "list_sessions", "account_name": "testaccount"})
    assert result["ok"] is True
    assert result["total"] >= 1


# ------------------------------------------------------------------
# delete_session
# ------------------------------------------------------------------

def test_delete_session():
    handler = _make_handler()
    sid = _create_test_session(handler)

    result = handler.execute({"action": "delete_session", "session_id": sid})
    assert result["ok"] is True

    # Verify deleted
    meta = handler.chat2_store.get_session(sid)
    assert meta is None


def test_delete_session_missing():
    handler = _make_handler()
    result = handler.execute({"action": "delete_session", "session_id": str(uuid4())})
    assert result["ok"] is False
    assert "not found" in result["error"].lower()


def test_delete_session_no_id():
    handler = _make_handler()
    result = handler.execute({"action": "delete_session"})
    assert result["ok"] is False
    assert "session_id is required" in result["error"].lower()


# ------------------------------------------------------------------
# update_session
# ------------------------------------------------------------------

def test_update_session():
    handler = _make_handler()
    sid = _create_test_session(handler)

    patch = json.dumps({"friendly_name": "Updated Name", "tags": ["important"]})
    result = handler.execute({"action": "update_session", "session_id": sid, "patch_fields": patch})
    assert result["ok"] is True
    assert result["session"]["friendly_name"] == "Updated Name"
    assert result["session"]["tags"] == ["important"]


def test_update_session_missing():
    handler = _make_handler()
    patch = json.dumps({"friendly_name": "Nope"})
    result = handler.execute({"action": "update_session", "session_id": str(uuid4()), "patch_fields": patch})
    assert result["ok"] is False
    assert "not found" in result["error"].lower()


def test_update_session_no_id():
    handler = _make_handler()
    result = handler.execute({"action": "update_session", "patch_fields": "{}"})
    assert result["ok"] is False
    assert "session_id is required" in result["error"].lower()


def test_update_session_no_patch():
    handler = _make_handler()
    sid = _create_test_session(handler)
    result = handler.execute({"action": "update_session", "session_id": sid})
    assert result["ok"] is False
    assert "patch_fields is required" in result["error"].lower()


def test_update_session_invalid_json():
    handler = _make_handler()
    sid = _create_test_session(handler)
    result = handler.execute({"action": "update_session", "session_id": sid, "patch_fields": "not json"})
    assert result["ok"] is False
    assert "Invalid" in result["error"]


# ------------------------------------------------------------------
# curate_session
# ------------------------------------------------------------------

def test_curate_session_remove_kinds():
    handler = _make_handler()
    sid = _create_test_session(handler)

    rules = json.dumps({"remove_kinds": ["assistant_message"]})
    result = handler.execute({"action": "curate_session", "session_id": sid, "curation_rules": rules})
    assert result["ok"] is True
    assert result["summary"]["original_count"] == 4
    assert result["summary"]["kept_count"] == 2  # only user messages remain
    assert result["summary"]["removed"]["by_kind"] == 2


def test_curate_session_keep_roles():
    handler = _make_handler()
    sid = _create_test_session(handler)

    rules = json.dumps({"keep_roles": ["assistant"]})
    result = handler.execute({"action": "curate_session", "session_id": sid, "curation_rules": rules})
    assert result["ok"] is True
    assert result["summary"]["kept_count"] == 2  # only assistant messages
    assert result["summary"]["removed"]["by_role"] == 2


def test_curate_session_deduplicate():
    handler = _make_handler()
    sid = str(uuid4())
    store = handler.chat2_store
    store.create_session(
        user_id="testuser", account_name="testaccount", agent_name="lucy",
        session_id=sid,
    )
    from src.chat2.models import ChatEvent
    # Add duplicate events
    for _ in range(3):
        store.add_event(sid, ChatEvent(
            role="user", actor="testuser", kind="user_message", payload="Hello"
        ))

    rules = json.dumps({"deduplicate": True})
    result = handler.execute({"action": "curate_session", "session_id": sid, "curation_rules": rules})
    assert result["ok"] is True
    assert result["summary"]["original_count"] == 3
    assert result["summary"]["kept_count"] == 1
    assert result["summary"]["removed"]["duplicates"] == 2


def test_curate_session_missing():
    handler = _make_handler()
    result = handler.execute({"action": "curate_session", "session_id": str(uuid4())})
    assert result["ok"] is False
    assert "not found" in result["error"].lower()


def test_curate_session_no_id():
    handler = _make_handler()
    result = handler.execute({"action": "curate_session"})
    assert result["ok"] is False
    assert "session_id is required" in result["error"].lower()


# ------------------------------------------------------------------
# invalid action
# ------------------------------------------------------------------

def test_invalid_action():
    handler = _make_handler()
    result = handler.execute({"action": "fly_to_the_moon"})
    assert result["ok"] is False
    assert "unknown action" in result["error"].lower()


# ------------------------------------------------------------------
# tool_def and result_schema
# ------------------------------------------------------------------

def test_tool_def():
    td = Chat2Handler.tool_def()
    assert td["type"] == "function"
    assert td["name"] == "chat2_handler"
    assert "parameters" in td
    props = td["parameters"]["properties"]
    assert "action" in props
    assert props["action"]["type"] == "string"
    assert "reset_chat" in props["action"]["enum"]


def test_result_schema():
    rs = Chat2Handler.result_schema()
    assert rs["type"] == "object"
    assert "ok" in rs["properties"]
    assert "tool" in rs["properties"]
