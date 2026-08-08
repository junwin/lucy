# src/prompt_builders/prompt_builder_interface.py

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


ChatMessageDict = Dict[str, Any]


class PromptBuilderInterface(ABC):
    @abstractmethod
    def build_prompt(
        self,
        *,
        content_text: str,
        conversation_id: str,
        agent_name: str,
        account_name: str,
        context_type: str = "none",
        max_prompt_chars: int = 6000,
        context_name: str = "",
        extra_system_messages: Optional[List[str]] = None,
        image_ids: Optional[List[str]] = None,
        file_ids: Optional[List[str]] = None,
        supports_images: bool = True,
    ) -> List[ChatMessageDict]:
        """Builds an OpenAI-compatible messages array."""
        raise NotImplementedError
