"""Pipeline unit tests for the tool selection pipeline (issue #126, design §3/§5).

Exercises ``ToolSelectionPipeline.resolve()`` end-to-end using fakes only
(``FakeRegistry``, ``FakeStorage``, ``FakeLLM``, ``FakeConfig``) — no live LLM.

Coverage (tasklist ts5):

- step 3 eligible: allowed ``None`` / ``[]`` / subset, unknown allowed names
  ignored, registry order preserved.
- step 4 required: aggregation (own ``mandatory_tools`` + resolved skills'
  ``mandatory_tools``), dedupe, empty/none.
- step 5 validate: pass; ``required_not_permissioned`` when a required tool is
  not in ``allowed``; ``required_not_registered`` when it is unknown to the
  registry — with precise messages.
- step 7 finalize: union + dedupe order; required always present even when the
  LLM omits them.
- step 8 budget: under cap unchanged; over cap raises ``ToolSelectionError``
  (``budget_exceeded``) with a message telling the user to increase the budget;
  cap <= 0 disables the check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import pytest

from src.storage.models import Context, Skill
from src.tool_selection import ToolSelection, ToolSelectionError, ToolSelectionPipeline
from tests.conftest import FakeConfig, FakeRegistry, FakeStorage

ACCOUNT = "acct"
CONTEXT_ID = "ctx"


# ---------------------------------------------------------------------------
# Fakes (no live LLM)
# ---------------------------------------------------------------------------


@dataclass
class FakeLLM:
    """Duck-typed LLM adapter: records every ``call_model`` and returns a
    canned reply via ``get_text``."""

    reply: str = "[]"
    calls: List[Dict[str, Any]] = field(default_factory=list)

    def call_model(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return ("response", kwargs)

    def get_text(self, response: Any) -> str:
        return self.reply


@dataclass
class FakeAgent:
    """Minimal agent carrying the fields the pipeline reads."""

    allowed_tools: Optional[List[str]] = None
    model: str = "test-model"
    provider: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _defs(*names: str) -> List[Dict[str, Any]]:
    """Tool defs with a description large enough that token math is meaningful."""
    return [
        {
            "name": name,
            "description": f"{name} does things",
            "parameters": {"type": "object", "properties": {}},
        }
        for name in names
    ]


def _make_config(
    *,
    enabled: bool = True,
    min_eligible: int = 1,
    schema_cap: Optional[int] = None,
) -> FakeConfig:
    values: Dict[str, Any] = {
        "lazy_tool_loading": {
            "enabled": enabled,
            "min_eligible_to_select": min_eligible,
        },
    }
    if schema_cap is not None:
        values["max_handler_schema_tokens"] = schema_cap
    return FakeConfig(values=values)


def _make_context(
    *,
    mandatory_tools: Optional[List[str]] = None,
    skills: Optional[List[Skill]] = None,
) -> Context:
    return Context(
        id=CONTEXT_ID,
        account_name=ACCOUNT,
        updated_at=datetime.now(timezone.utc),
        mandatory_tools=list(mandatory_tools or []),
        resolved_skills=skills or [],
    )


def _build(
    *,
    tool_names: List[str],
    allowed: Optional[List[str]] = None,
    context: Any = None,
    llm_reply: str = "[]",
    enabled: bool = True,
    min_eligible: int = 1,
    schema_cap: Optional[int] = None,
) -> Tuple[ToolSelectionPipeline, FakeLLM, FakeAgent]:
    registry = FakeRegistry(tool_defs=_defs(*tool_names))
    storage = FakeStorage()
    if context is not None:
        storage.save_context(context)
    llm = FakeLLM(reply=llm_reply)
    config = _make_config(enabled=enabled, min_eligible=min_eligible, schema_cap=schema_cap)
    agent = FakeAgent(allowed_tools=allowed)
    pipeline = ToolSelectionPipeline(
        registry=registry,
        storage=storage,
        llm_adapter=llm,
        config=config,
    )
    return pipeline, llm, agent


def _resolve(
    *,
    tool_names: List[str],
    allowed: Optional[List[str]] = None,
    context: Any = None,
    llm_reply: str = "[]",
    enabled: bool = True,
    min_eligible: int = 1,
    schema_cap: Optional[int] = None,
    prompt_text: str = "do something",
    context_name: str = CONTEXT_ID,
) -> Tuple[ToolSelection, FakeLLM]:
    pipeline, llm, agent = _build(
        tool_names=tool_names,
        allowed=allowed,
        context=context,
        llm_reply=llm_reply,
        enabled=enabled,
        min_eligible=min_eligible,
        schema_cap=schema_cap,
    )
    result = pipeline.resolve(
        agent=agent,
        account_name=ACCOUNT,
        context_name=context_name,
        prompt_text=prompt_text,
    )
    return result, llm


# ---------------------------------------------------------------------------
# Step 3 — eligible = registry ∩ allowed (registry order; unknown names ignored)
# ---------------------------------------------------------------------------


def test_step3_allowed_none_means_no_tools():
    """``allowed_tools=None`` is a permission to use 0 tools (design §4 / D1)."""
    result, llm = _resolve(tool_names=["t1", "t2", "t3"], allowed=None)

    assert result.allowed == []
    assert result.all_tools == ["t1", "t2", "t3"]
    assert result.eligible == []
    assert result.active == []
    # Nothing eligible to select from — the selection LLM must not be called.
    assert llm.calls == []


def test_step3_allowed_empty_means_no_tools():
    """``allowed_tools=[]`` is a permission to use 0 tools (design §4 / D1)."""
    result, _ = _resolve(tool_names=["t1", "t2", "t3"], allowed=[])

    assert result.allowed == []
    assert result.eligible == []


def test_step3_eligible_subset_preserves_registry_order():
    """Eligible follows registry order, not ``allowed_tools`` order."""
    result, _ = _resolve(tool_names=["t1", "t2", "t3"], allowed=["t3", "t1"])

    assert result.all_tools == ["t1", "t2", "t3"]
    assert result.eligible == ["t1", "t3"]


def test_step3_unknown_allowed_names_ignored():
    """Allowed names unknown to the registry are ignored (design §3 step 3)."""
    result, _ = _resolve(tool_names=["t1", "t2"], allowed=["t2", "nope", "t1"])

    # The raw permission list keeps the unknown entry...
    assert result.allowed == ["t2", "nope", "t1"]
    # ...but eligible only contains registered names, in registry order.
    assert result.eligible == ["t1", "t2"]


# ---------------------------------------------------------------------------
# Step 4 — required = context.required_tools (aggregated, deduped)
# ---------------------------------------------------------------------------


def test_step4_required_aggregates_context_and_skills_deduped():
    """Own ``mandatory_tools`` + resolved skills' tools, first-wins dedupe."""
    ctx = _make_context(
        mandatory_tools=["file_load", "file_save", "file_load"],
        skills=[
            Skill(name="s1", mandatory_tools=["file_save", "execute_command"]),
            Skill(name="s2", mandatory_tools=["execute_command"]),
        ],
    )
    result, _ = _resolve(
        tool_names=["file_load", "file_save", "execute_command"],
        allowed=["file_load", "file_save", "execute_command"],
        context=ctx,
    )

    assert result.required == ["file_load", "file_save", "execute_command"]


