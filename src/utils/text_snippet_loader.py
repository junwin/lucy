from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple


DEFAULT_MAX_CHARS = 2000  # default maximum characters to load from a text file


def load_text_snippet(path: str | Path, max_chars: int = DEFAULT_MAX_CHARS) -> Tuple[str, bool]:
    """Load a text file and return at most ``max_chars`` characters.

    Args:
        path: Path to the text file.
        max_chars: Maximum number of characters to return.

    Returns:
        (snippet, truncated):
            snippet: The text content (possibly truncated).
            truncated: True if the file was longer than ``max_chars``.
    """
    p = Path(path).expanduser()
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logging.warning("Failed to read text file %s: %s", p, e)
        return "", False

    if len(text) <= max_chars:
        return text, False

    return text[:max_chars], True
