"""Curation library — session digest, archive, and filter operations.

Provides the core logic for the `curate_chat` handler and CLI command.
"""

from src.curation.core import CurationEngine
from src.curation.resolver import resolve_session
from src.curation.templates import render_template, resolve_template
from src.curation.summarizer import summarize_session
from src.curation.archiver import archive_session

__all__ = [
    "CurationEngine",
    "resolve_session",
    "render_template",
    "resolve_template",
    "summarize_session",
    "archive_session",
]
