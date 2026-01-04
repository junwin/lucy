from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError

from src.config_manager import ConfigManager

from .dto import LLMResponse, LLMUsage, ToolCall
from .interface import LLMApi


def _extract_usage(usage_obj: Any) -> Optional[LLMUsage]:
    if usage_obj is None:
        return None

    raw: Optional[Dict[str, Any]] = None
    if hasattr(usage_obj, "to_dict"):
        try:
            raw = usage_obj.to_dict()
        except Exception:
            raw = None
    elif hasattr(usage_obj, "__dict__"):
        try:
            raw = dict(usage_obj.__dict__)
        except Exception:
            raw = None

    def _get_int(key: str) -> Optional[int]:
        if not raw:
            return None
        v = raw.get(key)
        return int(v) if isinstance(v, (int, float, str)) and str(v).isdigit() else None

    return LLMUsage(
        input_tokens=_get_int("input_tokens"),
        output_tokens=_get_int("output_tokens"),
        total_tokens=_get_int("total_tokens"),
        raw=raw,
    )


def _extract_tool_calls(resp: Any) -> List[ToolCall]:
    calls: List[ToolCall] = []
    out = getattr(resp, "output", None) or []

    for i, item in enumerate(out):
        item_type = getattr(item, "type", None)

        if item_type != "function_call":
            continue

        call_id = getattr(item, "call_id", None)
        name = getattr(item, "name", None)

        # IMPORTANT: don't default to "{}" yet — log what's really there
        raw_args = getattr(item, "arguments", None)

        logging.info(
            "_extract_tool_calls: idx=%d type=%s call_id=%r name=%r arguments_present=%s arguments_type=%s arguments_len=%s",
            i,
            item_type,
            call_id,
            name,
            raw_args is not None,
            type(raw_args).__name__ if raw_args is not None else None,
            len(raw_args) if isinstance(raw_args, str) else None,
        )

        # Also log a small preview if it's a string (safe-ish)
        if isinstance(raw_args, str):
            logging.info("_extract_tool_calls: arguments_preview=%r", raw_args[:300])

        # Normalize to JSON string
        if raw_args is None:
            arguments_json = ""   # distinguish missing from {}
        elif isinstance(raw_args, str):
            arguments_json = raw_args
        else:
            # sometimes SDKs give dict-like structures
            try:
                arguments_json = json.dumps(raw_args, ensure_ascii=False)
            except Exception:
                arguments_json = str(raw_args)

        if call_id and name:
            calls.append(
                ToolCall(
                    call_id=str(call_id),
                    name=str(name),
                    arguments_json=arguments_json,
                )
            )

    return calls



def _sleep_backoff(attempt: int, base: float, cap: float) -> None:
    """Exponential backoff with jitter."""
    delay = min(cap, base * (2**attempt))
    delay = delay * (0.6 + random.random() * 0.8)  # jitter 0.6–1.4x
    logging.warning("OpenAIResponsesApi: backing off for %.2fs (attempt=%d)", delay, attempt + 1)
    time.sleep(delay)


