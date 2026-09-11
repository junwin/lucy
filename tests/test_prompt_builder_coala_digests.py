from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from src.coala_memory.episodic import (
    EpisodicDigest,
    EpisodicEvent,
    EpisodicMemory,
    EpisodicMemoryRequest,
    EpisodicMemoryResult,
)
from src.prompt_builders.coala_prompt_builder import CoALAPromptBuilder


class _Config:
    def __init__(self, values=None):
        self._values = values or {}

    def get(self, key, default=None):
        return self._values.get(key, default)


class _AgentManager:
    def get_agent(self, name):
        return SimpleNamespace(
            system_prompt="You are Peace.",
            persona="",
            style_prompt="",
            use_embeddings=False,
            default_context=None,
            max_prompt_documents=0,
            max_prompt_conversations=2,
            allowed_tools=[],
            prompt_budget_max_tokens=None,
            context_text_soft_max_tokens=None,
        )


class _Episodic(EpisodicMemory):
    def __init__(self):
        self.requests = []
        self.saved = []

    def recall(self, request: EpisodicMemoryRequest) -> EpisodicMemoryResult:
        self.requests.append(request)
        return EpisodicMemoryResult(
            session_id=request.conversation_id,
            session_agent_name="peace" if request.conversation_id else "",
            session_updated_at=(datetime(2026, 9, 8, 8, 0, 0) if request.conversation_id else None),
            events=(
                [
                    EpisodicEvent(role="user", kind="user_message", content="old one"),
                    EpisodicEvent(role="assistant", kind="assistant_message", content="old two"),
                ]
                if request.conversation_id
                else []
            ),
            digests=[
                EpisodicDigest(
                    session_id="archive-123",
                    snippet="Archived discussion about CoALA memory.",
                    score=0.61,
                )
            ],
        )

    def save_overflow_digest(self, *, account_name, conversation_id, snippet):
        self.saved.append((account_name, conversation_id, snippet))
        return f"stored: {snippet}"


def _builder(memory, config=None):
    return CoALAPromptBuilder(
        agent_manager=_AgentManager(),
        config=config or _Config(),
        storage=SimpleNamespace(),
        episodic_memory=memory,
        procedural_memory=None,
    )


def test_prompt_builder_uses_single_episodic_recall_for_history_and_digests():
    memory = _Episodic()
    builder = _builder(memory)

    messages = builder.build_prompt(
        content_text="What did we discuss about CoALA?",
        conversation_id="session-1",
        agent_name="peace",
        account_name="junwin",
        context_type="none",
    )

    assert len(memory.requests) == 1
    request = memory.requests[0]
    assert request.conversation_id == "session-1"
    assert request.query == "What did we discuss about CoALA?"
    assert request.include_session_metadata is True
    assert request.include_recent_history is True
    assert request.include_archived_digests is True
    assert request.digest_top_k == 3
    assert request.digest_max_chars == 3000

    prompt_text = "\n".join(str(message.get("content", "")) for message in messages)
    assert "Archived discussion about CoALA memory." in prompt_text
    assert "archive-123" in prompt_text
    assert "old one" in prompt_text
    assert "old two" in prompt_text


def test_prompt_builder_recalls_archived_digests_without_active_session():
    memory = _Episodic()
    builder = _builder(memory)

    messages = builder.build_prompt(
        content_text="What happened before?",
        conversation_id="new",
        agent_name="peace",
        account_name="junwin",
        context_type="none",
    )

    assert len(memory.requests) == 1
    request = memory.requests[0]
    assert request.conversation_id == ""
    assert request.include_session_metadata is False
    assert request.include_recent_history is False
    assert request.include_archived_digests is True

    prompt_text = "\n".join(str(message.get("content", "")) for message in messages)
    assert "Archived discussion about CoALA memory." in prompt_text


def test_prompt_builder_persists_overflow_through_episodic_memory():
    memory = _Episodic()

    builder = _builder(memory, config=_Config({"prompt_budget_max_tokens": 1}))

    messages = builder.build_prompt(
        content_text="q",
        conversation_id="session-1",
        agent_name="peace",
        account_name="junwin",
        context_type="none",
    )

    assert memory.saved
    account_name, conversation_id, snippet = memory.saved[0]
    assert account_name == "junwin"
    assert conversation_id == "session-1"
    assert "earlier messages were summarized" in snippet
    assert any(
        isinstance(message.get("content"), str)
        and message["content"].startswith("Earlier in this session:\nstored:")
        for message in messages
    )
