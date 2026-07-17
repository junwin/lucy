---
tags:
  - src_llm
  - lucyproject
  - LLMApi
  - LLMAdapter
  - LLMResponse
  - LLMUsage
  - ToolCall
  - OpenAIResponsesApi
  - OpenAIResponsesAdapter
  - DeepSeekApi
  - MistralApi
  - MistralResponsesAdapter
  - RouterApi
---

## 1. Summary

`src/llm` is the LLM abstraction layer. It defines protocol interfaces for calling language models and adapters that normalize provider-specific response shapes into a common DTO. The module's single responsibility is to isolate every other subsystem from direct dependency on any particular LLM provider SDK.

It sits between the message processor layer (FunctionCallingProcessor, AutomationProcessor) and the external LLM providers (OpenAI, DeepSeek, Mistral). Everything above this layer works with `LLMApi` / `LLMAdapter` protocols and the frozen `LLMResponse` DTO, never with raw provider response objects.

The problem it solves: multiple LLM backends with different wire protocols (OpenAI Responses API vs. chat completions API) must look identical to the calling code. This module handles provider-specific tool transformation, message-format normalization, retry/backoff, and optional-dependency gating.

## 2. Architecture & Design

### Two-layer protocol stack

1. **`LLMApi` (Protocol)** — the low-level API interface. One method: `create_response(...) → LLMResponse`. Three concrete implementations: `OpenAIResponsesApi`, `DeepSeekApi`, `MistralApi`.

2. **`LLMAdapter` (Protocol)** — the glue layer for `FunctionCallingProcessor`. Five methods: `call_model`, `extract_tool_calls`, `format_tool_output`, `get_text`, `get_response_id`. Two concrete implementations: `OpenAIResponsesAdapter`, `MistralResponsesAdapter`.

The processor calls the adapter; the adapter delegates to the API; the API calls the provider. This indirection keeps the processor free of provider-specific concerns while the adapter handles the mapping between the processor's expected shapes and the DTO.

### Router pattern

`RouterApi` is an `LLMApi` implementation that inspects the `model` string prefix and dispatches to the correct backend:

| Prefix | Backend |
|--------|---------|
| `"deepseek"` | `DeepSeekApi` |
| `"mistral"` | `MistralApi` |
| anything else | `OpenAIResponsesApi` |

### Protocol vs. ABC

Both `LLMApi` and `LLMAdapter` use `typing.Protocol` (structural subtyping) rather than ABCs. This means any object with the right method signatures satisfies the interface — no explicit subclassing required. This is useful for testing (plain `Mock` objects work).

### DTO design

Three frozen `@dataclass(frozen=True)` DTOs:

- **`ToolCall`** — normalized tool invocation: `call_id`, `name`, `arguments_json`
- **`LLMUsage`** — best-effort token counts: `input_tokens`, `output_tokens`, `total_tokens`, plus a `raw` dict
- **`LLMResponse`** — the unified return value: `response_id`, `model`, `output_text`, `tool_calls` (list of `ToolCall`), `usage`, `raw`

Frozen dataclasses prevent accidental mutation of response data as it flows through the pipeline.

### Chat-completions backends (DeepSeek, Mistral)

Both `DeepSeekApi` and `MistralApi` use the OpenAI Python SDK configured with custom `base_url`, targeting each provider's OpenAI-compatible chat completions endpoint. Key differences from `OpenAIResponsesApi`:

- They call `client.chat.completions.create(...)` instead of `client.responses.create(...)`
- They maintain an internal `_conversation_context` dict keyed by `response_id` to reconstruct multi-turn tool-use conversations (the chat completions API is stateless)
- They must transform tool definitions (strip `strict`/`additionalProperties`) and normalize input messages
- They extract tool calls from `response.choices[0].message.tool_calls` instead of from `response.output`

Both share `_sleep_backoff` imported from `openai_responses.py`.

### Optional-dependency gating

