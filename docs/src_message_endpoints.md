# Module Documentation for `src/message_endpoints`

## YAML Front Matter
```yaml
tags:
  - src_message_endpoints
  - lucyproject
  - AskRequestHandler
  - ToolHandlerError
  - resolve_or_create_session
```

## 1. Summary
The `src/message_endpoints` module is responsible for handling requests to the `/ask` endpoint, which allows users to interact with agents in a conversational manner. It processes incoming requests, manages session states, and delegates message processing to appropriate agents. This module fits into the overall architecture as a critical component for user-agent interaction, enabling dynamic conversations and context management. It solves the problem of managing user queries and responses in a structured way, ensuring that sessions are created or resolved as needed, and that messages are processed correctly.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Factory Pattern**: The `ProcessorFactory` is used to create message processors based on agent configurations.
- **Dependency Injection**: The `AskRequestHandler` class receives its dependencies (like `AgentManager`, `ConfigManager`, etc.) through its constructor, promoting loose coupling and easier testing.
- **Error Handling**: The module uses structured logging and exception handling to manage errors gracefully, ensuring that issues are logged and appropriate responses are returned.

The `AskRequestHandler` class is the primary interface for handling requests, while the `resolve_or_create_session` function is a utility for managing session states. The design reflects a clear separation of concerns, where each class and function has a specific responsibility.

## 3. Key Classes
| Class                | Base/Parent | Purpose                                                                 |
|----------------------|--------------|-------------------------------------------------------------------------|
| AskRequestHandler     | None         | Handles the `/ask` endpoint, processes requests, and manages sessions. |

## 4. Source Files
| File                              | Responsibility                                           | Notable Exports                |
|-----------------------------------|---------------------------------------------------------|--------------------------------|
| ask_request_handler.py            | Implements the AskRequestHandler class and session logic. | AskRequestHandler, resolve_or_create_session |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `logging`
  - `uuid`
  - `typing`
  
- **Third-party packages**:
  - None

- **Internal modules**:
  - `src.agent`
  - `src.config_manager`
  - `src.storage.base`
  - `src.message_processors.processor_factory`
  - `src.message_processors.function_calling_processor`
  - `src.chat2.facade`
  - `src.chat2.models`

- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                     | Type   | Default | What it controls                      |
|-------------------------|--------|---------|---------------------------------------|
| None                    | None   | None    | None                                  |

## 7. Exceptions
| Exception            | Base                | When Raised                                      |
|----------------------|---------------------|-------------------------------------------------|
| ToolHandlerError     | Exception           | Raised when a tool execution fails during processing. |

## 8. Module-Level Constants
| Constant | Value | Description |
|----------|-------|-------------|
| None     | None  | None        |

## 9. Methods (by class)

### AskRequestHandler
| Method              | Type         | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|---------------------|--------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| handle              | instance     | `def handle(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]` | Processes the `/ask` request. It validates the input payload, resolves or creates a session, and delegates message processing to the appropriate agent. Returns a tuple containing the HTTP status code and a response dictionary. Key parameters include `payload` (the request data). Returns a tuple with status code and response data. Handles various error conditions and logs them. |
| handle_streaming    | instance     | `def handle_streaming(self, payload: Dict[str, Any]) -> Generator[str, None, None]` | Streaming variant of the `handle` method. Yields SSE-formatted strings for real-time communication. Similar validation and processing logic as `handle`, but designed for streaming responses. Returns a generator that yields SSE events. Handles errors and logs them appropriately.                                                                 |

## 10. Usage Examples
```python
from src.message_endpoints.ask_request_handler import AskRequestHandler

# Assuming necessary dependencies are instantiated
ask_handler = AskRequestHandler(agent_manager, config_manager, storage, processor_factory)

# Example payload
payload = {
    "question": "What is the weather today?",
    "agentName": "WeatherAgent",
    "accountName": "user123"
}

# Handling a request
status_code, response = ask_handler.handle(payload)
print(status_code, response)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a fail-fast approach, returning errors immediately when required fields are missing or invalid.
- **Session Management**: The `resolve_or_create_session` function ensures that sessions are consistently managed, but if the `chat2_store` is not provided, sessions will not be persisted.
- **Backward Compatibility**: The code includes checks for older storage implementations that may not support context management.
- **Thread Safety**: The module does not explicitly mention thread safety; care should be taken when using shared resources.

## 12. Consumers
| Consumer                | What it uses                                      |
|-------------------------|---------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |