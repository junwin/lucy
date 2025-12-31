# /home/junwin/src/repos/lucy/src/api_helpers.py
import json
import time
import random
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from openai import OpenAI
from openai import RateLimitError, APIError, APITimeoutError, APIConnectionError
from openai import BadRequestError  # helps catch 400s cleanly

from src.config_manager import ConfigManager  # <-- no container import

try:
    import jsonschema  # optional but recommended for schema validation
except Exception:  # pragma: no cover
    jsonschema = None


# -----------------------------------------------------------------------------
# Debug controls
# -----------------------------------------------------------------------------
DEBUG = os.getenv("LUCY_OPENAI_DEBUG", "0") in ("1", "true", "True", "yes", "YES")
DEBUG_FULL = os.getenv("LUCY_OPENAI_DEBUG_FULL", "0") in ("1", "true", "True", "yes", "YES")

# Truncation limits for logs (used when DEBUG_FULL is off)
MAX_STR = int(os.getenv("LUCY_OPENAI_DEBUG_MAX_STR", "1200"))
MAX_JSON = int(os.getenv("LUCY_OPENAI_DEBUG_MAX_JSON", "8000"))


# -----------------------------------------------------------------------------
# Config + client init (NO container import to avoid circular deps)
# -----------------------------------------------------------------------------
_config = ConfigManager("config.json")
credential_path = _config.get("credential_path")

with open(os.path.join(credential_path, "oaicred.json"), "r", encoding="utf-8") as f:
    config_data = json.load(f)

client = OpenAI(api_key=config_data["openai_api_key"])


# -----------------------------------------------------------------------------
# Helpers: safe-ish logging/dumping
# -----------------------------------------------------------------------------
def _truncate(s: Optional[str], limit: int = MAX_STR) -> str:
    if s is None:
        return ""
    if len(s) <= limit:
        return s
    return s[:limit] + f"... <truncated {len(s) - limit} chars>"


def _safe_json(obj: Any, limit: int = MAX_JSON) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        s = repr(obj)
    return s if DEBUG_FULL else _truncate(s, limit)


