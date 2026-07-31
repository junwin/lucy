# Documentation for `src/message_processors`

## YAML Front Matter
```yaml
tags:
  - src_message_processors
  - lucyproject
  - AutomationProcessor
  - FunctionCallingProcessor
  - TaskRunningProcessor
  - MessageProcessorInterface
  - ProcessorFactory
  - ToolResultTooLargeError
  - ToolHandlerError
```

## 1. Summary
The `src/message_processors` module is responsible for processing messages within the Lucy project architecture. It provides various message processors that handle different types of commands and tasks, particularly focusing on automation and function calling. The module's primary responsibility is to interpret incoming messages, execute tasks based on those messages, and manage the state of task lists. This module fits into the overall architecture by serving as a bridge between user commands and the underlying task execution logic, effectively solving the problem of orchestrating complex workflows in response to user inputs.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Dependency Injection**: Utilizes the `injector` library to manage dependencies, ensuring that each processor receives the necessary components without tight coupling.
- **Abstract Base Classes**: The `MessageProcessorInterface` defines a common interface for all message processors, promoting consistency and extensibility.
- **Factory Pattern**: The `ProcessorFactory` class dynamically resolves and instantiates the appropriate message processor based on configuration, allowing for flexible processor management.

Classes within the module relate through composition and inheritance. For instance, `AutomationProcessor` and `FunctionCallingProcessor` both implement the `MessageProcessorInterface`, ensuring they adhere to a common contract. The module does not exhibit a legacy/v2 split, as it appears to be a cohesive unit designed for the current architecture.

Key design decisions include:
- The use of JSON for command parsing, which allows for a flexible and structured way to define actions and parameters.
- Logging at various stages to facilitate debugging and monitoring of task execution.

## 3. Key Classes
| Class                        | Base/Parent                     | Purpose                                                                 |
|------------------------------|----------------------------------|-------------------------------------------------------------------------|
| AutomationProcessor           | MessageProcessorInterface        | Processes automation commands and manages task execution.               |
| FunctionCallingProcessor      | MessageProcessorInterface        | Handles function calling tasks and manages tool execution.              |
| TaskRunningProcessor          | MessageProcessorInterface        | Manages the state of tasks and processes commands related to task lists. |
| MessageProcessorInterface     | ABC                              | Defines the interface for all message processors.                       |
| ProcessorFactory             | ABC                              | Creates instances of message processors based on configuration.         |

## 4. Source Files
| File                                      | Responsibility                                           | Notable Exports                                      |
|-------------------------------------------|---------------------------------------------------------|-----------------------------------------------------|
| `__init__.py`                             | Initializes the module.                                 | None                                                |
| `automation_processor.py`                 | Implements the `AutomationProcessor` class.            | AutomationProcessor                                  |
| `function_calling_processor.py`           | Implements the `FunctionCallingProcessor` class.       | FunctionCallingProcessor                             |
| `message_processor_interface.py`          | Defines the `MessageProcessorInterface`.                | MessageProcessorInterface                            |
| `processor_factory.py`                     | Implements the `ProcessorFactory` class.               | ProcessorFactory                                     |
| `sse_events.py`                           | Defines the `SSEEvent` model for streaming responses.  | SSEEvent                                            |
| `task_running_processor.py`               | Implements the `TaskRunningProcessor` class.           | TaskRunningProcessor                                 |
| `types.py`                                | Defines type aliases for agent and account dictionaries. | AgentDict, AccountDict, OptionalAgentDict           |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `logging`
  - `datetime`
  - `time`
  - `abc`
  - `importlib`
  - `typing`
  
- **Third-party packages**:
  - `injector`
  - `pydantic`
  
- **Internal modules**:
  - `src.agent`
  - `src.config_manager`
  - `src.handlers.handler_registry`
  - `src.storage.base`
  - `src.tasklists.task`
  - `src.tasklists.task_list`
  - `src.tasklists.task_states`
  - `src.llm.adapter_interface`
  - `src.chat2.facade`
  - `src.chat2.models`
  
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                          | Type   | Default | What it controls                                      |
|------------------------------|--------|---------|------------------------------------------------------|
| `max_tool_result_chars`      | int    | 20000   | Maximum allowed characters for tool results.         |
| `environment_prompt_block`    | str    | ""      | Server-wide environment prompt injection messages.    |

