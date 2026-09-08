from types import SimpleNamespace

from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent
from src.chat2.store_primitives import InMemoryStore
from src.coala_memory.episodic import (
    Chat2EpisodicMemory,
    EpisodicEvent,
    EpisodicMemory,
    EpisodicMemoryRequest,
    EpisodicMemoryResult,
)
from src.prompt_builders.prompt_builder import PromptBuilder


class _Config:
    def get(self, key, default=None):
        return default


class _Storage:
    def get_or_create_context(self, account_name, context_name):
        return SimpleNamespace(
            id=context_name,
            account_name=account_name,
            tag=None,
            resolved_text="",
            search_namespaces=[],
            extra={},
        )


class _AgentManager:
    def __init__(self, agent):
        self.agent = agent

    def get_agent(self, name):
        return self.agent


class _FakeEpisodicMemory(EpisodicMemory):
    def __init__(self):
        self.requests = []

    def recall(self, request: EpisodicMemoryRequest) -> EpisodicMemoryResult:
        self.requests.append(request)
        return EpisodicMemoryResult(
            session_id=request.conversation_id,
            session_agent_name="peace",
            session_context_name="lucyproject",
            session_friendly_name="lucy_design",
            events=[
                EpisodicEvent(
                    role="user",
                    kind="user_message",
                    content="earlier user message",
                ),
                EpisodicEvent(
                    role="assistant",
                    kind="assistant_message",
                    content="earlier assistant reply",
                ),
            ],
        )

    def save_overflow_digest(self, *, account_name, conversation_id, snippet):
        return snippet


def _agent(max_prompt_conversations=2):
    return SimpleNamespace(
        system_prompt="You are Peace.",
        persona="",
        style_prompt="",
        use_embeddings=True,
        default_context=None,
        max_prompt_documents=3,
        max_prompt_conversations=max_prompt_conversations,
        allowed_tools=[],
        prompt_budget_max_tokens=None,
        context_text_soft_max_tokens=None,
    )


def test_prompt_builder_uses_one_episodic_recall_for_session_info_and_history():
    episodic = _FakeEpisodicMemory()
    builder = PromptBuilder(
        agent_manager=_AgentManager(_agent()),
        config=_Config(),
        storage=_Storage(),
        episodic_memory=episodic,
    )

    messages = builder.build_prompt(
        content_text="current question",
        conversation_id="session-123",
        agent_name="peace",
        account_name="junwin",
        context_type="none",
    )

    assert len(episodic.requests) == 1
    request = episodic.requests[0]
    assert request.conversation_id == "session-123"
    assert request.account_name == "junwin"
    assert request.agent_name == "peace"
    assert request.max_events == 2
    assert set(request.event_kinds or []) == {"user_message", "assistant_message"}
    assert request.include_session_metadata is True
    assert request.include_recent_history is True
    assert request.include_archived_digests is False

    text_messages = [m["content"] for m in messages if isinstance(m.get("content"), str)]
    assert any("Session: agent=peace, context=lucyproject" in text for text in text_messages)
    assert any(text == "earlier user message" for text in text_messages)
    assert any(text == "earlier assistant reply" for text in text_messages)
    assert text_messages[-1] == "current question"


def test_chat2_episodic_memory_filters_kinds_before_max_events():
    chat2 = Chat2Store(InMemoryStore())
    meta = chat2.create_session(
        user_id="junwin",
        account_name="junwin",
        agent_name="peace",
        friendly_name="filter-test",
        context_name="lucyproject",
    )
    chat2.add_event(
        meta.session_id,
        ChatEvent(
            role="user",
            actor="junwin",
            kind="user_message",
            payload="keep user",
        ),
    )
    chat2.add_event(
        meta.session_id,
        ChatEvent(
            role="tool",
            actor="semantic_memory",
            kind="tool_result",
            payload="drop tool",
        ),
    )
    chat2.add_event(
        meta.session_id,
        ChatEvent(
            role="assistant",
            actor="peace",
            kind="assistant_message",
            payload="keep assistant",
        ),
    )

    memory = Chat2EpisodicMemory(chat2)
    result = memory.recall(
        EpisodicMemoryRequest(
            account_name="junwin",
            agent_name="peace",
            conversation_id=meta.session_id,
            max_events=2,
            event_kinds=["user_message", "assistant_message"],
            include_archived_digests=False,
        )
    )

    assert result.session_context_name == "lucyproject"
    assert [event.content for event in result.events] == ["keep user", "keep assistant"]
    assert result.dropped_event_count == 0
