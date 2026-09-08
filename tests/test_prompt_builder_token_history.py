import logging
from unittest.mock import Mock

from src.chat2.store_primitives import InMemoryStore
from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent
from src.coala_memory.episodic import Chat2EpisodicMemory
from src.prompt_builders import prompt_builder as pb_module
from src.prompt_builders.prompt_builder import PromptBuilder


def _make_prompt_builder_with_config(chat2_store, model_limit, max_prompt_conversations=10):
    agent_manager = Mock()
    mock_agent = Mock()
    mock_agent.max_prompt_conversations = max_prompt_conversations
    mock_agent.system_prompt = None
    mock_agent.persona = None
    mock_agent.style_prompt = None
    mock_agent.allowed_tools = None
    mock_agent.use_embeddings = False
    mock_agent.max_prompt_documents = 0
    agent_manager.get_agent.return_value = mock_agent

    config = Mock()

    def cfg_get(key, default=None):
        if key == "prompt_budget_max_tokens":
            return model_limit
        return default

    config.get.side_effect = cfg_get
    storage = Mock()

    return PromptBuilder(
        agent_manager=agent_manager,
        config=config,
        storage=storage,
        episodic_memory=Chat2EpisodicMemory(chat2_store),
    )


def _system_token_estimate_for_fake_agent():
    return (34 + 55 + 90 + 20) // 4


def _history_only(messages, current_query):
    return [
        m["content"]
        for m in messages
        if m.get("role") in ("user", "assistant") and m.get("content") != current_query
    ]


