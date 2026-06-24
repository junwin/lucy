---
tags:
  - src_llm
  - lucyproject
  - LLMApi
  - LLMAdapter
  - LLMResponse
  - RouterApi
  - OpenAIResponsesApi
  - DeepSeekApi
  - Protocol
  - DTO
---

# src/llm — LLM Abstraction Layer

## Summary

Provides a clean abstraction over LLM backends (OpenAI Responses API, DeepSeek Chat Completions API). Defines **protocols** (`LLMApi`, `LLMAdapter`) so the rest of the codebase never depends on a specific SDK. Includes a **router** that dispatches by model name, and a **normalized DTO** (`LLMResponse`) that decouples callers from raw API response shapes.

## Key Classes

| Class | Role |
|---|---|
| `LLMApi` (Protocol) | Interface for calling an LLM — returns `LLMResponse` DTO |
| `LLMAdapter` (Protocol) | Protocol glue between `FunctionCallingProcessor` and a specific LLM API |
| `OpenAIResponsesApi` | OpenAI Responses API implementation with retry/backoff |
| `OpenAIResponsesAdapter` | Adapter wrapping `OpenAIResponsesApi` for the processor |
| `DeepSeekApi` | DeepSeek Chat Completions API (OpenAI-compatible endpoint) |
| `RouterApi` | Routes requests to `DeepSeekApi` or `OpenAIResponsesApi` by model prefix |
| `LLMResponse` | Frozen dataclass — normalized response DTO |
| `LLMUsage` | Frozen dataclass — normalized token usage |
| `ToolCall` | Frozen dataclass — normalized tool call |

## Source Files

| File | Description |
|---|---|
| `__init__.py` | Exports public API: `LLMApi`, `LLMAdapter`, `LLMResponse`, `LLMUsage`, `ToolCall`, `OpenAIResponsesApi`, `OpenAIResponsesAdapter` |
| `interface.py` | `LLMApi` protocol — single method `create_response(...)` |
| `adapter_interface.py` | `LLMAdapter` protocol — `call_model`, `extract_tool_calls`, `format_tool_output`, `get_text`, `get_response_id` |
| `dto.py` | Data classes: `ToolCall`, `LLMUsage`, `LLMResponse` |
| `openai_responses.py` | `OpenAIResponsesApi` — calls OpenAI Responses API, retry/backoff logic, helper `_extract_tool_calls`, `_extract_usage` |
| `openai_responses_adapter.py` | `OpenAIResponsesAdapter` — wraps `LLMApi` into `LLMAdapter` shape |
| `deepseek_responses.py` | `DeepSeekApi` — calls DeepSeek via OpenAI-compatible `/chat/completions`, manages conversation context for tool calls |
| `router_api.py` | `RouterApi` — dispatches by model name prefix (`"deepseek"` → DeepSeek, else OpenAI) |

## Dependencies

| Dependency | Usage |
|---|---|
| `openai` (SDK) | Required by `OpenAIResponsesApi` and `DeepSeekApi` |
| `src.config_manager.ConfigManager` | Loads API credentials from `config.json` |
| `json`, `os`, `time`, `random`, `logging` | Standard library — serialization, config paths, backoff, logging |

## Methods — `LLMApi` (Protocol)

```python
def create_response(
    self, *, model: str, input: Any,
    temperature: Optional[float] = None,
    tools: Optional[list[dict]] = None,
    tool_choice: Optional[str] = None,
    store: Optional[bool] = None,
    metadata: Optional[Dict[str, Any]] = None,
    previous_response_id: Optional[str] = None,
    text: Optional[Dict[str, Any]] = None,
) -> LLMResponse
```

## Methods — `LLMAdapter` (Protocol)

| Method | Signature | Description |
|---|---|---|
| `call_model` | `(self, *, model, input, temperature, tools, tool_choice, store, metadata, previous_response_id, text) -> Any` | Calls the LLM, returns raw response |
| `extract_tool_calls` | `(self, response: Any) -> List[Dict[str, Any]]` | Extracts tool calls in normalized shape `{id, name, arguments}` |
| `format_tool_output` | `(self, *, call_id: str, output: str) -> Dict[str, Any]` | Formats tool result for the model's protocol |
| `get_text` | `(self, response: Any) -> str` | Extracts text content from response |
| `get_response_id` | `(self, response: Any) -> Optional[str]` | Extracts response ID for continuation |

## Methods — `OpenAIResponsesApi`

| Method | Signature | Description |
|---|---|---|
| `__init__` | `(self, *, client, max_attempts, backoff_base, backoff_cap)` | Accepts optional mock client, configures retry |
| `create_response` | `(self, **kwargs) -> LLMResponse` | Calls OpenAI Responses API with retry/backoff |
| `_build_default_client` | `(static) -> OpenAI` | Loads credentials from `oaicred.json` |

## Methods — `DeepSeekApi`

| Method | Signature | Description |
|---|---|---|
| `__init__` | `(self, *, client, max_attempts, backoff_base, backoff_cap)` | Accepts optional mock client, configures retry |
| `create_response` | `(self, **kwargs) -> LLMResponse` | Calls DeepSeek `/chat/completions` with retry |
| `_build_default_client` | `(static) -> OpenAI` | Loads credentials from `deepseek_cred.json` |
| `_transform_tools_for_deepseek` | `(self, tools) -> Optional[list[dict]]` | Strips OpenAI-specific fields (`strict`, `additionalProperties`) |
| `_normalize_input_to_messages` | `(self, input, previous_response_id, previous_tool_calls) -> List[Dict]` | Converts tool outputs + context into message list |
| `_validate_and_fix_messages` | `(self, messages) -> List[Dict]` | Ensures proper message structure for DeepSeek |
| `_convert_tool_calls_to_assistant_message` | `(self, tool_calls) -> Dict` | Builds assistant message with `tool_calls` array |

## Methods — `RouterApi`

| Method | Signature | Description |
|---|---|---|
| `__init__` | `(self, *, openai_api, deepseek_api)` | Accepts optional pre-built API instances |
| `create_response` | `(self, **kwargs) -> LLMResponse` | Routes by model name prefix |
