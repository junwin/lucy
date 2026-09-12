from uuid import uuid4

from src.coala_memory.episodic import (
    Chat2EpisodicMemory,
    EpisodicEvent,
    EpisodicMemoryRequest,
    EpisodicSessionQuery,
)


def test_chat2_episodic_memory_sqlite_round_trip(tmp_path):
    memory = Chat2EpisodicMemory.from_sqlite(tmp_path / "chat2.sqlite")

    session = memory.create_session(
        account_name="junwin",
        agent_name="peace",
        friendly_name="memory test",
        context_name="lucyproject",
        tags=["memory"],
        metadata={"purpose": "test"},
    )

    stored = memory.append_event(
        session.session_id,
        EpisodicEvent(
            role="user",
            actor="junwin",
            kind="user_message",
            content="We decided to use Chat2 as episodic memory.",
        ),
    )
    memory.append_event(
        session.session_id,
        EpisodicEvent(
            role="assistant",
            actor="peace",
            kind="assistant_message",
            content="Agreed.",
        ),
    )

    assert stored.event_id

    result = memory.recall(
        EpisodicMemoryRequest(
            account_name="junwin",
            agent_name="peace",
            conversation_id=session.session_id,
            max_events=1,
            include_archived_digests=False,
        )
    )

    assert result.session_id == session.session_id
    assert result.session_account_name == "junwin"
    assert result.session_agent_name == "peace"
    assert result.session_context_name == "lucyproject"
    assert result.session_tags == ["memory"]
    assert result.events[0].content == "Agreed."
    assert result.events[0].actor == "peace"
    assert result.dropped_event_count == 1


def test_chat2_episodic_memory_lists_and_searches_sessions(tmp_path):
    memory = Chat2EpisodicMemory.from_sqlite(tmp_path / "chat2.sqlite")

    session = memory.create_session(account_name="junwin", agent_name="peace")
    memory.append_event(
        session.session_id,
        EpisodicEvent(
            role="user",
            kind="user_message",
            content="sqlite episodic memory",
        ),
    )

    matches = memory.list_sessions(
        EpisodicSessionQuery(
            account_name="junwin",
            agent_name="peace",
            query="episodic",
            limit=20,
        )
    )

    assert len(matches) == 1
    assert matches[0].session_id == session.session_id
    assert matches[0].events[0].content == "sqlite episodic memory"


def test_chat2_episodic_memory_overflow_digest_is_optional(tmp_path):
    memory = Chat2EpisodicMemory.from_sqlite(
        tmp_path / "chat2.sqlite",
        digests_root=tmp_path / "digests",
    )

    first = memory.save_overflow_digest(
        account_name="junwin",
        conversation_id="session-1",
        snippet="first",
    )
    second = memory.save_overflow_digest(
        account_name="junwin",
        conversation_id="session-1",
        snippet="second",
    )

    assert first == "first"
    assert second == "first\n\nsecond"


# ----------------------------------------------------------------------
# New primitives required so call sites stop reaching into Chat2Store:
#   session_exists / add_events / link_event
# ----------------------------------------------------------------------


def test_session_exists_reflects_session_lifecycle(tmp_path):
    memory = Chat2EpisodicMemory.from_sqlite(tmp_path / "chat2.sqlite")

    session = memory.create_session(account_name="junwin", agent_name="peace")
    assert memory.session_exists(session.session_id) is True

    assert memory.session_exists(str(uuid4())) is False

    memory.delete_session(session.session_id)
    assert memory.session_exists(session.session_id) is False


def test_add_events_returns_stored_events_and_persists_them(tmp_path):
    memory = Chat2EpisodicMemory.from_sqlite(tmp_path / "chat2.sqlite")

    session = memory.create_session(account_name="junwin", agent_name="peace")

    stored = memory.add_events(
        session.session_id,
        [
            EpisodicEvent(
                role="user",
                actor="junwin",
                kind="user_message",
                content="first",
            ),
            EpisodicEvent(
                role="assistant",
                actor="peace",
                kind="assistant_message",
                content="second",
            ),
        ],
    )

    assert isinstance(stored, list)
    assert len(stored) == 2
    assert all(event.event_id for event in stored)

    reloaded = memory.get_session(session.session_id, include_events=True)
    assert reloaded is not None
    assert [event.content for event in reloaded.events] == ["first", "second"]


def test_link_event_with_falsy_correlation_is_noop(tmp_path):
    memory = Chat2EpisodicMemory.from_sqlite(tmp_path / "chat2.sqlite")

    session = memory.create_session(account_name="junwin", agent_name="peace")
    stored = memory.append_event(
        session.session_id,
        EpisodicEvent(
            role="user",
            actor="junwin",
            kind="user_message",
            content="no correlation",
        ),
    )

    assert memory.link_event(None, session.session_id, stored.event_id) is None
    assert memory.link_event("", session.session_id, stored.event_id) is None


def test_link_event_links_event_to_correlation(tmp_path):
    memory = Chat2EpisodicMemory.from_sqlite(tmp_path / "chat2.sqlite")

    session = memory.create_session(account_name="junwin", agent_name="peace")
    stored = memory.append_event(
        session.session_id,
        EpisodicEvent(
            role="user",
            actor="junwin",
            kind="user_message",
            content="linked event",
        ),
    )

    correlation_id = str(uuid4())
    memory.link_event(correlation_id, session.session_id, stored.event_id)

    linked = memory.chat2_store.get_events_by_correlation(correlation_id)
    assert [event.event_id for event in linked] == [stored.event_id]
