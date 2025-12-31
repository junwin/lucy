---
tags:
  - AskRequestHandler
  - src.message_endpoints
  - message_endpoints
  - src.message_endpoints
---

# src.message_endpoints

Short description: HTTP-facing message endpoint layer. Currently contains the handler for the `/ask` HTTP route, which wires incoming requests into the agent and message-processing pipeline.

## Python files and key classes

- `src/message_endpoints/ask_request_handler.py`
  - `AskRequestHandler` – encapsulates the legacy `/ask` route logic from `app.py`, validating the payload, resolving agents, selecting the appropriate message processor, and returning HTTP-style `(status_code, body)` tuples.