class OpenAIResponsesApi(LLMApi):
    """OpenAI Responses API implementation.

    Notes:
    - By default, this class loads credentials the same way api_helpers.py does.
    - For tests, pass a fake/mocked client via `client=...`.

    Retry/backoff:
    - Retries RateLimitError, APIError, APITimeoutError, APIConnectionError.
    - Backoff is exponential with jitter.
    """

    def __init__(
        self,
        *,
        client: Optional[OpenAI] = None,
        max_attempts: int = 4,
        backoff_base: float = 0.5,
        backoff_cap: float = 8.0,
    ) -> None:
        self._client = client or self._build_default_client()
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._backoff_cap = backoff_cap

    @staticmethod
    def _build_default_client() -> OpenAI:
        config = ConfigManager("config.json")
        credential_path = config.get("credential_path")
        with open(os.path.join(credential_path, "oaicred.json"), "r", encoding="utf-8") as f:
            config_data = json.load(f)
        return OpenAI(api_key=config_data["openai_api_key"])

    def create_response(
        self,
        *,
        model: str,
        input: Any,
        temperature: Optional[float] = None,
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
        store: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
        previous_response_id: Optional[str] = None,
        text: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        last_err: Optional[BaseException] = None

        # ---- entry log ----
        logging.info(
            "OpenAIResponsesApi.create_response: enter model=%s prev_response_id=%s tools=%s tool_choice=%s store=%s",
            model,
            previous_response_id,
            len(tools) if tools else 0,
            tool_choice,
            store,
        )

        #try:
        #    tools_json = json.dumps(tools, indent=2, ensure_ascii=False)
        #except Exception:
        #    tools_json = str(tools)

        #logging.info(
        #    "OpenAIResponsesApi.create_response: tools (pretty)=%s",
        #    tools_json,
        #)

        #for tl in tools:
        #    logging.info("OpenAIResponsesApi.create_response: tool=%s", tl.get("name"))

        for attempt in range(self._max_attempts):
            t0 = time.time()
            logging.info(
                "OpenAIResponsesApi.create_response: attempt %d/%d starting",
                attempt + 1,
                self._max_attempts,
            )

            try:
                resp = self._client.responses.create(
                    model=model,
                    input=input,
                    temperature=temperature,
                    tools=tools,
                    tool_choice=tool_choice,
                    store=store,
                    metadata=metadata,
                    previous_response_id=previous_response_id,
                    text=text,
                )

                elapsed = time.time() - t0

                response_id = getattr(resp, "id", None)
                resp_model = getattr(resp, "model", None)
                output_text = getattr(resp, "output_text", "") or ""
                tool_calls = _extract_tool_calls(resp)
                usage = _extract_usage(getattr(resp, "usage", None))

                # ---- response summary ----
                logging.info(
                    "OpenAIResponsesApi.create_response: attempt %d succeeded in %.3fs "
                    "response_id=%s model=%s output_text_len=%d tool_calls=%d",
                    attempt + 1,
                    elapsed,
                    response_id,
                    resp_model,
                    len(output_text),
                    len(tool_calls),
                )

                # ---- tool call details (names only, safe) ----
                if tool_calls:
                    logging.info(
                        "OpenAIResponsesApi.create_response: tool_calls=%s",
                        [tc.name for tc in tool_calls],
                    )

                # ---- output item shape (useful for debugging tool-call weirdness) ----
                try:
                    output_items = getattr(resp, "output", None) or []
                    item_types = [getattr(item, "type", None) for item in output_items]
                    logging.debug(
                        "OpenAIResponsesApi.create_response: output_items count=%d types=%s",
                        len(output_items),
                        item_types,
                    )
                except Exception:
                    pass

                return LLMResponse(
                    response_id=response_id,
                    model=resp_model,
                    output_text=output_text,
                    tool_calls=tool_calls,
                    usage=usage,
                    raw=resp,
                )

            except (RateLimitError, APIError, APITimeoutError, APIConnectionError) as e:
                elapsed = time.time() - t0
                last_err = e

                logging.warning(
                    "OpenAIResponsesApi.create_response: attempt %d/%d failed after %.3fs "
                    "with %s: %s",
                    attempt + 1,
                    self._max_attempts,
                    elapsed,
                    type(e).__name__,
                    e,
                )

                if attempt == self._max_attempts - 1:
                    logging.error(
                        "OpenAIResponsesApi.create_response: exhausted retries after %d attempts",
                        self._max_attempts,
                    )
                    raise

                _sleep_backoff(attempt, self._backoff_base, self._backoff_cap)

            except Exception as e:
                elapsed = time.time() - t0
                logging.exception(
                    "OpenAIResponsesApi.create_response: unexpected error on attempt %d/%d after %.3fs",
                    attempt + 1,
                    self._max_attempts,
                    elapsed,
                )
                raise

        # Should be unreachable
        raise RuntimeError("OpenAIResponsesApi: exhausted retries unexpectedly") from last_err