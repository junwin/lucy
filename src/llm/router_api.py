from __future__ import annotations

from typing import Any, Dict, Optional

from .dto import LLMResponse
from .interface import LLMApi
from .openai_responses import OpenAIResponsesApi
from .deepseek_responses import DeepSeekApi


class RouterApi(LLMApi):
    """Routes LLM requests to the correct backend based on the model name.

    - Model names starting with ``"deepseek"`` → ``DeepSeekApi``
    - All other model names → ``OpenAIResponsesApi``
    """

    def __init__(
        self,
        *,
        openai_api: Optional[OpenAIResponsesApi] = None,
        deepseek_api: Optional[DeepSeekApi] = None,
    ) -> None:
        self._openai = openai_api or OpenAIResponsesApi()
        self._deepseek = deepseek_api or DeepSeekApi()

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
        if model.startswith("deepseek"):
            return self._deepseek.create_response(
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
        return self._openai.create_response(
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
