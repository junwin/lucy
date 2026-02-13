---
tags:
  - llm
  - protocol
  - llmresponse
  - openai
  - dataclasse
  - temperature
  - tool_choice
  - store
  - metadata
  - previous_response_id
  - src/llm
---

# `src/llm`

## Purpose
LLM abstraction layer. Defines a normalized interface (`LLMApi`) and adapter contract (`LLMAdapter`) so the rest of the codebase (e.g., the FunctionCallingProcessor) can stay mostly LLM-provider agnostic.

## Source files
- `src/llm/__init__.py` (exports public API; optional OpenAI imports)
- `src/llm/interface.py` (`LLMApi` protocol)
- `src/llm/adapter_interface.py` (`LLMAdapter` protocol)
- `src/llm/dto.py` (normalized DTOs: `ToolCall`, `LLMUsage`, `LLMResponse`)
- `src/llm/openai_responses_adapter.py` (`OpenAIResponsesAdapter`)
- `src/llm/openai_responses.py` (`OpenAIResponsesApi` + extraction helpers)

## Key classes / protocols
- **`LLMApi`** (`src/llm/interface.py`)
  - Protocol for calling an LLM and returning a normalized `LLMResponse`.
- **`LLMAdapter`** (`src/llm/adapter_interface.py`)
  - Protocol glue between the FunctionCallingProcessor and a specific LLM API.
  - Responsible for calling the model, extracting tool calls, formatting tool outputs, and reading text/response id.
- **DTOs** (`src/llm/dto.py`)
  - `ToolCall(call_id, name, arguments_json)`
  - `LLMUsage(input_tokens, output_tokens, total_tokens, raw)`
  - `LLMResponse(response_id, model, output_text, tool_calls, usage, raw)`
- **`OpenAIResponsesAdapter`** (`src/llm/openai_responses_adapter.py`)
  - Implements `LLMAdapter` on top of an `LLMApi`.
  - Normalizes tool calls into `{id, name, arguments}` and tool outputs into `{type: function_call_output, call_id, output}`.
- **`OpenAIResponsesApi`** (`src/llm/openai_responses.py`)
  - Implements `LLMApi` using the OpenAI Responses API.
  - Includes retry/backoff for common transient OpenAI errors.

## Dependencies
- **stdlib:** `typing`, `dataclasses`, `json`, `logging`, `os`, `random`, `time`
- **third-party:** `openai` (optional; module provides lightweight fallbacks when not installed)
- **internal:** `src.config_manager.ConfigManager`

## Methods in the module service/base class
### `LLMApi` (service interface)
- `create_response(*, model, input, temperature=None, tools=None, tool_choice=None, store=None, metadata=None, previous_response_id=None, text=None) -> LLMResponse`

### `LLMAdapter` (adapter interface)
- `call_model(*, model, input, temperature=None, tools=None, tool_choice=None, store=None, metadata=None, previous_response_id=None, text=None) -> Any`
- `extract_tool_calls(response) -> list[dict]`
- `format_tool_output(*, call_id, output) -> dict`
- `get_text(response) -> str`
- `get_response_id(response) -> str | None`

### `OpenAIResponsesApi` (concrete service)
- `__init__(*, client=None, max_attempts=4, backoff_base=0.5, backoff_cap=8.0)`
- `_build_default_client() -> OpenAI`
- `create_response(...) -> LLMResponse`

### `OpenAIResponsesAdapter` (concrete adapter)
- `__init__(api: LLMApi)`
- `call_model(...) -> Any`
- `extract_tool_calls(response) -> list[dict]`
- `format_tool_output(*, call_id, output) -> dict`
- `get_text(response) -> str`
- `get_response_id(response) -> str | None`
