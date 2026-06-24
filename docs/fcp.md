Here is a concise user guide for creating and using the FunctionCallingProcessor and its process_message(…) method, based on the code in repo_lucy.

What FunctionCallingProcessor does (high level)

    A Dialogue-to-Tool bridge: it builds prompts for the LLM, lets the LLM decide to call tools, executes those tool calls via a HandlerRegistry, and optionally runs task lists (delegate_tasks) produced by tools.
    It manages context, environment prompts, and conversation state (through a Storage backend).
    It can filter which tools are allowed for a given agent, and it supports chaining tool outputs back into the next LLM prompt.
    It exposes a single public API: process_message(…).

Where to look (references)

    Implementation: src/message_processors/function_calling_processor.py
    Example usage pathway: src/message_endpoints/ask_request_handler.py (AskRequestHandler delegates to the processor via processor_factory)
    Core exceptions used by the processor: ToolResultTooLargeError, ToolHandlerError (defined in function_calling_processor.py)

Prerequisites and dependencies you'll need

    The FunctionCallingProcessor depends on:
        ConfigManager (for config values like max_tool_result_chars and environment prompts)
        HandlerRegistry (to create tool handlers and execute them)
        Storage (to persist chat messages and contexts)
        PromptBuilderInterface (to build the prompt for the LLM)
        LLMAdapter (to talk to the language model and to format tool outputs)
    DI wiring: The constructor uses @inject, but there is a minimal shim if the injector package is not present.

Constructor signature (how to instantiate)

    init(self, config: ConfigManager, registry: HandlerRegistry, storage: Storage, prompt_builder: PromptBuilderInterface, llm_adapter: LLMAdapter)
    The instance fields used inside the class include:
        self.config, self.registry, self.storage, self.prompt_builder, self.llm_adapter

