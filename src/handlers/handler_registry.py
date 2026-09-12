"""Compatibility imports for the canonical galet-tools registry.

New code should import these names from galet_tools. Keeping this module
preserves Lucy's existing imports while ensuring there is only one registry
implementation.
"""

from galet_tools.framework.handler_registry import (
    HandlerRegistry,
    _context_tool_list,
    filter_eligible_tool_defs,
)

__all__ = [
    "HandlerRegistry",
    "filter_eligible_tool_defs",
]