def test_history_token_allocation_normal_case():
    sys_est = _system_token_estimate_for_fake_agent()
    msg_len = 25
    msg_tok = max(1, msg_len // 4)
    user_tok = max(1, len("query") // 4)
    model_limit = sys_est + msg_tok * 2 + user_tok + pb_module.PROMPT_BUDGET_SAFETY_MARGIN

    store = Chat2Store(InMemoryStore())
    meta = store.create_session(user_id="u", account_name="acct", agent_name="a")
    sid = meta.session_id
    for i in range(1, 6):
        content = f"msg{i}-" + ("x" * 20)
        store.add_event(sid, ChatEvent(role="user", actor="u", kind="user_message", payload=content))

    pb = _make_prompt_builder_with_config(store, model_limit=model_limit)
    prompt = pb.build_prompt(
        content_text="query",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
        context_type="none",
    )

    hist_contents = _history_only(prompt, "query")
    assert any("msg4-" in c for c in hist_contents)
    assert any("msg5-" in c for c in hist_contents)


def test_history_token_allocation_giant_message_included():
    store = Chat2Store(InMemoryStore())
    meta = store.create_session(user_id="u", account_name="acct", agent_name="a")
    sid = meta.session_id
    giant = "G" * 5000
    store.add_event(sid, ChatEvent(role="user", actor="u", kind="user_message", payload=giant))

    pb = _make_prompt_builder_with_config(store, model_limit=50)
    prompt = pb.build_prompt(
        content_text="query",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
        context_type="none",
    )

    hist_contents = _history_only(prompt, "query")
    assert any(len(c) >= 4000 for c in hist_contents)


def test_history_token_allocation_boundary_exact_fit():
    sys_est = _system_token_estimate_for_fake_agent()
    msg_tok = max(1, 25 // 4)
    user_tok = max(1, len("q") // 4)
    model_limit = sys_est + msg_tok * 3 + user_tok + pb_module.PROMPT_BUDGET_SAFETY_MARGIN

    store = Chat2Store(InMemoryStore())
    meta = store.create_session(user_id="u", account_name="acct", agent_name="a")
    sid = meta.session_id
    for i in range(1, 4):
        content = f"h{i}-" + ("y" * 20)
        store.add_event(sid, ChatEvent(role="user", actor="u", kind="user_message", payload=content))

    pb = _make_prompt_builder_with_config(store, model_limit=model_limit)
    prompt = pb.build_prompt(
        content_text="q",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
        context_type="none",
    )

    hist_contents = _history_only(prompt, "q")
    assert any("h1-" in c for c in hist_contents)
    assert any("h2-" in c for c in hist_contents)
    assert any("h3-" in c for c in hist_contents)


def test_max_prompt_conversations_zero_no_history():
    store = Chat2Store(InMemoryStore())
    meta = store.create_session(user_id="u", account_name="acct", agent_name="a")
    sid = meta.session_id
    for i in range(5):
        store.add_event(
            sid,
            ChatEvent(
                role="user",
                actor="u",
                kind="user_message",
                payload=f"msg-{i} " + ("x" * 20),
            ),
        )

    pb = _make_prompt_builder_with_config(
        store,
        model_limit=100000,
        max_prompt_conversations=0,
    )
    prompt = pb.build_prompt(
        content_text="query",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
        context_type="none",
    )

    assert _history_only(prompt, "query") == []


def test_max_prompt_conversations_caps_event_count():
    store = Chat2Store(InMemoryStore())
    meta = store.create_session(user_id="u", account_name="acct", agent_name="a")
    sid = meta.session_id
    for i in range(10):
        store.add_event(
            sid,
            ChatEvent(
                role="user",
                actor="u",
                kind="user_message",
                payload=f"msg-{i} " + ("x" * 20),
            ),
        )

    pb = _make_prompt_builder_with_config(
        store,
        model_limit=100000,
        max_prompt_conversations=3,
    )
    prompt = pb.build_prompt(
        content_text="query",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
        context_type="none",
    )

    hist_contents = _history_only(prompt, "query")
    assert len(hist_contents) == 3
    assert any("msg-7" in c for c in hist_contents)
    assert any("msg-8" in c for c in hist_contents)
    assert any("msg-9" in c for c in hist_contents)
    assert not any("msg-0" in c for c in hist_contents)


def test_max_prompt_conversations_cap_and_budget_combined():
    store = Chat2Store(InMemoryStore())
    meta = store.create_session(user_id="u", account_name="acct", agent_name="a")
    sid = meta.session_id
    for i in range(5):
        store.add_event(
            sid,
            ChatEvent(
                role="user",
                actor="u",
                kind="user_message",
                payload=f"small-{i} " + ("s" * 10),
            ),
        )
    for i in range(5, 10):
        store.add_event(
            sid,
            ChatEvent(
                role="user",
                actor="u",
                kind="user_message",
                payload=f"large-{i} " + ("L" * 2000),
            ),
        )

    sys_est = _system_token_estimate_for_fake_agent()
    user_tok = max(1, len("q") // 4)
    small_tok = max(1, 25 // 4)
    large_tok = max(1, 2010 // 4)
    model_limit = (
        sys_est
        + small_tok * 2
        + large_tok
        + user_tok
        + pb_module.PROMPT_BUDGET_SAFETY_MARGIN
    )

    pb = _make_prompt_builder_with_config(
        store,
        model_limit=model_limit,
        max_prompt_conversations=5,
    )
    prompt = pb.build_prompt(
        content_text="q",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
        context_type="none",
    )

    hist_contents = _history_only(prompt, "q")
    assert 1 <= len(hist_contents) <= 5


def _make_prompt_builder_with_cap_config(
    chat2_store,
    config_values,
    max_prompt_conversations=10,
    agent_budget=None,
):
    agent_manager = Mock()
    mock_agent = Mock()
    mock_agent.max_prompt_conversations = max_prompt_conversations
    mock_agent.system_prompt = None
    mock_agent.persona = None
    mock_agent.style_prompt = None
    mock_agent.allowed_tools = None
    mock_agent.use_embeddings = False
    mock_agent.max_prompt_documents = 0
    mock_agent.max_tool_result_chars = None
    mock_agent.max_handler_schema_tokens = None
    mock_agent.context_text_soft_max_tokens = None
    mock_agent.prompt_budget_max_tokens = agent_budget
    agent_manager.get_agent.return_value = mock_agent

    config = Mock()
    config.get.side_effect = lambda key, default=None: config_values.get(key, default)
    storage = Mock()

    return PromptBuilder(
        agent_manager=agent_manager,
        config=config,
        storage=storage,
        episodic_memory=Chat2EpisodicMemory(chat2_store),
    )


def _seed_history_messages(store):
    meta = store.create_session(user_id="u", account_name="acct", agent_name="a")
    sid = meta.session_id
    for i in range(1, 6):
        content = f"msg{i}-" + ("x" * 20)
        store.add_event(sid, ChatEvent(role="user", actor="u", kind="user_message", payload=content))
    return sid


def _budget_fitting_two_history_messages():
    sys_est = _system_token_estimate_for_fake_agent()
    msg_tok = max(1, 25 // 4)
    user_tok = max(1, len("query") // 4)
    return sys_est + msg_tok * 2 + user_tok + pb_module.PROMPT_BUDGET_SAFETY_MARGIN


def test_history_budget_env_ceiling_wins_over_config_with_fieldless_agent(monkeypatch):
    monkeypatch.setenv("PROMPT_BUDGET_MAX_TOKENS", str(_budget_fitting_two_history_messages()))
    store = Chat2Store(InMemoryStore())
    sid = _seed_history_messages(store)
    pb = _make_prompt_builder_with_cap_config(store, {"prompt_budget_max_tokens": 100000})

    prompt = pb.build_prompt(
        content_text="query",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
        context_type="none",
    )
    hist_contents = _history_only(prompt, "query")
    assert any("msg4-" in c for c in hist_contents)
    assert any("msg5-" in c for c in hist_contents)
    assert not any("msg1-" in c for c in hist_contents)


def test_history_budget_config_ceiling_honored_with_fieldless_agent(monkeypatch):
    monkeypatch.delenv("PROMPT_BUDGET_MAX_TOKENS", raising=False)
    store = Chat2Store(InMemoryStore())
    sid = _seed_history_messages(store)
    pb = _make_prompt_builder_with_cap_config(
        store,
        {"prompt_budget_max_tokens": _budget_fitting_two_history_messages()},
    )

    prompt = pb.build_prompt(
        content_text="query",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
        context_type="none",
    )
    hist_contents = _history_only(prompt, "query")
    assert any("msg4-" in c for c in hist_contents)
    assert any("msg5-" in c for c in hist_contents)
    assert not any("msg1-" in c for c in hist_contents)


def test_history_budget_defaults_to_module_constant_with_fieldless_agent(caplog, monkeypatch):
    monkeypatch.delenv("PROMPT_BUDGET_MAX_TOKENS", raising=False)
    caplog.set_level(logging.INFO)
    store = Chat2Store(InMemoryStore())
    sid = _seed_history_messages(store)
    pb = _make_prompt_builder_with_cap_config(store, {})

    pb.build_prompt(
        content_text="query",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
        context_type="none",
    )

    expected = f"ceiling={pb_module.DEFAULT_PROMPT_BUDGET_TOKENS}"
    assert any(expected in rec.getMessage() for rec in caplog.records)


def test_history_budget_agent_ceiling_smaller_than_config_caps_history(monkeypatch):
    monkeypatch.delenv("PROMPT_BUDGET_MAX_TOKENS", raising=False)
    store = Chat2Store(InMemoryStore())
    sid = _seed_history_messages(store)
    pb = _make_prompt_builder_with_cap_config(
        store,
        {"prompt_budget_max_tokens": 100000},
        agent_budget=_budget_fitting_two_history_messages(),
    )

    prompt = pb.build_prompt(
        content_text="query",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
        context_type="none",
    )
    hist_contents = _history_only(prompt, "query")
    assert any("msg4-" in c for c in hist_contents)
    assert any("msg5-" in c for c in hist_contents)
    assert not any("msg1-" in c for c in hist_contents)
