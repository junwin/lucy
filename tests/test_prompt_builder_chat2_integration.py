"""
End-to-end integration test: PromptBuilder reads history from chat2.

Tests the full chain:
  - Chat2Store (with InMemoryStore)
  - get_last_n_events() slicing
  - PromptBuilder._get_chat_history_messages() branching
  - Session-info system message injection

These tests use InMemoryStore (no filesystem) so they're fast and isolated.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock

from src.chat2.store_primitives import InMemoryStore
from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent
from src.chat2.prompt_slice import get_last_n_events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def chat2_store() -> Chat2Store:
    return Chat2Store(InMemoryStore())


@pytest.fixture
def seeded_session(chat2_store: Chat2Store) -> str:
    """Create a session with 6 events: 4 user/assistant + 2 tool/system."""
    meta = chat2_store.create_session(
        user_id="test_user",
        account_name="test_acct",
        agent_name="lucy",
    )
    session_id = meta.session_id

    events = [
        ChatEvent(role="user", actor="test_user", kind="user_message", payload="Hello"),
        ChatEvent(role="assistant", actor="lucy", kind="assistant_message", payload="Hi there"),
        ChatEvent(role="user", actor="test_user", kind="user_message", payload="What's the weather?"),
        ChatEvent(role="assistant", actor="lucy", kind="assistant_tool_call", payload='{"tool":"get_weather"}'),
        ChatEvent(role="assistant", actor="lucy", kind="tool_result", payload='{"temp":22}'),
        ChatEvent(role="assistant", actor="lucy", kind="assistant_message", payload="It's 22C"),
    ]
    chat2_store.add_events(session_id, events)
    return session_id


@pytest.fixture
def session_with_context(chat2_store: Chat2Store) -> str:
    """Create a session with context_name set."""
    meta = chat2_store.create_session(
        user_id="test_user",
        account_name="test_acct",
        agent_name="lucy",
        context_name="lucyproject",
    )
    return meta.session_id


@pytest.fixture
def session_with_friendly_name(chat2_store: Chat2Store) -> str:
    """Create a session with friendly_name but no context_name."""
    meta = chat2_store.create_session(
        user_id="test_user",
        account_name="test_acct",
        agent_name="lucy",
        friendly_name="my-friendly-session",
    )
    return meta.session_id


# ---------------------------------------------------------------------------
# Tests for get_last_n_events (unit-level, but critical for integration)
# ---------------------------------------------------------------------------


def test_get_last_n_events_returns_only_user_assistant(seeded_session, chat2_store):
    """Only user_message and assistant_message kinds are returned."""
    events = list(chat2_store.stream_events(seeded_session))
    result = get_last_n_events(events, 10)

    # 4 matching: Hello, Hi there, What's the weather?, It's 22C
    assert len(result) == 4
    for e in result:
        assert e.kind in ("user_message", "assistant_message")


def test_get_last_n_events_respects_limit(seeded_session, chat2_store):
    events = list(chat2_store.stream_events(seeded_session))
    result = get_last_n_events(events, 2)

    assert len(result) == 2
    assert result[0].payload == "What's the weather?"
    assert result[1].payload == "It's 22C"


def test_get_last_n_events_zero_returns_empty(seeded_session, chat2_store):
    events = list(chat2_store.stream_events(seeded_session))
    assert get_last_n_events(events, 0) == []
    assert get_last_n_events(events, -1) == []


def test_get_last_n_events_fewer_than_n(seeded_session, chat2_store):
    events = list(chat2_store.stream_events(seeded_session))
    result = get_last_n_events(events, 100)
    assert len(result) == 4  # only 4 matching events exist


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prompt_builder(chat2_store=None):
    """Build a PromptBuilder with minimal dependencies for testing."""
    from src.prompt_builders.prompt_builder import PromptBuilder

    agent_manager = Mock()
    # Return a mock agent with max_prompt_conversations set so build_prompt
    # actually requests history.
    mock_agent = Mock()
    mock_agent.max_prompt_conversations = 10
    mock_agent.system_prompt = None
    mock_agent.persona = None
    mock_agent.style_prompt = None
    agent_manager.get_agent.return_value = mock_agent

    config = Mock()
    config.get.return_value = None

    storage = Mock()

    return PromptBuilder(
        agent_manager=agent_manager,
        config=config,
        storage=storage,
        chat2_store=chat2_store,
    )


def _find_session_info_message(messages):
    """Find the session-info system message, if present."""
    for msg in messages:
        if msg["role"] == "system" and msg["content"].startswith("Session:"):
            return msg
    return None


# ---------------------------------------------------------------------------
# Tests for PromptBuilder chat2 integration (history)
# ---------------------------------------------------------------------------


def test_prompt_builder_returns_history_from_chat2(seeded_session, chat2_store):
    """When chat2 has events, PromptBuilder returns them as role/content dicts."""
    pb = _make_prompt_builder(chat2_store=chat2_store)

    messages = pb._get_chat_history_messages(
        conversation_id=seeded_session,
        account_name="test_acct",
        agent_name="lucy",
        max_conversations=10,
    )

    # 4 matching: Hello, Hi there, What's the weather?, It's 22C
    assert len(messages) == 4
    assert messages[0] == {"role": "user", "content": "Hello"}
    assert messages[1] == {"role": "assistant", "content": "Hi there"}
    assert messages[2] == {"role": "user", "content": "What's the weather?"}
    assert messages[3] == {"role": "assistant", "content": "It's 22C"}


def test_prompt_builder_respects_max_conversations(seeded_session, chat2_store):
    """max_conversations limits the number of returned events."""
    pb = _make_prompt_builder(chat2_store=chat2_store)

    messages = pb._get_chat_history_messages(
        conversation_id=seeded_session,
        account_name="test_acct",
        agent_name="lucy",
        max_conversations=1,
    )

    assert len(messages) == 1
    assert messages[0]["content"] == "It's 22C"


def test_prompt_builder_zero_max_conversations(seeded_session, chat2_store):
    """max_conversations=0 returns empty list regardless of chat2 data."""
    pb = _make_prompt_builder(chat2_store=chat2_store)

    messages = pb._get_chat_history_messages(
        conversation_id=seeded_session,
        account_name="test_acct",
        agent_name="lucy",
        max_conversations=0,
    )

    assert messages == []


def test_prompt_builder_returns_empty_when_no_chat2_store():
    """When chat2_store is None, returns empty history (no v1 fallback)."""
    from src.prompt_builders.prompt_builder import PromptBuilder

    agent_manager = Mock()
    agent_manager.get_agent.return_value = None

    config = Mock()
    config.get.return_value = None

    storage = Mock()

    pb = PromptBuilder(
        agent_manager=agent_manager,
        config=config,
        storage=storage,
        chat2_store=None,
    )

    messages = pb._get_chat_history_messages(
        conversation_id="some-session",
        account_name="test_acct",
        agent_name="lucy",
        max_conversations=10,
    )

    assert messages == []


def test_prompt_builder_returns_empty_when_session_not_in_chat2(chat2_store):
    """When session doesn't exist in chat2, returns empty history (no v1 fallback)."""
    from src.prompt_builders.prompt_builder import PromptBuilder

    agent_manager = Mock()
    agent_manager.get_agent.return_value = None

    config = Mock()
    config.get.return_value = None

    storage = Mock()

    pb = PromptBuilder(
        agent_manager=agent_manager,
        config=config,
        storage=storage,
        chat2_store=chat2_store,
    )

    messages = pb._get_chat_history_messages(
        conversation_id="nonexistent-session",
        account_name="test_acct",
        agent_name="lucy",
        max_conversations=10,
    )

    assert messages == []


