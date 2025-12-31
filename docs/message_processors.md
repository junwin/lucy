# Message processors

This document describes what a **message processor** is in this codebase, how it works, and what it depends on, based on:

- `src/message_processors/message_processor_interface.py`
- `src/message_processors/processor_factory.py`
- `src/message_processors/function_calling_processor.py`

---

## 1. What is a message processor?

A **message processor** is a component that takes an incoming user message plus agent/account configuration, and returns a response string. It encapsulates the end-to-end logic of:

- How to build prompts for the LLM.
- How to call the LLM (and possibly tools/handlers).
- How to loop over multiple LLM/tool steps if needed.
- How to store conversation history.

All message processors implement the same interface: `MessageProcessorInterface`.

### 1.1 `MessageProcessorInterface`

Defined in `message_processor_interface.py`:

```python
class MessageProcessorInterface(ABC):
    @abstractmethod
    def process_message(
        self,
        *,
        primary_agent: AgentDict,
        account: AccountDict,
        message: str,
        conversation_id: str = "0",
        context_name: str = "",
        secondary_agent: Optional[AgentDict] = None,
        processor_factory: Optional[Any] = None,
    ) -> str:
        pass
```

Key points:

- `process_message` is the **single entry point**.
- It is responsible for:
  - Using `primary_agent` configuration (model, temperature, etc.).
  - Using `account` information (e.g. account ID, sandbox paths, etc.).
  - Handling the raw `message` text.
  - Optionally using `conversation_id` and `context_name` to fetch or store context.
  - Optionally using `secondary_agent` or `processor_factory` for more complex flows.
- It must return a **string**: the assistant’s reply.

Conceptually:

> A message processor is the strategy that defines how to turn an incoming message into a reply, given agent and account configuration.

---

## 2. ProcessorFactory

`ProcessorFactory` is a small factory that maps a string name (from agent config) to a concrete message processor implementation.

Defined in `processor_factory.py`:

```python
class ProcessorFactory:
    """Maps agent-config "message_processor" strings to concrete processor instances."""

    @inject
    def __init__(self, injector: Injector):
        self.injector = injector

        self._registry = {
            "function_calling_processor": FunctionCallingProcessor,
            "automation_processor": AutomationProcessor,
        }

    def get(self, processor_name: str):
        key = (processor_name or "").strip().lower()
        cls = self._registry.get(key)
        if not cls:
            raise ValueError(f"Unknown message_processor '{processor_name}'")
        return self.injector.get(cls)
```

Responsibilities:

- Holds a registry: `processor_name -> processor_class`.
- Normalizes the requested name (strip + lowercase).
- Uses `injector.get(cls)` to construct the processor with dependency injection.
- Raises a clear error if the name is unknown.

This allows agent configuration to specify, for example:

```json
{
  "message_processor": "function_calling_processor",
  "model": "gpt-5.1",
  "temperature": 0.2
}
```

and the system will obtain a `FunctionCallingProcessor` instance via `ProcessorFactory.get`.

---

## 3. Example: FunctionCallingProcessor

`FunctionCallingProcessor` is a concrete implementation of `MessageProcessorInterface` that:

- Builds a prompt using a `PromptBuilderInterface`.
- Calls the OpenAI API with tool/function calling enabled.
- Uses the `HandlerRegistry` to execute tools (handlers) when the model requests them.
- Iterates up to a maximum number of tool-calling steps.
- Optionally stores the conversation in `Storage`.

### 3.1 Constructor and dependencies

```python
class FunctionCallingProcessor(MessageProcessorInterface):
    @inject
    def __init__(
        self,
        config: ConfigManager,
        registry: HandlerRegistry,
        storage: Storage,
        prompt_builder: PromptBuilderInterface,
    ):
        self.config = config
        self.registry = registry
        self.storage = storage
        self.context_type = ""
        self.prompt_builder = prompt_builder
```

Dependencies:

- `ConfigManager` – for configuration values (e.g. `max_tool_result_chars`).
- `HandlerRegistry` – to list available tools and create handler instances.
- `Storage` – to persist chat messages.
- `PromptBuilderInterface` – to build the list of messages sent to the LLM.

These are injected via the DI container (`injector`).

### 3.2 Tool result handling

`FunctionCallingProcessor` includes helpers to safely parse tool arguments and serialize tool results:

- `_safe_json_loads` – parses tool arguments from JSON, logs a warning and falls back to `{}` if parsing fails.
- `_tool_result_to_text` – converts a handler’s result (usually a dict) into a JSON string and enforces a maximum size (`max_tool_result_chars`). If the result is too large, it raises `ToolResultTooLargeError`.

