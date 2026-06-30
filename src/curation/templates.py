"""Template rendering and resolution for curation digests.

Template resolution order:
1. ContextState override (account-scoped storage-backed template)
2. Config file defaults (shipped with the code)
3. Fallback hardcoded minimal template
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.chat2.models import ChatEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fallback template (hardcoded last resort)
# ---------------------------------------------------------------------------

FALLBACK_TEMPLATE = """# Session Digest: {friendly_name}
- **Session ID**: {session_id}
- **Date**: {date}
- **Account**: {account}

## Summary

{summary_text}

## Key events

{events_bullets}
"""

# ---------------------------------------------------------------------------
# Default config template (shipped with code)
# ---------------------------------------------------------------------------

DEFAULT_SUMMARIZE_TEMPLATE = """# Session Digest: {friendly_name}
- **Session ID**: {session_id}
- **Date**: {date}
- **Account**: {account}

## Decisions made
{decisions}

## Files created/modified
{files}

## Commands run (with outcomes)
{commands}

## Open questions / next steps
{next_steps}
"""

# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

_BUILTIN_TEMPLATES: Dict[str, str] = {
    "default": DEFAULT_SUMMARIZE_TEMPLATE,
    "minimal": FALLBACK_TEMPLATE,
}


def resolve_template(
    template_name: str,
    *,
    context_state_override: Optional[str] = None,
) -> str:
    """Resolve a template by name using the resolution order.

    1. ContextState override (if provided)
    2. Built-in config templates
    3. Fallback hardcoded template

    Args:
        template_name: Name of the template to resolve.
        context_state_override: Optional template content from ContextState.

    Returns:
        Template string.
    """
    # 1) ContextState override
    if context_state_override:
        logger.info(
            "template_resolved source=context_state template_name=%s",
            template_name,
        )
        return context_state_override

    # 2) Built-in config templates
    if template_name in _BUILTIN_TEMPLATES:
        logger.info(
            "template_resolved source=config template_name=%s",
            template_name,
        )
        return _BUILTIN_TEMPLATES[template_name]

    # 3) Fallback
    logger.info(
        "template_resolved source=fallback template_name=%s (not found in config)",
        template_name,
    )
    return FALLBACK_TEMPLATE


def render_template(
    template: str,
    *,
    friendly_name: str = "",
    session_id: str = "",
    account: str = "",
    events: Optional[List[ChatEvent]] = None,
    summary_text: str = "",
    decisions: str = "",
    files: str = "",
    commands: str = "",
    next_steps: str = "",
    **extra: Any,
) -> str:
    """Render a template with the given values.

    Supports {placeholder} substitution. Unknown placeholders are left as-is.

    Args:
        template: Template string with {placeholders}.
        friendly_name: Session friendly name.
        session_id: Session UUID.
        account: Account name.
        events: List of ChatEvent objects (used to build events_bullets).
        summary_text: Free-text summary.
        decisions: Decisions made section content.
        files: Files created/modified section content.
        commands: Commands run section content.
        next_steps: Open questions / next steps.
        **extra: Additional placeholder values.

    Returns:
        Rendered Markdown string.
    """
    now = datetime.now(timezone.utc)

    # Build events_bullets from events list
    events_bullets = ""
    if events:
        bullets = []
        for e in events:
            payload_str = str(e.payload) if isinstance(e.payload, str) else str(e.payload)
            snippet = payload_str[:120].replace("\n", " ")
            bullets.append(f"- **[{e.role}]** ({e.kind}): {snippet}")
        events_bullets = "\n".join(bullets)

    context = {
        "friendly_name": friendly_name or "Untitled",
        "session_id": session_id,
        "date": now.strftime("%Y-%m-%d %H:%M UTC"),
        "account": account,
        "summary_text": summary_text,
        "events_bullets": events_bullets,
        "decisions": decisions,
        "files": files,
        "commands": commands,
        "next_steps": next_steps,
        **extra,
    }

    try:
        return template.format(**context)
    except KeyError as e:
        logger.warning("render_template: missing placeholder %s — rendering with partial context", e)
        # Best-effort: replace known placeholders, leave unknown ones
        result = template
        for key, value in context.items():
            result = result.replace("{" + key + "}", str(value))
        return result
