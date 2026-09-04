```markdown
---
tags:
  - message_processors
  - lucyproject
  - AutomationProcessor
  - FunctionCallingProcessor
  - Chat2Recorder
  - ToolExecutor
  - LLMLoopRunner
  - ProcessorContext
  - ToolResultTooLargeError
  - ToolHandlerError
---

## 1. Summary
The `message_processors` module provides a framework for processing messages in a conversational AI context. It includes various processors that handle tasks such as executing commands, managing task lists, and interacting with external tools. The module aims to streamline the execution of complex workflows by integrating various components, including agents, storage, and chat interfaces.

## 2. Key Classes

| Class                        | Base/Parent                     | Purpose                                                                 |
|------------------------------|----------------------------------|-------------------------------------------------------------------------|
| AutomationProcessor           | MessageProcessorInterface        | Manages the execution of task lists and automation commands.            |
| FunctionCallingProcessor      | MessageProcessorInterface        | Handles function calling and tool execution in a conversational context.|
| Chat2Recorder                | -                                | Records chat events and manages chat sessions.                          |
| ToolExecutor                 | -                                | Executes tool calls and manages interactions with external tools.       |
| LLMLoopRunner                | -                                | Manages the loop for LLM interactions and tool calls.                  |
| ProcessorContext             | -                                | Holds contextual information for processing messages.                   |
| ToolResultTooLargeError      | Exception                        | Raised when a tool result exceeds the maximum allowed size.             |
| ToolHandlerError             | Exception                        | Raised when a tool handler fails during execution.                      |

## 3. Source Files

| File                                   | Responsibility                                      | Notable Exports                                   |
|----------------------------------------|----------------------------------------------------|--------------------------------------------------|
| `__init__.py`                         | Initializes the message_processors module.         | -                                                |
| `automation_processor.py`              | Implements the AutomationProcessor class.          | AutomationProcessor                               |
| `fcp_chat2.py`                        | Implements Chat2Recorder for chat event handling.  | Chat2Recorder                                     |
| `fcp_loop.py`                         | Implements LLMLoopRunner for LLM interactions.     | LLMLoopRunner                                     |
| `fcp_models.py`                       | Defines models for processing context and errors.   | ProcessorContext, ToolResultTooLargeError, ToolHandlerError |
| `fcp_tool_executor.py`                | Implements ToolExecutor for executing tool calls.  | ToolExecutor                                      |
| `function_calling_processor.py`       | Implements FunctionCallingProcessor for message processing. | FunctionCallingProcessor                          |
| `lazy_tool_selection.py`              | Implements lazy tool selection logic.               | select_active_tool_defs                           |
| `message_processor_interface.py`      | Defines the MessageProcessorInterface.              | MessageProcessorInterface                         |
| `processor_factory.py`                | Implements ProcessorFactory for creating processors. | ProcessorFactory                                  |
| `run_metrics.py`                      | Defines metrics for tracking execution performance.  | RunMetrics                                       |
| `sse_events.py`                       | Defines the SSEEvent model for streaming responses.  | SSEEvent                                         |
| `types.py`                            | Defines type aliases for agent and account dictionaries. | AgentDict, AccountDict                           |

## 4. Dependencies

- **Standard library**
  - json
  - logging
  - os
  - re
  - time
  - uuid
  - contextvars
  - datetime

- **Third-party packages**
  - injector
  - pydantic

- **Internal modules**
  - src.agent
  - src.config_manager
  - src.chat2.facade
  - src.handlers.handler_registry
  - src.prompt_builders.prompt_builder_interface
  - src.storage.interfaces
  - galet.adapter_interface
  - galet.provider_registry

## 5. Methods (by class)

### AutomationProcessor

| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | Instance     | `def __init__(self, config: ConfigManager, registry: HandlerRegistry, ...)` | Initializes the processor with necessary dependencies.                     |
| `process_message`          | Instance     | `def process_message(self, primary_agent: Agent, account: Dict[str, Any], message: str, ...)` | Processes incoming messages and executes tasks based on the command.      |
| `execute_tasklist`         | Instance     | `def execute_tasklist(self, tasklist_id: str, mode: str, ...)`         | Executes a task list based on the provided ID and mode.                   |

### FunctionCallingProcessor

| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | Instance     | `def __init__(self, config: ConfigManager, registry: HandlerRegistry, ...)` | Initializes the processor with necessary dependencies.                     |
| `process_message`          | Instance     | `def process_message(self, primary_agent: Agent, account: Dict[str, Any], message: str, ...)` | Processes incoming messages and executes functions based on the command.   |
| `process_message_streaming`| Instance     | `def process_message_streaming(self, primary_agent: Agent, account: Dict[str, Any], message: str, ...)` | Processes messages in a streaming manner, yielding events as they occur.   |

### Chat2Recorder

| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | Instance     | `def __init__(self, chat2_store: Chat2Store = None)`                   | Initializes the recorder with a chat store.                               |
| `ensure_session`           | Instance     | `def ensure_session(self, ctx: ProcessorContext) -> None`               | Ensures a chat session exists for the given context.                      |
| `write_streaming_events`   | Instance     | `def write_streaming_events(self, ctx: ProcessorContext, user_message: str, streamed_events: List[SSEEvent], ...)` | Writes streaming events to the chat store.                                 |

### ToolExecutor

| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | Instance     | `def __init__(self, registry: HandlerRegistry, config: ConfigManager, ...)` | Initializes the executor with necessary dependencies.                      |
| `execute_tool_calls`       | Instance     | `def execute_tool_calls(self, tool_calls: List[_ToolCall], primary_agent: Agent, ...)` | Executes the provided tool calls and returns results.                     |

### LLMLoopRunner

| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | Instance     | `def __init__(self, llm_adapter: LLMAdapter, config: ConfigManager, tool_executor: ToolExecutor)` | Initializes the loop runner with necessary dependencies.                   |
| `run`                      | Instance     | `def run(self, ctx: ProcessorContext, prompt_messages: List[Dict[str, Any]], ...)` | Runs the LLM loop, yielding events as they occur.                          |

### ProcessorContext

| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `from_agent`               | Class Method | `@classmethod def from_agent(cls, primary_agent: Agent, account: Dict[str, Any], ...)` | Creates a ProcessorContext from the given agent and account information.   |
```