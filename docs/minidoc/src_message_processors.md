# Documentation for `src/message_processors`

## YAML Front Matter
```yaml
tags:
  - src_message_processors
  - lucyproject
  - AutomationProcessor
  - FunctionCallingProcessor
  - Chat2Recorder
  - ToolExecutor
  - ToolResultTooLargeError
  - ToolHandlerError
```

## 1. Summary
The `src/message_processors` module is responsible for processing messages in a conversational AI system, particularly focusing on executing tasks and managing interactions with various tools. It serves as a bridge between user commands and the underlying task execution logic, allowing for dynamic tool selection and execution based on user input. This module fits into the overall architecture by facilitating the interaction between agents and tools, ensuring that user requests are handled efficiently and effectively.

The primary problem it solves is the orchestration of task execution in response to user commands, enabling a seamless interaction experience. It manages the complexities of tool selection, execution, and error handling, ensuring that the system can respond to user requests in a robust manner.

## 2. Architecture & Design
The module employs several key design patterns:

- **Dependency Injection**: Utilizes the `injector` library to manage dependencies, allowing for flexible and testable code.
- **Command Pattern**: The `FunctionCallingProcessor` and `AutomationProcessor` classes encapsulate command execution logic, allowing for easy extension and modification of command handling.
- **Observer Pattern**: The use of events (e.g., `SSEEvent`) allows different parts of the system to react to changes in state or actions taken, promoting loose coupling.

### Class Relationships
- `FunctionCallingProcessor` and `AutomationProcessor` both implement the `MessageProcessorInterface`, ensuring they adhere to a common interface for processing messages.
- The `ToolExecutor` class is responsible for executing tool calls, while `Chat2Recorder` handles logging events to a chat storage system.
- The `LLMLoopRunner` orchestrates the execution of tasks in a loop, managing the interaction with the LLM (Language Model).

### Legacy/V2 Split
There is no explicit legacy or v2 split mentioned in the code, but the use of dependency injection and modular design suggests a focus on maintainability and future extensibility.

### Important Design Decisions
- The decision to use JSON for command parsing and event handling allows for a flexible and easily extensible communication format.
- The use of context variables for correlation IDs in logging ensures that all logs related to a specific request can be traced easily.

## 3. Key Classes
| Class                        | Base/Parent                     | Purpose                                                                 |
|------------------------------|----------------------------------|-------------------------------------------------------------------------|
| `FunctionCallingProcessor`    | `MessageProcessorInterface`      | Processes messages and manages function calling logic.                  |
| `AutomationProcessor`         | `MessageProcessorInterface`      | Manages the execution of task lists and automation commands.            |
| `Chat2Recorder`              | N/A                              | Records chat events to a storage system.                                |
| `ToolExecutor`               | N/A                              | Executes tool calls and manages tool results.                          |
| `LLMLoopRunner`              | N/A                              | Manages the execution loop for LLM interactions.                       |
| `ToolResultTooLargeError`    | Exception                        | Raised when a tool result exceeds the maximum allowed size.            |
| `ToolHandlerError`           | Exception                        | Raised when a tool handler fails during execution.                     |

## 4. Source Files
| File                                      | Responsibility                                           | Notable Exports                                      |
|-------------------------------------------|---------------------------------------------------------|-----------------------------------------------------|
| `__init__.py`                             | Initializes the module.                                | N/A                                                 |
| `automation_processor.py`                 | Implements the `AutomationProcessor` class.           | `AutomationProcessor`                               |
| `fcp_chat2.py`                           | Implements the `Chat2Recorder` class.                 | `Chat2Recorder`                                    |
| `fcp_loop.py`                             | Implements the `LLMLoopRunner` class.                 | `LLMLoopRunner`                                    |
| `fcp_models.py`                           | Defines data models and exceptions for function calling.| `ProcessorContext`, `ToolResultTooLargeError`, `ToolHandlerError` |
| `fcp_tool_executor.py`                    | Implements the `ToolExecutor` class.                   | `ToolExecutor`                                     |
| `function_calling_processor.py`           | Implements the `FunctionCallingProcessor` class.       | `FunctionCallingProcessor`                          |
| `lazy_tool_selection.py`                  | Implements lazy tool selection logic.                  | `select_active_tool_defs`                           |
| `message_processor_interface.py`          | Defines the `MessageProcessorInterface`.                | `MessageProcessorInterface`                         |
| `processor_factory.py`                     | Implements the `ProcessorFactory` class.               | `ProcessorFactory`                                  |
| `run_metrics.py`                          | Defines metrics for tracking execution performance.     | `RunMetrics`                                       |
| `sse_events.py`                           | Defines the `SSEEvent` model for streaming responses.   | `SSEEvent`                                         |
| `types.py`                                | Defines type aliases for agent and account dictionaries. | `AgentDict`, `AccountDict`                         |

