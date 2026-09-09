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
