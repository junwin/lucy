"""Regression for issue #190: large sessions must keep the newest events."""

from types import SimpleNamespace

from src.curation.summarizer import _build_events_text


def _event(text):
    return SimpleNamespace(
        created_at=None, role="user", actor="user",
        kind="message", content=text,
    )


def test_curation_budget_keeps_recent_events_in_chronological_order():
    events = [_event("old " + "a" * 100), _event("middle"), _event("newest")]
    rendered = _build_events_text(events, max_chars=100)
    assert len(rendered) <= 100
    assert "old " not in rendered
    assert rendered.index("middle") < rendered.index("newest")
    assert rendered.startswith("... (older events omitted)")


def test_single_recent_event_is_bounded_even_with_tiny_budget():
    rendered = _build_events_text([_event("x" * 500)], max_chars=20)
    assert len(rendered) == 20


def test_no_truncation_preserves_all_events():
    rendered = _build_events_text([_event("first"), _event("last")], max_chars=1000)
    assert "first" in rendered and "last" in rendered
    assert "omitted" not in rendered
