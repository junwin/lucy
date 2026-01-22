from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Agent:
    """Agent configuration.

    allowed_tools: Optional[List[str]]
        - If missing or None, no tools are allowed (strict intersection default).
        - If an empty list, no tools are allowed.
        - If a non-empty list, only the named tools are permitted for this agent.
    """

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
    allowed_tools: Optional[List[str]] = None

    @staticmethod
    def from_dict(data: dict) -> "Agent":
        """Create an Agent from a raw dict, handling legacy field names."""

        # Handle legacy/alternate field names
        if "select_type" in data and "context_type" not in data:
            data["context_type"] = data.pop("select_type")
        if "save_reposnses" in data and "save_responses" not in data:
            data["save_responses"] = data.pop("save_reposnses")

        # Strict intersection semantics:
        # - missing => None (treated as allow none)
        # - [] => allow none
        # - [..] => allow intersection
        data["allowed_tools"] = data.get("allowed_tools", None)

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
            "allowed_tools": self.allowed_tools,
        }

    def allows_tool(self, tool_name: str) -> bool:
        """Return True if the given tool is allowed for this agent.

        Rules (strict intersection):
        - allowed_tools is None => allow no tools
        - allowed_tools is [] => allow no tools
        - otherwise => allow only if tool_name is in allowed_tools
        """

        if not self.allowed_tools:
            return False
        return tool_name in self.allowed_tools


# Simple sanity check when run as a script
if __name__ == "__main__":
    # Missing allowed_tools => allow none
    a = Agent.from_dict({"name": "test-agent"})
    assert a.allowed_tools is None
    assert a.allows_tool("any_tool") is False

    # Empty list => allow none
    b = Agent.from_dict({"name": "no-tools", "allowed_tools": []})
    assert b.allowed_tools == []
    assert b.allows_tool("any_tool") is False

    # Restricting tools
    c = Agent.from_dict({"name": "restricted", "allowed_tools": ["tool_a", "tool_b"]})
    assert c.allows_tool("tool_a") is True
    assert c.allows_tool("other") is False

    print("Agent sanity checks passed")