`__init__.py` wraps the OpenAI and Mistral imports in try/except blocks. If the `openai` package is absent (e.g., in a test venv without it), `OpenAIResponsesApi`, `OpenAIResponsesAdapter`, `MistralApi`, and `MistralResponsesAdapter` are set to `None`. This prevents import-time crashes while allowing the rest of the system to import the DTOs and protocols.

The `openai_responses.py` file has its own fallback: if `from openai import OpenAI` fails, it defines stub classes so the module still imports (though runtime calls will fail).

Note: `DeepSeekApi` is **not** in the try/except block — it will fail at import time if `openai` is not installed.

## 3. Key Classes

| Class | Base/Parent | Purpose |
|-------|-------------|---------|
| `ToolCall` | (frozen dataclass) | Normalized tool call from any provider |
| `LLMUsage` | (frozen dataclass) | Normalized token usage (best-effort) |
| `LLMResponse` | (frozen dataclass) | Unified response DTO for all providers |
| `LLMApi` | `Protocol` | Interface for calling any LLM — one method `create_response` |
| `LLMAdapter` | `Protocol` | Glue between FunctionCallingProcessor and an LLMApi — 5 methods |
| `OpenAIResponsesApi` | `LLMApi` | OpenAI Responses API with retry/backoff |
| `OpenAIResponsesAdapter` | `LLMAdapter` | Adapter for OpenAI Responses API |
| `DeepSeekApi` | `LLMApi` | DeepSeek via OpenAI-compatible chat completions |
| `MistralApi` | `LLMApi` | Mistral via OpenAI-compatible chat completions |
| `MistralResponsesAdapter` | `LLMAdapter` | Adapter for Mistral API |
| `RouterApi` | `LLMApi` | Routes to the correct backend by model name prefix |

## 4. Source Files

| File | Responsibility | Notable Exports |
|------|---------------|-----------------|
| `__init__.py` | Package exports with optional-dependency gating | `LLMApi`, `LLMAdapter`, `LLMResponse`, `LLMUsage`, `ToolCall`, `OpenAIResponsesApi`, `OpenAIResponsesAdapter`, `MistralApi`, `MistralResponsesAdapter` |
| `dto.py` | Frozen dataclasses for normalized LLM data | `ToolCall`, `LLMUsage`, `LLMResponse` |
| `interface.py` | LLMApi Protocol definition | `LLMApi` |
| `adapter_interface.py` | LLMAdapter Protocol definition | `LLMAdapter` |
| `openai_responses.py` | OpenAI Responses API + helper functions + retry logic | `OpenAIResponsesApi`, `_extract_usage`, `_extract_tool_calls`, `_sleep_backoff` |
| `openai_responses_adapter.py` | Adapter wrapping OpenAIResponsesApi for processor use | `OpenAIResponsesAdapter` |
| `deepseek_responses.py` | DeepSeek chat-completions backend | `DeepSeekApi` |
| `mistral_api.py` | Mistral chat-completions backend | `MistralApi` |
| `mistral_responses_adapter.py` | Adapter wrapping MistralApi for processor use | `MistralResponsesAdapter` |
| `router_api.py` | Model-name-based dispatch to correct backend | `RouterApi` |

## 5. Dependencies

### Standard library
`json`, `logging`, `os`, `random`, `time`, `typing` (Any, Dict, List, Optional, Protocol, Tuple), `dataclasses` (dataclass), `__future__` (annotations)

### Third-party packages
- **`openai`** — OpenAI Python SDK (required at runtime for all three backends; optional at import time for OpenAI/Mistral via try/except gating)
- **`pydantic`** — (none directly; the module uses plain dataclasses, not Pydantic)