def test_step4_required_empty_when_no_context():
    """A ``"none"`` context name means no context ⇒ no required tools."""
    result, _ = _resolve(
        tool_names=["t1", "t2"],
        allowed=["t1", "t2"],
        context_name="none",
    )
    assert result.required == []


def test_step4_required_empty_when_context_missing():
    """A context that storage cannot find yields an empty required list."""
    result, _ = _resolve(
        tool_names=["t1", "t2"],
        allowed=["t1", "t2"],
        context_name="missing",
    )
    assert result.required == []


def test_step4_required_empty_when_no_mandatory_tools():
    """A context with no mandatory tools and no skills ⇒ nothing required."""
    result, _ = _resolve(
        tool_names=["t1", "t2"],
        allowed=["t1", "t2"],
        context=_make_context(),
    )
    assert result.required == []


def test_step4_required_none_attribute_treated_as_empty():
    """A context whose ``required_tools`` attribute is ``None`` ⇒ empty."""
    pipeline, llm, agent = _build(
        tool_names=["t1", "t2"],
        allowed=["t1", "t2"],
        context=SimpleNamespace(account_name=ACCOUNT, id=CONTEXT_ID, required_tools=None),
    )
    result = pipeline.resolve(
        agent=agent,
        account_name=ACCOUNT,
        context_name=CONTEXT_ID,
        prompt_text="hi",
    )
    assert result.required == []