def _redact_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Redact/truncate message content for debug logging.

    If you later add secrets into message metadata, redact here.
    For now: truncate content unless DEBUG_FULL.
    """
    out: List[Dict[str, Any]] = []
    for m in messages or []:
        mm = dict(m)
        if "content" in mm and isinstance(mm["content"], str) and not DEBUG_FULL:
            mm["content"] = _truncate(mm["content"])
        if "tool_calls" in mm and not DEBUG_FULL:
            mm["tool_calls"] = "<tool_calls truncated>"
        out.append(mm)
    return out


def _log_request(label: str, payload: Dict[str, Any]) -> None:
    """Debug log the outbound OpenAI request payload (redacted)."""
    if not DEBUG:
        return
    logging.debug("[OPENAI REQ] %s payload:\n%s", label, _safe_json(payload))


def _extract_usage_dict(usage_obj: Any) -> Any:
    if usage_obj is None:
        return None
    if hasattr(usage_obj, "to_dict"):
        try:
            return usage_obj.to_dict()
        except Exception:
            return repr(usage_obj)
    if hasattr(usage_obj, "__dict__"):
        try:
            return dict(usage_obj.__dict__)
        except Exception:
            return repr(usage_obj)
    return usage_obj


def _log_response(label: str, resp: Any) -> None:
    """Debug log a summarized OpenAI response (Responses API)."""
    if not DEBUG:
        return

    info: Dict[str, Any] = {}
    try:
        info["id"] = getattr(resp, "id", None)
        info["model"] = getattr(resp, "model", None)
        info["created_at"] = getattr(resp, "created_at", None)
        info["status"] = getattr(resp, "status", None)

        info["usage"] = _extract_usage_dict(getattr(resp, "usage", None))

        # output_text is the simplest “final text” surface
        info["output_text_preview"] = _truncate(getattr(resp, "output_text", "") or "")

        # tool calls live inside resp.output as items with type=="function_call"
        out_items = getattr(resp, "output", None) or []
        info["output_items_count"] = len(out_items)

        tool_calls: List[Dict[str, Any]] = []
        for item in out_items:
            if getattr(item, "type", None) == "function_call":
                tool_calls.append(
                    {
                        "call_id": getattr(item, "call_id", None),
                        "name": getattr(item, "name", None),
                        "arguments_preview": _truncate(getattr(item, "arguments", "") or ""),
                    }
                )

        info["tool_calls_count"] = len(tool_calls)
        if tool_calls:
            info["tool_calls"] = tool_calls

    except Exception as e:
        info["parse_error"] = f"{type(e).__name__}: {e}"
        info["raw_repr"] = repr(resp)

    logging.debug("[OPENAI RESP] %s summary:\n%s", label, _safe_json(info))


def _log_messages_brief(messages: List[Dict[str, Any]], label: str) -> None:
    """Info-level log of message count and last message preview."""
    n = len(messages or [])
    last = messages[-1] if n else {}
    preview = (last.get("content") or "")
    preview = preview.replace("\n", " ")
    if len(preview) > 160:
        preview = preview[:160] + "…"
    logging.info("%s: %d messages; last role=%s; last preview=%r", label, n, last.get("role"), preview)


def _sleep_backoff(attempt: int, base: float, cap: float) -> None:
    """Exponential backoff with jitter for retryable OpenAI errors."""
    delay = min(cap, base * (2 ** attempt))
    delay = delay * (0.6 + random.random() * 0.8)  # jitter 0.6–1.4x
    logging.warning("openai_call: backing off for %.2fs (attempt=%d)", delay, attempt + 1)
    time.sleep(delay)


# -----------------------------------------------------------------------------
# Tools normalization (Responses API)
# -----------------------------------------------------------------------------
def _normalize_tools(functions: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Normalize tool definitions for the Responses API.

    Accepts either:
      A) list of function defs: {"name":..., "description":..., "parameters":...}
      B) list of chat.completions tools: {"type":"function","function":{...}}
      C) already-responses tools: {"type":"function","name":..., "description":..., "parameters":...}

    Returns tools suitable for client.responses.create(tools=...).
    """
    tools: List[Dict[str, Any]] = []
    if not functions:
        if DEBUG:
            logging.debug("[TOOLS] No tools provided.")
        return tools

    for i, item in enumerate(functions):
        if not item:
            if DEBUG:
                logging.debug("[TOOLS] Skipping tool %d: empty/null", i)
            continue

        # B) chat.completions-style tool entry
        if isinstance(item, dict) and item.get("type") == "function" and isinstance(item.get("function"), dict):
            fn_def = item["function"]
        else:
            fn_def = item

        # C) already Responses-style
        if isinstance(fn_def, dict) and fn_def.get("type") == "function" and fn_def.get("name"):
            name = fn_def.get("name")
            parameters = fn_def.get("parameters") or {"type": "object", "properties": {}}
            if not isinstance(parameters, dict):
                parameters = {"type": "object", "properties": {}}

            tools.append(
                {
                    "type": "function",
                    "name": name,
                    "description": fn_def.get("description", "") or "",
                    "parameters": parameters,
                }
            )
            if DEBUG:
                logging.debug("[TOOLS] Accepted Responses-style tool %d name=%s", i, name)
            continue

        # A) plain function def
        if not isinstance(fn_def, dict):
            logging.warning("[TOOLS] Skipping tool %d: not a dict (%r)", i, type(fn_def).__name__)
            continue

        name = fn_def.get("name")
        if not name:
            logging.warning(
                "[TOOLS] Skipping tool %d: missing required function name. keys=%s item=%s",
                i,
                list(fn_def.keys()),
                _safe_json(fn_def),
            )
            continue

        parameters = fn_def.get("parameters")
        if not isinstance(parameters, dict):
            parameters = {"type": "object", "properties": {}}

        tools.append(
            {
                "type": "function",
                "name": name,
                "description": fn_def.get("description", "") or "",
                "parameters": parameters,
            }
        )

        if DEBUG:
            logging.debug("[TOOLS] Accepted tool %d name=%s", i, name)

    if DEBUG:
        logging.debug("[TOOLS] Total accepted tools=%d", len(tools))
        if DEBUG_FULL:
            logging.debug("[TOOLS] tools dump:\n%s", _safe_json(tools))

    return tools


# -----------------------------------------------------------------------------
# Result types
# -----------------------------------------------------------------------------
@dataclass
class SchemaResult:
    ok: bool
    data: Optional[Dict[str, Any]]
    raw_text: str
    errors: List[str]
    schema_name: Optional[str] = None
    schema_version: Optional[str] = None
    response_id: Optional[str] = None


@dataclass
class ToolResult:
    role: str
    content: str
    tool_calls: List[Dict[str, Any]]
    response_id: Optional[str] = None


@dataclass
class TextResult:
    role: str
    content: str
    response_id: Optional[str] = None


# -----------------------------------------------------------------------------
# Schema helpers
# -----------------------------------------------------------------------------
def _extract_text_and_tool_calls(resp: Any) -> Tuple[str, List[Dict[str, Any]]]:
    """Normalize Responses API response into text content + tool_calls list."""
    text = getattr(resp, "output_text", "") or ""

    calls: List[Dict[str, Any]] = []
    for item in getattr(resp, "output", []) or []:
        if getattr(item, "type", None) == "function_call":
            calls.append(
                {
                    # IMPORTANT: this must be the Responses call_id
                    "id": getattr(item, "call_id", None),
                    "type": "function_call",
                    "name": getattr(item, "name", None),
                    "arguments": getattr(item, "arguments", None) or "{}",
                }
            )

    if DEBUG:
        logging.debug("[TOOLS] extracted tool call_ids=%s", [c.get("id") for c in calls])

    return text, calls