def test_prompt_builder_empty_when_chat2_session_has_no_matching_events(chat2_store):
    """Session exists in chat2 but has no user/assistant events -> return empty."""
    meta = chat2_store.create_session(
        user_id="test_user",
        account_name="test_acct",
        agent_name="lucy",
    )
    session_id = meta.session_id

    # Only tool events, no user/assistant
    chat2_store.add_event(
        session_id,
        ChatEvent(role="assistant", actor="lucy", kind="tool_result", payload="{}"),
    )

    pb = _make_prompt_builder(chat2_store=chat2_store)

    messages = pb._get_chat_history_messages(
        conversation_id=session_id,
        account_name="test_acct",
        agent_name="lucy",
        max_conversations=10,
    )

    assert messages == []


def test_build_prompt_includes_history_from_chat2(seeded_session, chat2_store):
    """Full build_prompt() call includes chat2 history in the output."""
    pb = _make_prompt_builder(chat2_store=chat2_store)

    prompt = pb.build_prompt(
        content_text="What was my last question?",
        conversation_id=seeded_session,
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )

    # Find history messages (between system and current user)
    user_msgs = [m for m in prompt if m["role"] == "user"]
    assistant_msgs = [m for m in prompt if m["role"] == "assistant"]

    # The current query is the last user message
    assert user_msgs[-1]["content"] == "What was my last question?"

    # History should include the earlier user messages
    assert any("Hello" in m["content"] for m in user_msgs)
    assert any("What's the weather?" in m["content"] for m in user_msgs)

    # History should include assistant responses
    assert any("Hi there" in m["content"] for m in assistant_msgs)
    assert any("It's 22C" in m["content"] for m in assistant_msgs)


