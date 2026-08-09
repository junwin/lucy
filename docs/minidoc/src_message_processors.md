# Documentation for `src/message_processors`

## YAML Front Matter
```yaml
tags:
  - src_message_processors
  - lucyproject
  - AutomationProcessor
  - FunctionCallingProcessor
  - MessageProcessorInterface
  - ProcessorFactory
  - ToolResultTooLargeError
  - ToolHandlerError
```

## 1. Summary
The `src/message_processors` module is responsible for processing messages in a conversational AI system. It includes various processors that handle different types of messages, such as automation commands and function calls. The module fits into the overall architecture by acting as an intermediary between user inputs and the underlying logic that executes tasks or retrieves information. It solves the problem of managing complex interactions by providing a structured way to process commands, execute tasks, and handle responses.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Dependency Injection**: Utilizes the `injector` library to manage dependencies, ensuring that each processor receives the necessary components without hardcoding them.
- **Abstract Base Classes**: The `MessageProcessorInterface` defines a common interface for all message processors, promoting consistency and extensibility.

Classes within the module relate through composition and inheritance. For instance, `FunctionCallingProcessor` and `AutomationProcessor` both implement the `MessageProcessorInterface`, allowing them to be used interchangeably in contexts where a message processor is required.

The module does not appear to have a legacy/v2 split, indicating a focus on maintaining a single, coherent design.

Key design decisions include:
- The use of JSON for command parsing, which allows for flexible and structured input.
- Logging at various stages to facilitate debugging and monitoring.

## 3. Key Classes
| Class                        | Base/Parent                     | Purpose                                                                 |
|------------------------------|----------------------------------|-------------------------------------------------------------------------|
| AutomationProcessor           | MessageProcessorInterface        | Processes automation commands and manages task execution.               |
| FunctionCallingProcessor      | MessageProcessorInterface        | Handles function calls and manages interactions with external tools.    |
| MessageProcessorInterface     | ABC                              | Defines the interface for all message processors.                       |
| ProcessorFactory             | ABC                              | Creates instances of message processors based on configuration.         |
| ToolResultTooLargeError      | Exception                        | Raised when a tool result exceeds the maximum allowed size.            |
| ToolHandlerError             | Exception                        | Raised when a tool handler fails during execution.                      |

## 4. Source Files
| File                                      | Responsibility                                           | Notable Exports                                      |
|-------------------------------------------|---------------------------------------------------------|-----------------------------------------------------|
| `__init__.py`                             | Initializes the module.                                | None                                                |
| `automation_processor.py`                 | Implements the `AutomationProcessor` class.           | AutomationProcessor                                  |
| `function_calling_processor.py`           | Implements the `FunctionCallingProcessor` class.      | FunctionCallingProcessor                             |
| `message_processor_interface.py`          | Defines the `MessageProcessorInterface`.               | MessageProcessorInterface                            |
| `processor_factory.py`                     | Implements the `ProcessorFactory` class.              | ProcessorFactory                                     |
| `sse_events.py`                           | Defines the `SSEEvent` model for streaming responses.  | SSEEvent                                            |
| `types.py`                                 | Defines type aliases for agent and account dictionaries.| AgentDict, AccountDict, OptionalAgentDict           |

## 5. Dependencies
- **Standard library**:
  - `abc`
  - `importlib`
  - `json`
  - `logging`
  - `re`
  - `time`
  - `typing`
  
- **Third-party packages**:
  - `injector`
  - `pydantic`
  
- **Internal modules**:
  - `src.agent`
  - `src.config_manager`
  - `src.handlers.handler_registry`
  - `src.llm.adapter_interface`
  - `src.llm.provider_registry`
  - `src.prompt_builders.prompt_builder_interface`
  - `src.storage.base`
  - `src.storage.models`
  - `src.chat2.facade`
  - `src.chat2.models`
  - `src.tasklists.task`
  - `src.tasklists.task_list`
  
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                          | Type   | Default | What it controls                                      |
|------------------------------|--------|---------|------------------------------------------------------|
| `max_tool_result_chars`      | int    | 20000   | Maximum allowed characters for tool results.         |
| `environment_prompt_block`    | str    | ""      | System messages injected into prompts.               |
| `provider_throttle_ms`        | dict   | {}      | Throttle settings for different providers.           |
| `provider_prompt_blocks`      | dict   | {}      | Provider-specific prompt rules.                       |

## 7. Exceptions
| Exception                     | Base      | When Raised                                      |
|-------------------------------|-----------|--------------------------------------------------|
| ToolResultTooLargeError       | Exception | Raised when a tool result exceeds the max size. |
| ToolHandlerError              | Exception | Raised when a tool handler fails during execution.|

## 8. Module-Level Constants
None.

## 9. Methods (by class)

### AutomationProcessor
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance     | `def __init__(self, config: ConfigManager, registry: HandlerRegistry, ...)` | Initializes the processor with necessary dependencies.                     |
| `process_message`          | instance     | `def process_message(self, primary_agent: Agent, account: Dict[str, Any], ...)` | Processes incoming messages and executes tasks based on commands.         |
| `execute_tasklist`         | instance     | `def execute_tasklist(self, tasklist_id: str, mode: str, ...)`          | Executes a task list based on the provided ID and mode.                  |

### FunctionCallingProcessor
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance     | `def __init__(self, config: ConfigManager, registry: HandlerRegistry, ...)` | Initializes the processor with necessary dependencies.                     |
| `process_message`          | instance     | `def process_message(self, primary_agent: Agent, account: Dict[str, Any], ...)` | Processes incoming messages and manages function calls.                    |
| `process_message_streaming`| instance     | `def process_message_streaming(self, primary_agent: Agent, account: Dict[str, Any], ...)` | Handles streaming messages and yields responses in real-time.              |

### MessageProcessorInterface
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `process_message`          | abstract     | `def process_message(self, primary_agent: Agent, account: AccountDict, ...)` | Abstract method to process messages.                                        |

### ProcessorFactory
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `get`                      | instance     | `def get(self, processor_name: str)`                                     | Returns a constructed message processor instance for a given name.         |

## 10. Usage Examples
```python
from src.message_processors import ProcessorFactory

# Create a processor factory
factory = ProcessorFactory()

# Get an instance of the FunctionCallingProcessor
function_processor = factory.get("function_calling_processor")

# Process a message
response = function_processor.process_message(
    primary_agent=agent,
    account=account_info,
    message="Run the task list.",
    conversation_id="12345"
)
print(response)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The processors are designed to log errors and continue processing where possible. However, certain failures (like tool execution errors) will raise exceptions that need to be handled upstream.
- **Duplicate Tool Calls**: The `FunctionCallingProcessor` includes logic to detect and handle duplicate tool calls to prevent infinite loops.
- **Throttling**: The module supports throttling for different providers, which can affect performance if not configured correctly.
- **JSON Parsing**: Care should be taken when parsing JSON commands, as invalid formats will lead to errors.

## 12. Consumers
| Consumer                     | What it uses                                      |
|------------------------------|--------------------------------------------------|
| Various components of the system | Uses message processors for handling user commands and executing tasks. |
| Agent classes                | Interacts with message processors to manage task execution. |
| Chat interfaces              | Utilizes processors to handle user interactions and responses. |

---

This document provides a comprehensive overview of the `src/message_processors` module, detailing its structure, functionality, and usage.