def _try_parse_json(text: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    if not text or not text.strip():
        return None, ["Empty response text; cannot parse JSON."]
    try:
        return json.loads(text), []
    except Exception as e:
        return None, [f"JSON parse error: {type(e).__name__}: {e}"]


def _validate_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    if jsonschema is None:
        return ["jsonschema not installed; skipping schema validation."]
    try:
        jsonschema.validate(instance=data, schema=schema)
        return []
    except Exception as e:
        return [f"Schema validation error: {type(e).__name__}: {e}"]


def _log_schema_status(result: SchemaResult) -> None:
    if not DEBUG:
        return
    logging.debug(
        "[SCHEMA] ok=%s name=%s version=%s errors=%s data_preview=%s",
        result.ok,
        result.schema_name,
        result.schema_version,
        result.errors[:3],
        _truncate(_safe_json(result.data, 2000)) if result.data is not None else None,
    )


# -----------------------------------------------------------------------------
# Core API call: one place that knows text vs tools vs schema vs store
# -----------------------------------------------------------------------------
def openai_call(
    *,
    messages: List[Dict[str, Any]],
    model: str = "gpt-4o-mini",
    temperature: float = 0,
    functions: Optional[List[Dict[str, Any]]] = None,
    schema: Optional[Dict[str, Any]] = None,
    schema_name: Optional[str] = None,
    schema_version: Optional[str] = None,
    store: bool = False,
    conversation_id: Optional[str] = None,
    session_id: Optional[str] = None,
    previous_response_id: Optional[str] = None,
    max_attempts: int = 4,
    backoff_base: float = 0.5,
    backoff_cap: float = 8.0,
) -> Union[TextResult, ToolResult, SchemaResult]:
    """Single entry point for OpenAI Responses API."""

    tools = _normalize_tools(functions) if functions else []

    _log_messages_brief(messages, f"openai_call({model})")
    payload = {
        "model": model,
        "temperature": temperature,
        "store": store,
        "previous_response_id": previous_response_id,
        "metadata": {
            "conversation_id": conversation_id,
            "session_id": session_id,
            "schema_name": schema_name,
            "schema_version": schema_version,
        },
        "messages_count": len(messages or []),
        "messages_preview": _redact_messages(messages) if DEBUG else None,
        "tools": tools if (DEBUG and tools) else None,
        "tool_choice": "auto" if tools else None,
        "schema_enabled": bool(schema),
    }
    _log_request("openai_call", payload)

    metadata: Optional[Dict[str, Any]] = None
    if conversation_id or session_id or schema_name or schema_version:
        metadata = {
            "conversation_id": conversation_id,
            "session_id": session_id,
            "schema_name": schema_name,
            "schema_version": schema_version,
        }

    text_cfg: Optional[Dict[str, Any]] = None
    if schema is not None:
        text_cfg = {
            "format": {
                "type": "json_schema",
                "strict": True,
                "schema": schema,
            }
        }

    for attempt in range(max_attempts):
        try:
            resp = client.responses.create(
                model=model,
                input=messages,
                temperature=temperature,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                store=store,
                metadata=metadata,
                previous_response_id=previous_response_id,
                text=text_cfg,
            )

            _log_response(f"openai_call attempt={attempt+1}", resp)

            # ✅ THIS is the id you must propagate back to the processor
            resp_id = getattr(resp, "id", None)

            text, tool_calls = _extract_text_and_tool_calls(resp)

            # -------------------------
            # Schema path
            # -------------------------
            if schema is not None:
                data, parse_errors = _try_parse_json(text)
                errors = list(parse_errors)

                if data is not None:
                    errors.extend(_validate_schema(data, schema))

                ok = (data is not None) and not any("error" in e.lower() for e in errors)

                result = SchemaResult(
                    ok=ok,
                    data=data,
                    raw_text=text,
                    errors=errors,
                    schema_name=schema_name,
                    schema_version=schema_version,
                    response_id=resp_id,  # ✅ propagate
                )
                _log_schema_status(result)
                return result

            # -------------------------
            # Tools path
            # -------------------------
            if tools:
                return ToolResult(
                    role="assistant",
                    content=text,
                    tool_calls=tool_calls,
                    response_id=resp_id,  # ✅ propagate (THIS FIXES YOUR None)
                )

            # -------------------------
            # Text path
            # -------------------------
            return TextResult(
                role="assistant",
                content=text,
                response_id=resp_id,  # ✅ propagate (also helpful)
            )

        except BadRequestError as e:
            logging.error("[OPENAI 400] %s", str(e))
            body = getattr(e, "body", None)
            if body:
                logging.error("[OPENAI 400 BODY]\n%s", _safe_json(body))
            if tools:
                logging.error("[TOOLS NAMES] %s", [t.get("name") for t in tools])
            raise

        except (RateLimitError, APIError, APITimeoutError, APIConnectionError) as e:
            if attempt == max_attempts - 1:
                logging.error(
                    "openai_call: exhausted retries after %d attempts due to %s: %s",
                    max_attempts,
                    type(e).__name__,
                    e,
                )
                raise
            logging.warning(
                "OpenAI error (%s) on attempt %d/%d; will retry.",
                type(e).__name__,
                attempt + 1,
                max_attempts,
            )
            _sleep_backoff(attempt, backoff_base, backoff_cap)

        except Exception as e:
            logging.exception("openai_call: unexpected error: %s", e)
            raise

    raise RuntimeError("openai_call: exhausted retries unexpectedly.")