### Internal modules
- `src.config_manager.ConfigManager` — credential loading in `OpenAIResponsesApi._build_default_client()`, `DeepSeekApi._build_default_client()`, `MistralApi._build_default_client()`
- `src.llm.dto` — `LLMResponse`, `LLMUsage`, `ToolCall` (used by all API implementations)
- `src.llm.interface` — `LLMApi` (used by all API implementations)
- `src.llm.adapter_interface` — `LLMAdapter` (used by both adapters)
- `src.llm.openai_responses._sleep_backoff` — imported by `deepseek_responses.py` and `mistral_api.py`

### Optional dependencies
- The `openai` package is effectively optional at import time for the OpenAI and Mistral paths (caught by try/except in `__init__.py` and `openai_responses.py`). `DeepSeekApi` does NOT have this guard and will fail at import if `openai` is missing.

## 6. Configuration / Settings

| Key | Type | Default | What it controls |
|-----|------|---------|------------------|
| `credential_path` | `str` (from `ConfigManager("config.json")`) | None | Directory containing credential JSON files |

The `credential_path` directory is expected to contain:

| File | Loaded by | Key read |
|------|-----------|----------|
| `oaicred.json` | `OpenAIResponsesApi._build_default_client()` | `openai_api_key` |
| `deepseek_cred.json` | `DeepSeekApi._build_default_client()` | `deepseek_api_key` |
| `mistral_cred.json` | `MistralApi._build_default_client()` | `mistral_api_key` |

Constructor parameters (`max_attempts`, `backoff_base`, `backoff_cap`) are not read from config; they default to 4, 0.5, 8.0 and can only be overridden programmatically.

## 7. Exceptions

None. No custom exception classes are defined in this module.

The module uses these built-in/third-party exception types:
- `ValueError` — raised by `DeepSeekApi` and `MistralApi` when `_normalize_input_to_messages` produces an empty message list
- `RuntimeError` — raised as a safety net after retry exhaustion (should be unreachable)
- `openai.RateLimitError`, `openai.APIError`, `openai.APITimeoutError`, `openai.APIConnectionError` — caught and retried by `OpenAIResponsesApi`
- Generic `Exception` — caught broadly in `DeepSeekApi` and `MistralApi` retry loops

## 8. Module-Level Constants

| Constant | File | Value / Purpose |
|----------|------|-----------------|
| `DEEPSEEK_BASE_URL` | `deepseek_responses.py` | `"https://api.deepseek.com"` — class attribute on `DeepSeekApi` |
| `MISTRAL_BASE_URL` | `mistral_api.py` | `"https://api.mistral.ai/v1"` — class attribute on `MistralApi` |

No other module-level constants. Backoff defaults (0.5, 8.0, 4) are constructor parameter defaults, not named constants.

## 9. Methods (by class)

### ToolCall (frozen dataclass — no methods)

Fields: `call_id: str`, `name: str`, `arguments_json: str`

### LLMUsage (frozen dataclass — no methods)

Fields: `input_tokens: Optional[int]`, `output_tokens: Optional[int]`, `total_tokens: Optional[int]`, `raw: Optional[Dict[str, Any]]`

### LLMResponse (frozen dataclass — no methods)

Fields: `response_id: Optional[str]`, `model: Optional[str]`, `output_text: str`, `tool_calls: List[ToolCall]`, `usage: Optional[LLMUsage]`, `raw: Optional[Any]`

### LLMApi (Protocol)

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `create_response` | instance | `(*, model: str, input: Any, temperature: Optional[float] = None, tools: Optional[list[dict]] = None, tool_choice: Optional[str] = None, store: Optional[bool] = None, metadata: Optional[Dict[str, Any]] = None, previous_response_id: Optional[str] = None, text: Optional[Dict[str, Any]] = None) -> LLMResponse` | Calls the LLM and returns a normalized `LLMResponse`. All parameters are keyword-only. `input` can be a string, list of messages, or list of tool outputs (provider-dependent). Returns a frozen DTO with `output_text`, `tool_calls`, `usage`, and the raw provider response. |

