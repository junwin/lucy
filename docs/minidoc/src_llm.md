# Module Documentation for `src/llm`

## YAML Front Matter
```yaml
tags:
  - src_llm
  - lucyproject
  - LLMResponse
  - LLMUsage
  - ToolCall
  - LLMApi
  - LLMAdapter
  - DeepSeekApi
  - MistralApi
  - OpenAIResponsesApi
  - RouterApi
  - OpenAIResponsesAdapter
  - MistralResponsesAdapter
```

## 1. Summary
The `src/llm` module provides a unified interface for interacting with various Large Language Model (LLM) APIs, including OpenAI, DeepSeek, and Mistral. Its primary responsibility is to abstract the differences between these APIs, allowing users to interact with them in a consistent manner. This module fits into the overall architecture as a middleware layer that facilitates communication between the application and different LLM backends, effectively solving the problem of API compatibility and simplifying the integration process for developers.

## 2. Architecture & Design
The module employs several design patterns to achieve its goals:

- **Protocol and Interface**: The `LLMApi` protocol defines a standard interface for all LLM implementations, ensuring that they return a normalized `LLMResponse`. This allows the rest of the codebase to remain agnostic of the underlying API specifics.
  
- **Adapter Pattern**: The `LLMAdapter` interface serves as a bridge between the function-calling processor and specific LLM APIs. Adapters like `OpenAIResponsesAdapter` and `MistralResponsesAdapter` implement this interface, allowing for seamless integration with their respective APIs.

- **Factory Pattern**: The `RouterApi` class acts as a factory that routes requests to the appropriate backend based on the model name, encapsulating the logic for selecting the correct API.

- **Error Handling**: The module includes robust error handling, particularly in the `create_response` methods of various API classes, which implement retry logic with exponential backoff for transient errors.

The design decisions are evident in the comments and docstrings, emphasizing the need for a consistent interface and the importance of error handling in API interactions.

## 3. Key Classes
| Class                       | Base/Parent | Purpose                                                                 |
|-----------------------------|--------------|-------------------------------------------------------------------------|
| `LLMApi`                    | Protocol     | Defines the interface for LLM implementations.                          |
| `LLMAdapter`                | Protocol     | Interface for adapters that connect to specific LLM APIs.              |
| `OpenAIResponsesApi`        | LLMApi       | Implementation for OpenAI's API.                                       |
| `DeepSeekApi`               | LLMApi       | Implementation for DeepSeek's API.                                     |
| `MistralApi`                | LLMApi       | Implementation for Mistral's API.                                      |
| `RouterApi`                 | LLMApi       | Routes requests to the appropriate LLM backend based on model name.    |
| `OpenAIResponsesAdapter`    | LLMAdapter   | Adapter for OpenAI Responses API.                                       |
| `MistralResponsesAdapter`   | LLMAdapter   | Adapter for Mistral API.                                               |
| `LLMResponse`               | None         | Data Transfer Object for normalized LLM responses.                     |
| `LLMUsage`                  | None         | Data Transfer Object for usage statistics.                              |
| `ToolCall`                  | None         | Data Transfer Object for normalized tool calls.                        |

