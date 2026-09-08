"""Integration tests for PromptBuilder history through CoALA episodic memory."""

from unittest.mock import Mock

import pytest

from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent
from src.chat2.prompt_slice import get_last_n_events
from src.chat2.store_primitives import InMemoryStore
from src.coala_memory.episodic import Chat2EpisodicMemory
from src.prompt_builders.prompt_builder import PromptBuilder


@pytest.fixture
def chat2_store() -> Chat2Store:
    return Chat2Store(InMemoryStore())


@pytest.fixture
def seeded_session(chat2_store: Chat2Store) -> str:
    meta = chat2_store.create_session(
        user_id="test_user",
        account_name="test_acct",
        agent_name="lucy",
    )
    events = [
        ChatEvent(role="user", actor="test_user", kind="user_message", payload="Hello"),
        ChatEvent(role="assistant", actor="lucy", kind="assistant_message", payload="Hi there"),
        ChatEvent(role="user", actor="test_user", kind="user_message", payload="What's the weather?"),
        ChatEvent(role="assistant", actor="lucy", kind="assistant_tool_call", payload='{"tool":"get_weather"}'),
        ChatEvent(role="assistant", actor="lucy", kind="tool_result", payload='{"temp":22}'),
        ChatEvent(role="assistant", actor="lucy", kind="assistant_message", payload="It's 22C"),
    ]
    chat2_store.add_events(meta.session_id, events)
    return meta.session_id


@pytest.fixture
def session_with_context(chat2_store: Chat2Store) -> str:
    return chat2_store.create_session(
        user_id="test_user",
        account_name="test_acct",
        agent_name="lucy",
        context_name="lucyproject",
    ).session_id


@pytest.fixture
def session_with_friendly_name(chat2_store: Chat2Store) -> str:
    return chat2_store.create_session(
        user_id="test_user",
        account_name="test_acct",
        agent_name="lucy",
        friendly_name="my-friendly-session",
    ).session_id


def test_get_last_n_events_returns_only_user_assistant(seeded_session, chat2_store):
    result = get_last_n_events(list(chat2_store.stream_events(seeded_session)), 10)
    assert [event.payload for event in result] == [
        "Hello",
        "Hi there",
        "What's the weather?",
        "It's 22C",
    ]


def test_get_last_n_events_respects_limit(seeded_session, chat2_store):
    result = get_last_n_events(list(chat2_store.stream_events(seeded_session)), 2)
    assert [event.payload for event in result] == ["What's the weather?", "It's 22C"]


def test_get_last_n_events_zero_returns_empty(seeded_session, chat2_store):
    events = list(chat2_store.stream_events(seeded_session))
    assert get_last_n_events(events, 0) == []
    assert get_last_n_events(events, -1) == []


def test_get_last_n_events_fewer_than_n(seeded_session, chat2_store):
    result = get_last_n_events(list(chat2_store.stream_events(seeded_session)), 100)
    assert len(result) == 4


def _make_prompt_builder(chat2_store=None, max_prompt_conversations=10):
    agent_manager = Mock()
    agent = Mock()
    agent.max_prompt_conversations = max_prompt_conversations
    agent.system_prompt = None
    agent.persona = None
    agent.style_prompt = None
    agent.allowed_tools = None
    agent.use_embeddings = False
    agent.max_prompt_documents = 0
    agent_manager.get_agent.return_value = agent

    config = Mock()
    config.get.side_effect = lambda key, default=None: default

    return PromptBuilder(
        agent_manager=agent_manager,
        config=config,
        storage=Mock(),
        episodic_memory=(Chat2EpisodicMemory(chat2_store) if chat2_store else None),
    )


def _find_session_info_message(messages):
    return next(
        (
            msg
            for msg in messages
            if msg["role"] == "system" and msg["content"].startswith("Session:")
        ),
        None,
    )


def _history(messages, current):
    return [
        m["content"]
        for m in messages
        if m["role"] in ("user", "assistant") and m["content"] != current
    ]


