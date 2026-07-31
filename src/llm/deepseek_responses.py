from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from src.config_manager import ConfigManager
from .dto import LLMResponse, LLMUsage, ToolCall
from .interface import LLMApi
from .openai_responses import _sleep_backoff


class DeepSeekApi(LLMApi):
    """DeepSeek API implementation using OpenAI-compatible endpoint.

    DeepSeek V4 is text-only. For image support, a vision proxy (GPT-4o)
    is used to describe images before sending text to DeepSeek.
    """

    DEEPSEEK_BASE_URL = "https://api.deepseek.com"

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
        # Store conversation context by response_id
        self._conversation_context: Dict[str, List[Dict[str, Any]]] = {}

    @staticmethod
    def _build_default_client() -> OpenAI:
        config = ConfigManager("config.json")
        credential_path = config.get("credential_path")

        with open(os.path.join(credential_path, "deepseek_cred.json"), "r", encoding="utf-8") as f:
            config_data = json.load(f)

        return OpenAI(
            api_key=config_data["deepseek_api_key"],
            base_url=DeepSeekApi.DEEPSEEK_BASE_URL,
        )

    # ------------------------------------------------------------------
    # Vision proxy helpers (Step 7)
    # ------------------------------------------------------------------

    @staticmethod
    def _has_image_content(messages: List[Dict[str, Any]]) -> bool:
        """Return True if any message has image content parts."""
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image":
                    return True
        return False

    @staticmethod
    def _strip_image_parts(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove image content parts from all messages, keeping text parts."""
        result = []
        for msg in messages:
            if not isinstance(msg, dict):
                result.append(msg)
                continue

            content = msg.get("content")
            if isinstance(content, list):
                # Keep only text parts
                text_parts = [
                    p for p in content
                    if not (isinstance(p, dict) and p.get("type") == "image")
                ]
                if len(text_parts) == 1 and text_parts[0].get("type") == "text":
                    # Collapse to plain string
                    msg_copy = dict(msg)
                    msg_copy["content"] = text_parts[0].get("text", "")
                    result.append(msg_copy)
                elif text_parts:
                    msg_copy = dict(msg)
                    msg_copy["content"] = text_parts
                    result.append(msg_copy)
                else:
                    # All parts were images — keep as empty text
                    msg_copy = dict(msg)
                    msg_copy["content"] = ""
                    result.append(msg_copy)
            else:
                result.append(msg)

        return result

    @staticmethod
    def _describe_image_via_proxy(
        image_part: Dict[str, Any],
        question_text: str,
        *,
        config: Optional[ConfigManager] = None,
        max_chars: int = 500,
    ) -> str:
        """Send an image to a vision-capable model and return a text description.

        Uses the vision proxy model (default: gpt-4o) from config.
        Returns a description string, or raises on failure.
        """
        source = image_part.get("source", {}) if isinstance(image_part, dict) else {}
        data = source.get("data", "") if isinstance(source, dict) else ""
        mime = source.get("mime_type", "image/png") if isinstance(source, dict) else "image/png"

        cfg = config or ConfigManager("config.json")

        credential_path = cfg.get("credential_path")
        with open(os.path.join(credential_path, "oaicred.json"), "r", encoding="utf-8") as f:
            cred = json.load(f)

        vision_client = OpenAI(api_key=cred["openai_api_key"])

        prompt = (
            f"Please describe this image in detail"
            f"{': ' + question_text if question_text else '.'} "
            f"Keep the description under {max_chars} characters. "
            f"Then, on a new line, provide about 10 relevant tags/keywords "
            f"as a comma-separated list prefixed with 'Tags: '."
        )

        resp = vision_client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                ],
            }],
            max_tokens=max_chars // 2,
        )

        description = resp.choices[0].message.content or ""
        return description.strip()

    @staticmethod
    def _resolve_images_via_proxy(
        messages: List[Dict[str, Any]],
        *,
        config: Optional[ConfigManager] = None,
    ) -> List[Dict[str, Any]]:
        """Process image content parts through the vision proxy.

        For each user message with image parts:
        1. Collect the text question
        2. Send each image to GPT-4o for description
        3. Replace image parts with a text description block
        4. Strip remaining image parts (safety net)
        """
        if not DeepSeekApi._has_image_content(messages):
            return messages

        cfg = config or ConfigManager("config.json")
        proxy_cfg = cfg.get("vision_proxy", {})
        if not proxy_cfg.get("enabled", True):
            raise RuntimeError(
                "DeepSeek V4 API does not support images and the vision proxy "
                "is disabled. Use an agent with OpenAI or Mistral, or enable "
                "the vision_proxy in config.json."
            )

        max_chars = int(proxy_cfg.get("max_description_chars", 500))

        result = []
        for msg in messages:
            if not isinstance(msg, dict):
                result.append(msg)
                continue

            content = msg.get("content")
            if not isinstance(content, list):
                result.append(msg)
                continue

            # Separate text and image parts
            text_parts = []
            image_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image":
                    image_parts.append(part)
                elif isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))

            if not image_parts:
                result.append(msg)
                continue

            question = " ".join(text_parts).strip()

            descriptions = []
            for img in image_parts:
                desc = DeepSeekApi._describe_image_via_proxy(
                    img, question, config=cfg, max_chars=max_chars
                )
                descriptions.append(desc)

            # Build new content: text question + image descriptions
            new_content = question + "\n\n" if question else ""
            for i, desc in enumerate(descriptions, 1):
                new_content += f"[Image {i} description: {desc}]\n\n"

            msg_copy = dict(msg)
            msg_copy["content"] = new_content.strip()
            result.append(msg_copy)

        return result

    # ------------------------------------------------------------------
    # Tool format transform
    # ------------------------------------------------------------------

    def _transform_tools_for_deepseek(self, tools: Optional[list[dict]]) -> Optional[list[dict]]:
        """Transform OpenAI tool format to DeepSeek format."""
        if not tools:
            return None

        deepseek_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                function_def = {}

                if "name" in tool:
                    function_def["name"] = tool["name"]

                if "description" in tool:
                    function_def["description"] = tool["description"]

                if "parameters" in tool:
                    params = tool["parameters"].copy() if isinstance(tool["parameters"], dict) else {}
                    params.pop("strict", None)
                    params.pop("additionalProperties", None)
                    function_def["parameters"] = params

                deepseek_tools.append({
                    "type": "function",
                    "function": function_def
                })
            else:
                deepseek_tools.append(tool)

        return deepseek_tools

    def _convert_tool_calls_to_assistant_message(self, tool_calls: List[ToolCall]) -> Dict[str, Any]:
        """Convert ToolCall objects to an assistant message with tool_calls."""
        formatted_tool_calls = []
        for tc in tool_calls:
            formatted_tool_calls.append({
                "id": tc.call_id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": tc.arguments_json
                }
            })

        return {
            "role": "assistant",
            "content": None,
            "tool_calls": formatted_tool_calls
        }

    def _normalize_input_to_messages(
        self,
        input: Any,
        previous_response_id: Optional[str] = None,
        previous_tool_calls: Optional[List[ToolCall]] = None
    ) -> List[Dict[str, Any]]:
        """Convert various input formats to a list of messages for DeepSeek.

        When image content parts are detected, runs the vision proxy
        to replace images with text descriptions before sending to DeepSeek.
        """

        # Case 1: Input is a list of tool outputs from the processor
        if isinstance(input, list) and input and isinstance(input[0], dict):
            if "type" in input[0] and input[0].get("type") == "function_call_output":
                # This is a tool response. We need to combine with previous context.
                context_messages = []
                if previous_response_id and previous_response_id in self._conversation_context:
                    context_messages = self._conversation_context[previous_response_id].copy()
                    logging.info(f"DeepSeekApi: retrieved {len(context_messages)} messages from context for response_id={previous_response_id}")

                # Add the assistant message with tool_calls if we have them
                if previous_tool_calls:
                    assistant_msg = self._convert_tool_calls_to_assistant_message(previous_tool_calls)
                    context_messages.append(assistant_msg)

                # Convert tool outputs to tool response messages
                for item in input:
                    if item.get("type") == "function_call_output":
                        tool_message = {
                            "role": "tool",
                            "tool_call_id": item.get("call_id"),
                            "content": item.get("output", "")
                        }
                        context_messages.append(tool_message)

                logging.info(f"DeepSeekApi: built conversation with {len(context_messages)} total messages")
                return context_messages

        # Case 2: Input is already a list of messages — resolve images via proxy
        if isinstance(input, list):
            return self._resolve_images_via_proxy(input)

        # Case 3: Input is a single message
        if isinstance(input, dict):
            return [input]

        # Case 4: Unknown format
        logging.warning(f"DeepSeekApi: unexpected input type: {type(input)}")
        return []

    def _validate_and_fix_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensure all messages have required fields and proper format."""
        fixed_messages = []

        for i, msg in enumerate(messages):
            fixed_msg = dict(msg)

            # Ensure role exists
            if "role" not in fixed_msg:
                logging.error(f"Message at index {i} missing 'role' field: {fixed_msg}")
                continue

            # Ensure assistant messages with tool_calls have proper structure
            if fixed_msg.get("role") == "assistant":
                if "tool_calls" in fixed_msg and fixed_msg["tool_calls"]:
                    # Ensure each tool call has the proper structure
                    for tc in fixed_msg["tool_calls"]:
                        if isinstance(tc, dict) and "function" not in tc:
                            # Convert from flat format to nested format if needed
                            if "name" in tc and "arguments" in tc:
                                tc["function"] = {
                                    "name": tc.pop("name"),
                                    "arguments": tc.pop("arguments")
                                }

            fixed_messages.append(fixed_msg)

        return fixed_messages

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
        # Transform tools to DeepSeek format
        deepseek_tools = self._transform_tools_for_deepseek(tools)

        # Extract previous tool_calls from metadata if available
        previous_tool_calls = None
        if metadata and "previous_tool_calls" in metadata:
            previous_tool_calls = metadata["previous_tool_calls"]

        # Normalize input to messages list
        messages = self._normalize_input_to_messages(input, previous_response_id, previous_tool_calls)

        # Validate and fix messages
        fixed_messages = self._validate_and_fix_messages(messages)

        logging.info("DeepSeekApi: model=%s temperature=%s tool_choice=%s tools_count=%d messages_count=%d previous_response_id=%s",
                    model, temperature, tool_choice, len(deepseek_tools) if deepseek_tools else 0,
                    len(fixed_messages), previous_response_id)

        # Check for empty messages
        if not fixed_messages:
            logging.error("DeepSeekApi: no messages to send after normalization")
            raise ValueError("No messages to send to DeepSeek API")

        for attempt in range(self._max_attempts):
            try:
                # Prepare request parameters
                request_params = {
                    "model": model,
                    "messages": fixed_messages,
                    "temperature": temperature,
                }

                if deepseek_tools:
                    request_params["tools"] = deepseek_tools

                if tool_choice:
                    request_params["tool_choice"] = tool_choice

                resp = self._client.chat.completions.create(**request_params)

                # Extract from chat completion response format
                response_id = getattr(resp, "id", None)
                resp_model = getattr(resp, "model", None)

                # Extract text from the first choice
                output_text = ""
                if resp.choices and len(resp.choices) > 0:
                    message = resp.choices[0].message
                    output_text = message.content or ""

                # Extract tool calls from the response
                tool_calls_list = []
                if resp.choices and len(resp.choices) > 0:
                    message = resp.choices[0].message
                    if hasattr(message, "tool_calls") and message.tool_calls:
                        for tc in message.tool_calls:
                            tool_calls_list.append(ToolCall(
                                call_id=tc.id,
                                name=tc.function.name,
                                arguments_json=tc.function.arguments,
                            ))

                # Store the conversation context for future tool responses
                if response_id:
                    self._conversation_context[response_id] = fixed_messages.copy()
                    # Also store the assistant's response if it had tool_calls
                    if tool_calls_list:
                        assistant_msg = self._convert_tool_calls_to_assistant_message(tool_calls_list)
                        self._conversation_context[response_id].append(assistant_msg)
                    logging.debug(f"DeepSeekApi: stored context for response_id={response_id} with {len(self._conversation_context[response_id])} messages")

                # Extract usage
                usage = None
                if hasattr(resp, "usage") and resp.usage:
                    usage = LLMUsage(
                        input_tokens=getattr(resp.usage, "prompt_tokens", None),
                        output_tokens=getattr(resp.usage, "completion_tokens", None),
                        total_tokens=getattr(resp.usage, "total_tokens", None),
                        raw=resp.usage,
                    )

                logging.info(
                    "DeepSeekApi: response_id=%s model=%s output_text_len=%d tool_calls=%d",
                    response_id,
                    resp_model,
                    len(output_text),
                    len(tool_calls_list),
                )

                return LLMResponse(
                    response_id=response_id,
                    model=resp_model,
                    output_text=output_text,
                    tool_calls=tool_calls_list,
                    usage=usage,
                    raw=resp,
                )

            except Exception as e:
                logging.warning(
                    "DeepSeekApi: attempt %d/%d failed: %s",
                    attempt + 1,
                    self._max_attempts,
                    e,
                )
                if attempt == self._max_attempts - 1:
                    logging.error("DeepSeekApi: failed with messages count: %d", len(fixed_messages))
                    if fixed_messages:
                        for i, msg in enumerate(fixed_messages[:3]):  # Log first 3 messages
                            logging.error(f"DeepSeekApi: message[{i}]: role={msg.get('role')} keys={list(msg.keys())}")
                    raise
                _sleep_backoff(attempt, self._backoff_base, self._backoff_cap)

        raise RuntimeError("DeepSeekApi: exhausted retries")
