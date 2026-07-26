# Module Documentation for `src/llm`

## YAML Front Matter
```yaml
tags:
  - src_llm
  - lucyproject
  - LLMResponse
  - LLMUsage
  - ToolCall
  - LLMAdapter
  - LLMApi
  - DeepSeekApi
  - MistralApi
  - OpenAIResponsesApi
  - EmbeddingApi
  - ImageGenApi
```

## 1. Summary
The `src/llm` module serves as a comprehensive interface for interacting with various Large Language Models (LLMs) and embedding/image generation APIs. It abstracts the complexities of different LLM backends, allowing users to seamlessly switch between them based on model names. This module is crucial in the architecture of the Lucy project, as it provides a unified way to handle requests and responses from multiple LLM providers, including OpenAI, DeepSeek, and Mistral. The primary problem it solves is the need for a consistent interface to interact with diverse LLMs, enabling developers to focus on application logic rather than the intricacies of each API.

## 2. Architecture & Design
The module employs several design patterns to achieve its goals:

- **Protocol and Adapter Patterns**: The use of `LLMApi` and `LLMAdapter` protocols allows for a flexible architecture where different LLM implementations can be easily swapped without changing the core logic. Adapters like `OpenAIResponsesAdapter` and `MistralResponsesAdapter` serve as glue between the LLM API and the function calling processor, ensuring that the processor remains LLM-agnostic.

- **Factory Pattern**: The `RouterApi` class acts as a factory that routes requests to the appropriate backend based on the model name. This design decision simplifies the client code, allowing it to interact with a single interface regardless of the underlying implementation.

- **Error Handling and Retry Logic**: The module includes robust error handling and retry mechanisms, particularly in the `MistralApi` and `OpenAIResponsesApi` classes. This ensures that transient errors do not disrupt the user experience.

- **Normalization of Responses**: The module normalizes responses from different LLMs into a consistent format (`LLMResponse`), which simplifies downstream processing.

The design also reflects a clear separation of concerns, with distinct classes handling specific functionalities, such as embedding and image generation.

## 3. Key Classes
| Class                       | Base/Parent | Purpose                                                                 |
|-----------------------------|--------------|-------------------------------------------------------------------------|
| `LLMApi`                    | Protocol     | Interface for calling an LLM.                                           |
| `LLMAdapter`                | Protocol     | Protocol glue between the processor and specific LLM APIs.             |
| `OpenAIResponsesApi`        | LLMApi       | Implementation for OpenAI's responses API.                             |
| `DeepSeekApi`               | LLMApi       | Implementation for DeepSeek API.                                       |
| `MistralApi`                | LLMApi       | Implementation for Mistral API.                                        |
| `RouterApi`                 | LLMApi       | Routes requests to the appropriate LLM backend based on model name.    |
| `EmbeddingApi`              | Protocol     | Interface for calling an embeddings model.                              |
| `ImageGenApi`               | Protocol     | Interface for calling an image generation model.                        |
| `OpenAIEmbeddingApi`        | EmbeddingApi | Implementation for OpenAI's embedding API.                             |
| `MistralEmbeddingApi`       | EmbeddingApi | Implementation for Mistral's embedding API.                            |
| `OpenAIImageGenApi`         | ImageGenApi  | Implementation for OpenAI's image generation API.                      |
| `MistralResponsesAdapter`   | LLMAdapter    | Adapter for Mistral API responses.                                     |
| `OpenAIResponsesAdapter`    | LLMAdapter    | Adapter for OpenAI responses.                                          |