## 4. Source Files
| File                          | Responsibility                                           | Notable Exports                                                                 |
|-------------------------------|---------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`                 | Initializes the module and exports key classes.        | `LLMApi`, `LLMAdapter`, `LLMResponse`, `LLMUsage`, `ToolCall`, `OpenAIResponsesApi`, `MistralApi`, `DeepSeekApi` |
| `adapter_interface.py`        | Defines the `LLMAdapter` protocol.                      | `LLMAdapter`                                                                    |
| `deepseek_responses.py`       | Implements the DeepSeek API.                            | `DeepSeekApi`                                                                  |
| `dto.py`                      | Contains data transfer objects for responses and usage. | `LLMResponse`, `LLMUsage`, `ToolCall`                                         |
| `interface.py`                | Defines the `LLMApi` protocol.                          | `LLMApi`                                                                       |
| `mistral_api.py`             | Implements the Mistral API.                            | `MistralApi`                                                                   |
| `mistral_responses_adapter.py`| Adapter for Mistral API.                               | `MistralResponsesAdapter`                                                      |
| `openai_responses.py`         | Implements the OpenAI Responses API.                    | `OpenAIResponsesApi`                                                           |
| `openai_responses_adapter.py`  | Adapter for OpenAI Responses API.                       | `OpenAIResponsesAdapter`                                                       |
| `router_api.py`               | Routes requests to the appropriate LLM backend.        | `RouterApi`                                                                    |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `os`
  - `logging`
  - `random`
  - `time`
  - `typing`

- **Third-party packages**:
  - `openai`

- **Internal modules**:
  - `src.config_manager`
  - `src.llm.dto`
  - `src.llm.interface`

- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                     | Type    | Default | What it controls                                      |
|-------------------------|---------|---------|------------------------------------------------------|
| `credential_path`       | String  | None    | Path to the directory containing API credentials.    |
| `max_description_chars` | Integer | 500     | Maximum characters for image descriptions.           |
| `vision_proxy`          | Dict    | None    | Configuration for the vision proxy.                  |

## 7. Exceptions
| Exception                | Base         | When Raised                                      |
|--------------------------|--------------|--------------------------------------------------|
| None                     | None         | None                                             |

## 8. Module-Level Constants
| Constant                 | Value                          |
|--------------------------|--------------------------------|
| `DEEPSEEK_BASE_URL`      | `"https://api.deepseek.com"`  |
| `MISTRAL_BASE_URL`       | `"https://api.mistral.ai/v1"` |

## 9. Methods (by class)

### `LLMApi`
| Method          | Type         | Signature                                                                 | Description                                                                 |
|-----------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `create_response`| instance     | `def create_response(self, *, model: str, input: Any, ...) -> LLMResponse:` | Creates a response from the LLM based on the provided model and input.    |

### `LLMAdapter`
| Method          | Type         | Signature                                                                 | Description                                                                 |
|-----------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `call_model`    | instance     | `def call_model(self, *, model: str, input: Any, ...) -> Any:`          | Calls the model with the specified parameters.                             |
| `extract_tool_calls` | instance | `def extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:` | Extracts tool calls from the model's response.                            |
| `format_tool_output` | instance | `def format_tool_output(self, *, call_id: str, output: str) -> Dict[str, Any]:` | Formats the tool output for the model.                                     |
| `get_text`      | instance     | `def get_text(self, response: Any) -> str:`                             | Retrieves the text from the model's response.                              |
| `get_response_id` | instance   | `def get_response_id(self, response: Any) -> Optional[str]:`           | Retrieves the response ID from the model's response.                       |

### `OpenAIResponsesApi`
| Method          | Type         | Signature                                                                 | Description                                                                 |
|-----------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `create_response`| instance     | `def create_response(self, *, model: str, input: Any, ...) -> LLMResponse:` | Creates a response from the OpenAI API.                                   |

### `DeepSeekApi`
| Method          | Type         | Signature                                                                 | Description                                                                 |
|-----------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `create_response`| instance     | `def create_response(self, *, model: str, input: Any, ...) -> LLMResponse:` | Creates a response from the DeepSeek API.                                 |

### `MistralApi`
| Method          | Type         | Signature                                                                 | Description                                                                 |
|-----------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `create_response`| instance     | `def create_response(self, *, model: str, input: Any, ...) -> LLMResponse:` | Creates a response from the Mistral API.                                  |

### `RouterApi`
| Method          | Type         | Signature                                                                 | Description                                                                 |
|-----------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `create_response`| instance     | `def create_response(self, *, model: str, input: Any, ...) -> LLMResponse:` | Routes the request to the appropriate LLM backend based on the model name. |

## 10. Usage Examples
```python
from src.llm import RouterApi

router = RouterApi()
response = router.create_response(
    model="deepseek",
    input="What is the capital of France?",
    temperature=0.7
)
print(response.output_text)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module implements a robust error handling mechanism, particularly in the `create_response` methods, which include retries for transient errors.
- **Model Routing**: Ensure that the model names are correctly prefixed (e.g., "deepseek", "mistral") to route requests properly.
- **Configuration**: Missing or incorrect configuration can lead to runtime errors, especially when accessing API credentials.

## 12. Consumers
| Consumer                | What it uses                                      |
|-------------------------|--------------------------------------------------|
| Unknown                 | Unknown — trace imports to confirm.              |