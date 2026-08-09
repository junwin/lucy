# Documentation for `src/llm` Module

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
  - OpenAIEmbeddingApi
  - MistralEmbeddingApi
  - ImageGenApi
  - EmbeddingApi
  - RouterApi
```

## 1. Summary
The `src/llm` module provides a framework for interacting with various Large Language Model (LLM) APIs, including OpenAI, DeepSeek, and Mistral. Its primary responsibility is to abstract the differences between these APIs, allowing developers to interact with them in a unified manner. This module fits into a larger architecture that aims to leverage multiple LLMs for various tasks, such as text generation, image generation, and embeddings. By providing a consistent interface, it simplifies the integration of different LLMs, enabling users to switch between them without significant code changes.

## 2. Architecture & Design
The module employs several design patterns:
- **Protocol and Adapter Pattern**: The `LLMAdapter` and `LLMApi` protocols define a standard interface for LLM interactions, while specific implementations (e.g., `OpenAIResponsesApi`, `DeepSeekApi`, `MistralApi`) adapt these protocols to their respective APIs.
- **Factory Pattern**: The `ProviderRegistry` class resolves the appropriate LLM provider based on model names and explicit provider names, allowing for lazy loading of provider classes.
- **Decorator Pattern**: The `RouterApi` class acts as a facade, routing requests to the appropriate backend based on the model name.

Classes within the module often use composition over inheritance, with many classes depending on interfaces rather than concrete implementations. This design choice enhances flexibility and testability.

The module does not appear to have a legacy/v2 split, as it is designed to be modular and extensible from the outset. Important design decisions include the use of DTOs (Data Transfer Objects) like `LLMResponse` and `LLMUsage` to standardize the data returned from various APIs.

## 3. Key Classes
| Class                     | Base/Parent | Purpose                                                                 |
|---------------------------|-------------|-------------------------------------------------------------------------|
| `LLMApi`                  | Protocol    | Interface for calling an LLM.                                          |
| `LLMAdapter`              | Protocol    | Protocol glue between the FunctionCallingProcessor and a specific LLM API. |
| `OpenAIResponsesApi`      | LLMApi      | Implementation for OpenAI's responses API.                             |
| `DeepSeekApi`             | LLMApi      | Implementation for DeepSeek API.                                       |
| `MistralApi`              | LLMApi      | Implementation for Mistral API.                                        |
| `RouterApi`               | LLMApi      | Routes LLM requests to the correct backend based on the model name.    |
| `EmbeddingApi`            | Protocol    | Interface for calling an embeddings model.                             |
| `ImageGenApi`             | Protocol    | Interface for calling an image generation model.                       |
| `ProviderRegistry`        | -           | Resolves provider names and returns instances of their LLMApi implementations. |

## 4. Source Files
| File                          | Responsibility                                               | Notable Exports                                                                 |
|-------------------------------|-------------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`                 | Initializes the module and exports key classes and APIs.   | `LLMApi`, `LLMAdapter`, `LLMResponse`, `LLMUsage`, `ToolCall`, `OpenAIResponsesApi`, `DeepSeekApi`, `MistralApi` |
| `adapter_interface.py`        | Defines the `LLMAdapter` protocol.                          | `LLMAdapter`                                                                    |
| `deepseek_responses.py`       | Implements the DeepSeek API.                                | `DeepSeekApi`                                                                   |
| `dto.py`                      | Defines data transfer objects for responses and usage.      | `LLMResponse`, `LLMUsage`, `ToolCall`                                         |
| `embedding_interface.py`      | Defines the `EmbeddingApi` protocol.                        | `EmbeddingApi`                                                                  |
| `embedding_router.py`         | Routes embedding requests to the correct backend.           | `EmbeddingRouter`                                                               |
| `imagegen_interface.py`       | Defines the `ImageGenApi` protocol.                         | `ImageGenApi`                                                                  |
| `imagegen_router.py`          | Routes image generation requests to the correct backend.    | `ImageGenRouter`                                                                |
| `interface.py`                | Defines the `LLMApi` protocol.                             | `LLMApi`                                                                       |
| `mistral_api.py`             | Implements the Mistral API.                                | `MistralApi`                                                                   |
| `mistral_embedding.py`        | Implements the Mistral Embeddings API.                      | `MistralEmbeddingApi`                                                          |
| `mistral_responses_adapter.py`| Adapter for Mistral API responses.                          | `MistralResponsesAdapter`                                                      |
| `openai_embedding.py`         | Implements the OpenAI Embeddings API.                       | `OpenAIEmbeddingApi`                                                            |
| `openai_imagegen.py`         | Implements the OpenAI Image Generation API.                 | `OpenAIImageGenApi`                                                            |
| `openai_responses.py`         | Implements the OpenAI Responses API.                        | `OpenAIResponsesApi`                                                            |
| `openai_responses_adapter.py` | Adapter for OpenAI Responses API.                           | `OpenAIResponsesAdapter`                                                        |
| `provider_registry.py`        | Manages provider resolution for LLM backends.              | `ProviderRegistry`                                                              |
| `router_api.py`              | Routes LLM requests to the correct backend.                 | `RouterApi`                                                                     |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `logging`
  - `os`
  - `random`
  - `time`
  - `importlib`
  - `typing`
  
