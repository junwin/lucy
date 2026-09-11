from types import SimpleNamespace
from unittest.mock import Mock

from src.prompt_builders.history_selector import HistorySelector
from src.prompt_builders.prompt_sections import PromptSections
from src.prompt_builders.token_budget import TokenBudgetAllocator, estimate_tokens_from_text


class FakeConfig:
    def get(self, key, default=None):
        return default


def test_estimate_tokens_preserves_prompt_builder_heuristic():
    assert estimate_tokens_from_text("") == 0
    assert estimate_tokens_from_text("abc") == 1
    assert estimate_tokens_from_text("abcdefgh") == 2


def test_token_budget_allocator_preserves_breakdown_keys():
    allocator = TokenBudgetAllocator(FakeConfig())
    agent = SimpleNamespace(prompt_budget_max_tokens=None)
    budget = allocator.allocate_history_budget(
        agent=agent,
        system_text_parts=["system"],
        context_text="context",
        document_text="document",
        digest_text="digest",
        user_text="question",
    )
    breakdown = allocator.build_breakdown(
        budget=budget,
        history_messages=[{"role": "assistant", "content": "answer"}],
        overflow_digest_text="older",
    )
    assert list(breakdown) == [
        "system_session",
        "context_text",
        "obsidian_notes",
        "digest_embeddings",
        "chat_history",
        "overflow_digest",
        "current_user_message",
        "total_without_handlers",
    ]


def test_history_selector_keeps_newest_events_that_fit_budget():
    selector = HistorySelector()
    older = SimpleNamespace(role="user", content="a" * 40)
    newer = SimpleNamespace(role="assistant", content="b" * 8)
    episodic = SimpleNamespace(events=[older, newer], dropped_event_count=0)
    messages = []
    saved = Mock(return_value="saved summary")

    selected, overflow = selector.select(
        episodic_result=episodic,
        max_convs=2,
        history_budget=2,
        messages=messages,
        account_name="john",
        conversation_id="session-1",
        agent_name="peace",
        summarize_overflow=lambda texts: "summary",
        save_overflow_digest=saved,
    )

    assert selected == [{"role": "assistant", "content": "b" * 8}]
    assert overflow == "saved summary"
    assert messages[-1] == {"role": "system", "content": "Earlier in this session:\nsaved summary"}


def test_prompt_sections_render_document_context_unchanged():
    messages = []
    PromptSections.append_document_contexts(
        messages,
        [
            {
                "title": "Note",
                "tags": ["lucy", "design"],
                "snippet": "body",
                "truncated": True,
            }
        ],
    )
    assert messages == [
        {
            "role": "system",
            "content": (
                "The following Obsidian notes may be relevant to the user's question:\n"
                "1. Title: Note | Tags: lucy, design\n"
                "body\n"
                "[Note: content truncated]"
            ),
        }
    ]
