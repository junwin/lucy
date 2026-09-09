"""Template rendering and resolution for curation digests.

Template resolution order:
1. Context override (account-scoped storage-backed template)
2. Config file defaults (shipped with the code)
3. Fallback hardcoded minimal template
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.coala_memory.episodic import EpisodicEvent

logger = logging.getLogger(__name__)

FALLBACK_TEMPLATE = """# Session Digest: {friendly_name}
- **Session ID**: {session_id}
- **Date**: {date}
- **Account**: {account}
- **Source**: {archive_path}

## Summary

{summary_text}

## Key events

{events_bullets}
"""

DEFAULT_SUMMARIZE_TEMPLATE = """# Session Digest: {friendly_name}
- **Session ID**: {session_id}
- **Date**: {date}
- **Account**: {account}
- **Source**: {archive_path}

{summary_text}
"""

_BUILTIN_TEMPLATES: Dict[str, str] = {
    "default": DEFAULT_SUMMARIZE_TEMPLATE,
    "minimal": FALLBACK_TEMPLATE,
}


def resolve_template(
    template_name: str,
    *,
    context_state_override: Optional[str] = None,
) -> str:
    """Resolve a template by name using the resolution order."""
    if context_state_override:
        logger.info(
            "template_resolved source=context_state template_name=%s",
            template_name,
        )
        return context_state_override

    if template_name in _BUILTIN_TEMPLATES:
        logger.info(
            "template_resolved source=config template_name=%s",
            template_name,
        )
        return _BUILTIN_TEMPLATES[template_name]

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
    archive_path: str = "",
    events: Optional[List[EpisodicEvent]] = None,
    summary_text: str = "",
    decisions: str = "",
    files: str = "",
    commands: str = "",
    next_steps: str = "",
    **extra: Any,
) -> str:
    """Render a curation template from provider-neutral episodic events."""
    now = datetime.now(timezone.utc)

    events_bullets = ""
    if events:
        bullets = []
        for event in events:
            content = str(event.content)
            snippet = content[:120].replace("\n", " ")
            bullets.append(f"- **[{event.role}]** ({event.kind}): {snippet}")
        events_bullets = "\n".join(bullets)

    context = {
        "friendly_name": friendly_name or "Untitled",
        "session_id": session_id,
        "date": now.strftime("%Y-%m-%d %H:%M UTC"),
        "account": account,
        "archive_path": archive_path,
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
    except KeyError as exc:
        logger.warning(
            "render_template: missing placeholder %s — rendering with partial context",
            exc,
        )
        result = template
        for key, value in context.items():
            result = result.replace("{" + key + "}", str(value))
        return result
