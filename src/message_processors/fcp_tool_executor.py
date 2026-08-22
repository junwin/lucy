import json
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.agent import Agent
from src.agent.agent_manager import AgentManager
from src.chat2.facade import Chat2Store
from src.config_manager import ConfigManager
from src.handlers.handler_registry import HandlerRegistry
from src.llm.adapter_interface import LLMAdapter
from src.message_processors.automation_processor import AutomationProcessor
from src.message_processors.fcp_models import (
    ProcessorContext,
    ToolHandlerError,
    ToolResultTooLargeError,
    _ToolCall,
)
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList

def load_context_state(prompt_builder: Any, account_name: str, context_name: str) -> Optional[Any]:
    """Load the active Context (or None) for the given account/context.

    Delegates to PromptBuilder._get_context_state when available so the FCP
    sees exactly the same Context the prompt builder used (same
    get_or_create_context/get_context fallback). Fails softly: any error
    yields None (no context tool list applies).
    """
    if not context_name or context_name == "none":
        return None
    try:
        loader = getattr(prompt_builder, "_get_context_state", None)
        if callable(loader):
            return loader(account_name, context_name)
        storage = getattr(prompt_builder, "storage", None)
        if storage is None:
            return None
        if hasattr(storage, "get_or_create_context"):
            return storage.get_or_create_context(account_name, context_name)
        return storage.get_context(account_name, context_name)
    except Exception as ex:
        logging.warning(
            "FunctionCallingProcessor: failed to load context '%s' for account '%s': %s",
            context_name,
            account_name,
            ex,
        )
        return None