## 5. Dependencies
### Standard Library
- `json`
- `logging`
- `os`
- `time`
- `uuid`
- `contextvars`
- `datetime`

### Third-party Packages
- `injector`
- `pydantic`

### Internal Modules
- `src.agent`
- `src.config_manager`
- `src.chat2`
- `src.handlers`
- `src.prompt_builders`
- `src.storage`
- `src.tool_selection`
- `src.message_processors.types`

### Optional Dependencies
- None

## 6. Configuration / Settings
| Key                             | Type   | Default | What it controls                                      |
|---------------------------------|--------|---------|------------------------------------------------------|
| `max_tool_result_chars`         | int    | 20000   | Maximum allowed characters for tool results.         |
| `provider_throttle_ms`          | dict   | {}      | Throttle settings for different providers.           |
| `environment_prompt_block`      | str    | ""      | Environment prompt injection messages.                |
| `metrics_runs_log_path`         | str    | N/A     | Path for logging run metrics.                         |

## 7. Exceptions
| Exception                     | Base       | When Raised                                      |
|-------------------------------|------------|--------------------------------------------------|
| `ToolResultTooLargeError`     | Exception  | Raised when a tool result exceeds the max size. |
| `ToolHandlerError`            | Exception  | Raised when a tool handler fails during execution.|

## 8. Module-Level Constants
| Constant                       | Value      |
|--------------------------------|------------|
| `DEFAULT_MAX_HANDLER_SCHEMA_TOKENS` | 8000   |

## 9. Methods (by class)
### `FunctionCallingProcessor`
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `process_message`          | instance     | `def process_message(self, *, primary_agent: Agent, account: Dict[str, Any], message: str, ...)` | Processes a message and returns a result.                                  |
| `process_message_streaming`| instance     | `def process_message_streaming(self, *, primary_agent: Agent, account: Dict[str, Any], message: str, ...)` | Streaming variant of `process_message`.                                    |

### `AutomationProcessor`
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `process_message`          | instance     | `def process_message(self, *, primary_agent: Agent, account: Dict[str, Any], message: str, ...)` | Processes a message and manages task execution.                           |

### `Chat2Recorder`
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `ensure_session`           | instance     | `def ensure_session(self, ctx: ProcessorContext) -> None`               | Ensures a chat session exists for the given context.                      |
| `write_streaming_events`   | instance     | `def write_streaming_events(self, ctx: ProcessorContext, user_message: str, streamed_events: List[SSEEvent], ...)` | Writes streaming events to chat storage.                                   |

### `ToolExecutor`
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `execute_tool_calls`       | instance     | `def execute_tool_calls(self, *, tool_calls: List[_ToolCall], primary_agent: Agent, ...)` | Executes the given tool calls and returns results.                        |

### `LLMLoopRunner`
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `run`                      | instance     | `def run(self, *, ctx: ProcessorContext, prompt_messages: List[Dict[str, Any]], ...)` | Runs the LLM loop and yields events.                                       |

## 10. Usage Examples
```python
from src.message_processors import FunctionCallingProcessor

# Example of processing a message
processor = FunctionCallingProcessor(...)
result = processor.process_message(
    primary_agent=agent,
    account=account_info,
    message="Run the task list.",
    conversation_id="12345"
)
print(result.text)
```

## 11. Edge Cases & Gotchas
- **Error Handling Patterns**: The system employs a fail-fast approach, raising exceptions for invalid states or configurations. This ensures that issues are caught early in the processing pipeline.
- **Tool Selection**: The lazy tool selection mechanism may lead to under-selection of tools if the LLM does not recognize the user's intent clearly. This can be mitigated by ensuring that the prompt is clear and specific.
- **Thread-Safety**: The use of context variables for correlation IDs ensures that logging is thread-safe, as each request has its own context.

## 12. Consumers
| Consumer                          | What it uses                                      |
|-----------------------------------|--------------------------------------------------|
| `src.agent`                       | Uses `FunctionCallingProcessor` for message processing. |
| `src.chat2`                       | Uses `Chat2Recorder` for logging chat events.   |
| `src.handlers`                    | Uses various processors for handling messages.   |
| `src.prompt_builders`             | Interacts with `FunctionCallingProcessor` for prompt generation. |

---

This document provides a comprehensive overview of the `src/message_processors` module, detailing its architecture, key components, and usage patterns.