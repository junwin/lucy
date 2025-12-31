"""Task list data structures and helpers.

This package defines a minimal, serialisable task list model used by
supervising/worker assistants. The initial implementation is intentionally
simple: a task list is represented as a dictionary containing a list of
per-task dictionaries. The entire structure can be JSON-serialised to a
single string for persistence or inclusion in assistant context.
"""
