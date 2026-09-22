from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Optional

DIGEST_HEX_LENGTH = 16

ERROR_CODE_SECURITY_REFUSAL = "security_refusal"
ERROR_CODE_UNKNOWN_TOOL = "unknown_tool"
ERROR_CODE_TOOL_HANDLER_ERROR = "tool_handler_error"
ERROR_CODE_RESULT_TOO_LARGE = "result_too_large"
ERROR_CODE_OTHER = "other"

_ERROR_TEXT_KEYS = ("error", "message", "detail")

_SECURITY_RESULT_CODES = frozenset(
    {"policy_refused", "embedded_shell_refused", "permission_denied"}
)
_SECURITY_TEXT_MARKERS = (
    "security policy",
    "outside allowed base path",
    "permission denied",
    "not permitted",
    "not allowed",
)
_TOO_LARGE_TEXT_MARKERS = ("too large",)
_UNKNOWN_TOOL_TEXT_MARKERS = ("unknown tool",)
_HANDLER_TEXT_MARKERS = ("tool returned none", "tool result not serializable")
_HANDLER_EXCEPTION_PREFIX = re.compile(r"^[a-z_][a-z0-9_]*(error|exception)\b")
_WHITESPACE = re.compile(r"\s+")
_TRAILING_PUNCTUATION = ".,;:!?"


def _sorted(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sorted(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sorted(item) for item in value]
    return value


def normalize_args(args_raw: str) -> str:
    try:
        parsed = json.loads(args_raw)
    except (TypeError, ValueError):
        return args_raw

    return json.dumps(
        _sorted(parsed),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def args_digest(args_raw: str) -> str:
    normalized = normalize_args(args_raw)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:DIGEST_HEX_LENGTH]


def _result_error_text(parsed: Any) -> str:
    if not isinstance(parsed, dict):
        return ""

    for key in _ERROR_TEXT_KEYS:
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            return value

    return ""


def _contains_marker(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def error_code(result_text: str) -> Optional[str]:
    try:
        parsed = json.loads(result_text)
    except (TypeError, ValueError):
        return None

    if not isinstance(parsed, dict) or parsed.get("ok") is not False:
        return None

    text = _result_error_text(parsed).lower()
    raw_result_code = parsed.get("error_code")
    result_code = raw_result_code.lower() if isinstance(raw_result_code, str) else ""

    if _contains_marker(text, _TOO_LARGE_TEXT_MARKERS):
        return ERROR_CODE_RESULT_TOO_LARGE
    if _contains_marker(text, _UNKNOWN_TOOL_TEXT_MARKERS):
        return ERROR_CODE_UNKNOWN_TOOL
    if result_code in _SECURITY_RESULT_CODES or _contains_marker(text, _SECURITY_TEXT_MARKERS):
        return ERROR_CODE_SECURITY_REFUSAL
    if _contains_marker(text, _HANDLER_TEXT_MARKERS) or _HANDLER_EXCEPTION_PREFIX.match(text):
        return ERROR_CODE_TOOL_HANDLER_ERROR

    return ERROR_CODE_OTHER


def _normalize_error_text(error_text: str) -> str:
    collapsed = _WHITESPACE.sub(" ", (error_text or "").lower()).strip()
    return collapsed.rstrip(_TRAILING_PUNCTUATION).strip()


def error_signature(error_text: str) -> Optional[str]:
    normalized = _normalize_error_text(error_text)
    if not normalized:
        return None

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:DIGEST_HEX_LENGTH]
