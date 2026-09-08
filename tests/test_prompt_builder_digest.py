from pathlib import Path
from unittest.mock import Mock

from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent
from src.chat2.store_primitives import InMemoryStore
from src.coala_memory.episodic import Chat2EpisodicMemory
from src.prompt_builders.coala_prompt_builder import CoALAPromptBuilder


def _make_prompt_builder_with_storage(
    chat2_store: Chat2Store,
    storage,
    digests_root: Path,
    model_limit: int = 1000,
):
    agent_manager = Mock()
    mock_agent = Mock()
    mock_agent.max_prompt_conversations = 50
    mock_agent.system_prompt = None
    mock_agent.persona = None
    mock_agent.style_prompt = None
    mock_agent.allowed_tools = None
    mock_agent.use_embeddings = False
    mock_agent.max_prompt_documents = 0
    mock_agent.default_context = None
    mock_agent.context_text_soft_max_tokens = None
    mock_agent.prompt_budget_max_tokens = None
    agent_manager.get_agent.return_value = mock_agent

    config = Mock()

    def cfg_get(key, default=None):
        if key == "prompt_budget_max_tokens":
            return model_limit
        return default

    config.get.side_effect = cfg_get

    episodic_memory = Chat2EpisodicMemory(
        chat2_store,
        digests_root=digests_root,
    )
    return CoALAPromptBuilder(
        agent_manager=agent_manager,
        config=config,
        storage=storage,
        episodic_memory=episodic_memory,
        procedural_memory=None,
    )


def _digest_path(digests_root: Path, session_id: str, account: str) -> Path:
    return digests_root / account / f"{session_id}_overflow.md"


def test_digest_generation_and_persistence(tmp_path):
    store = Chat2Store(InMemoryStore())
    meta = store.create_session(user_id="u", account_name="acct", agent_name="a")
    sid = meta.session_id

    for i in range(6):
        store.add_event(
            sid,
            ChatEvent(
                role="user",
                actor="u",
                kind="user_message",
                payload=f"old-msg-{i} " + ("x" * 50),
            ),
        )

    digests_root = tmp_path / "digests"
    pb = _make_prompt_builder_with_storage(
        store,
        Mock(),
        digests_root,
        model_limit=200,
    )

    messages = pb.build_prompt(
        content_text="query",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
    )

    sys_msgs = [
        m
        for m in messages
        if m.get("role") == "system"
        and "Earlier in this session:" in m.get("content", "")
    ]
    assert len(sys_msgs) >= 1

    dpath = _digest_path(digests_root, sid, "acct")
    assert dpath.exists(), f"Expected digest file at {dpath}"
    content = dpath.read_text(encoding="utf-8")
    assert "old-msg-0" in content or "old-msg-1" in content


def test_digest_accumulates_over_multiple_turns(tmp_path):
    store = Chat2Store(InMemoryStore())
    meta = store.create_session(user_id="u", account_name="acct", agent_name="a")
    sid = meta.session_id

    for i in range(4):
        store.add_event(
            sid,
            ChatEvent(
                role="user",
                actor="u",
                kind="user_message",
                payload=f"old-first-{i} " + ("x" * 40),
            ),
        )

    digests_root = tmp_path / "digests"
    pb = _make_prompt_builder_with_storage(
        store,
        Mock(),
        digests_root,
        model_limit=250,
    )
    pb.build_prompt(
        content_text="q1",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
    )

    dpath = _digest_path(digests_root, sid, "acct")
    assert dpath.exists()
    first_digest = dpath.read_text(encoding="utf-8")
    assert "old-first-0" in first_digest

    for i in range(4, 8):
        store.add_event(
            sid,
            ChatEvent(
                role="user",
                actor="u",
                kind="user_message",
                payload=f"old-second-{i} " + ("y" * 40),
            ),
        )

    pb.build_prompt(
        content_text="q2",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
    )

    new_digest = dpath.read_text(encoding="utf-8")
    assert first_digest in new_digest
    assert "old-second-4" in new_digest


def test_digest_truncation_for_very_long_overflow(tmp_path):
    store = Chat2Store(InMemoryStore())
    meta = store.create_session(user_id="u", account_name="acct", agent_name="a")
    sid = meta.session_id

    for i in range(20):
        store.add_event(
            sid,
            ChatEvent(
                role="user",
                actor="u",
                kind="user_message",
                payload=f"long-{i} " + ("L" * 2000),
            ),
        )

    digests_root = tmp_path / "digests"
    pb = _make_prompt_builder_with_storage(
        store,
        Mock(),
        digests_root,
        model_limit=300,
    )

    messages = pb.build_prompt(
        content_text="query",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
    )

    sys_msgs = [
        m
        for m in messages
        if m.get("role") == "system"
        and "Earlier in this session:" in m.get("content", "")
    ]
    assert len(sys_msgs) >= 1
    digest_text = sys_msgs[0]["content"]
    assert len(digest_text) < 2000 or "..." in digest_text
