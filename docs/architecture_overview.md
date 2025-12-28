# Architecture overview

This document connects the main pieces of the system:

- HTTP endpoints (`app.py`)
- DI container (`container_config.py`)
- Message processors (`src/message_processors/…`)
- Handlers (`src/handlers/…`)

…and shows how they work together.

## 1. Request → Processor → Handlers

(Existing prose description of the flow should be here; this update adds a DI-focused diagram.)

### DI wiring overview (Mermaid)

```mermaid
graph TD
    subgraph App[Flask app.py]
        A[Flask routes<br/>/ask, /chats, ...]
    end

    subgraph DI[DI Container<br/>container_config.py]
        Cfg[ConfigManager]
        HR[HandlerRegistry]
        PF[ProcessorFactory]
        PB[PromptBuilderInterface<br/>implementation]
        St[Storage]
        AM[AgentManager]
    end

    subgraph MP[Message processors]
        FCP[FunctionCallingProcessor]
        MPI[MessageProcessorInterface]
    end

    subgraph H[Handlers]
        H1[file_load]
        H2[file_save]
        H3[execute_command]
        H4[scrape_web_page]
        Hn[other handlers...]
    end

    A --> AM

    AM --- Cfg
    AM --- PF
    AM --- St

    PF --- Cfg
    PF --> FCP

    FCP -.implements .-> MPI

    FCP --- PB
    FCP --- HR
    FCP --- St

    HR --> H1
    HR --> H2
    HR --> H3
    HR --> H4
    HR --> Hn

    Cfg -.provides config to .- HR
    Cfg -.provides config to .- St
    Cfg -.provides config to .- PB
```

This diagram shows:

- `app.py` only knows about `AgentManager` (resolved from the DI container).
- `AgentManager` depends on `ConfigManager`, `ProcessorFactory`, and `Storage`.
- `ProcessorFactory` uses `ConfigManager` and constructs concrete `MessageProcessor` implementations (e.g. `FunctionCallingProcessor`).
- `FunctionCallingProcessor` depends on:
  - `PromptBuilderInterface` implementation
  - `HandlerRegistry`
  - `Storage`
- `HandlerRegistry` knows about all handler classes and uses `ConfigManager` when instantiating them.

See also:

- [`handlers.md`](./handlers.md) – details on handlers/tools.
- [`message_processors.md`](./message_processors.md) – details on message processors.
- [`request_endpoints.md`](./request_endpoints.md) – HTTP endpoints and request flow.
