import json
import time
import random
import logging
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI
from openai import RateLimitError, APIError, APITimeoutError, APIConnectionError
from openai import BadRequestError  # helps catch 400s cleanly

from src.container_config import container
from src.config_manager import ConfigManager


# -----------------------------------------------------------------------------
# Debug controls
# -----------------------------------------------------------------------------
DEBUG = os.getenv("LUCY_OPENAI_DEBUG", "0") in ("1", "true", "True", "yes", "YES")
DEBUG_FULL = os.getenv("LUCY_OPENAI_DEBUG_FULL", "0") in ("1", "true", "True", "yes", "YES")

# Truncation limits for logs (used when DEBUG_FULL is off)
MAX_STR = int(os.getenv("LUCY_OPENAI_DEBUG_MAX_STR", "1200"))
MAX_JSON = int(os.getenv("LUCY_OPENAI_DEBUG_MAX_JSON", "8000"))

config = container.get(ConfigManager)
credential_path = config.get("credential_path")

with open(f"{credential_path}/oaicred.json", "r", encoding="utf-8") as f:
    config_data = json.load(f)

client = OpenAI(api_key=config_data["openai_api_key"])


# -----------------------------------------------------------------------------
# Helpers: safe-ish logging/dumping
# -----------------------------------------------------------------------------
def _truncate(s: str, limit: int = MAX_STR) -> str:
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

    # Extract useful fields without relying on private SDK internals.
    info: Dict[str, Any] = {}
    try:
        info["id"] = getattr(resp, "id", None)
        info["model"] = getattr(resp, "model", None)
        info["created"] = getattr(resp, "created", None)
        usage = getattr(resp, "usage", None)
        if usage is not None:
            # usage is often a dataclass-ish object
            info["usage"] = getattr(usage, "to_dict", lambda: usage).__call__() if hasattr(usage, "to_dict") else getattr(usage, "__dict__", usage)
        # choices summary
        choices = getattr(resp, "choices", None)
        if choices:
            info["choices_count"] = len(choices)
            # summarize first choice message
            msg = choices[0].message
            info["first_choice_role"] = getattr(msg, "role", None)
            info["first_choice_content_preview"] = _truncate(getattr(msg, "content", "") or "")
            tcs = getattr(msg, "tool_calls", None)
            if tcs:
                info["first_choice_tool_calls"] = [
                    {
                        "id": getattr(tc, "id", None),
                        "type": getattr(tc, "type", None),
                        "function_name": getattr(getattr(tc, "function", None), "name", None),
                        "arguments_preview": _truncate(getattr(getattr(tc, "function", None), "arguments", "") or ""),
                    }
                    for tc in tcs
                ]
    except Exception as e:
        info["parse_error"] = f"{type(e).__name__}: {e}"
        info["raw_repr"] = repr(resp)

    logging.debug("[OPENAI RESP] %s summary:\n%s", label, _safe_json(info))

def _log_messages_brief(messages: List[Dict[str, Any]], label: str) -> None:
    n = len(messages)
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
# API calls
# -----------------------------------------------------------------------------
def get_completion_text_from_messages(
    messages: List[Dict[str, Any]],
    model: str = "gpt-4o-mini",
    temperature: float = 0,
    max_attempts: int = 4,
    backoff_base: float = 0.5,
    backoff_cap: float = 8.0,
) -> str:
    _log_messages_brief(messages, f"send({model})")

    for attempt in range(max_attempts):
        try:
            payload = {
                "model": model,
                "messages": _redact_messages(messages) if DEBUG else None,
                "temperature": temperature,
            }
            _log_request(f"chat.completions.create text attempt={attempt+1}", payload)

            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )

            _log_response(f"chat.completions.create text attempt={attempt+1}", resp)
            return resp.choices[0].message.content or ""

        except BadRequestError as e:
            # 400s are usually not retryable; log details and re-raise
            logging.error("[OPENAI 400] %s", str(e))
            # The SDK often includes a JSON body in e.body
            body = getattr(e, "body", None)
            if body:
                logging.error("[OPENAI 400 BODY]\n%s", _safe_json(body))
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


def ask_question(conversation, model="gpt-4o", temperature=0) -> str:
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
    tools = _normalize_tools(functions)
    _log_messages_brief(messages, f"send_tools({model})")

    for attempt in range(max_attempts):
        try:
            payload = {
                "model": model,
                "messages": _redact_messages(messages) if DEBUG else None,
                "tools": tools if DEBUG else None,
                "tool_choice": "auto" if tools else None,
                "temperature": temperature,
            }
            _log_request(f"chat.completions.create tools attempt={attempt+1}", payload)

            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                temperature=temperature,
            )

            _log_response(f"chat.completions.create tools attempt={attempt+1}", resp)

            msg = resp.choices[0].message
            out: Dict[str, Any] = {"role": msg.role, "content": msg.content or ""}

            if msg.tool_calls:
                if len(msg.tool_calls) > 1:
                    logging.warning("Model returned %d tool_calls; only first will be used.", len(msg.tool_calls))
                tc = msg.tool_calls[0]
                out["function_call"] = {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}

            return out

        except BadRequestError as e:
            logging.error("[OPENAI 400] %s", str(e))
            body = getattr(e, "body", None)
            if body:
                logging.error("[OPENAI 400 BODY]\n%s", _safe_json(body))
            # also log tools list names, because 400s here are often malformed tools
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
            _sleep_backoff(attempt, 0.5, 8.0)


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

    tools = _normalize_tools(functions)
    retries = 0

    while retries <= max_retries:
        try:
            payload = {
                "model": model,
                "messages": messages,
                "tools": tools ,
                "tool_choice": "auto" if tools else None,
                "temperature": temperature,
                "attempt": retries + 1,
            }
            logging.info("payload: %s", payload)

            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                temperature=temperature,
            )

            logging.info("resp: %s", resp)                        

           

            msg = resp.choices[0].message
            out: Dict[str, Any] = {"role": msg.role, "content": msg.content or ""}

            if msg.tool_calls:
                tc = msg.tool_calls[0]  # single tool call assumption
                out["tool_call_id"] = tc.id
                out["function_call"] = {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                }

            logging.info("get_completion_with_tools end: %s", model)
            return out

        except BadRequestError as e:
            logging.error("[OPENAI 400] %s", str(e))
            body = getattr(e, "body", None)
            if body:
                logging.error("[OPENAI 400 BODY]\n%s", _safe_json(body))
            logging.error("[TOOLS NAMES] %s", [t.get("function", {}).get("name") for t in tools])
            raise

        except RateLimitError:
            if retries == max_retries:
                raise
            retries += 1
            logging.warning("RateLimitError encountered, retrying... (attempt %d)", retries)
            time.sleep(retry_wait)

        except APIError as e:
            if retries == max_retries:
                raise
            retries += 1
            logging.warning("APIError encountered, retrying... (attempt %d) err=%s", retries, str(e))
            time.sleep(retry_wait)


# Deprecated placeholder kept to avoid import errors in older modules
def get_completionWithFunctions(messages, functions, temperature: int = 0,
                              model: str = "gpt-4o-mini",
                              max_retries: int = 3, retry_wait: int = 1):
    return ""
