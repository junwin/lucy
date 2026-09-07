import logging
from datetime import datetime, timezone

from src.agent.agent import Agent
from src.prompt_builders.prompt_builder import PromptBuilder
from src.storage.models import Context


def test_context_soft_maximum_triggers_warning(caplog):
    caplog.set_level(logging.WARNING)

    # Fake agent manager: returns None for any agent (agent-less defaults)
    class FakeAgentManager:
        def get_agent(self, name):
            return None

    # Fake config: no explicit setting -> use default fallback (2000)
    class FakeConfig:
        def get(self, key, default=None):
            return default

    # Fake storage: returns a context with a very large text body
    class FakeStorage:
        def get_or_create_context(self, account_name, context_name):
            return Context(
                id=context_name,
                account_name=account_name,
                text="x" * 10000,
                updated_at=datetime.now(timezone.utc),
            )

    pb = PromptBuilder(
        agent_manager=FakeAgentManager(),
        config=FakeConfig(),
        storage=FakeStorage(),
        chat2_store=None,
    )

    # Call build_prompt with a named context — should trigger the soft-max warning
    pb.build_prompt(
        content_text="hello",
        conversation_id="new",
        agent_name="test",
        account_name="acct",
        context_type="none",
        context_name="bigctx",
    )

    assert any("exceeds soft max" in rec.message for rec in caplog.records), (
        "Expected a warning log about soft max being exceeded"
    )


def _build_prompt_with(agent, config_values, context_text):
    class FakeAgentManager:
        def __init__(self, agent):
            self._agent = agent

        def get_agent(self, name):
            return self._agent

    class FakeConfig:
        def __init__(self, values):
            self._values = values

        def get(self, key, default=None):
            return self._values.get(key, default)

    class FakeStorage:
        def __init__(self, text):
            self._text = text

        def get_or_create_context(self, account_name, context_name):
            return Context(
                id=context_name,
                account_name=account_name,
                text=self._text,
                updated_at=datetime.now(timezone.utc),
            )

    pb = PromptBuilder(
        agent_manager=FakeAgentManager(agent),
        config=FakeConfig(config_values),
        storage=FakeStorage(context_text),
        chat2_store=None,
    )

    return pb.build_prompt(
        content_text="hello",
        conversation_id="new",
        agent_name="test",
        account_name="acct",
        context_type="none",
        context_name="bigctx",
    )


def _additional_context_content(messages):
    prefix = "Additional context for this conversation:"
    for m in messages:
        content = m.get("content")
        if isinstance(content, str) and content.startswith(prefix):
            return content[len(prefix):]
    return None


def test_context_truncation_uses_config_when_agent_has_no_override_fields():
    agent = Agent(name="test")
    truncated = _build_prompt_with(agent, {"context_text_soft_max_tokens": 500}, "x" * 2400)
    assert "[Context truncated due to token budget]" in (_additional_context_content(truncated) or "")

    intact = _build_prompt_with(agent, {"context_text_soft_max_tokens": 500}, "x" * 1600)
    assert "[Context truncated due to token budget]" not in (_additional_context_content(intact) or "")


def test_context_truncation_defaults_to_2000_when_config_unset_and_agent_has_no_override_fields():
    agent = Agent(name="test")
    truncated = _build_prompt_with(agent, {}, "x" * 9000)
    assert "[Context truncated due to token budget]" in (_additional_context_content(truncated) or "")

    intact = _build_prompt_with(agent, {}, "x" * 7600)
    assert "[Context truncated due to token budget]" not in (_additional_context_content(intact) or "")


def test_agent_context_soft_max_override_smaller_than_config_still_truncates():
    agent = Agent(name="test", context_text_soft_max_tokens=300)
    prompt = _build_prompt_with(agent, {"context_text_soft_max_tokens": 1000}, "x" * 2400)
    assert "[Context truncated due to token budget]" in (_additional_context_content(prompt) or "")


def test_agent_context_soft_max_override_larger_than_config_skips_truncation():
    agent = Agent(name="test", context_text_soft_max_tokens=3000)
    prompt = _build_prompt_with(agent, {"context_text_soft_max_tokens": 1000}, "x" * 6000)
    assert "[Context truncated due to token budget]" not in (_additional_context_content(prompt) or "")
