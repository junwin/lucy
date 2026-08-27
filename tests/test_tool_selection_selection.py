"""Selection-stage unit tests for the tool selection pipeline (issue #126, design §5.4/§8).

Exercises ``selection.suggest_tools`` directly (prompt build + JSON parse +
clamp) and the stage-6 behaviours through ``ToolSelectionPipeline.resolve()``:

- LLM failure falls back to required-only and records ``meta['selection_error']`` (D5).
- the "too small to bother" skip threshold, ``len(eligible) <
  min_eligible_to_select``, skips the LLM call and keeps the full eligible
  set active (D6).
- ``lazy_tool_loading.enabled=false`` skips the LLM call and keeps the full
  eligible set active (D7).

Fakes only (``FakeLLM``, ``FakeRegistry``, ``FakeStorage``, ``FakeConfig``)
— no live LLM. The ``FakeLLM`` records every ``call_model`` so the skip
paths can be asserted on the recorded call count.

Coverage (tasklist ts5, design §8 step 6):

- valid JSON array → parsed, clamped, eligible order preserved.
- garbage text → empty suggestion (no crash, no invented names).
- names not in eligible → clamped away; result follows eligible order.
- empty result → ``[]`` suggestion.
- LLM raises → ``suggest_tools`` surfaces the exception so the pipeline can
  fall back to required-only (asserted both at ``suggest_tools`` level and
  through the pipeline per D5).
- skip threshold: ``len(eligible) < min_eligible_to_select`` → no LLM call,
  active = eligible (D6).
- disabled toggle: ``lazy_tool_loading.enabled=false`` → no LLM call,
  active = eligible (D7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import pytest

from src.storage.models import Context
from src.tool_selection import ToolSelectionPipeline
from src.tool_selection.selection import suggest_tools
from tests.conftest import FakeConfig, FakeRegistry, FakeStorage

ACCOUNT = "acct"
CONTEXT_ID = "ctx"


# ---------------------------------------------------------------------------
# Fakes (no live LLM)
# ---------------------------------------------------------------------------


@dataclass
class FakeLLM:
    """Duck-typed LLM adapter that records every ``call_model`` call.

    Mirrors the adapter contract used by ``pipeline.resolve_llm_target``
    (``call_model`` + ``get_text``) and doubles as a ``llm_call`` callable
    for direct ``suggest_tools`` tests. ``exc`` (optional) makes the next
    ``call_model`` raise, simulating a selection-LLM failure (D5).
    """

    reply: str = "[]"
    exc: Optional[BaseException] = None
    calls: List[Dict[str, Any]] = field(default_factory=list)

    def call_model(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return ("response", kwargs)

    def get_text(self, response: Any) -> str:
        return self.reply

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def llm_call(self, messages: List[Dict[str, str]]) -> str:
        """``selection.suggest_tools``-style callable: messages in, text out."""
        response = self.call_model(
            model="test-model",
            input=messages,
            temperature=0.0,
            provider=None,
        )
        return self.get_text(response)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _defs(*names: str) -> List[Dict[str, Any]]:
    """Tool defs with a description long enough for the menu tests."""
    return [
        {
            "name": name,
            "description": f"{name} does things",
            "parameters": {"type": "object", "properties": {}},
        }
        for name in names
    ]


def _make_context(mandatory_tools: Optional[List[str]] = None) -> Context:
    return Context(
        id=CONTEXT_ID,
        account_name=ACCOUNT,
        updated_at=datetime.now(timezone.utc),
        mandatory_tools=list(mandatory_tools or []),
        resolved_skills=[],
    )


def _suggest(
    prompt_text: str,
    defs: List[Dict[str, Any]],
    *,
    reply: str = "[]",
    exc: Optional[BaseException] = None,
) -> Tuple[List[str], Dict[str, Any], FakeLLM]:
    llm = FakeLLM(reply=reply, exc=exc)
    selected, meta = suggest_tools(
        prompt_text,
        defs,
        llm_call=llm.llm_call,
        model="test-model",
        provider=None,
    )
    return selected, meta, llm


def _resolve(
    *,
    tool_names: List[str],
    allowed: Optional[List[str]] = None,
    context: Any = None,
    reply: str = "[]",
    exc: Optional[BaseException] = None,
    enabled: bool = True,
    min_eligible: int = 1,
    prompt_text: str = "do something",
) -> Tuple[Any, FakeLLM]:
    registry = FakeRegistry(tool_defs=_defs(*tool_names))
    storage = FakeStorage()
    if context is not None:
        storage.save_context(context)
    llm = FakeLLM(reply=reply, exc=exc)
    config = FakeConfig(
        values={
            "lazy_tool_loading": {
                "enabled": enabled,
                "min_eligible_to_select": min_eligible,
            },
        }
    )
    agent = SimpleNamespace(allowed_tools=allowed, model="test-model", provider=None)
    pipeline = ToolSelectionPipeline(
        registry=registry,
        storage=storage,
        llm_adapter=llm,
        config=config,
    )
    result = pipeline.resolve(
        agent=agent,
        account_name=ACCOUNT,
        context_name=CONTEXT_ID,
        prompt_text=prompt_text,
    )
    return result, llm


# ---------------------------------------------------------------------------
# suggest_tools — prompt build, JSON parse, clamp (design §5.4)
# ---------------------------------------------------------------------------


def test_suggest_valid_json_array_parsed_and_clamped_in_eligible_order():
    """A valid JSON array is parsed; the result follows eligible order, not
    reply order (deterministic clamp, design §5.4)."""
    selected, meta, llm = _suggest(
        "read and save the file",
        _defs("file_load", "file_save", "execute_command"),
        reply='["file_save", "file_load"]',
    )

    assert llm.call_count == 1
    assert selected == ["file_load", "file_save"]  # eligible order, deduped
    assert meta["selected_raw"] == ["file_save", "file_load"]
    assert meta["selected_tools"] == ["file_load", "file_save"]
    assert meta["eligible_tools"] == ["file_load", "file_save", "execute_command"]
    assert meta["eligible_count"] == 3
    assert meta["model"] == "test-model"
    assert meta["provider"] is None


@pytest.mark.parametrize(
    "reply",
    [
        "I don't know what tools to use.",
        "Sure! Here is the answer: maybe use the file one?",
        "No tools. Just do it yourself.",
    ],
)
def test_suggest_garbage_text_yields_empty_suggestion(reply):
    """Garbage (non-JSON, no quoted names) parses to nothing — no crash, no
    invented names."""
    selected, meta, llm = _suggest("do something", _defs("file_load", "file_save"), reply=reply)

    assert llm.call_count == 1
    assert selected == []
    assert meta["selected_raw"] == []


def test_suggest_names_not_in_eligible_are_clamped():
    """Names the LLM invents are clamped away; duplicates collapse (design
    §5.4)."""
    selected, meta, llm = _suggest(
        "do something",
        _defs("file_load", "file_save", "execute_command"),
        reply='["ghost_tool", "file_save", "nope", "file_save"]',
    )

    assert llm.call_count == 1
    assert selected == ["file_save"]
    assert meta["selected_raw"] == ["ghost_tool", "file_save", "nope", "file_save"]
    assert meta["selected_tools"] == ["file_save"]


def test_suggest_clamped_result_follows_eligible_order():
    """Even when the reply lists valid names out of order, the clamped result
    preserves eligible (registry) order."""
    selected, _, llm = _suggest(
        "search and save",
        _defs("file_load", "file_save", "execute_command", "web_search_handler"),
        reply='["web_search_handler", "file_save"]',
    )

    assert llm.call_count == 1
    assert selected == ["file_save", "web_search_handler"]


def test_suggest_empty_result():
    """The LLM may legitimately suggest no tools; the result is an empty
    list (empty-result behaviour lives in the pipeline)."""
    selected, meta, llm = _suggest("do something", _defs("file_load", "file_save"), reply="[]")

    assert llm.call_count == 1
    assert selected == []
    assert meta["selected_raw"] == []
    assert meta["selected_tools"] == []


def test_suggest_llm_exception_surfaces_for_pipeline_to_handle():
    """A raising LLM propagates out of ``suggest_tools`` so the pipeline can
    fall back to required-only per D5 (never swallowed here)."""
    llm = FakeLLM(reply="[]", exc=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
        suggest_tools(
            "do something",
            _defs("file_load", "file_save"),
            llm_call=llm.llm_call,
            model="test-model",
            provider=None,
        )

    assert llm.call_count == 1  # the call was attempted and failed


def test_suggest_empty_eligible_never_calls_llm():
    """Nothing to choose from ⇒ the LLM is never called with an empty menu."""
    selected, meta, llm = _suggest("do something", [])

    assert llm.call_count == 0
    assert selected == []
    assert meta["eligible_count"] == 0


def test_suggest_builds_compact_name_first_sentence_menu():
    """Stage 6 sends a compact 'name — first sentence of description' menu,
    not full schemas (design §5.4)."""
    defs = [
        {
            "name": "t1",
            "description": "Does the thing. And then another thing.",
            "parameters": {},
        },
        {"name": "t2", "description": "", "parameters": {}},
    ]
    llm = FakeLLM(reply="[]")
    suggest_tools(
        "read the file",
        defs,
        llm_call=llm.llm_call,
        model="test-model",
        provider=None,
    )

    assert llm.call_count == 1
    messages = llm.calls[0]["input"]
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "tool router" in messages[0]["content"]
    user = messages[1]["content"]
    assert "- t1: Does the thing." in user            # first sentence only
    assert "And then another thing" not in user       # second sentence cut
    assert "- t2: (no description)" in user           # empty description fallback
    assert "REQUEST:\nread the file" in user


# ---------------------------------------------------------------------------
# Pipeline stage 6 — fallback (D5), skip threshold (D6), toggle (D7)
# ---------------------------------------------------------------------------


def test_pipeline_valid_json_suggestion_unions_with_required():
    """End-to-end: a valid JSON suggestion is clamped to eligible and unioned
    with the required tools (required first)."""
    ctx = _make_context(mandatory_tools=["file_load"])
    result, llm = _resolve(
        tool_names=["file_load", "file_save", "execute_command", "web_search_handler"],
        allowed=["file_load", "file_save", "execute_command", "web_search_handler"],
        context=ctx,
        reply='["web_search_handler", "file_save"]',
    )

    assert llm.call_count == 1
    assert result.prompt_based == ["file_save", "web_search_handler"]  # eligible order
    assert result.active == ["file_load", "file_save", "web_search_handler"]
    assert result.meta["selection"]["skipped"] is False


def test_pipeline_garbage_reply_yields_required_only():
    """Garbage reply ⇒ empty suggestion ⇒ the active set degrades to the
    required tools only (never the full eligible set)."""
    ctx = _make_context(mandatory_tools=["file_load"])
    result, llm = _resolve(
        tool_names=["file_load", "file_save"],
        allowed=["file_load", "file_save"],
        context=ctx,
        reply="sorry, I cannot pick tools",
    )

    assert llm.call_count == 1
    assert result.prompt_based == []
    assert result.active == ["file_load"]


def test_pipeline_llm_raises_falls_back_to_required_only():
    """Any selection-LLM failure falls back to required-only and is recorded
    in ``meta['selection_error']`` (D5) — the pipeline never crashes."""
    ctx = _make_context(mandatory_tools=["file_load"])
    result, llm = _resolve(
        tool_names=["file_load", "file_save", "execute_command"],
        allowed=["file_load", "file_save", "execute_command"],
        context=ctx,
        exc=RuntimeError("boom"),
    )

    assert llm.call_count == 1  # the selection LLM was attempted, then failed
    assert result.prompt_based == []
    assert result.active == ["file_load"]  # required-only, NOT full eligible
    assert result.meta["selection"]["skipped"] is False
    assert "error" in result.meta["selection"]
    assert "RuntimeError" in result.meta["selection_error"]
    assert "boom" in result.meta["selection_error"]


def test_pipeline_below_min_eligible_skips_llm_call():
    """``len(eligible) < min_eligible_to_select`` ⇒ no LLM call; the full
    eligible set stays active (D6)."""
    result, llm = _resolve(
        tool_names=["t1", "t2", "t3"],
        allowed=["t1", "t2", "t3"],
        min_eligible=5,  # 3 eligible < 5 ⇒ skip
    )

    assert llm.call_count == 0
    assert result.prompt_based == []
    assert result.meta["selection"]["skipped"] is True
    assert result.meta["selection"]["reason"] == "below_threshold"
    assert result.meta["selection"]["min_eligible_to_select"] == 5
    assert result.meta["selection"]["eligible_count"] == 3
    assert result.active == ["t1", "t2", "t3"]  # full eligible (D6)


def test_pipeline_selection_disabled_skips_llm_call_and_active_is_eligible():
    """``lazy_tool_loading.enabled=false`` ⇒ no LLM call and
    active = eligible (D7)."""
    result, llm = _resolve(
        tool_names=["t1", "t2", "t3"],
        allowed=["t1", "t2", "t3"],
        enabled=False,
    )

    assert llm.call_count == 0
    assert result.prompt_based == []
    assert result.meta["selection"]["skipped"] is True
    assert result.meta["selection"]["reason"] == "disabled"
    assert result.active == ["t1", "t2", "t3"]  # active = eligible (D7)
