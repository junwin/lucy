"""Exercise actual app.py event routes without composing LLM/embedding services."""
import ast
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, jsonify, request
import pytest

from galet_memory import NewEvent, SqliteEpisodicMemory
from src.api_key import validate_api_key
from src.http_endpoints.events_endpoints import get_events_impl, deactivate_events_impl


@pytest.fixture
def memory(tmp_path):
    with SqliteEpisodicMemory(tmp_path / "events.sqlite") as store:
        for account, session in (("alice", "chat"), ("alice", "other"), ("bob", "bob-chat")):
            store.create_session(account_name=account, session_id=session)
        for role, text, correlation in (("user", "Question one", "one"),
                                        ("assistant", {"answer": "Full answer"}, "one"),
                                        ("user", "Question two", "two"),
                                        ("assistant", "Second answer", "two")):
            store.append_event(account_name="alice", session_id="chat",
                event=NewEvent(role=role, actor="alice" if role == "user" else "lucy",
                               kind=f"{role}_message", content=text,
                               correlation_ids=(correlation,), metadata={"message_id": text if isinstance(text, str) else "response"}))
        for account, session in (("alice", "other"), ("bob", "bob-chat")):
            store.append_event(account_name=account, session_id=session,
                event=NewEvent(role="user", actor=account, content="Unrelated", correlation_ids=("one",)))
        yield store


@pytest.fixture
def client(memory):
    import logging
    app = Flask(__name__)
    config = SimpleNamespace(get=lambda key, default=None: {"api_key_enabled": True, "api_key": "test-key"}.get(key, default))
    namespace = dict(app=app, request=request, jsonify=jsonify, logging=logging,
        config=config, validate_api_key=validate_api_key, episodic_memory_manager=memory,
        get_events_impl=get_events_impl, deactivate_events_impl=deactivate_events_impl)
    tree = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text())
    names = {"_check_api_key", "_enforce_api_key", "get_events", "deactivate_events"}
    routes = ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[])
    exec(compile(routes, "app.py", "exec"), namespace)
    app.config["TESTING"] = True
    return app.test_client()


KEY = {"X-API-Key": "test-key"}
SCOPE = {"accountName": "alice", "sessionId": "chat"}


def test_last_n_events_keep_order_full_content_and_targeting_ids(client):
    response = client.get("/events", query_string={**SCOPE, "count": 3}, headers=KEY)
    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == 3
    events = body["events"]
    assert [event["correlation_ids"] for event in events] == [["one"], ["two"], ["two"]]
    assert events[0]["content"] == {"answer": "Full answer"}
    assert events[0]["metadata"]["message_id"] == "response"
    assert all(event["event_id"] and event["created_at"] and event["stored_at"] for event in events)
    assert [e["sequence"] for e in events] == sorted(e["sequence"] for e in events)
    assert events[-1]["event_id"] == body["last_event_id"]
    assert client.get("/events", query_string=SCOPE, headers=KEY).get_json()["count"] == 4
    assert client.get("/events", query_string={**SCOPE, "count": 0}, headers=KEY).get_json()["events"] == []


def test_deactivate_exchange_repeat_and_reload_preserve_unrelated_events(client, memory):
    original = memory.get_recent_events(account_name="alice", session_id="chat", count=10).events
    response = client.delete("/events/one", query_string=SCOPE, headers=KEY)
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "invalidated"
    assert body["event_count"] == 2
    assert set(body["event_ids"]) == {event.event_id for event in original[:2]}
    assert body["marker_event_id"]
    assert client.delete("/events/one", query_string=SCOPE, headers=KEY).get_json()["status"] == "already_invalidated"
    remaining = client.get("/events", query_string=SCOPE, headers=KEY).get_json()["events"]
    assert [e["content"] for e in remaining] == ["Question two", "Second answer"]
    assert len(memory.get_active_snapshot(account_name="alice", session_id="chat").events) == 2
    # Originals are retained through the public audit read, not physical deletion.
    assert original[0].event_id in {e.event_id for e in memory.get_audit_snapshot(account_name="alice", session_id="chat").events}
    for account, session in (("alice", "other"), ("bob", "bob-chat")):
        assert len(memory.get_recent_events(account_name=account, session_id=session).events) == 1


@pytest.mark.parametrize("query", [{}, {"accountName": "alice"}, {"sessionId": "chat"},
    {**SCOPE, "count": "oops"}, {**SCOPE, "count": -1}, {**SCOPE, "count": "1.5"}, {**SCOPE, "count": 1001}])
def test_get_rejects_invalid_inputs(client, query):
    assert client.get("/events", query_string=query, headers=KEY).status_code == 400


@pytest.mark.parametrize("scope", [{"accountName": "bob", "sessionId": "chat"}, {**SCOPE, "sessionId": "missing"}])
def test_wrong_owner_or_session_is_not_found(client, scope):
    assert client.get("/events", query_string=scope, headers=KEY).status_code == 404
    assert client.delete("/events/one", query_string=scope, headers=KEY).status_code == 404


def test_missing_correlation_or_scope(client, memory):
    assert client.delete("/events/unknown", query_string=SCOPE, headers=KEY).status_code == 404
    assert client.delete("/events/one", headers=KEY).status_code == 400
    assert len(memory.get_recent_events(account_name="alice", session_id="chat").events) == 4


def test_unauthorized_delete_cannot_modify_memory(client, memory):
    assert client.delete("/events/one", query_string=SCOPE).status_code == 401
    assert client.delete("/events/one", query_string=SCOPE, headers={"X-API-Key": "wrong"}).status_code == 401
    assert len(memory.get_recent_events(account_name="alice", session_id="chat").events) == 4
    assert client.get("/events", query_string=SCOPE).status_code == 401
    assert client.delete("/events/one", query_string=SCOPE, headers={"Authorization": "Bearer test-key"}).status_code == 200


def test_deactivation_survives_reopen_and_invalidates_derived_digest(tmp_path):
    path = tmp_path / "persist.sqlite"
    with SqliteEpisodicMemory(path) as store:
        store.create_session(account_name="alice", session_id="chat")
        source = store.append_event(account_name="alice", session_id="chat",
            event=NewEvent(role="user", actor="alice", content="Question", correlation_ids=("one",)))
        digest = store.append_boundary(account_name="alice", session_id="chat",
            expected_last_event_id=source.event_id,
            event=NewEvent(role="system", actor="curator", kind="session_digest", content="Summary",
                           metadata={"source_event_ids": [source.event_id], "visibility_boundary": True}))
        body, status = deactivate_events_impl(store, account_name="alice", session_id="chat", correlation_id="one")
        assert status == 200
        assert digest.event_id in body["invalidated_digest_ids"]
    with SqliteEpisodicMemory(path) as reopened:
        assert get_events_impl(reopened, account_name="alice", session_id="chat")[0]["events"] == []
        assert reopened.get_active_snapshot(account_name="alice", session_id="chat").events == ()
        assert source.event_id in {e.event_id for e in reopened.get_audit_snapshot(account_name="alice", session_id="chat").events}
