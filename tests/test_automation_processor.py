import json

from unittest.mock import Mock

import pytest


def _make_processor_factory(worker_processor: Mock) -> object:
    """AutomationProcessor expects a processor_factory with .get(name)."""

    class _Factory:
        def get(self, name: str):
            if name == "function_calling_processor":
                return worker_processor
            return None

    return _Factory()


def _make_raising_processor_factory() -> object:
    """Factory stub that fails the test if any worker processor is requested."""

    class _Factory:
        def get(self, name: str):
            raise AssertionError(f"processor_factory.get({name!r}) should not be called")

    return _Factory()


@pytest.mark.parametrize(
    "message_text, expected_mode_substrings",
    [
        ("run tasks single step", ["single", "step"]),
        ("run tasks multi-step", ["multi", "step"]),
    ],
)
def test_automation_processor_selects_mode_from_message_text(
    storage, config, registry, prompt_builder, caplog, message_text, expected_mode_substrings
):
    """Inbound message is parsed to select mode (single vs multi-step).

    We pass a missing context_name so the processor should fail fast on context loading.
    This test only asserts that:
    - context existence is checked ("not found")
    - mode text is present in the response and/or logs
    - worker processor is NOT invoked
    """

    from tests.conftest import FakeAgent
    from src.message_processors.automation_processor import AutomationProcessor

    proc = AutomationProcessor(
        config=config,
        registry=registry,
        storage=storage,
        prompt_builder=prompt_builder,
    )

    processor_factory = _make_raising_processor_factory()

    caplog.clear()

    out = proc.process_message(
        primary_agent=FakeAgent(name="doris", save_responses=False),
        secondary_agent=FakeAgent(name="colin"),
        processor_factory=processor_factory,
        account={"accountId": "acct1"},
        message=message_text,
        conversation_id="c1",
        context_name="missing.ctx",
    )

    assert "context" in out.lower()
    assert "not found" in out.lower()

    haystack = (out + "\n" + caplog.text).lower()
    for s in expected_mode_substrings:
        assert s in haystack


def test_automation_processor_invalid_message_text_returns_helpful_error(
    storage, config, registry, prompt_builder, caplog
):
    """Invalid command should return a helpful error listing allowed commands."""

    from tests.conftest import FakeAgent
    from src.message_processors.automation_processor import AutomationProcessor

    proc = AutomationProcessor(
        config=config,
        registry=registry,
        storage=storage,
        prompt_builder=prompt_builder,
    )

    processor_factory = _make_raising_processor_factory()

    caplog.clear()

    out = proc.process_message(
        primary_agent=FakeAgent(name="doris", save_responses=False),
        secondary_agent=FakeAgent(name="colin"),
        processor_factory=processor_factory,
        account={"accountId": "acct1"},
        message="do something else",
        conversation_id="c1",
        context_name="missing.ctx",
    )

    out_l = out.lower()
    assert "invalid" in out_l or "unknown" in out_l
    assert "run tasks" in out_l
    assert "single step" in out_l
    assert "multi-step" in out_l


def test_automation_processor_missing_context_returns_not_found(storage, config, registry, prompt_builder):
    """Only assert that context existence is checked based on context_name."""

    from tests.conftest import FakeAgent
    from src.message_processors.automation_processor import AutomationProcessor

    proc = AutomationProcessor(
        config=config,
        registry=registry,
        storage=storage,
        prompt_builder=prompt_builder,
    )

    worker = Mock()
    processor_factory = _make_processor_factory(worker)

    out = proc.process_message(
        primary_agent=FakeAgent(name="doris", save_responses=False),
        secondary_agent=FakeAgent(name="colin"),
        processor_factory=processor_factory,
        account={"accountId": "acct1"},
        message="run tasks single step",
        conversation_id="c1",
        context_name="missing.ctx",
    )

    assert "context" in out.lower()
    assert "not found" in out.lower()


def test_automation_processor_missing_context_name_returns_help(storage, config, registry, prompt_builder):
    from tests.conftest import FakeAgent
    from src.message_processors.automation_processor import AutomationProcessor

    proc = AutomationProcessor(
        config=config,
        registry=registry,
        storage=storage,
        prompt_builder=prompt_builder,
    )

    worker = Mock()
    processor_factory = _make_processor_factory(worker)

    out = proc.process_message(
        primary_agent=FakeAgent(name="doris", save_responses=False),
        secondary_agent=FakeAgent(name="colin"),
        processor_factory=processor_factory,
        account={"accountId": "acct1"},
        message=json.dumps({"action": "status"}),
        conversation_id="c1",
        context_name="",
    )

    assert "missing context_name" in out.lower()
