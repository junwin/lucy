import json

from src.config_manager import ConfigManager
from src.coala_memory.episodic import EpisodicEvent
from src.handlers.episodic_memory_handler import EpisodicMemoryHandler


def _config(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "code_sandbox_path": str(tmp_path),
                "chat2_store_backend": "sqlite",
                "chat2_store_db_path": str(tmp_path / "chat2.sqlite"),
                "storage_root_path": str(tmp_path),
                "storage_namespace": "data",
            }
        ),
        encoding="utf-8",
    )
    return ConfigManager(str(config_path))


def _base_args(**overrides):
    args = {
        "action": "recall",
        "session_id": "",
        "account_name": "",
        "agent_name": "",
        "query": "",
        "limit": 20,
        "max_events": 6,
        "include_events": True,
        "role": "user",
        "kind": "",
        "content": "",
    }
    args.update(overrides)
    return args


def test_tool_def_exposes_expected_integration_actions():
    tool = EpisodicMemoryHandler.tool_def()
    assert tool["name"] == "episodic_memory"
    enum = tool["parameters"]["properties"]["action"]["enum"]
    assert enum == ["recall", "get_session", "list_sessions", "append_event"]


def test_handler_recall_uses_sqlite_chat2_and_returns_recent_events(tmp_path):
    handler = EpisodicMemoryHandler(_config(tmp_path))
    session = handler.memory.create_session(
        account_name="junwin",
        agent_name="peace",
        friendly_name="episodic integration",
        context_name="lucyproject",
    )
    handler.memory.append_event(
        session.session_id,
        EpisodicEvent(role="user", actor="user", kind="user_message", content="first memory"),
    )
    handler.memory.append_event(
        session.session_id,
        EpisodicEvent(role="assistant", actor="peace", kind="assistant_message", content="second memory"),
    )

    result = handler.execute(
        _base_args(action="recall", session_id=session.session_id, max_events=1),
        account_name="junwin",
    )

    assert result["ok"] is True
    assert result["tool"] == "episodic_memory"
    assert result["session"]["friendly_name"] == "episodic integration"
    assert result["session"]["context_name"] == "lucyproject"
    assert result["event_count"] == 1
    assert result["events"][0]["content"] == "second memory"
    assert result["dropped_event_count"] == 1


def test_handler_list_sessions_can_search_event_text(tmp_path):
    handler = EpisodicMemoryHandler(_config(tmp_path))
    session = handler.memory.create_session(
        account_name="junwin",
        agent_name="peace",
        friendly_name="needle session",
    )
    handler.memory.append_event(
        session.session_id,
        EpisodicEvent(role="user", actor="user", kind="user_message", content="the special episodic needle"),
    )

    result = handler.execute(
        _base_args(action="list_sessions", query="episodic needle", agent_name="peace"),
        account_name="junwin",
    )

    assert result["ok"] is True
    assert result["count"] == 1
    assert result["sessions"][0]["session_id"] == session.session_id


def test_handler_append_event_round_trips_through_coala_layer(tmp_path):
    handler = EpisodicMemoryHandler(_config(tmp_path))
    session = handler.memory.create_session(account_name="junwin", agent_name="peace")

    appended = handler.execute(
        _base_args(
            action="append_event",
            session_id=session.session_id,
            role="user",
            kind="user_message",
            content="remember this",
        ),
        account_name="junwin",
    )
    fetched = handler.execute(
        _base_args(action="get_session", session_id=session.session_id, include_events=True),
        account_name="junwin",
    )

    assert appended["ok"] is True
    assert appended["event"]["content"] == "remember this"
    assert fetched["ok"] is True
    assert fetched["session"]["events"][0]["content"] == "remember this"
