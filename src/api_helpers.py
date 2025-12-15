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
    """
    If you later add secrets into message metadata, redact here.
    For now: truncate content unless DEBUG_FULL.
    """
    out: List[Dict[str, Any]] = []
    for m in messages or []:
        mm = dict(m)
        if "content" in mm and isinstance(mm["content"], str) and not DEBUG_FULL:
            mm["content"] = _truncate(mm["content"])
        # tool call arguments can be enormous; truncate unless DEBUG_FULL
        if "tool_calls" in mm and not DEBUG_FULL:
            mm["tool_calls"] = "<tool_calls truncated>"
        out.append(mm)
    return out


def _log_request(label: str, payload: Dict[str, Any]) -> None:
    if not DEBUG:
        return
    logging.debug("[OPENAI REQ] %s payload:\n%s", label, _safe_json(payload))


def _log_response(label: str, resp: Any) -> None:
    if not DEBUG:
        return

    info: Dict[str, Any] = {}
    try:
        info["id"] = getattr(resp, "id", None)
        info["model"] = getattr(resp, "model", None)
        info["created"] = getattr(resp, "created", None)

        usage = getattr(resp, "usage", None)
        if usage is not None:
            if hasattr(usage, "to_dict"):
                info["usage"] = usage.to_dict()
            elif hasattr(usage, "__dict__"):
                info["usage"] = dict(usage.__dict__)
            else:
                info["usage"] = usage

        choices = getattr(resp, "choices", None)
        if choices:
            info["choices_count"] = len(choices)
            msg = choices[0].message
            info["first_choice_role"] = getattr(msg, "role", None)
            info["first_choice_content_preview"] = _truncate(getattr(msg, "content", "") or "")

            tcs = getattr(msg, "tool_calls", None)
            if tcs:
                info["first_choice_tool_calls_count"] = len(tcs)
                info["first_choice_tool_calls"] = [
                    {
                        "id": getattr(tc, "id", None),
                        "type": getattr(tc, "type", None),
                        "function_name": getattr(getattr(tc, "function", None), "name", None),
                        "arguments_preview": _truncate(getattr(getattr(tc, "function", None), "arguments", "") or ""),
                    }
                    for tc in tcs
                ]
            else:
                info["first_choice_tool_calls_count"] = 0

    except Exception as e:
        info["parse_error"] = f"{type(e).__name__}: {e}"
        info["raw_repr"] = repr(resp)

    logging.debug("[OPENAI RESP] %s summary:\n%s", label, _safe_json(info))


def _log_messages_brief(messages: List[Dict[str, Any]], label: str) -> None:
    n = len(messages or [])
    last = messages[-1] if n else {}
    preview = (last.get("content") or "")
    preview = preview.replace("\n", " ")
    if len(preview) > 160:
        preview = preview[:160] + "…"
    logging.info("%s: %d messages; last role=%s; last preview=%r", label, n, last.get("role"), preview)


def _sleep_backoff(attempt: int, base: float, cap: float) -> None:
    delay = min(cap, base * (2 ** attempt))
    delay = delay * (0.6 + random.random() * 0.8)  # jitter 0.6–1.4x
    time.sleep(delay)


def _normalize_tools(functions: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Accepts either:
      A) list of function defs: {"name":..., "description":..., "parameters":...}
      B) list of tools entries: {"type":"function","function":{...}}
    Returns a clean tools=[] list suitable for chat.completions.create(tools=...).

    Logs exactly what was accepted/skipped.
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

        if isinstance(item, dict) and item.get("type") == "function" and isinstance(item.get("function"), dict):
            fn_def = item["function"]
        else:
            fn_def = item

        if not isinstance(fn_def, dict):
            logging.warning("[TOOLS] Skipping tool %d: not a dict (%r)", i, type(fn_def).__name__)
            continue

        name = fn_def.get("name")
        if not name:
            logging.warning(
                "[TOOLS] Skipping tool %d: missing required function.name. keys=%s item=%s",
                i,
                list(fn_def.keys()),
                _safe_json(fn_def),
            )
            continue

        parameters = fn_def.get("parameters")
        if not isinstance(parameters, dict):
            parameters = {"type": "object", "properties": {}}

        tool_obj = {
            "type": "function",
            "function": {
                "name": name,
                "description": fn_def.get("description", "") or "",
                "parameters": parameters,
            },
        }
        tools.append(tool_obj)

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