def test_step4_required_normalizes_blank_entries():
    """Blank/whitespace-only entries are dropped before dedupe."""
    result, _ = _resolve(
        tool_names=["file_load"],
        allowed=["file_load"],
        context=_make_context(mandatory_tools=["", "  ", "file_load", "file_load"]),
    )
    assert result.required == ["file_load"]


# ---------------------------------------------------------------------------
# Step 5 — validate required ⊆ allowed ∩ registry (hard, user-facing error)
# ---------------------------------------------------------------------------


def test_step5_validate_passes_when_required_is_allowed_and_registered():
    """A required tool that is both allowed and registered passes silently."""
    ctx = _make_context(mandatory_tools=["file_load"])
    result, _ = _resolve(
        tool_names=["file_load", "file_save"],
        allowed=["file_load", "file_save"],
        context=ctx,
        llm_reply="[]",
    )
    assert result.required == ["file_load"]


def test_step5_required_not_permissioned_raises_precise_message():
    """Required tool registered but not allowed ⇒ ``required_not_permissioned``.

    The LLM is never invoked (design D2).
    """
    ctx = _make_context(mandatory_tools=["file_save"])
    pipeline, llm, agent = _build(
        tool_names=["file_load", "file_save"],  # file_save IS a registered handler
        allowed=["file_load"],                  # ...but the agent may not use it
        context=ctx,
    )

    with pytest.raises(ToolSelectionError) as excinfo:
        pipeline.resolve(agent=agent, account_name=ACCOUNT, context_name=CONTEXT_ID, prompt_text="hi")

    err = excinfo.value
    assert err.code == "required_not_permissioned"
    assert err.offending_tools == ["file_save"]
    assert err.message == (
        "Required tools not permissioned for this agent: 'file_save'. "
        "The agent is not allowed to use them; add them to the agent's "
        "allowed_tools or remove them from the context's required_tools."
    )
    assert llm.calls == []


def test_step5_required_not_registered_raises_precise_message():
    """Required tool allowed but unknown to the registry ⇒ ``required_not_registered``.

    The LLM is never invoked (design D2).
    """
    ctx = _make_context(mandatory_tools=["ghost_tool"])
    pipeline, llm, agent = _build(
        tool_names=["file_load"],                # ghost_tool is NOT registered
        allowed=["file_load", "ghost_tool"],     # ...but the agent allows it
        context=ctx,
    )

    with pytest.raises(ToolSelectionError) as excinfo:
        pipeline.resolve(agent=agent, account_name=ACCOUNT, context_name=CONTEXT_ID, prompt_text="hi")

    err = excinfo.value
    assert err.code == "required_not_registered"
    assert err.offending_tools == ["ghost_tool"]
    assert err.message == (
        "Required tools are not registered handlers: 'ghost_tool'. "
        "These tools are unknown to the system; register the handler or fix "
        "the context's required_tools."
    )
    assert llm.calls == []


def test_step5_permission_check_precedes_registry_check():
    """A tool that is neither allowed nor registered reports the permission problem."""
    ctx = _make_context(mandatory_tools=["ghost_tool"])
    pipeline, llm, agent = _build(
        tool_names=["file_load"],
        allowed=["file_load"],
        context=ctx,
    )

    with pytest.raises(ToolSelectionError) as excinfo:
        pipeline.resolve(agent=agent, account_name=ACCOUNT, context_name=CONTEXT_ID, prompt_text="hi")

    assert excinfo.value.code == "required_not_permissioned"
    assert llm.calls == []


# ---------------------------------------------------------------------------
# Step 7 — finalize: active = required ∪ prompt_based (dedup, first-wins)
# ---------------------------------------------------------------------------


