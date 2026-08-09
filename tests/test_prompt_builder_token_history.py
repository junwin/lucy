from types import SimpleNamespace
from unittest.mock import Mock

from src.chat2.store_primitives import InMemoryStore
from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent

from src.prompt_builders import prompt_builder as pb_module
from src.prompt_builders.prompt_builder import PromptBuilder


def _make_prompt_builder_with_config(chat2_store, model_limit):
    agent_manager = Mock()
    mock_agent = Mock()
    mock_agent.max_prompt_conversations = 10
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

    return PromptBuilder(agent_manager=agent_manager, config=config, storage=storage, chat2_store=chat2_store)


def _system_token_estimate_for_fake_agent():
    """Estimate tokens consumed by the system messages for a fake agent named 'a'.

    PromptBuilder always emits:
      1. Agent system message: "You are a, a helpful assistant." (~34 chars)
      2. Session ID line: "Current session ID: <uuid>" (~55 chars)
      3. Session info: "Session: agent=a, ..., last activity ..." (~90 chars)

    The session-info line length varies slightly by timestamp.
    We add a safety margin of 20 chars to account for that.
    """
    return (34 + 55 + 90 + 20) // 4  # rough estimate in real-token terms


def test_history_token_allocation_normal_case():
    """Many small messages — the most recent ones that fit the budget are included."""
    sys_est = _system_token_estimate_for_fake_agent()
    msg_len = 25  # "msg1-" + 20 x's = 25 chars
    msg_tok = max(1, msg_len // 4)
    user_tok = max(1, len("query") // 4)

    # model_limit must cover system + 2 history msgs + current query + safety margin (500)
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

    hist_contents = [m["content"] for m in prompt if m.get("role") in ("user", "assistant")]
    # msg4 and msg5 should be the most recent that fit
    assert any("msg4-" in c for c in hist_contents), "Expected msg4 in history"
    assert any("msg5-" in c for c in hist_contents), "Expected msg5 in history"


def test_history_token_allocation_giant_message_included():
    """A single giant message — included even though it exceeds the budget."""
    store = Chat2Store(InMemoryStore())
    meta = store.create_session(user_id="u", account_name="acct", agent_name="a")
    sid = meta.session_id

    giant = "G" * 5000
    store.add_event(sid, ChatEvent(role="user", actor="u", kind="user_message", payload=giant))

    # Tiny limit that system + safety margin will far exceed
    pb = _make_prompt_builder_with_config(store, model_limit=50)

    prompt = pb.build_prompt(
        content_text="query",
        conversation_id=sid,
        agent_name="a",
        account_name="acct",
        context_type="none",
    )

    hist_contents = [m["content"] for m in prompt if m.get("role") in ("user", "assistant")]
    # Giant message should be present despite being over budget
    assert any(len(c) >= 4000 for c in hist_contents), "Expected giant message included in history"


def test_history_token_allocation_boundary_exact_fit():
    """Exactly at the budget limit — all messages fit."""
    sys_est = _system_token_estimate_for_fake_agent()
    msg_len = 25  # "h1-" + 21 y's = 25 chars
    msg_tok = max(1, msg_len // 4)  # ~6 tokens real
    user_tok = max(1, len("q") // 4)  # 1 token

    # 3 history messages + current query + safety margin (500)
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

    hist_contents = [m["content"] for m in prompt if m.get("role") in ("user", "assistant")]
    assert any("h1-" in c for c in hist_contents), "Expected h1 in history"
    assert any("h2-" in c for c in hist_contents), "Expected h2 in history"
    assert any("h3-" in c for c in hist_contents), "Expected h3 in history"