## 7. Exceptions
| Exception                     | Base                     | When Raised                                               |
|-------------------------------|--------------------------|----------------------------------------------------------|
| ToolResultTooLargeError       | Exception                | Raised when a tool result exceeds the configured limit.  |
| ToolHandlerError              | Exception                | Raised when a tool handler fails during execution.       |

## 8. Module-Level Constants
| Constant                      | Value                     |
|-------------------------------|---------------------------|
| None                          | None                      |

## 9. Methods (by class)

### AutomationProcessor
| Method                       | Type         | Signature                                                                 | Description                                                                 |
|------------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `process_message`            | instance     | `def process_message(self, *, primary_agent: Agent, account: Dict[str, Any], message: str, conversation_id: str = "0", context_name: str = "", secondary_agent: Optional[Agent] = None, processor_factory: Optional[Any] = None) -> str:` | Processes incoming messages, validates commands, and executes task lists.  |
| `execute_tasklist`           | instance     | `def execute_tasklist(self, *, tasklist_id: str, mode: str, account_name: str, agent_name: str, conversation_id: str, context_name: str, primary_agent: Agent, account: Dict[str, Any], secondary_agent: Optional[Agent] = None, processor_factory: Optional[Any] = None) -> str:` | Executes a task list based on the provided parameters.                     |

### FunctionCallingProcessor
| Method                       | Type         | Signature                                                                 | Description                                                                 |
|------------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `process_message`            | instance     | `def process_message(self, *, primary_agent: Agent, account: Dict[str, Any], message: str, conversation_id: str = "0", context_name: str = "", secondary_agent: Optional[Agent] = None, processor_factory: Optional[Any] = None) -> str:` | Processes incoming messages and executes function calls.                    |
| `_run_llm_loop`             | instance     | `def _run_llm_loop(self, *, ctx: _ProcessorContext, prompt_messages: List[Dict[str, Any]], function_defs: List[Dict[str, Any]], primary_agent: Agent, secondary_agent: Optional[Agent], processor_factory: Optional[Any], account: Dict[str, Any], metrics: Dict[str, Any]) -> str:` | Runs the LLM loop for processing function calls.                           |

### TaskRunningProcessor
| Method                       | Type         | Signature                                                                 | Description                                                                 |
|------------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `process_message`            | instance     | `def process_message(self, *, primary_agent: Agent, account: AccountDict, message: str, conversation_id: str = "0", context_name: str = "", secondary_agent: Optional[Agent] = None, processor_factory: Optional[Any] = None) -> str:` | Processes incoming messages and identifies the next pending task.          |

## 10. Usage Examples
```python
# Example of using AutomationProcessor
automation_processor = AutomationProcessor(config, registry, storage, prompt_builder)
result = automation_processor.process_message(
    primary_agent=agent,
    account=account_dict,
    message='{"action": "run", "tasklist_id": "my_tasklist_1", "mode": "multi-step"}'
)

# Example of using FunctionCallingProcessor
function_calling_processor = FunctionCallingProcessor(config, registry, prompt_builder, llm_adapter)
response = function_calling_processor.process_message(
    primary_agent=agent,
    account=account_dict,
    message='{"action": "call_function", "function_name": "example_function"}'
)
```

## 11. Edge Cases & Gotchas
- **Error Handling Patterns**: The processors generally follow a fail-fast approach, logging errors and returning informative messages when encountering issues.
- **Task State Management**: Care must be taken to ensure that task states are correctly updated, especially in the event of failures during execution.
- **Thread-Safety**: The module does not explicitly mention thread-safety, so concurrent access to shared resources should be managed carefully.
- **JSON Command Parsing**: The processors expect well-formed JSON commands; malformed commands will result in errors.

## 12. Consumers
| Consumer                      | What it uses                                               |
|-------------------------------|-----------------------------------------------------------|
| Various agents                | Utilize message processors for task execution and command processing. |
| `src.chat2`                  | Interacts with chat storage for logging events and messages. |
| `src.tasklists`              | Manages task lists and states through the processors.     |

---

This document provides a comprehensive overview of the `src/message_processors` module, detailing its structure, functionality, and usage within the Lucy project.