### LLMAdapter (Protocol)

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `call_model` | instance | `(*, model, input, temperature, tools, tool_choice, store, metadata, previous_response_id, text) -> Any` | Delegates to the underlying `LLMApi.create_response`. Same signature. Returns the normalized `LLMResponse`. |
| `extract_tool_calls` | instance | `(response: Any) -> List[Dict[str, Any]]` | Extracts tool calls from a response into dicts with keys `id`, `name`, `arguments`. The `arguments` value is always a JSON string. |
| `format_tool_output` | instance | `(*, call_id: str, output: str) -> Dict[str, Any]` | Formats a tool execution result into the provider's expected shape: `{"type": "function_call_output", "call_id": ..., "output": ...}`. |
| `get_text` | instance | `(response: Any) -> str` | Extracts the plain-text output from a response. Returns stripped string, or `""` if absent. |
| `get_response_id` | instance | `(response: Any) -> Optional[str]` | Extracts the response ID for multi-turn conversation linking. Returns `None` if absent. |

### OpenAIResponsesApi

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `__init__` | instance | `(*, client: Optional[OpenAI] = None, max_attempts: int = 4, backoff_base: float = 0.5, backoff_cap: float = 8.0) -> None` | If `client` is not provided, calls `_build_default_client()` which reads `config.json` → `credential_path` → `oaicred.json` → `openai_api_key` and constructs an `OpenAI` client. Stores retry parameters. |
| `_build_default_client` | static | `() -> OpenAI` | Reads credentials from `config.json` and `oaicred.json`. Returns a configured `OpenAI` client. |
| `create_response` | instance | `(*, model, input, temperature, tools, tool_choice, store, metadata, previous_response_id, text) -> LLMResponse` | Calls `self._client.responses.create(...)`. On `RateLimitError`, `APIError`, `APITimeoutError`, or `APIConnectionError`, retries up to `max_attempts` with exponential backoff + jitter via `_sleep_backoff`. On final failure, re-raises the last exception. Extracts `response_id`, `model`, `output_text`, tool calls (via `_extract_tool_calls`), and usage (via `_extract_usage`). Extensive logging at INFO level for entry, success, and failure. |

### OpenAIResponsesAdapter

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `__init__` | instance | `(api: LLMApi) -> None` | Stores the API reference. |
| `call_model` | instance | `(*, model, input, temperature, tools, tool_choice, store, metadata, previous_response_id, text) -> Any` | Delegates to `self._api.create_response(...)`. |
| `extract_tool_calls` | instance | `(response: Any) -> List[Dict[str, Any]]` | Iterates `response.tool_calls`. For each, reads `call_id`, `name`, `arguments_json`. Converts dict `arguments` to JSON string via `json.dumps`. Returns list of `{"id", "name", "arguments"}` dicts. |
| `format_tool_output` | instance | `(*, call_id: str, output: str) -> Dict[str, Any]` | Returns `{"type": "function_call_output", "call_id": str(call_id), "output": str(output)}`. |
| `get_text` | instance | `(response: Any) -> str` | Returns `response.output_text` stripped, or `""`. |
| `get_response_id` | instance | `(response: Any) -> Optional[str]` | Returns `str(response.response_id)` or `None`. |