@dataclass
class ToolResult:
    role: str
    content: str
    tool_calls: List[Dict[str, Any]]  # normalized list of dicts


@dataclass
class TextResult:
    role: str
    content: str


# -----------------------------------------------------------------------------
# Schema helpers
# -----------------------------------------------------------------------------
def _extract_text_and_tool_calls(resp: Any) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Normalize SDK response into:
      - text content (may be empty)
      - tool_calls list (normalized dicts)
    """
    msg = resp.choices[0].message
    text = msg.content or ""

    calls: List[Dict[str, Any]] = []
    tcs = getattr(msg, "tool_calls", None) or []
    for tc in tcs:
        fn = getattr(tc, "function", None)
        calls.append(
            {
                "id": getattr(tc, "id", None),
                "type": getattr(tc, "type", None),
                "name": getattr(fn, "name", None),
                "arguments": getattr(fn, "arguments", None) or "{}",
            }
        )
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
    max_attempts: int = 4,
    backoff_base: float = 0.5,
    backoff_cap: float = 8.0,
) -> Union[TextResult, ToolResult, SchemaResult]:
    """
    Single entry point:
      - If schema is provided => SchemaResult (parsed JSON + validation errors + raw fallback)
      - Else if functions/tools provided => ToolResult (tool_calls + content)
      - Else => TextResult

    NOTE: 'store' is accepted here to standardize the call signature. chat.completions
    may not support store in your SDK; you can persist locally or later migrate the
    internal call to the Responses API without changing callers.
    """
    tools = _normalize_tools(functions) if functions else []

    _log_messages_brief(messages, f"openai_call({model})")
    payload = {
        "model": model,
        "temperature": temperature,
        "store": store,
        "conversation_id": conversation_id,
        "session_id": session_id,
        "messages": _redact_messages(messages) if DEBUG else None,
        "tools": tools if (DEBUG and tools) else None,
        "tool_choice": "auto" if tools else None,
        "schema_name": schema_name,
        "schema_version": schema_version,
        "schema_enabled": bool(schema),
    }
    _log_request("openai_call", payload)

    for attempt in range(max_attempts):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
            )

            _log_response(f"openai_call attempt={attempt+1}", resp)

            text, tool_calls = _extract_text_and_tool_calls(resp)

            # Schema path
            if schema is not None:
                data, parse_errors = _try_parse_json(text)
                errors = list(parse_errors)

                if data is not None:
                    errors.extend(_validate_schema(data, schema))

                ok = (data is not None) and not any(
                    ("parse error" in e.lower()) or ("validation error" in e.lower()) for e in errors
                )

                result = SchemaResult(
                    ok=ok,
                    data=data,
                    raw_text=text,
                    errors=errors,
                    schema_name=schema_name,
                    schema_version=schema_version,
                )
                _log_schema_status(result)
                return result

            # Tools path
            if tools:
                return ToolResult(role="assistant", content=text, tool_calls=tool_calls)

            # Text path
            return TextResult(role="assistant", content=text)

        except BadRequestError as e:
            logging.error("[OPENAI 400] %s", str(e))
            body = getattr(e, "body", None)
            if body:
                logging.error("[OPENAI 400 BODY]\n%s", _safe_json(body))
            if tools:
                logging.error("[TOOLS NAMES] %s", [t.get("function", {}).get("name") for t in tools])
            raise

        except (RateLimitError, APIError, APITimeoutError, APIConnectionError) as e:
            if attempt == max_attempts - 1:
                raise
            logging.warning(
                "OpenAI error (%s). Retrying attempt %d/%d",
                type(e).__name__,
                attempt + 2,
                max_attempts,
            )
            _sleep_backoff(attempt, backoff_base, backoff_cap)

    raise RuntimeError("openai_call: exhausted retries unexpectedly.")


# -----------------------------------------------------------------------------
# Backwards-compatible wrappers
# -----------------------------------------------------------------------------
def get_completion_text_from_messages(
    messages: List[Dict[str, Any]],
    model: str = "gpt-4o-mini",
    temperature: float = 0,
    max_attempts: int = 4,
    backoff_base: float = 0.5,
    backoff_cap: float = 8.0,
) -> str:
    res = openai_call(
        messages=messages,
        model=model,
        temperature=temperature,
        max_attempts=max_attempts,
        backoff_base=backoff_base,
        backoff_cap=backoff_cap,
    )
    return getattr(res, "content", "") or ""


def ask_question(conversation, model: str = "gpt-4o", temperature: float = 0) -> str:
    return get_completion_text_from_messages(
        messages=conversation,
        model=model,
        temperature=temperature,
    )


def get_completion(prompt: str, temperature: float = 0, model: str = "gpt-4o-mini") -> str:
    return get_completion_text_from_messages(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        temperature=temperature,
    )


def get_completion_with_functions(
    messages: List[Dict[str, Any]],
    functions: List[Dict[str, Any]],
    model: str = "gpt-4o-mini",
    temperature: float = 0,
    max_attempts: int = 4,
) -> Dict[str, Any]:
    """
    Backwards-compatible wrapper around tools=.
    Returns:
      {"role": "...", "content": "...", "function_call": {"name": "...", "arguments": "..."}}
    """
    res = openai_call(
        messages=messages,
        functions=functions,
        model=model,
        temperature=temperature,
        max_attempts=max_attempts,
    )

    out: Dict[str, Any] = {"role": "assistant", "content": getattr(res, "content", "") or ""}

    tool_calls = getattr(res, "tool_calls", []) or []
    if tool_calls:
        if len(tool_calls) > 1:
            logging.warning("Model returned %d tool_calls; only first will be used.", len(tool_calls))
        tc0 = tool_calls[0]
        out["function_call"] = {"name": tc0.get("name"), "arguments": tc0.get("arguments") or "{}"}

    return out


def get_completion_with_tools(
    messages: List[Dict[str, Any]],
    functions: List[Dict[str, Any]],
    temperature: float = 0,
    model: str = "gpt-4o-mini",
    max_retries: int = 3,
    retry_wait: int = 1,
) -> Dict[str, Any]:
    """
    Returns either:
      {"role": "assistant", "content": "..."} OR
      {"role": "assistant", "content": "", "tool_call_id": "...",
       "function_call": {"name": "...", "arguments": "..."}}
    """
    logging.info("get_completion_with_tools start: %s", model)

    # Map legacy retry knobs onto core retry knobs
    res = openai_call(
        messages=messages,
        functions=functions,
        model=model,
        temperature=temperature,
        max_attempts=max_retries + 1,
        backoff_base=float(retry_wait),
        backoff_cap=max(8.0, float(retry_wait) * 4),
    )

    out: Dict[str, Any] = {"role": "assistant", "content": getattr(res, "content", "") or ""}

    tool_calls = getattr(res, "tool_calls", []) or []
    if tool_calls:
        tc0 = tool_calls[0]
        out["tool_call_id"] = tc0.get("id")
        out["function_call"] = {
            "name": tc0.get("name"),
            "arguments": tc0.get("arguments") or "{}",
        }

    logging.info("get_completion_with_tools end: %s", model)
    return out


# -----------------------------------------------------------------------------
# New: schema call convenience wrapper (optional)
# -----------------------------------------------------------------------------
def get_completion_with_schema(
    messages: List[Dict[str, Any]],
    schema: Dict[str, Any],
    schema_name: Optional[str] = None,
    schema_version: Optional[str] = None,
    model: str = "gpt-4o-mini",
    temperature: float = 0,
    store: bool = False,
    conversation_id: Optional[str] = None,
    session_id: Optional[str] = None,
    max_attempts: int = 4,
) -> SchemaResult:
    res = openai_call(
        messages=messages,
        model=model,
        temperature=temperature,
        schema=schema,
        schema_name=schema_name,
        schema_version=schema_version,
        store=store,
        conversation_id=conversation_id,
        session_id=session_id,
        max_attempts=max_attempts,
    )
    if not isinstance(res, SchemaResult):
        # defensive; should not happen
        return SchemaResult(ok=False, data=None, raw_text=getattr(res, "content", "") or "", errors=["Unexpected result type."])
    return res


# -----------------------------------------------------------------------------
# Deprecated placeholder kept to avoid import errors in older modules
# -----------------------------------------------------------------------------
def get_completionWithFunctions(
    messages,
    functions,
    temperature: int = 0,
    model: str = "gpt-4o-mini",
    max_retries: int = 3,
    retry_wait: int = 1,
):
    return ""
