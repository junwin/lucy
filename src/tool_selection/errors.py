"""Typed error for the tool selection pipeline (issue #126, design doc §6).

``ToolSelectionError`` is the single error type the pipeline raises. It carries
a machine-readable ``code`` plus a human-readable ``message`` that callers
(the FCP, streaming SSE, the probe handler) can surface directly to the user.

Dependency-free by design: stdlib only, no imports from the rest of the repo.
"""

from __future__ import annotations

from typing import List, Literal, Sequence, Union

# The only codes ToolSelectionError may carry (design doc §6).
ToolSelectionCode = Literal[
    "required_not_permissioned",
    "required_not_registered",
    "budget_exceeded",
]

VALID_CODES: frozenset = frozenset(
    {"required_not_permissioned", "required_not_registered", "budget_exceeded"}
)

# Default human-readable templates per code. ``{tools}`` is replaced with the
# quoted list of offending tool names (or "(none)" when empty).
_DEFAULT_TEMPLATES = {
    "required_not_permissioned": (
        "Required tools not permissioned for this agent: {tools}. "
        "The agent is not allowed to use them; add them to the agent's "
        "allowed_tools or remove them from the context's required_tools."
    ),
    "required_not_registered": (
        "Required tools are not registered handlers: {tools}. "
        "These tools are unknown to the system; register the handler or fix "
        "the context's required_tools."
    ),
    "budget_exceeded": (
        "The combined tool schemas exceed the configured schema budget "
        "(max_handler_schema_tokens). Offending tools: {tools}. "
        "Increase the budget for this request or reduce the active tool set."
    ),
}

__all__ = ["ToolSelectionError", "ToolSelectionCode", "VALID_CODES"]


def _format_tools(tools: Sequence[str]) -> str:
    names = [str(t).strip() for t in tools if str(t).strip()]
    if not names:
        return "(none)"
    return ", ".join(f"'{n}'" for n in names)


class ToolSelectionError(Exception):
    """Raised by the tool selection pipeline (design doc §6).

    Construct with either form::

        ToolSelectionError("required_not_permissioned", ["file_load", "file_save"])
        ToolSelectionError("budget_exceeded", "Active schemas are 12000 tokens; cap is 8000.")

    A list of tool names builds a human-readable message listing the offending
    tools; a string is used as the message verbatim.

    Attributes:
        code: one of ``VALID_CODES``.
        offending_tools: offending tool names (empty when constructed with a
            message or no second argument).
        message: the human-readable message (also available via ``str(exc)``).
    """

    def __init__(
        self,
        code: ToolSelectionCode,
        message_or_tools: Union[str, Sequence[str], None] = None,
    ) -> None:
        if code not in VALID_CODES:
            raise ValueError(
                f"invalid ToolSelectionError code: {code!r}; "
                f"expected one of {sorted(VALID_CODES)}"
            )
        self.code = code
        self.offending_tools: List[str] = []
        if isinstance(message_or_tools, str):
            message = message_or_tools
        elif message_or_tools is None:
            message = _DEFAULT_TEMPLATES[code].format(tools="(none)")
        else:
            try:
                tools = [str(t).strip() for t in message_or_tools if str(t).strip()]
            except TypeError:
                tools = []
            self.offending_tools = tools
            message = _DEFAULT_TEMPLATES[code].format(tools=_format_tools(tools))
        self.message = message
        super().__init__(message)