### DeepSeekApi

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `__init__` | instance | `(*, client: Optional[OpenAI] = None, max_attempts: int = 4, backoff_base: float = 0.5, backoff_cap: float = 8.0) -> None` | Builds client from `deepseek_cred.json` if not provided. Initializes `_conversation_context` dict. |
| `_build_default_client` | static | `() -> OpenAI` | Reads `config.json` → `credential_path` → `deepseek_cred.json` → `deepseek_api_key`. Constructs `OpenAI` client pointed at `https://api.deepseek.com`. |
| `_transform_tools_for_deepseek` | instance | `(tools: Optional[list[dict]]) -> Optional[list[dict]]` | Strips `strict` and `additionalProperties` from parameter schemas. Restructures flat `{"type":"function","name":...}` into nested `{"type":"function","function":{"name":...}}` format. |
| `_convert_tool_calls_to_assistant_message` | instance | `(tool_calls: List[ToolCall]) -> Dict[str, Any]` | Converts a list of `ToolCall` objects into an assistant message dict with `role: "assistant"`, `content: None`, and a `tool_calls` array in the chat-completions format. |
| `_normalize_input_to_messages` | instance | `(input: Any, previous_response_id: Optional[str], previous_tool_calls: Optional[List[ToolCall]]) -> List[Dict[str, Any]]` | Handles 4 input cases: tool outputs (reconstructs from `_conversation_context`), list of messages (pass-through), single dict (wraps in list), unknown (logs warning, returns `[]`). When input is tool outputs and `previous_response_id` matches stored context, rebuilds the full conversation by appending the assistant message (with tool_calls) and the tool response messages. |
| `_validate_and_fix_messages` | instance | `(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]` | Ensures every message has a `role` key. Converts flat-format tool_calls to nested format (with `function` sub-object) if needed. |
| `create_response` | instance | `(*, model, input, temperature, tools, tool_choice, store, metadata, previous_response_id, text) -> LLMResponse` | Transforms tools, normalizes input to messages, validates messages, then calls `self._client.chat.completions.create(...)`. Retries on any `Exception` with backoff. Stores conversation context keyed by `response_id`. Extracts `output_text` from `choices[0].message.content`, tool calls from `choices[0].message.tool_calls`, and usage from `resp.usage`. Returns `LLMResponse`. |

### MistralApi

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `__init__` | instance | `(*, client: Optional[OpenAI] = None, max_attempts: int = 4, backoff_base: float = 0.5, backoff_cap: float = 8.0) -> None` | Builds client from `mistral_cred.json` if not provided. Initializes `_conversation_context` dict. |
| `_build_default_client` | static | `() -> OpenAI` | Reads `config.json` → `credential_path` → `mistral_cred.json` → `mistral_api_key`. Constructs `OpenAI` client pointed at `https://api.mistral.ai/v1`. |
| `_transform_tools_for_mistral` | instance | `(tools: Optional[list[dict]]) -> Optional[list[dict]]` | Handles both nested format (`{"type":"function","function":{...}}`) and flat format (`{"type":"function","name":...}`). Always outputs nested format. Strips `strict` and `additionalProperties` via `_clean_parameters`. |
| `_clean_parameters` | instance | `(params: Any) -> dict` | Removes `strict` and `additionalProperties` keys from a parameter schema dict. These are unsupported by Mistral. |
| `_convert_tool_calls_to_assistant_message` | instance | `(tool_calls: List[ToolCall]) -> Dict[str, Any]` | Same as DeepSeekApi — converts ToolCall list to assistant message with tool_calls. |
| `_normalize_input_to_messages` | instance | `(input, previous_response_id, previous_tool_calls) -> List[Dict[str, Any]]` | Same 4-case logic as DeepSeekApi: tool outputs (reconstructs from context), message list (pass-through), single dict (wrap), unknown (warn + `[]`). |
| `_validate_and_fix_messages` | instance | `(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]` | Same as DeepSeekApi — ensures `role` field and nested tool_call format. |
| `create_response` | instance | `(*, model, input, temperature, tools, tool_choice, store, metadata, previous_response_id, text) -> LLMResponse` | Same flow as DeepSeekApi: transform tools, normalize input, validate, call chat completions, retry on Exception, store context, return `LLMResponse`. |

### MistralResponsesAdapter

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `__init__` | instance | `(api: LLMApi) -> None` | Stores the API reference. |
| `call_model` | instance | `(*, model, input, temperature, tools, tool_choice, store, metadata, previous_response_id, text) -> Any` | Delegates to `self._api.create_response(...)`. |
| `extract_tool_calls` | instance | `(response: Any) -> List[Dict[str, Any]]` | Identical to `OpenAIResponsesAdapter.extract_tool_calls`. |
| `format_tool_output` | instance | `(*, call_id: str, output: str) -> Dict[str, Any]` | Identical to `OpenAIResponsesAdapter.format_tool_output`. |
| `get_text` | instance | `(response: Any) -> str` | Identical to `OpenAIResponsesAdapter.get_text`. |
| `get_response_id` | instance | `(response: Any) -> Optional[str]` | Identical to `OpenAIResponsesAdapter.get_response_id`. |

