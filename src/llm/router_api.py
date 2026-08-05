from __future__ import annotations

from typing import Any, Dict, Optional

from .dto import LLMResponse
from .interface import LLMApi
from .openai_responses import OpenAIResponsesApi
from .deepseek_responses import DeepSeekApi
from .mistral_api import MistralApi


class RouterApi(LLMApi):
    """Routes LLM requests to the correct backend based on the model name.

    - Model names starting with ``"deepseek"`` → ``DeepSeekApi``
    - Model names starting with ``"mistral"`` → ``MistralApi``
    - All other model names → ``OpenAIResponsesApi``
    """

    def __init__(
        self,
        *,
        openai_api: Optional[OpenAIResponsesApi] = None,
        deepseek_api: Optional[DeepSeekApi] = None,
        mistral_api: Optional[MistralApi] = None,
    ) -> None:
        self._openai = openai_api or OpenAIResponsesApi()
        self._deepseek = deepseek_api or DeepSeekApi()
        self._mistral = mistral_api or MistralApi()

    def supports_image_processing(self, model: str) -> bool:
        """Check whether the selected model supports native image processing.

        Routes to the correct provider based on model name prefix.
        Raises ValueError for unrecognized model prefixes.
        """
        if model.startswith("deepseek"):
            return self._deepseek.supports_image_processing(model)
        if model.startswith("mistral"):
            return self._mistral.supports_image_processing(model)
        if model.startswith("gpt") or model.startswith("o1") or model.startswith("o3"):
            return self._openai.supports_image_processing(model)
        raise ValueError(
            f"Unknown model prefix in '{model}'. "
            f"Expected 'gpt', 'o1', 'o3', 'deepseek', or 'mistral'."
        )

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
        if model.startswith("mistral"):
            return self._mistral.create_response(
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
