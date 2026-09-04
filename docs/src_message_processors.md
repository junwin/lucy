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
  - LLMLoopRunner
  - ToolResultTooLargeError
  - ToolHandlerError
```

## 1. Summary
The `src/message_processors` module is responsible for processing messages in a conversational AI system, particularly focusing on executing tasks and managing interactions with various tools. It serves as a bridge between user commands and the underlying task execution logic, allowing for dynamic tool selection and execution based on user input. This module fits into the overall architecture by enabling the integration of various agents and tools, facilitating complex workflows, and ensuring that tasks are executed efficiently and correctly.

The primary problem it solves is the orchestration of task execution in response to user commands, allowing for a flexible and extensible system that can adapt to different user needs and tool capabilities.

## 2. Architecture & Design
The module employs several key design patterns:
- **Dependency Injection**: Utilizes the `injector` library to manage dependencies, ensuring that components are loosely coupled and easily testable.
- **Strategy Pattern**: The `ProcessorFactory` class allows for dynamic selection of message processors based on configuration, enabling different processing strategies.
- **Observer Pattern**: The use of events (e.g., `SSEEvent`) allows for a decoupled way to handle asynchronous updates and notifications.

Classes within the module relate to each other through composition and inheritance. For example, `FunctionCallingProcessor` and `AutomationProcessor` both implement the `MessageProcessorInterface`, ensuring they adhere to a common interface while providing specific implementations.

There is no explicit legacy/v2 split, but the design allows for backward compatibility through careful management of tool definitions and command parsing.

Important design decisions include:
- The use of JSON for command parsing, which allows for a structured and extensible way to handle user input.
- The separation of concerns between different processors, allowing for specialized handling of various types of messages and tasks.

## 3. Key Classes
| Class                        | Base/Parent                     | Purpose                                                                 |
|------------------------------|----------------------------------|-------------------------------------------------------------------------|
| `AutomationProcessor`        | `MessageProcessorInterface`      | Manages the execution of task lists based on user commands.            |
| `FunctionCallingProcessor`   | `MessageProcessorInterface`      | Handles the processing of messages that involve function calls.        |
| `Chat2Recorder`             | `None`                           | Records events to the Chat2 storage system.                            |
| `ToolExecutor`              | `None`                           | Executes tool calls and manages their results.                        |
| `LLMLoopRunner`             | `None`                           | Manages the loop for LLM interactions and tool calls.                 |
| `ToolResultTooLargeError`   | `Exception`                      | Raised when a tool result exceeds the maximum allowed size.           |
| `ToolHandlerError`          | `Exception`                      | Raised when a tool handler fails during execution.                     |

## 4. Source Files
| File                                   | Responsibility                                           | Notable Exports                                      |
|----------------------------------------|---------------------------------------------------------|-----------------------------------------------------|
| `__init__.py`                         | Initializes the module.                                 | None                                                |
| `automation_processor.py`             | Implements the `AutomationProcessor` class.            | `AutomationProcessor`                               |
| `fcp_chat2.py`                        | Implements the `Chat2Recorder` class.                  | `Chat2Recorder`                                    |
| `fcp_loop.py`                         | Implements the `LLMLoopRunner` class.                  | `LLMLoopRunner`                                    |
| `fcp_models.py`                       | Defines models and exceptions for function calling.     | `ProcessorContext`, `ToolResultTooLargeError`, `ToolHandlerError` |
| `fcp_tool_executor.py`                | Implements the `ToolExecutor` class.                   | `ToolExecutor`                                     |
| `function_calling_processor.py`       | Implements the `FunctionCallingProcessor` class.       | `FunctionCallingProcessor`                          |
| `lazy_tool_selection.py`              | Implements lazy tool selection logic.                   | `select_active_tool_defs`                           |
| `message_processor_interface.py`      | Defines the `MessageProcessorInterface`.                | `MessageProcessorInterface`                         |
| `processor_factory.py`                 | Implements the `ProcessorFactory` class.                | `ProcessorFactory`                                  |
| `run_metrics.py`                      | Defines metrics for tracking execution performance.      | `RunMetrics`                                       |
| `sse_events.py`                       | Defines the `SSEEvent` model for streaming responses.   | `SSEEvent`                                         |
| `types.py`                            | Defines type aliases for agent and account dictionaries. | `AgentDict`, `AccountDict`                         |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `logging`
  - `os`
  - `re`
  - `time`
  - `uuid`
  - `contextvars`
  - `datetime`
  
- **Third-party packages**:
  - `injector`
  - `pydantic`
  
- **Internal modules**:
  - `src.agent`
  - `src.config_manager`
  - `src.chat2`
  - `src.handlers`
  - `src.prompt_builders`
  - `src.storage`
  - `src.tool_selection`
  
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                             | Type   | Default | What it controls                                      |
|---------------------------------|--------|---------|------------------------------------------------------|
| `max_tool_result_chars`        | int    | 20000   | Maximum allowed characters for tool results.         |
| `provider_throttle_ms`         | dict   | {}      | Throttle settings for different providers.           |
| `environment_prompt_block`      | str    | ""      | Environment-wide prompt injection messages.           |
| `metrics_runs_log_path`        | str    | None    | Path for logging run metrics.                        |
| `storage_root_path`            | str    | None    | Root path for storage.                               |
| `storage_namespace`            | str    | None    | Namespace for storage.                               |

## 7. Exceptions
| Exception                       | Base       | When Raised                                                  |
|---------------------------------|------------|------------------------------------------------------------|
| `ToolResultTooLargeError`      | `Exception`| Raised when a tool result exceeds the configured limit.    |
| `ToolHandlerError`             | `Exception`| Raised when a tool handler fails during execution.         |

## 8. Module-Level Constants
| Constant                        | Value       | Description                                      |
|---------------------------------|-------------|--------------------------------------------------|
| `DEFAULT_MAX_HANDLER_SCHEMA_TOKENS` | 8000    | Default cap for handler schema tokens.          |

## 9. Methods (by class)

### AutomationProcessor
| Method                          | Type        | Signature                                                                 | Description                                                                 |
|---------------------------------|-------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                     | instance    | `def __init__(self, config: ConfigManager, registry: HandlerRegistry, ...)` | Initializes the processor with necessary dependencies.                     |
| `process_message`              | instance    | `def process_message(self, primary_agent: Agent, account: Dict[str, Any], ...)` | Processes a message and executes the corresponding task list.              |
| `execute_tasklist`             | instance    | `def execute_tasklist(self, tasklist_id: str, mode: str, ...)`         | Executes a persisted task list based on the provided ID and mode.         |

### FunctionCallingProcessor
| Method                          | Type        | Signature                                                                 | Description                                                                 |
|---------------------------------|-------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                     | instance    | `def __init__(self, config: ConfigManager, registry: HandlerRegistry, ...)` | Initializes the processor with necessary dependencies.                     |
| `process_message`              | instance    | `def process_message(self, primary_agent: Agent, account: Dict[str, Any], ...)` | Processes a message and executes the corresponding function calls.         |
| `process_message_streaming`    | instance    | `def process_message_streaming(self, primary_agent: Agent, account: Dict[str, Any], ...)` | Processes a message in a streaming manner, yielding events as they occur.  |

### Chat2Recorder
| Method                          | Type        | Signature                                                                 | Description                                                                 |
|---------------------------------|-------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                     | instance    | `def __init__(self, chat2_store: Chat2Store = None)`                   | Initializes the recorder with a Chat2 store instance.                      |
| `ensure_session`               | instance    | `def ensure_session(self, ctx: ProcessorContext) -> None`               | Ensures a chat session exists for the given context.                       |
| `write_streaming_events`       | instance    | `def write_streaming_events(self, ctx: ProcessorContext, user_message: str, streamed_events: List[SSEEvent], ...)` | Writes streaming events to the Chat2 storage.                              |

### ToolExecutor
| Method                          | Type        | Signature                                                                 | Description                                                                 |
|---------------------------------|-------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                     | instance    | `def __init__(self, registry: HandlerRegistry, config: ConfigManager, ...)` | Initializes the executor with necessary dependencies.                      |
| `execute_tool_calls`           | instance    | `def execute_tool_calls(self, tool_calls: List[_ToolCall], ...)`       | Executes the provided tool calls and returns their results.               |

## 10. Usage Examples
```python
from src.message_processors import FunctionCallingProcessor
from src.config_manager import ConfigManager
from src.handlers.handler_registry import HandlerRegistry

