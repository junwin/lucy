---
tags:
  - llm
  - protocol
  - openai
  - response
  - implementation
  - llmresponse
  - llmadapter
  - implement
  - module
  - api
  - src/llm
  - lucyproject
---

# Module: `src/llm`

## Key Classes

| Class | Type | Description |
|-------|------|-------------|
| **LLMApi** | Protocol | Interface for calling an LLM. Defines `create_response()` returning a normalized `LLMResponse` DTO. |
| **LLMAdapter** | Protocol | Protocol glue between FunctionCallingProcessor and a specific LLM API. |
| **RouterApi** | LLMApi impl | Routes LLM requests by model name prefix: `deepseek*` → DeepSeekApi, everything else → OpenAIResponsesApi. |
| **OpenAIResponsesApi** | LLMApi impl | OpenAI Responses API implementation with exponential backoff/retry. |
| **OpenAIResponsesAdapter** | LLMAdapter impl | Adapter for OpenAI Responses API — normalizes tool calls, formats tool outputs. |
| **DeepSeekApi** | LLMApi impl | DeepSeek API via OpenAI-compatible endpoint. Manages conversation context for tool responses. |
| **ToolCall** | dataclass | Normalized tool call: `call_id`, `name`, `arguments_json`. |
| **LLMUsage** | dataclass | Normalized usage info: `input_tokens`, `output_tokens`, `total_tokens`, `raw`. |
| **LLMResponse** | dataclass | Normalized response: `response_id`, `model`, `output_text`, `tool_calls`, `usage`, `raw`. |

## Source Files

| File | Purpose |
|------|---------|
| `src/llm/__init__.py` | Module exports |
| `src/llm/interface.py` | `LLMApi` Protocol definition |
| `src/llm/adapter_interface.py` | `LLMAdapter` Protocol definition |
| `src/llm/dto.py` | `ToolCall`, `LLMUsage`, `LLMResponse` dataclasses |
| `src/llm/router_api.py` | `RouterApi` implementation |
| `src/llm/openai_responses.py` | `OpenAIResponsesApi` implementation |
| `src/llm/openai_responses_adapter.py` | `OpenAIResponsesAdapter` implementation |
| `src/llm/deepseek_responses.py` | `DeepSeekApi` implementation |

## Dependencies

- **stdlib**: `json`, `os`, `logging`, `random`, `time`, `typing`
- **external**: `openai` (OpenAI SDK)
- **internal**: `src.config_manager.ConfigManager`

## LLMApi Protocol Methods

```python
def create_response(
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
) -> LLMResponse: ...
```

## LLMAdapter Protocol Methods

```python
def call_model(...) -> Any: ...
def extract_tool_calls(response) -> List[Dict[str, Any]]: ...
def format_tool_output(*, call_id: str, output: str) -> Dict[str, Any]: ...
def get_text(response) -> str: ...
def get_response_id(response) -> Optional[str]: ...
```

## Module-level Helpers

| Helper | Description |
|--------|-------------|
| `_extract_usage(usage_obj)` | Extracts `LLMUsage` from OpenAI response object |
| `_extract_tool_calls(resp)` | Extracts `List[ToolCall]` from OpenAI response |
| `_sleep_backoff(attempt, base, cap)` | Exponential backoff with jitter |