This ensures that:

- Tool outputs are always valid strings for the `tool` role messages.
- Oversized tool outputs are caught and reported instead of silently truncating.

### 3.3 `process_message` flow

The core logic in `process_message`:

1. **Validate inputs**
   - Ensure `primary_agent` is present.
   - Extract and validate `account_id` from `account["accountId"]`.

2. **Extract agent settings**
   - `agent_name`, `model`, `temperature`, `context_type` from `primary_agent`.

3. **Build the initial prompt**
   - Calls `self.prompt_builder.build_prompt(...)` with:
     - `content_text` (the user message),
     - `conversation_id`,
     - `agent_name`,
     - `account_name` (account ID),
     - `context_type`,
     - limits like `max_prompt_chars` and `max_prompt_conversations`,
     - `context_name`.
   - This returns `completion_messages`, a list of messages for the OpenAI API.

4. **Prepare tools**
   - `function_defs = self.registry.tools()` – gets all handler tool definitions.

5. **Iterative tool-calling loop**
   - Up to `max_iterations` (default 5):
     - Calls `openai_call(...)` with:
       - `messages=completion_messages`,
       - `functions=function_defs`,
       - `temperature`, `model`,
       - `store` flag and IDs for logging/storage.
     - If the result is a `ToolResult` with `tool_calls`:
       - For each tool call:
         - Extract `tool_name` and raw JSON `arguments`.
         - Parse arguments with `_safe_json_loads`.
         - Use `self.registry.create(tool_name, config=self.config)` to get a handler.
         - Call `handler.execute(tool_args, account_name=account_id)`.
         - Convert the result to text with `_tool_result_to_text`.
         - Append two messages to `completion_messages`:
           - An `assistant` message with the tool call metadata.
           - A `tool` message with the tool result text.
       - Then continue the loop to let the model see the tool results and respond.
     - If the result is a normal completion (no tool calls):
       - Extract `response_text` from `result.content` and break.

6. **Optional storage**
   - If `primary_agent["save_reposnses"]` is truthy and `response_text` is non-empty:
     - Append the user message and assistant response to `Storage` as `ChatMessage` objects.

7. **Return the final response**
   - Returns `response_text` as the final answer to the caller.

In summary:

> `FunctionCallingProcessor` orchestrates a tool-enabled conversation with the LLM: it builds prompts, calls the model, executes requested tools via handlers, feeds results back, and finally returns the model’s answer.

---

## 4. Dependencies of message processors

From these files, message processors depend on:

### 4.1 Core types and interfaces

- `MessageProcessorInterface` – the base interface all processors must implement.
- `AgentDict`, `AccountDict` – type aliases for agent and account configuration dictionaries.

### 4.2 Dependency injection

- `injector.Injector` and `@inject` – used by `ProcessorFactory` and processors to get their dependencies.

### 4.3 LLM and tools

- `openai_call` and `ToolResult` from `src.api_helpers` – abstraction over the OpenAI Chat Completions API.
- `HandlerRegistry` from `src.handlers.handler_registry` – provides tool definitions and handler instances.

### 4.4 Prompt building

- `PromptBuilderInterface` from `src.prompt_builders.prompt_builder_interface` – builds the message list for the LLM.

### 4.5 Configuration and storage

- `ConfigManager` – configuration values (e.g. limits, model defaults).
- `Storage` and `ChatMessage` – persistence for chat history.

### 4.6 Standard library

- `logging`, `json`, and typing utilities (`Optional`, `Dict`, `Any`).

---

## 5. How to add a new message processor

To add a new processor:

1. **Create a class** that implements `MessageProcessorInterface` and its `process_message` method.
2. **Inject dependencies** via `@inject` and the constructor, similar to `FunctionCallingProcessor`.
3. **Implement your strategy** for turning a message into a reply:
   - You can choose to use tools/handlers or not.
   - You can choose a different prompting strategy.
4. **Register it in `ProcessorFactory`**:

   ```python
   from src.message_processors.my_new_processor import MyNewProcessor

   self._registry = {
       "function_calling_processor": FunctionCallingProcessor,
       "automation_processor": AutomationProcessor,
       "my_new_processor": MyNewProcessor,
   }
   ```

5. **Reference it in agent config** by setting `"message_processor": "my_new_processor"`.

This keeps the system flexible: different agents can use different message processors depending on their needs.