- **Third-party packages**:
  - `openai` (optional, for LLM interactions)

- **Internal modules**:
  - `src.config_manager`
  
- **Optional dependencies**:
  - The `openai` package is conditionally imported in several files, allowing the module to function in test environments without it.

## 6. Configuration / Settings
| Key                     | Type   | Default         | What it controls                                      |
|-------------------------|--------|-----------------|------------------------------------------------------|
| `credential_path`       | String | None            | Path to the credentials for API access.              |

## 7. Exceptions
| Exception                     | Base                | When Raised                                      |
|-------------------------------|---------------------|--------------------------------------------------|
| None                          | None                | None                                             |

## 8. Module-Level Constants
| Constant                     | Value                          |
|------------------------------|--------------------------------|
| None                         | None                           |

## 9. Methods (by class)

### `LLMApi`
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `supports_image_processing` | instance     | `def supports_image_processing(self, model: str) -> bool:`              | Checks if the model supports image processing.                             |
| `create_response`          | instance     | `def create_response(self, *, model: str, input: Any, ...) -> LLMResponse:` | Creates a response from the LLM based on the input and model.             |

### `LLMAdapter`
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `supports_image_processing` | instance     | `def supports_image_processing(self, model: str, provider: Optional[str] = None) -> bool:` | Checks if the model supports image processing.                             |
| `call_model`               | instance     | `def call_model(self, *, model: str, input: Any, ...) -> Any:`         | Calls the model with the provided input and parameters.                    |
| `extract_tool_calls`       | instance     | `def extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:` | Extracts tool calls from the model's response.                            |
| `format_tool_output`       | instance     | `def format_tool_output(self, *, call_id: str, output: str) -> Dict[str, Any]:` | Formats the tool output for the model's expected protocol.                |
| `get_text`                 | instance     | `def get_text(self, response: Any) -> str:`                             | Extracts text from the model's response.                                   |
| `get_response_id`          | instance     | `def get_response_id(self, response: Any) -> Optional[str]:`           | Retrieves the response ID from the model's response.                      |

### `OpenAIResponsesApi`
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `supports_image_processing` | instance     | `def supports_image_processing(self, model: str) -> bool:`              | Checks if OpenAI models support image processing.                          |
| `create_response`          | instance     | `def create_response(self, *, model: str, input: Any, ...) -> LLMResponse:` | Creates a response from the OpenAI API based on the input and model.      |

### `DeepSeekApi`
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `supports_image_processing` | instance     | `def supports_image_processing(self, model: str) -> bool:`              | Checks if DeepSeek models support image processing.                        |
| `create_response`          | instance     | `def create_response(self, *, model: str, input: Any, ...) -> LLMResponse:` | Creates a response from the DeepSeek API based on the input and model.    |

### `MistralApi`
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `supports_image_processing` | instance     | `def supports_image_processing(self, model: str) -> bool:`              | Checks if Mistral models support image processing.                         |
| `create_response`          | instance     | `def create_response(self, *, model: str, input: Any, ...) -> LLMResponse:` | Creates a response from the Mistral API based on the input and model.     |

### `RouterApi`
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `supports_image_processing` | instance     | `def supports_image_processing(self, model: str, provider: Optional[str] = None) -> bool:` | Checks if the selected model supports native image processing.             |
| `create_response`          | instance     | `def create_response(self, *, model: str, input: Any, ...) -> LLMResponse:` | Routes the request to the appropriate backend and creates a response.      |

## 10. Usage Examples
```python
from src.llm import RouterApi

# Initialize the router API
router = RouterApi()

# Create a response using the router
response = router.create_response(
    model="openai-gpt-3.5-turbo",
    input="What is the capital of France?",
    temperature=0.7
)

print(response.output_text)  # Outputs the response from the LLM
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a retry mechanism with exponential backoff for transient errors when calling external APIs. This is crucial for robustness, especially when dealing with rate limits or temporary outages.
- **Provider Resolution**: The `ProviderRegistry` class resolves providers based on model names and explicit provider names. If a provider cannot be instantiated, a dummy implementation is returned to avoid breaking the application.
- **Thread Safety**: The module does not explicitly mention thread safety. Care should be taken when using shared instances of API clients across threads.

## 12. Consumers
| Consumer                     | What it uses                                                   |
|------------------------------|---------------------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm.                          |