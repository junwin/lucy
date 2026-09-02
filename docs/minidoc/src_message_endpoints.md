# src/message_endpoints Documentation

## YAML Front Matter
```yaml
tags:
  - src_message_endpoints
  - lucyproject
  - AskRequestHandler
  - resolve_or_create_session
```

## 1. Summary
The `src/message_endpoints` module is responsible for handling requests to the `/ask` endpoint, which allows users to interact with agents in a conversational manner. It processes incoming requests, validates the data, manages sessions, and delegates message processing to appropriate agents. This module fits into the overall architecture as a critical component for user-agent interaction, enabling dynamic conversations and context management. It solves the problem of managing user queries and responses in a structured way, ensuring that sessions are maintained and that agents can process messages effectively.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Factory Pattern**: The `ProcessorFactory` is used to create message processors based on agent configurations.
- **Dependency Injection**: The `AskRequestHandler` class receives its dependencies (like `AgentManager`, `ConfigManager`, etc.) through its constructor, promoting loose coupling and easier testing.
- **Error Handling**: The module uses structured logging and exception handling to manage errors gracefully, ensuring that issues are logged and appropriate responses are returned.

The `AskRequestHandler` class is the primary class in this module, encapsulating the logic for handling both standard and streaming requests. It interacts with various components like `AgentManager`, `Storage`, and `ProcessorFactory`, demonstrating a composition relationship. The module does not appear to have a legacy/v2 split, indicating a focus on maintaining a single, coherent implementation.

## 3. Key Classes
| Class                | Base/Parent | Purpose                                                                 |
|----------------------|--------------|-------------------------------------------------------------------------|
| AskRequestHandler     | None         | Handles requests to the `/ask` endpoint, managing sessions and processing messages. |

## 4. Source Files
| File                             | Responsibility                                           | Notable Exports                |
|----------------------------------|---------------------------------------------------------|--------------------------------|
| ask_request_handler.py           | Implements the AskRequestHandler class and session management logic. | AskRequestHandler, resolve_or_create_session |

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
| Exception              | Base                | When Raised                                      |
|------------------------|---------------------|-------------------------------------------------|
| None                   | None                | None                                            |

## 8. Module-Level Constants
| Constant               | Value               |
|------------------------|---------------------|
| None                   | None                |

## 9. Methods (by class)

### AskRequestHandler
| Method                | Type         | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|-----------------------|--------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| handle                | instance     | `def handle(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]` | Processes the `/ask` request. Validates input, resolves or creates sessions, and delegates message processing to the appropriate agent. Returns a tuple containing the HTTP status code and a response dictionary. Key parameters include `payload` (the incoming request data). Returns a tuple with status code and response data. Handles various error conditions and logs them. |
| handle_streaming      | instance     | `def handle_streaming(self, payload: Dict[str, Any]) -> Generator[str, None, None]` | Streaming variant of the `handle` method. Yields SSE-formatted strings for real-time communication. Validates input and manages session resolution similarly to `handle`, but returns data in a streaming format. Handles errors and yields appropriate SSE events.                                                                                 |

## 10. Usage Examples
```python
from src.message_endpoints.ask_request_handler import AskRequestHandler

# Assuming necessary dependencies are instantiated
ask_handler = AskRequestHandler(agent_manager, config_manager, storage, processor_factory)

# Example payload for a request
payload = {
    "question": "What is the weather today?",
    "agentName": "WeatherAgent",
    "accountName": "user123",
}

# Handling a request
status_code, response = ask_handler.handle(payload)
print(status_code, response)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a fail-fast approach, returning early on validation errors and logging them.
- **Session Management**: The `resolve_or_create_session` function ensures that sessions are consistently managed, but if the `chat2_store` is not provided, sessions will not be persisted.
- **Backward Compatibility**: The code includes checks for legacy behavior, such as handling both `selectType` and `contextType`.
- **Thread Safety**: The module does not explicitly mention thread safety; care should be taken when using shared resources.

## 12. Consumers
| Consumer               | What it uses                                      |
|------------------------|---------------------------------------------------|
| Unknown                | Unknown — trace imports to confirm.               |