### RouterApi

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `__init__` | instance | `(*, openai_api=None, deepseek_api=None, mistral_api=None) -> None` | Defaults each backend to a new instance if not provided. |
| `create_response` | instance | `(*, model, input, temperature, tools, tool_choice, store, metadata, previous_response_id, text) -> LLMResponse` | Routes by `model` prefix: `"deepseek"` → `self._deepseek`, `"mistral"` → `self._mistral`, else → `self._openai`. All parameters are forwarded verbatim. |

### Module-level helper functions (openai_responses.py)

| Function | Signature | Description |
|----------|-----------|-------------|
| `_extract_usage` | `(usage_obj: Any) -> Optional[LLMUsage]` | Converts an OpenAI usage object (or any object with `to_dict()` or `__dict__`) into an `LLMUsage`. Tries `to_dict()` first (Pydantic v1/v2), then `__dict__`. Extracts `input_tokens`, `output_tokens`, `total_tokens` as ints. Returns `None` if `usage_obj` is `None`. |
| `_extract_tool_calls` | `(resp: Any) -> List[ToolCall]` | Iterates `resp.output`, filters for `type == "function_call"`, extracts `call_id`, `name`, `arguments`. Normalizes arguments to JSON string (handles `None`, `str`, and dict). Extensive INFO-level logging of each item's shape. Skips items missing `call_id` or `name`. |
| `_sleep_backoff` | `(attempt: int, base: float, cap: float) -> None` | Exponential backoff with jitter. Sleeps for `min(cap, base * 2^attempt) * random(0.6, 1.4)` seconds. Logs a WARNING with delay and attempt number. Used by all three API implementations. |

## 10. Usage Examples

### Example 1: Direct OpenAI API call

```python
from src.llm.openai_responses import OpenAIResponsesApi

api = OpenAIResponsesApi()
response = api.create_response(
    model="gpt-4o",
    input="What is the capital of France?",
    temperature=0.7,
)
print(response.output_text)  # "The capital of France is Paris."
print(response.response_id)  # "resp_abc123..."
print(response.usage.input_tokens)  # 15
```

### Example 2: Through RouterApi (multi-provider)

```python
from src.llm.router_api import RouterApi

router = RouterApi()

# Automatically dispatched to OpenAIResponsesApi
resp = router.create_response(model="gpt-4o", input="Hello")

# Automatically dispatched to DeepSeekApi
resp = router.create_response(model="deepseek-chat", input="Hello")

# Automatically dispatched to MistralApi
resp = router.create_response(model="mistral-large-latest", input="Hello")
```

### Example 3: Adapter pattern (as used by FunctionCallingProcessor)

```python
from src.llm.openai_responses import OpenAIResponsesApi
from src.llm.openai_responses_adapter import OpenAIResponsesAdapter

api = OpenAIResponsesApi()
adapter = OpenAIResponsesAdapter(api)

response = adapter.call_model(model="gpt-4o", input="...")
tool_calls = adapter.extract_tool_calls(response)
text = adapter.get_text(response)
rid = adapter.get_response_id(response)

# After executing a tool:
output = adapter.format_tool_output(call_id="call_1", output="result here")
```

## 11. Edge Cases & Gotchas

1. **Optional import gating is inconsistent.** `OpenAIResponsesApi` and `MistralApi` are guarded by try/except in `__init__.py`, so they become `None` if `openai` is missing. But `DeepSeekApi` is imported eagerly by `router_api.py` without a guard — a missing `openai` package will crash the import of `router_api`.