def test_step7_active_is_union_dedup_required_first():
    """Required first, then LLM suggestions; duplicates removed first-wins."""
    ctx = _make_context(mandatory_tools=["file_load", "file_save"])
    result, llm = _resolve(
        tool_names=["file_load", "file_save", "execute_command", "web_search_handler"],
        allowed=["file_load", "file_save", "execute_command", "web_search_handler"],
        context=ctx,
        llm_reply='["file_save", "web_search_handler", "file_save"]',
    )

    assert llm.calls, "the selection LLM should have been called"
    assert result.prompt_based == ["file_save", "web_search_handler"]
    assert result.active == ["file_load", "file_save", "web_search_handler"]
    # The resolved full defs mirror the active names, in the same order.
    assert [d["name"] for d in result.meta["active_defs"]] == result.active


def test_step7_required_always_present_when_llm_omits_them():
    """The LLM cannot drop a required tool from the active set (design step 7)."""
    ctx = _make_context(mandatory_tools=["file_load", "execute_command"])
    result, _ = _resolve(
        tool_names=["file_load", "file_save", "execute_command"],
        allowed=["file_load", "file_save", "execute_command"],
        context=ctx,
        llm_reply='["file_save"]',
    )

    assert result.active == ["file_load", "execute_command", "file_save"]


def test_step7_llm_suggestions_outside_eligible_are_clamped():
    """Names the LLM invents are clamped away by selection (design §5.4)."""
    ctx = _make_context(mandatory_tools=["file_load"])
    result, _ = _resolve(
        tool_names=["file_load", "file_save"],
        allowed=["file_load", "file_save"],
        context=ctx,
        llm_reply='["ghost_tool", "file_save"]',
    )

    assert result.prompt_based == ["file_save"]
    assert result.active == ["file_load", "file_save"]


def test_step7_selection_disabled_active_is_full_eligible():
    """``lazy_tool_loading.enabled=false`` ⇒ no LLM call, active = eligible (D7)."""
    result, llm = _resolve(
        tool_names=["t1", "t2", "t3"],
        allowed=["t1", "t2", "t3"],
        enabled=False,
    )

    assert llm.calls == []
    assert result.meta["selection"]["skipped"] is True
    assert result.meta["selection"]["reason"] == "disabled"
    assert result.active == ["t1", "t2", "t3"]


# ---------------------------------------------------------------------------
# Step 8 — schema budget (fail loud, never trim silently — D4)
# ---------------------------------------------------------------------------


def test_budget_under_cap_unchanged():
    """Under the cap the active set passes through untouched."""
    result, _ = _resolve(
        tool_names=["t1", "t2"],
        allowed=["t1", "t2"],
        enabled=False,
        schema_cap=10_000_000,
    )

    assert [d["name"] for d in result.meta["active_defs"]] == ["t1", "t2"]
    assert result.meta["schema_cap"] == 10_000_000
    assert result.meta["schema_tokens"] > 0


def test_budget_over_cap_raises_budget_exceeded_with_increase_message():
    """Over the cap ⇒ ``ToolSelectionError(budget_exceeded)`` telling the user
    to increase the budget; nothing is trimmed silently (D4)."""
    pipeline, llm, agent = _build(
        tool_names=["t1", "t2"],
        allowed=["t1", "t2"],
        enabled=False,
        schema_cap=2,  # tiny cap: any real def exceeds it
    )

    with pytest.raises(ToolSelectionError) as excinfo:
        pipeline.resolve(agent=agent, account_name=ACCOUNT, context_name="none", prompt_text="hi")

    err = excinfo.value
    assert err.code == "budget_exceeded"
    assert err.offending_tools == ["t1", "t2"]
    assert err.message == (
        "The combined tool schemas exceed the configured schema budget "
        "(max_handler_schema_tokens). Offending tools: 't1', 't2'. "
        "Increase the budget for this request or reduce the active tool set."
    )


@pytest.mark.parametrize("cap", [0, -1])
def test_budget_cap_zero_or_negative_disables(cap):
    """``max_handler_schema_tokens <= 0`` disables the budget check entirely."""
    result, _ = _resolve(
        tool_names=["t1", "t2"],
        allowed=["t1", "t2"],
        enabled=False,
        schema_cap=cap,
    )

    assert result.meta["schema_cap"] is None
    assert result.active == ["t1", "t2"]
