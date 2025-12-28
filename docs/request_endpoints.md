# Request endpoints and DI overview

## Sequence diagram for `/ask`

```mermaid
sequenceDiagram
    participant Client
    participant Flask as Flask app.py
    participant Container as DI Container<br/>(container_config)
    participant AgentMgr as AgentManager
    participant ProcFactory as ProcessorFactory
    participant Processor as MessageProcessor<br/>(e.g. FunctionCallingProcessor)
    participant LLM as OpenAI API
    participant Handlers as Handlers<br/>(via HandlerRegistry)
    participant Storage as Storage

    Client->>Flask: POST /ask { message, account, agent, ... }
    Flask->>Container: resolve AgentManager
    Container-->>Flask: AgentManager instance

    Flask->>AgentMgr: process_incoming_message(...)
    AgentMgr->>ProcFactory: get_processor(processor_name)
    ProcFactory-->>AgentMgr: MessageProcessor instance

    AgentMgr->>Processor: process_message(...)

    loop one or more LLM/tool iterations
        Processor->>LLM: openai_call(messages, tools=HandlerRegistry.tools())
        LLM-->>Processor: assistant response or tool_calls

        alt assistant message (no tools)
            Processor->>Storage: save ChatMessage(s)
            Storage-->>Processor: ack
        else tool calls
            Processor->>Handlers: HandlerRegistry.create(handler_name)
            Handlers-->>Processor: handler instance
            Processor->>Handlers: handler.execute(args, account_name)
            Handlers-->>Processor: tool result dict
            Processor->>LLM: openai_call(... + tool result)
            LLM-->>Processor: updated assistant response
        end
    end

    Processor-->>AgentMgr: final assistant text
    AgentMgr-->>Flask: final response
    Flask-->>Client: HTTP 200 { answer, ... }
```

(Other explanatory text omitted here for brevity; this file should already contain the prose description you requested earlier, with this diagram appended.)
