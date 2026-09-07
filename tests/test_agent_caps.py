"""Resolver precedence tests for per-agent cap overrides (issue #171).

Covers the design doc agent-tuning.md sections 4.2/4.3 precedence table for
the four cap keys: agent > config > code default, with the schema-cap
disable semantics (agent <= 0 -> None, config <= 0 -> None, missing ->
DEFAULT_MAX_HANDLER_SCHEMA_TOKENS) and the env > agent > config ordering
for prompt_budget_max_tokens.
"""

import pytest

from src.agent.agent import Agent
from src.agent.caps import resolve_effective_cap
from src.message_processors.fcp_models import DEFAULT_MAX_HANDLER_SCHEMA_TOKENS

FALL_THROUGH_KEYS = [
    ("max_tool_result_chars", 20000),
    ("context_text_soft_max_tokens", 2000),
    ("prompt_budget_max_tokens", 12000),
]


class _Cfg:
    def __init__(self, values=None):
        self._values = dict(values or {})

    def get(self, key, default=None):
        return self._values.get(key, default)


def _agent(**overrides):
    return Agent(name="resolver-agent", **overrides)


@pytest.fixture(autouse=True)
def _no_budget_env(monkeypatch):
    monkeypatch.delenv("PROMPT_BUDGET_MAX_TOKENS", raising=False)


@pytest.mark.parametrize("key,code_default", FALL_THROUGH_KEYS)
class TestFallThroughCapKeys:
    """Agent present & >0 wins; agent <=0 falls through to config, else code default."""

    def test_agent_positive_beats_config(self, key, code_default):
        assert resolve_effective_cap(key, _agent(**{key: 321}), _Cfg({key: 111}), code_default) == 321

    def test_agent_positive_wins_when_config_unset(self, key, code_default):
        assert resolve_effective_cap(key, _agent(**{key: 321}), _Cfg({}), code_default) == 321

    def test_agent_non_positive_falls_through_to_config(self, key, code_default):
        assert resolve_effective_cap(key, _agent(**{key: 0}), _Cfg({key: 111}), code_default) == 111

    def test_agent_non_positive_uses_code_default_when_config_unset(self, key, code_default):
        assert resolve_effective_cap(key, _agent(**{key: 0}), _Cfg({}), code_default) == code_default

    def test_agent_non_positive_uses_code_default_when_config_non_positive(self, key, code_default):
        assert resolve_effective_cap(key, _agent(**{key: -1}), _Cfg({key: -5}), code_default) == code_default

    def test_agent_none_uses_config_value(self, key, code_default):
        assert resolve_effective_cap(key, None, _Cfg({key: 111}), code_default) == 111

    def test_agent_none_uses_code_default_when_config_non_positive(self, key, code_default):
        assert resolve_effective_cap(key, None, _Cfg({key: -5}), code_default) == code_default

    def test_agent_none_uses_code_default_when_config_unset(self, key, code_default):
        assert resolve_effective_cap(key, None, _Cfg({}), code_default) == code_default

    def test_agent_field_none_matches_agent_none(self, key, code_default):
        plain = _agent()
        assert getattr(plain, key) is None
        assert resolve_effective_cap(key, plain, _Cfg({key: 111}), code_default) == resolve_effective_cap(
            key, None, _Cfg({key: 111}), code_default
        )
        assert resolve_effective_cap(key, plain, _Cfg({}), code_default) == resolve_effective_cap(
            key, None, _Cfg({}), code_default
        )