2. **DeepSeek/Mistral context is stateful.** `DeepSeekApi` and `MistralApi` maintain `_conversation_context` as an unbounded in-memory dict keyed by `response_id`. This dict grows indefinitely and is never pruned. In long-running processes with many tool-use turns, this leaks memory.

3. **Chat-completions tool transformation is destructive.** `_transform_tools_for_deepseek` and `_transform_tools_for_mistral` strip `strict` and `additionalProperties` from parameter schemas. These keys are meaningful in OpenAI's structured output mode and their removal may cause unexpected behavior if the same tool definitions are used across providers.

4. **Flat vs. nested tool format.** Handlers produce tools in flat format (`{"type":"function","name":"x","parameters":{...}}`). The DeepSeek/Mistral `_transform_tools_*` methods handle both flat and nested (`{"type":"function","function":{"name":"x",...}}`) formats, but this dual-path logic is delicate — if a new tool format appears, both paths must be updated.

5. **Mistral adapter is a copy of OpenAI adapter.** `MistralResponsesAdapter` is structurally identical to `OpenAIResponsesAdapter` (same method implementations). The duplication exists for clarity and future divergence, but currently they could share a base class.

6. **Credentials loaded from disk on every default construction.** `_build_default_client()` reads `config.json` and a credential JSON file from disk. If many instances are created, this is wasteful. In practice, `RouterApi` creates one instance per backend at init time.

7. **Retry catches broad Exception in DeepSeek/Mistral.** `DeepSeekApi.create_response` and `MistralApi.create_response` catch plain `Exception` in their retry loops. This means even bugs (e.g., `AttributeError`) will be retried up to 4 times before surfacing.

8. **Usage extraction is best-effort.** `_extract_usage` tries `to_dict()` then `__dict__`. If the usage object has neither, `raw` is `None` and all token counts are `None`. This is silent — callers must handle `None` token counts.

9. **`RouterApi` does not validate model names.** Any unknown prefix falls through to `OpenAIResponsesApi`. There is no warning or error for mistyped model names — they just get sent to OpenAI.

10. **`_sleep_backoff` is a cross-module internal dependency.** Both `deepseek_responses.py` and `mistral_api.py` import `_sleep_backoff` from `openai_responses.py`. This creates a hidden coupling: changes to the backoff function affect all three providers.

11. **Empty arguments_json vs missing.** `_extract_tool_calls` in `openai_responses.py` uses `""` to represent missing arguments (as opposed to `"{}"` for empty object). This distinction may matter to downstream code that parses the JSON.

## 12. Consumers

| Consumer | What it uses |
|----------|-------------|
| `src/container_config.py` | `LLMAdapter`, `LLMApi`, `OpenAIResponsesAdapter`, `RouterApi` — wires up dependency injection |
| `src/curation/core.py` | `LLMApi` — passes it to summarizer for LLM-based digests |
| `src/curation/summarizer.py` | `LLMResponse` (type hint), `LLMApi` — calls `create_response` for LLM-powered summarization |
| `src/handlers/curate_chat_handler.py` | `LLMApi`, `RouterApi` — instantiates RouterApi for on-demand LLM calls during curation |
| `src/message_processors/automation_processor.py` | `LLMAdapter` — calls `call_model`, `extract_tool_calls`, `format_tool_output`, `get_text`, `get_response_id` |
| `src/message_processors/function_calling_processor.py` | `LLMAdapter` — primary consumer; drives the entire tool-calling loop through the adapter |
| `tests/conftest.py` | `Mock` LLMAdapter — all test fixtures mock the adapter protocol |
| `tests/test_function_calling_processor.py` | Mock LLMAdapter — all 9 test functions exercise the processor through mocked adapter |
| `tests/test_allowed_tools.py` | Mock LLMAdapter — 4 test functions verify tool filtering through mocked adapter |
| `tests/test_tasklists_run_handler.py` | Mock LLMAdapter — passes `None` as adapter for handler construction |