# ---------------------------------------------------------------------------
# Tests for session-info system message
# ---------------------------------------------------------------------------


def test_session_info_present_with_valid_session(session_with_context, chat2_store):
    """A valid session_id produces a session-info system message."""
    pb = _make_prompt_builder(chat2_store=chat2_store)

    prompt = pb.build_prompt(
        content_text="Hello",
        conversation_id=session_with_context,
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )

    info = _find_session_info_message(prompt)
    assert info is not None, "Expected a system message starting with 'Session:'"
    assert "agent=lucy" in info["content"]


def test_session_info_includes_context_name(session_with_context, chat2_store):
    """context_name from session meta appears in the info message."""
    pb = _make_prompt_builder(chat2_store=chat2_store)

    prompt = pb.build_prompt(
        content_text="Hello",
        conversation_id=session_with_context,
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )

    info = _find_session_info_message(prompt)
    assert "context=lucyproject" in info["content"]


def test_session_info_context_falls_back_to_friendly_name(
    session_with_friendly_name, chat2_store
):
    """When context_name is None, friendly_name is used in the info."""
    pb = _make_prompt_builder(chat2_store=chat2_store)

    prompt = pb.build_prompt(
        content_text="Hello",
        conversation_id=session_with_friendly_name,
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )

    info = _find_session_info_message(prompt)
    assert "context=my-friendly-session" in info["content"]


def test_session_info_no_context_when_both_none(seeded_session, chat2_store):
    """When both context_name and friendly_name are None, no 'context=' part."""
    pb = _make_prompt_builder(chat2_store=chat2_store)

    prompt = pb.build_prompt(
        content_text="Hello",
        conversation_id=seeded_session,
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )

    info = _find_session_info_message(prompt)
    assert "agent=lucy" in info["content"]
    assert ", context=" not in info["content"]


def test_session_info_includes_elapsed_time(session_with_context, chat2_store):
    """The info message includes an elapsed time string and timestamp."""
    pb = _make_prompt_builder(chat2_store=chat2_store)

    prompt = pb.build_prompt(
        content_text="Hello",
        conversation_id=session_with_context,
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )

    info = _find_session_info_message(prompt)
    assert "last activity" in info["content"]
    # Should end with "... ago (timestamp: ...Z)"
    assert "ago (timestamp:" in info["content"]
    assert info["content"].rstrip().endswith("Z)")


def test_session_info_missing_session_no_crash(chat2_store):
    """A nonexistent session_id does not crash build_prompt."""
    pb = _make_prompt_builder(chat2_store=chat2_store)

    prompt = pb.build_prompt(
        content_text="Hello",
        conversation_id="nonexistent-session",
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )

    info = _find_session_info_message(prompt)
    assert info is None


def test_session_info_no_chat2_store():
    """When chat2_store is None, no session-info message appears."""
    pb = _make_prompt_builder(chat2_store=None)

    prompt = pb.build_prompt(
        content_text="Hello",
        conversation_id="some-session",
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )

    info = _find_session_info_message(prompt)
    assert info is None


def test_session_info_conversation_id_none(chat2_store):
    """When conversation_id is 'none', no session-info message."""
    pb = _make_prompt_builder(chat2_store=chat2_store)

    prompt = pb.build_prompt(
        content_text="Hello",
        conversation_id="none",
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )

    info = _find_session_info_message(prompt)
    assert info is None


def test_session_info_conversation_id_new(chat2_store):
    """When conversation_id is 'new', no session-info message."""
    pb = _make_prompt_builder(chat2_store=chat2_store)

    prompt = pb.build_prompt(
        content_text="Hello",
        conversation_id="new",
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )

    info = _find_session_info_message(prompt)
    assert info is None


def test_session_info_conversation_id_empty_string(chat2_store):
    """When conversation_id is '', no session-info message."""
    pb = _make_prompt_builder(chat2_store=chat2_store)

    prompt = pb.build_prompt(
        content_text="Hello",
        conversation_id="",
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )

    info = _find_session_info_message(prompt)
    assert info is None


def test_session_info_agent_name_from_meta(seeded_session, chat2_store):
    """The info message uses the agent_name from session meta, not the parameter."""
    pb = _make_prompt_builder(chat2_store=chat2_store)

    prompt = pb.build_prompt(
        content_text="Hello",
        conversation_id=seeded_session,
        agent_name="different-agent",
        account_name="test_acct",
        context_type="none",
    )

    info = _find_session_info_message(prompt)
    # The session was created with agent_name="lucy", so info should say "lucy"
    assert "agent=lucy" in info["content"]