class TestSchemaCapDisableSemantics:
    """max_handler_schema_tokens: agent <=0 or config <=0 disables (None)."""

    key = "max_handler_schema_tokens"

    def test_agent_positive_beats_config(self):
        assert (
            resolve_effective_cap(
                self.key,
                _agent(max_handler_schema_tokens=9000),
                _Cfg({self.key: 1000}),
                DEFAULT_MAX_HANDLER_SCHEMA_TOKENS,
                disable_on_non_positive=True,
            )
            == 9000
        )

    def test_agent_positive_wins_when_config_unset(self):
        assert (
            resolve_effective_cap(
                self.key,
                _agent(max_handler_schema_tokens=9000),
                _Cfg({}),
                DEFAULT_MAX_HANDLER_SCHEMA_TOKENS,
                disable_on_non_positive=True,
            )
            == 9000
        )

    def test_agent_non_positive_disables_even_when_config_positive(self):
        assert (
            resolve_effective_cap(
                self.key,
                _agent(max_handler_schema_tokens=0),
                _Cfg({self.key: 1000}),
                DEFAULT_MAX_HANDLER_SCHEMA_TOKENS,
                disable_on_non_positive=True,
            )
            is None
        )

    def test_agent_non_positive_disables_when_config_unset(self):
        assert (
            resolve_effective_cap(
                self.key,
                _agent(max_handler_schema_tokens=0),
                _Cfg({}),
                DEFAULT_MAX_HANDLER_SCHEMA_TOKENS,
                disable_on_non_positive=True,
            )
            is None
        )

    def test_agent_none_uses_config_value(self):
        assert (
            resolve_effective_cap(
                self.key,
                None,
                _Cfg({self.key: 1000}),
                DEFAULT_MAX_HANDLER_SCHEMA_TOKENS,
                disable_on_non_positive=True,
            )
            == 1000
        )

    def test_agent_none_config_zero_disables(self):
        assert (
            resolve_effective_cap(
                self.key,
                None,
                _Cfg({self.key: 0}),
                DEFAULT_MAX_HANDLER_SCHEMA_TOKENS,
                disable_on_non_positive=True,
            )
            is None
        )

    def test_agent_none_config_negative_disables(self):
        assert (
            resolve_effective_cap(
                self.key,
                None,
                _Cfg({self.key: -5}),
                DEFAULT_MAX_HANDLER_SCHEMA_TOKENS,
                disable_on_non_positive=True,
            )
            is None
        )

    def test_agent_none_missing_uses_default_constant(self):
        assert (
            resolve_effective_cap(
                self.key,
                None,
                _Cfg({}),
                DEFAULT_MAX_HANDLER_SCHEMA_TOKENS,
                disable_on_non_positive=True,
            )
            == DEFAULT_MAX_HANDLER_SCHEMA_TOKENS
        )

    def test_agent_field_none_matches_agent_none(self):
        plain = _agent()
        assert plain.max_handler_schema_tokens is None
        assert resolve_effective_cap(
            self.key, plain, _Cfg({self.key: 1000}), DEFAULT_MAX_HANDLER_SCHEMA_TOKENS, disable_on_non_positive=True
        ) == resolve_effective_cap(
            self.key, None, _Cfg({self.key: 1000}), DEFAULT_MAX_HANDLER_SCHEMA_TOKENS, disable_on_non_positive=True
        )
        assert resolve_effective_cap(
            self.key, plain, _Cfg({}), DEFAULT_MAX_HANDLER_SCHEMA_TOKENS, disable_on_non_positive=True
        ) == resolve_effective_cap(
            self.key, None, _Cfg({}), DEFAULT_MAX_HANDLER_SCHEMA_TOKENS, disable_on_non_positive=True
        )


class TestBudgetEnvOrdering:
    """prompt_budget_max_tokens: env (operator brake) outranks agent and config."""

    def test_env_wins_over_agent_and_config(self, monkeypatch):
        monkeypatch.setenv("PROMPT_BUDGET_MAX_TOKENS", "77")
        agent = _agent(prompt_budget_max_tokens=5000)
        assert resolve_effective_cap("prompt_budget_max_tokens", agent, _Cfg({"prompt_budget_max_tokens": 6000}), 12000) == 77

    def test_env_invalid_falls_through_to_agent(self, monkeypatch):
        monkeypatch.setenv("PROMPT_BUDGET_MAX_TOKENS", "not-a-number")
        agent = _agent(prompt_budget_max_tokens=5000)
        assert resolve_effective_cap("prompt_budget_max_tokens", agent, _Cfg({"prompt_budget_max_tokens": 6000}), 12000) == 5000

    def test_env_only_applies_to_budget_key(self, monkeypatch):
        monkeypatch.setenv("PROMPT_BUDGET_MAX_TOKENS", "77")
        agent = _agent(max_tool_result_chars=5000)
        assert resolve_effective_cap("max_tool_result_chars", agent, _Cfg({"max_tool_result_chars": 6000}), 20000) == 5000


class TestAgentAsDict:
    """The resolver also accepts a raw agent dict (not only Agent instances)."""

    def test_dict_agent_positive_value_wins(self):
        assert (
            resolve_effective_cap("max_tool_result_chars", {"max_tool_result_chars": 321}, _Cfg({"max_tool_result_chars": 111}), 20000)
            == 321
        )

    def test_dict_agent_non_positive_falls_through_to_config(self):
        assert (
            resolve_effective_cap("max_tool_result_chars", {"max_tool_result_chars": 0}, _Cfg({"max_tool_result_chars": 111}), 20000)
            == 111
        )
