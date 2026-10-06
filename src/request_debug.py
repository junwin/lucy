"""Opt-in diagnostics for comparing explicit and automatically routed turns."""

import hashlib
import json
import logging
import re


logger = logging.getLogger(__name__)
_DATA_URL = re.compile(r"data:[^\s\"']*", re.IGNORECASE)
_TEXT_LIMIT = 20000


def _snapshot(value):
    """Keep prompt text and IDs, never inline image bytes or data URLs."""
    if isinstance(value, dict):
        return {
            str(key): (
                {"omitted": "binary attachment", "length": len(item) if hasattr(item, "__len__") else None}
                if str(key) in {"data", "image_bytes", "base64", "b64_json"}
                else _snapshot(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_snapshot(item) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return {"omitted": "binary attachment", "length": len(value)}
    if isinstance(value, str):
        safe = _DATA_URL.sub("[inline data omitted]", value)
        if len(safe) > _TEXT_LIMIT:
            return {"preview": safe[:_TEXT_LIMIT], "length": len(safe),
                    "sha256": hashlib.sha256(safe.encode("utf-8")).hexdigest(), "truncated": True}
        return safe
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return {"omitted": "unsupported value", "type": type(value).__name__}


def log_request_debug(config, stage, *, correlation_id=None, **details):
    """Emit INFO records only when request_routing_debug is explicitly true.

    These records include private prompt/history text. Enable temporarily for
    diagnosis, then disable. Logging failures must not interrupt a user turn.
    """
    if config.get("request_routing_debug", False) is not True:
        return
    try:
        record = _snapshot({"stage": stage, "correlation_id": correlation_id, **details})
        logger.info("request_routing_debug %s", json.dumps(record, ensure_ascii=True))
    except Exception:
        logger.warning("request_routing_debug snapshot failed", exc_info=True)
