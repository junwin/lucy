"""Bounded edit diagnostics, separate from the ordinary 200-character preview."""
from __future__ import annotations

import json
import logging


def _bounded(value, limit):
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"... [truncated, {len(value)} chars]"
    return value


def log_edit_diagnostic(tool, args, outcome, *, correlation_id, call_id):
    if tool not in {"patch_apply", "text_replace"}:
        return
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (ValueError, TypeError):
            args = {}
    if not isinstance(args, dict):
        args = {}
    parameters = {key: _bounded(args[key], 16000 if key == "patch_content" else 2000)
                  for key in ("external_root", "path", "patch_content", "old_text", "new_text", "check_only")
                  if key in args}
    result = {key: _bounded(outcome[key], 4000)
              for key in ("ok", "applied", "error_code", "error", "details", "stderr", "stdout",
                          "strip_components", "match_count", "diff", "diff_truncated") if key in outcome}
    logging.info("tool_edit_diagnostic correlation_id=%s tool=%s call_id=%s diagnostic=%r",
                 correlation_id, tool, call_id,
                 json.dumps({"parameters": parameters, "result": result}, ensure_ascii=True))
