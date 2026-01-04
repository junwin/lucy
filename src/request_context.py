"""Request-scoped context utilities.

This module provides request_id correlation via contextvars.

The request_id is set at request start (see app.py) and can be used anywhere
in-process. Logging is configured with a Filter that injects request_id into
every LogRecord.
"""

from __future__ import annotations

import contextvars

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
