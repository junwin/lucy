from src.prompt_builders.prompt_sections import PromptSections


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