## 4. Source Files
| File                          | Responsibility                                               | Notable Exports                                                                 |
|-------------------------------|-------------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`                 | Initializes the module and exports key classes and APIs.   | `LLMApi`, `LLMAdapter`, `LLMResponse`, `LLMUsage`, `ToolCall`, `OpenAIResponsesApi`, `DeepSeekApi`, `MistralApi` |
| `adapter_interface.py`        | Defines the `LLMAdapter` protocol.                          | `LLMAdapter`                                                                    |
| `deepseek_responses.py`       | Implements the DeepSeek API.                                | `DeepSeekApi`                                                                  |
| `dto.py`                      | Defines data transfer objects for responses and usage.      | `LLMResponse`, `LLMUsage`, `ToolCall`                                        |
| `embedding_interface.py`      | Defines the `EmbeddingApi` protocol.                        | `EmbeddingApi`                                                                  |
| `embedding_router.py`         | Routes embedding requests to the correct backend.           | `EmbeddingRouter`                                                               |
| `imagegen_interface.py`       | Defines the `ImageGenApi` protocol.                         | `ImageGenApi`                                                                  |
| `imagegen_router.py`          | Routes image generation requests to the correct backend.    | `ImageGenRouter`                                                               |
| `interface.py`                | Defines the `LLMApi` protocol.                             | `LLMApi`                                                                       |
| `mistral_api.py`             | Implements the Mistral API.                                | `MistralApi`                                                                   |
| `mistral_embedding.py`        | Implements Mistral's embedding API.                         | `MistralEmbeddingApi`                                                          |
| `mistral_responses_adapter.py`| Adapter for Mistral API responses.                          | `MistralResponsesAdapter`                                                      |
| `openai_embedding.py`         | Implements OpenAI's embedding API.                          | `OpenAIEmbeddingApi`                                                           |
| `openai_imagegen.py`          | Implements OpenAI's image generation API.                   | `OpenAIImageGenApi`                                                            |
| `openai_responses.py`         | Implements OpenAI's responses API.                          | `OpenAIResponsesApi`                                                           |
| `openai_responses_adapter.py` | Adapter for OpenAI responses.                               | `OpenAIResponsesAdapter`                                                       |
| `router_api.py`               | Routes LLM requests to the correct backend.                 | `RouterApi`                                                                    |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `logging`
  - `os`
  - `random`
  - `time`
  - `typing`
  
- **Third-party packages**:
  - `openai` (optional, for LLM interactions)

- **Internal modules**:
  - `src.config_manager`
  - `src.llm.dto`
  - `src.llm.interface`
  - `src.llm.openai_responses`
  
- **Optional dependencies**:
  - The `openai` package is imported within a try/except block to allow for test environments where it may not be available.

## 6. Configuration / Settings
| Key                     | Type    | Default         | What it controls                                      |
|-------------------------|---------|------------------|------------------------------------------------------|
| `credential_path`       | String  | None             | Path to the directory containing credential files.   |
| `max_attempts`         | Integer | 4                | Maximum number of attempts for API calls.            |
| `backoff_base`         | Float   | 0.5              | Base time for exponential backoff on retries.       |
| `backoff_cap`          | Float   | 8.0              | Maximum cap for backoff time.                        |
| `vision_proxy.enabled`  | Boolean | True             | Enables or disables the vision proxy for image handling. |
| `vision_proxy.max_description_chars` | Integer | 500 | Maximum characters for image descriptions. |

## 7. Exceptions
| Exception                     | Base         | When Raised                                      |
|-------------------------------|--------------|--------------------------------------------------|
| None                          | None         | No custom exceptions defined in this module.    |

## 8. Module-Level Constants
| Constant                     | Value                          |
|------------------------------|--------------------------------|
| `DEEPSEEK_BASE_URL`          | "https://api.deepseek.com"    |
| `MISTRAL_BASE_URL`           | "https://api.mistral.ai/v1"   |

## 9. Methods (by class)

### `DeepSeekApi`
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `create_response`          | instance     | `def create_response(self, *, model: str, input: Any, ...) -> LLMResponse:` | Creates a response from the DeepSeek API, normalizing input and handling retries. |
| `_build_default_client`    | static       | `def _build_default_client() -> OpenAI:`                                 | Builds a default OpenAI client using credentials from a config file.      |
| `_has_image_content`       | static       | `def _has_image_content(messages: List[Dict[str, Any]]) -> bool:`       | Checks if any message contains image content.                             |
| `_strip_image_parts`       | static       | `def _strip_image_parts(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:` | Strips image parts from messages, retaining only text.                   |
| `_describe_image_via_proxy`| static       | `def _describe_image_via_proxy(image_part: Dict[str, Any], ...) -> str:` | Describes an image using a vision proxy model.                           |
| `_resolve_images_via_proxy`| static       | `def _resolve_images_via_proxy(messages: List[Dict[str, Any]], ...) -> List[Dict[str, Any]]:` | Processes image content through a vision proxy.                          |
| `_transform_tools_for_deepseek` | instance | `def _transform_tools_for_deepseek(tools: Optional[list[dict]]) -> Optional[list[dict]]:` | Transforms tools to DeepSeek format.                                     |
| `_convert_tool_calls_to_assistant_message` | instance | `def _convert_tool_calls_to_assistant_message(tool_calls: List[ToolCall]) -> Dict[str, Any]:` | Converts tool calls to an assistant message format.                      |
| `_normalize_input_to_messages` | instance | `def _normalize_input_to_messages(input: Any, ...) -> List[Dict[str, Any]]:` | Normalizes various input formats to a list of messages.                 |
| `_validate_and_fix_messages` | instance | `def _validate_and_fix_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:` | Validates and fixes message formats.                                     |

### `MistralApi`
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `create_response`          | instance     | `def create_response(self, *, model: str, input: Any, ...) -> LLMResponse:` | Creates a response from the Mistral API, normalizing input and handling retries. |
| `_build_default_client`    | static       | `def _build_default_client() -> OpenAI:`                                 | Builds a default OpenAI client using credentials from a config file.      |
| `_normalize_content_parts`  | static       | `def _normalize_content_parts(content: Any) -> Any:`                     | Normalizes content parts to Mistral format.                               |
| `_transform_tools_for_mistral` | instance | `def _transform_tools_for_mistral(tools: Optional[list[dict]]) -> Optional[list[dict]]:` | Transforms tools to Mistral format.                                     |
| `_convert_tool_calls_to_assistant_message` | instance | `def _convert_tool_calls_to_assistant_message(tool_calls: List[ToolCall]) -> Dict[str, Any]:` | Converts tool calls to an assistant message format.                      |
| `_normalize_input_to_messages` | instance | `def _normalize_input_to_messages(input: Any, ...) -> List[Dict[str, Any]]:` | Normalizes various input formats to a list of messages.                 |
| `_validate_and_fix_messages` | instance | `def _validate_and_fix_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:` | Validates and fixes message formats.                                     |

### `OpenAIResponsesApi`
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `create_response`          | instance     | `def create_response(self, *, model: str, input: Any, ...) -> LLMResponse:` | Creates a response from the OpenAI API, normalizing input and handling retries. |
| `_build_default_client`    | static       | `def _build_default_client() -> OpenAI:`                                 | Builds a default OpenAI client using credentials from a config file.      |
| `_normalize_content_parts`  | static       | `def _normalize_content_parts(content: Any) -> Any:`                     | Normalizes content parts to OpenAI Responses API format.                   |
| `_normalize_messages`      | static       | `def _normalize_messages(messages: Any) -> Any:`                         | Normalizes messages for the OpenAI Responses API.                          |

## 10. Usage Examples
```python
from src.llm import RouterApi

# Initialize the router API
router = RouterApi()

# Create a response using a specific model
response = router.create_response(
    model="openai-gpt-3.5-turbo",
    input="What is the capital of France?",
    temperature=0.7
)

print(response.output_text)  # Outputs the response from the model
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a robust error handling mechanism, including retries with exponential backoff for transient errors. However, if the maximum number of attempts is reached, a `ValueError` will be raised.
- **Model Compatibility**: Ensure that the model names used in requests are compatible with the respective APIs. For instance, using a model name that starts with "mistral" will route the request to the Mistral API.
- **Image Handling**: The vision proxy is optional and must be enabled in the configuration for image content to be processed correctly. If disabled, attempts to send image content will raise a `RuntimeError`.
- **Thread Safety**: The module does not guarantee thread safety. If used in a multi-threaded environment, additional synchronization may be required.

## 12. Consumers
| Consumer                     | What it uses                                      |
|------------------------------|--------------------------------------------------|
| Various application modules   | Interacts with LLMs for text generation, embeddings, and image generation. |
| Testing frameworks            | May mock the LLM APIs for unit testing.         |
| Configuration management      | Uses `ConfigManager` for loading credentials.   |

---

This document provides a comprehensive overview of the `src/llm` module, detailing its architecture, key components, and usage patterns. It serves as a guide for developers looking to understand or extend the functionality of the module within the Lucy project.