def test_build_prompt_includes_history_from_episodic_memory(seeded_session, chat2_store):
    pb = _make_prompt_builder(chat2_store)
    prompt = pb.build_prompt(
        content_text="What was my last question?",
        conversation_id=seeded_session,
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )

    user_msgs = [m for m in prompt if m["role"] == "user"]
    assistant_msgs = [m for m in prompt if m["role"] == "assistant"]
    assert user_msgs[-1]["content"] == "What was my last question?"
    assert any(m["content"] == "Hello" for m in user_msgs)
    assert any(m["content"] == "What's the weather?" for m in user_msgs)
    assert any(m["content"] == "Hi there" for m in assistant_msgs)
    assert any(m["content"] == "It's 22C" for m in assistant_msgs)


def test_prompt_builder_respects_max_conversations(seeded_session, chat2_store):
    pb = _make_prompt_builder(chat2_store, max_prompt_conversations=1)
    prompt = pb.build_prompt(
        content_text="current",
        conversation_id=seeded_session,
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )
    assert _history(prompt, "current") == ["It's 22C"]


def test_prompt_builder_zero_max_conversations(seeded_session, chat2_store):
    pb = _make_prompt_builder(chat2_store, max_prompt_conversations=0)
    prompt = pb.build_prompt(
        content_text="current",
        conversation_id=seeded_session,
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )
    assert _history(prompt, "current") == []


def test_tool_only_session_produces_no_prompt_history(chat2_store):
    meta = chat2_store.create_session(
        user_id="test_user",
        account_name="test_acct",
        agent_name="lucy",
    )
    chat2_store.add_event(
        meta.session_id,
        ChatEvent(role="assistant", actor="lucy", kind="tool_result", payload="{}"),
    )
    prompt = _make_prompt_builder(chat2_store).build_prompt(
        content_text="current",
        conversation_id=meta.session_id,
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )
    assert _history(prompt, "current") == []


def test_missing_session_produces_no_prompt_history(chat2_store):
    prompt = _make_prompt_builder(chat2_store).build_prompt(
        content_text="current",
        conversation_id="missing",
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )
    assert _history(prompt, "current") == []


def test_session_info_includes_context_name(session_with_context, chat2_store):
    pb = _make_prompt_builder(chat2_store)
    prompt = pb.build_prompt(
        content_text="Hello",
        conversation_id=session_with_context,
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )
    info = _find_session_info_message(prompt)
    assert info is not None
    assert "agent=lucy" in info["content"]
    assert "context=lucyproject" in info["content"]
    assert "last activity" in info["content"]
    assert "ago (timestamp:" in info["content"]
    assert info["content"].rstrip().endswith("Z)")


def test_session_info_context_falls_back_to_friendly_name(
    session_with_friendly_name,
    chat2_store,
):
    pb = _make_prompt_builder(chat2_store)
    prompt = pb.build_prompt(
        content_text="Hello",
        conversation_id=session_with_friendly_name,
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )
    info = _find_session_info_message(prompt)
    assert info is not None
    assert "context=my-friendly-session" in info["content"]


def test_session_info_omits_context_when_metadata_has_none(seeded_session, chat2_store):
    prompt = _make_prompt_builder(chat2_store).build_prompt(
        content_text="Hello",
        conversation_id=seeded_session,
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )
    info = _find_session_info_message(prompt)
    assert info is not None
    assert ", context=" not in info["content"]


def test_missing_episode_does_not_add_session_info():
    pb = _make_prompt_builder(None)
    prompt = pb.build_prompt(
        content_text="Hello",
        conversation_id="some-session",
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )
    assert _find_session_info_message(prompt) is None


def test_nonexistent_session_does_not_add_session_info(chat2_store):
    prompt = _make_prompt_builder(chat2_store).build_prompt(
        content_text="Hello",
        conversation_id="nonexistent-session",
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )
    assert _find_session_info_message(prompt) is None


@pytest.mark.parametrize("conversation_id", ["none", "new"])
def test_special_conversation_ids_do_not_add_session_info(conversation_id, chat2_store):
    prompt = _make_prompt_builder(chat2_store).build_prompt(
        content_text="Hello",
        conversation_id=conversation_id,
        agent_name="lucy",
        account_name="test_acct",
        context_type="none",
    )
    assert _find_session_info_message(prompt) is None
