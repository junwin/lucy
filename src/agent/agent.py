from dataclasses import dataclass
from typing import Optional


@dataclass
class Agent:
    name: str
    language_code: str = "en-US"
    context_type: str = "hybrid"  # previously select_type
    max_prompt_conversations: int = 6
    max_prompt_documents: int = 4
    temperature: float = 0.0
    save_responses: bool = True  # previously save_reposnses
    model: str = "gpt-5.1"
    message_processor: str = "function_calling_processor"
    max_function_call_iterations: int = 10
    partner_agent: Optional[str] = None
    system_prompt: str = ""
    style_prompt: str = ""
    persona: str = ""

    @staticmethod
    def from_dict(data: dict) -> "Agent":
        """Create an Agent from a raw dict, handling legacy field names."""
        # Handle legacy/alternate field names
        if "select_type" in data and "context_type" not in data:
            data["context_type"] = data.pop("select_type")
        if "save_reposnses" in data and "save_responses" not in data:
            data["save_responses"] = data.pop("save_reposnses")

        return Agent(**data)

    def to_dict(self) -> dict:
        """Serialize Agent to a dict suitable for JSON storage."""
        return {
            "name": self.name,
            "language_code": self.language_code,
            "context_type": self.context_type,
            "max_prompt_conversations": self.max_prompt_conversations,
            "max_prompt_documents": self.max_prompt_documents,
            "temperature": self.temperature,
            "save_responses": self.save_responses,
            "model": self.model,
            "message_processor": self.message_processor,
            "max_function_call_iterations": self.max_function_call_iterations,
            "partner_agent": self.partner_agent,
            "system_prompt": self.system_prompt,
            "style_prompt": self.style_prompt,
            "persona": self.persona,
        }
