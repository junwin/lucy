import logging
from types import SimpleNamespace

from src.prompt_builders.prompt_builder import PromptBuilder


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
            return SimpleNamespace(data={"text": "x" * 10000})

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