config = ConfigManager()
registry = HandlerRegistry()
processor = FunctionCallingProcessor(config=config, registry=registry)

result = processor.process_message(
    primary_agent=agent,
    account=account,
    message='{"action": "run", "tasklist_id": "my_tasklist_1", "mode": "multi-step"}'
)
print(result.text)
```

## 11. Edge Cases & Gotchas
- **Error Handling Patterns**: The module employs a fail-fast approach, raising exceptions when encountering invalid states or configurations. This ensures that issues are caught early in the processing pipeline.
- **Tool Selection**: The lazy tool selection mechanism may lead to under-selection of tools if the LLM does not recognize the necessary actions. This can be mitigated by ensuring that the prompt is clear and specific.
- **Thread-Safety**: The use of context variables ensures that state is managed correctly across concurrent executions, but care should be taken when accessing shared resources.
- **Known Limitations**: The module may not handle all edge cases in JSON parsing, particularly with malformed input. Robust validation should be implemented where necessary.

## 12. Consumers
| Consumer                        | What it uses                                           |
|--------------------------------|-------------------------------------------------------|
| `src.main`                     | Uses `FunctionCallingProcessor` for processing messages. |
| `src.agent`                    | Interacts with `AutomationProcessor` for task execution. |
| `src.chat2`                   | Uses `Chat2Recorder` for logging chat events.       |
| `src.handlers`                 | Uses `ToolExecutor` for executing tool calls.       |

---

This document provides a comprehensive overview of the `src/message_processors` module, detailing its structure, functionality, and usage.