class ToolExecutor:
    def __init__(
        self,
        *,
        registry: HandlerRegistry,
        config: ConfigManager,
        prompt_builder: PromptBuilderInterface,
        llm_adapter: LLMAdapter,
        automation_processor: Optional[AutomationProcessor],
        agent_manager: Optional[AgentManager],
        chat2_store: Optional[Chat2Store] = None,
    ):
        self.registry = registry
        self.config = config
        self.prompt_builder = prompt_builder
        self.llm_adapter = llm_adapter
        self.automation_processor = automation_processor
        self.agent_manager = agent_manager
        self.chat2_store = chat2_store

    def safe_json_loads(self, s: str) -> Dict[str, Any]:
        if not s:
            return {}
        try:
            loaded = json.loads(s)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            logging.warning(
                "Tool arguments were not valid JSON; using empty dict. args=%r",
                (s or "")[:500],
            )
            return {}


    def tool_result_to_text(self, tool_result_text: Any) -> str:
        """Ensure the tool result is a string and enforce max size.

        We do not parse/serialize tool I/O here anymore. Handlers are expected
        to return a JSON object string.
        """

        if tool_result_text is None:
            s = json.dumps({"ok": False, "error": "Tool returned None"}, ensure_ascii=False)
        elif isinstance(tool_result_text, str):
            s = tool_result_text
        else:
            try:
                s = json.dumps(tool_result_text, ensure_ascii=False)
            except Exception as e:
                s = json.dumps({"ok": False, "error": f"Tool result not serializable: {e}"}, ensure_ascii=False)

        max_chars = int(self.config.get("max_tool_result_chars", 20000))
        if len(s) > max_chars:
            logging.error(
                "Tool result too large: %d chars (limit %d). Sample: %r",
                len(s),
                max_chars,
                s[:1000],
            )
            raise ToolResultTooLargeError(f"Tool result too large: {len(s)} chars (limit {max_chars})")

        return s


    def wrap_tool_calls(self, tool_calls: Iterable[Dict[str, Any]]) -> List[_ToolCall]:
        wrapped: List[_ToolCall] = []
        for tc in tool_calls or []:
            tool_name = tc.get("name") or ""
            tool_call_id = tc.get("id")
            args_raw = tc.get("arguments") or "{}"
            wrapped.append(_ToolCall(name=tool_name, call_id=str(tool_call_id or ""), arguments_raw=args_raw))
        return wrapped


    def execute_tool_calls(
        self,
        *,
        tool_calls: List[_ToolCall],
        primary_agent: Agent,
        secondary_agent: Optional[Agent],
        processor_factory: Optional[Any],
        account: Dict[str, Any],
        ctx: ProcessorContext,
        metrics: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[Tuple[_ToolCall, str]]]:
        tool_output_items: List[Dict[str, Any]] = []
        raw_results: List[Tuple[_ToolCall, str]] = []

        # Build the shared execution context for handlers that need it
        # (e.g. TasklistsRunHandler needs primary_agent, account, conversation_id, etc.)
        # NOTE: account_name is NOT included here — it's passed explicitly to execute().
        handler_context: Dict[str, Any] = {
            "primary_agent": primary_agent,
            "secondary_agent": secondary_agent,
            "secondary_agent_default_context": getattr(secondary_agent, "default_context", None),
            "processor_factory": processor_factory,
            "account": account,
            "conversation_id": ctx.conversation_id,
            "context_name": ctx.context_name,
            "context_state": load_context_state(self.prompt_builder, ctx.account_id, ctx.context_name),
            "agent_name": ctx.agent_name,
            "storage": getattr(self, "_storage", None),
            "registry": self.registry,
            "prompt_builder": self.prompt_builder,
            "config": self.config,
            "chat2_store": self.chat2_store,
            "llm_adapter": self.llm_adapter,
            "agent_manager": self.agent_manager,
        }

        for tc in tool_calls:
            metrics["tool_calls"] += 1

            if not tc.call_id:
                metrics["failures"] += 1
                raise ToolHandlerError(
                    f"Tool call missing id/call_id for tool '{tc.name}'. Cannot send function_call_output."
                )

            # Unknown tool name: the model asked for a tool we don't have
            # (e.g. 'bash'). Return a recoverable error to the LLM instead of
            # crashing the whole request, so the model can correct itself on
            # the next turn.
            has_tool = getattr(self.registry, "has_tool", None)
            if callable(has_tool) and not has_tool(tc.name):
                metrics["failures"] += 1
                valid = getattr(self.registry, "tool_names", lambda: [])()
                logging.error(
                    "Unknown tool requested by model: tool=%r call_id=%s args=%r valid_tools=%s",
                    tc.name,
                    tc.call_id,
                    tc.arguments_raw,
                    valid,
                )
                tool_result_text = json.dumps(
                    {
                        "ok": False,
                        "tool": tc.name,
                        "error": f"Unknown tool '{tc.name}'. Valid tools: {valid}",
                    },
                    ensure_ascii=False,
                )
                raw_results.append((tc, tool_result_text))
                tool_output_items.append(
                    self.llm_adapter.format_tool_output(
                        call_id=str(tc.call_id), output=tool_result_text
                    )
                )
                continue

            try:
                handler = self.registry.create(tc.name, config=self.config)

                logging.info(
                    "tool_execute_start tool=%s call_id=%s account=%s",
                    tc.name,
                    tc.call_id,
                    ctx.account_id,
                )

                if hasattr(handler, "execute_raw"):
                    tool_result_text = handler.execute_raw(tc.arguments_raw, account_name=ctx.account_id, call_id=tc.call_id, **handler_context)  # type: ignore[attr-defined]
                else:
                    tool_args = self.safe_json_loads(tc.arguments_raw)
                    tool_result = handler.execute(tool_args, account_name=ctx.account_id, **handler_context)
                    tool_result_text = json.dumps(tool_result, ensure_ascii=False)

                logging.info(
                    "tool_execute_done tool=%s call_id=%s result_preview=%r",
                    tc.name,
                    tc.call_id,
                    (tool_result_text or "")[:200],
                )

                if tc.name == "delegate_tasks" and secondary_agent is not None and processor_factory is not None and self.automation_processor is not None:
                    try:
                        maybe = json.loads(tool_result_text or "{}")
                    except Exception:
                        maybe = {}

                    if isinstance(maybe, dict) and maybe.get("ok") and maybe.get("kind") == "tasklist":
                        logging.info(
                            "FunctionCallingProcessor: delegating tasklist to AutomationProcessor supervisor=%s worker=%s session_id=%s call_id=%s",
                            ctx.agent_name,
                            secondary_agent.name,
                            ctx.conversation_id,
                            tc.call_id,
                        )
                        try:
                            # Build TaskList from delegate_tasks result
                            tasklist_id = f"auto-{ctx.conversation_id}"
                            description = maybe.get("description") or ""
                            tasks = maybe.get("tasks") or []

                            task_objects = []
                            for t in tasks:
                                t_id = t.get("id") or f"task-{len(task_objects)+1}"
                                t_name = t.get("title") or ""
                                t_instruction = t.get("instruction") or ""
                                t_meta = {}
                                if t.get("file"):
                                    t_meta["file"] = t["file"]
                                if t.get("params"):
                                    t_meta.update(t["params"])
                                task_objects.append(Task(
                                    id=t_id,
                                    name=t_name,
                                    instructions=t_instruction,
                                    meta=t_meta,
                                ))

                            tasklist = TaskList(
                                id=tasklist_id,
                                name=description[:80] or "auto-tasklist",
                                description=description,
                                tasks=task_objects,
                            )

                            # Persist to storage via AutomationProcessor storage
                            self.automation_processor.storage.save_tasklist(
                                ctx.account_id, tasklist_id, tasklist.to_dict()
                            )

                            # Execute via AutomationProcessor
                            result_text = self.automation_processor.execute_tasklist(
                                tasklist_id=tasklist_id,
                                mode="multi-step",
                                account_name=ctx.account_id,
                                agent_name=ctx.agent_name,
                                conversation_id=ctx.conversation_id,
                                context_name=ctx.context_name,
                                primary_agent=primary_agent,
                                account=account,
                                secondary_agent=secondary_agent,
                                processor_factory=processor_factory,
                            )

                            tool_result_text = json.dumps({
                                "ok": True,
                                "tasklist_id": tasklist_id,
                                "result": result_text,
                            }, ensure_ascii=False)

                        except Exception as e:
                            logging.exception(
                                "FunctionCallingProcessor: AutomationProcessor delegation failed supervisor=%s session_id=%s",
                                ctx.agent_name,
                                ctx.conversation_id,
                            )
                            tool_result_text = json.dumps({
                                "ok": False,
                                "error": f"Tasklist delegation failed: {type(e).__name__}: {e}",
                            }, ensure_ascii=False)

                # Collect raw result before enforcing max size (for SSE action/image inspection)
                raw_results.append((tc, tool_result_text))

                tool_result_text = self.tool_result_to_text(tool_result_text)

            except ToolResultTooLargeError as e:
                metrics["failures"] += 1
                # Replace the too-large raw result with a compact error so the
                # LLM sees a graceful tool-failure message instead of a hard crash.
                error_msg = str(e)
                if tc.name == "serve_image":
                    # Parse char count and limit from the error string to craft
                    # a helpful message that tells the LLM exactly what to do.
                    m = re.match(r"Tool result too large: (\d+) chars \(limit (\d+)\)", error_msg)
                    if m:
                        error_msg = (
                            f"Image too large for tool result ({m.group(1)} chars, limit {m.group(2)}). "
                            "Please retry with max_dimension=512 or smaller."
                        )
                    else:
                        error_msg += " Please retry with max_dimension=512 or smaller."
                error_dict = {"ok": False, "tool": tc.name, "error": error_msg}
                tool_result_text = json.dumps(error_dict, ensure_ascii=False)
                raw_results.pop()  # remove the too-large entry
                raw_results.append((tc, tool_result_text))
                # Fall through to tool_output_items.append below.
            except Exception as e:
                metrics["failures"] += 1
                logging.exception("Tool execution failed: %s call_id=%s", tc.name, tc.call_id)
                raise ToolHandlerError(f"{type(e).__name__}: {e}")

            tool_output_items.append(self.llm_adapter.format_tool_output(call_id=str(tc.call_id), output=tool_result_text))

        return tool_output_items, raw_results