Key internal structures (as you'll implement or mock in tests)

    _ProcessorContext (dataclass)
        account_id, agent_name, conversation_id, context_name
        model, temperature, context_type
        max_iterations, store_this_call, delegation_depth
    _ToolCall (dataclass)
        name, call_id, arguments_raw

Public API: process_message(…)

    Signature: process_message( self, *, primary_agent: Agent, account: Dict[str, Any], message: str, conversation_id: str = "0", context_name: str = "", secondary_agent: Optional[Agent] = None, processor_factory: Optional[Any] = None, ) -> str
    What you pass in:
        primary_agent: The main Agent config driving this interaction (name, model, temperature, context_type, max_function_call_iterations, allowed_tools, etc.)
        account: Dict with account identification, typically containing accountId
        message: The user's message to process
        conversation_id: Optional session id; if omitted, the processor will attempt to resolve or create a session via storage
        context_name: Optional context identifier for the session
        secondary_agent: Optional Agent used for delegation (e.g., a partner agent)
        processor_factory: Optional factory used when you need to trigger nested processing (e.g., task lists)
    What it returns:
        A string: the LLM's final response after potential tool execution loops
    Behavior overview:
        Build a _ProcessorContext from primary_agent and account
        Build system/environment prompts (from environment_prompt_block in config, if provided)
        Build the prompt via prompt_builder.build_prompt(…)
        Fetch tool definitions with registry.tools() and filter them by primary_agent.allowed_tools (if provided)
        Run the LLM loop via _run_llm_loop(…) which:
            Calls the LLM with the current prompt and tool definitions
            Extracts tool_calls from the LLM response
            Executes each tool via _execute_tool_calls(…)
            If a delegate_tasks tool is invoked and a secondary_agent + processor_factory are available, may trigger task list execution via _execute_simple_tasklist(…)
            Uses tool outputs as the next prompt input and repeats up to max_iterations
            If no more tool calls, uses LLM's textual output as the final answer
        Optionally persist user and assistant messages to storage if store_this_call is True
    Important behaviors and limits:
        Tool result size limit: The tool results are serialized to text and checked against max_tool_result_chars from config. If too large, ToolResultTooLargeError is raised and handled as a failed tool execution.
        Tool execution errors: ToolHandlerError is raised when a tool handler fails; this is surfaced to the caller (and can be logged/stored).
        Delegation depth and tasklists: If a tasklist (delegate_tasks) is produced, the processor can execute it directly or via the supplied processor_factory/secondary_agent, depending on your setup.
        Environment prompts: You can inject environment/system messages via environment_prompt_block in config; they are prepended to the user's prompt as system messages.

What happens inside the main flow (step-by-step)

    _build_context(…)
        Builds context like account_id, agent_name, conversation_id, model, temperature, context_type, max_iterations
    _get_environment_system_messages(…)
        Reads environment_prompt_block from config and returns a list of system messages (if any)
    prompt construction
        prompt_builder.build_prompt(content_text=message, …, extra_system_messages=env_messages)
    Tool definitions filtering
        function_defs = registry.tools()
        allowed = primary_agent.allowed_tools
        If allowed is falsy or empty, filtered_function_defs becomes []
        If allowed exists, filter function_defs to only those whose "name" is in allowed
    _run_llm_loop(…)
        Calls llm_adapter.call_model with:
            model, input (prompt messages), temperature
            tools=function_defs
            tool_choice="auto" if there are tools, else None
            store flag from context
            metadata with conversation_id and session_id
            previous_response_id to chain context
        Extracts tool_calls via llm_adapter.extract_tool_calls(…)
        If tool_calls are present:
            Ensure there is a previous_response_id; otherwise raise ToolHandlerError
            _execute_tool_calls(…) to run each tool
            Convert tool outputs to text and feed back as next input
            If max_iterations is reached, provide a fallback short message and break
        If no tool_calls:
            Use llm_adapter.get_text(llm_response) as the final response
    _execute_tool_calls(…)
        For each tool_call:
            Create a handler via registry.create(tc.name, config=self.config)
            If handler has execute_raw, invoke with arguments_raw, account_name, call_id
            Else, parse arguments (JSON) with _safe_json_loads and call handler.execute(tool_args, account_name=…)
            After getting tool_result_text, if the call is delegate_tasks and there is a secondary_agent and processor_factory:
                Parse tool_result_text as JSON; if it's a tasklist (ok and kind == "tasklist"), run _execute_simple_tasklist(…)
                Set tool_result_text to the JSON-serialized tasklist_result
            Enforce max tool result size via _tool_result_to_text(…)
            Append tool output to tool_output_items via llm_adapter.format_tool_output(call_id, output)
    _execute_simple_tasklist(…)
        Very simple executor that runs a sequence of tasks
        For each task, if type is "task" and it has an instruction, it calls process_message(…) on the worker (secondary) agent
        Aggregates results into a summary with per-task results and a final ok flag
        Returns a summary dictionary
    Wrap-up
        If store_this_call is True, store the user message and the assistant response as chat messages
        Return the final response_text to the caller

Example usage paths (reference the example in AskRequestHandler)

    The AskRequestHandler demonstrates how this processor is wired in the app:
        It resolves a processor by name from processor_factory
        It sets up primary_agent (agent config), secondary_agent (optional), and account
        It calls processor.process_message(primary_agent=…, account=…, message=…, conversation_id=…, context_name=…, secondary_agent=…, processor_factory=…)
        It returns a response string to the HTTP layer
    See:
        AskRequestHandler.handle(…) in src/message_endpoints/ask_request_handler.py
        The processor is invoked here via processor_factory and the process_message(…) call

Practical usage snippet (conceptual)

    Create the processor (DI wiring assumed in your app):
        processor = FunctionCallingProcessor(config, registry, storage, prompt_builder, llm_adapter)
    Call process_message with required inputs:
        response = processor.process_message( primary_agent=primary_agent, account={"accountId": "my-account"}, message="How do I reset my password?", conversation_id="sess-123", context_name="ctx-abc", secondary_agent=optional_partner_agent, # if you have one processor_factory=processor_factory, # if you need to support task lists )
    The returned response is the final assistant text after any tool calls.

Notes and tips

    Agent and tool configuration
        Primary agent should optionally specify allowed_tools to restrict which tools can be used. If allowed_tools is not provided or is empty, no tools will be invoked.
        Tools are obtained from registry.tools() and then filtered by allowed_tools.
    Environment prompts
        You can influence the initial system prompts using environment_prompt_block in config. This can be used to inject global constraints or context for all interactions.
    Persistence
        If save_responses (or store_this_call) is enabled on the agent, user and assistant messages are persisted to storage after a successful processing cycle.
    Error handling
        ToolResultTooLargeError: The processor will surface this when a tool output exceeds the configured size. It's raised during tool result serialization and should be handled by the caller (e.g., by returning an error snippet to the user or by truncating the tool output).
        ToolHandlerError: Raised when a tool handler fails; this propagates up and should be surfaced to the user or logged for investigation.
    Integration with AskRequestHandler
        The AskRequestHandler shows how to obtain a processor instance from ProcessorFactory and call process_message with the expected arguments. This is the recommended usage pattern in the web API flow.

If you want, I can extract a compact "quick-start" cheat sheet with:

    Required fields for primary_agent (as observed in code)
    Minimal example of calling process_message
    A short bullet list of common failure modes and how to mitigate them

Would you like me to add a small code snippet you can drop into tests or a new example script to exercise process_message end-to-end?
