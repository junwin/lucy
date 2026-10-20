"""Assemble FCP prompts and resolve tools through the existing pipeline.

Dependencies and processor hooks are supplied per call so replacements made by
tests or callers remain visible. No processor, run state, persistence or model
loop is imported here.
"""
import logging
from typing import Any, Callable, Dict, List, NamedTuple, Optional

from galet.provider_registry import ProviderRegistry
from src.agent import Agent
from src.message_processors.fcp_models import ProcessorContext


_TOOL_DISCOVERY_SYSTEM_MESSAGE = (
    "When the currently active tools are insufficient, use discover_tools to "
    "search the tools you are permitted to use. Before calling a discovered "
    "tool that is not currently active, call activate_tools with its qualified "
    "tool ID. Activated tools remain available only for the current request."
)


class _PromptSetupResult(NamedTuple):
    prompt_messages: List[Dict[str, Any]]
    filtered_function_defs: List[Dict[str, Any]]
    supports_images: bool
    prompt_breakdown: Dict[str, int]


def get_environment_system_messages(config: Any) -> List[str]:
    """Return server-wide environment prompt injection messages.

    Config key: environment_prompt_block

    - Missing/empty => []
    - Non-empty string => one system message containing the full block
    """

    env_block = config.get("environment_prompt_block", "")
    if not isinstance(env_block, str) or not env_block.strip():
        return []

    # Keep as a single structured block to preserve formatting.
    return [env_block.strip()]


def resolve_tool_defs_pipeline(
    *,
    registry: Any,
    prompt_builder: Any,
    llm_adapter: Any,
    config: Any,
    pipeline_factory: Any,
    primary_agent: Agent,
    ctx: ProcessorContext,
    message: str,
) -> List[Dict[str, Any]]:
    """Resolve active tool defs via the tool-selection pipeline (issue #126).

    The pipeline owns tool-list resolution end to end: agent.allowed_tools
    (permission) → registry ∩ allowed (eligible) → context required tools →
    LLM prompt-based subset → schema budget. It replaces the FCP's previous
    four-step sequence (resolve_tool_defs → lazy selection →
    mandatory-tool merge → apply_handler_schema_budget).

    Unlike the old path, the pipeline raises ToolSelectionError on
    required-tool validation failures and on budget overflow (no silent
    skip / trim). Those propagate to the caller, which surfaces the
    human-readable message to the user.
    """
    pipeline = pipeline_factory(
        registry=registry,
        storage=getattr(prompt_builder, "storage", None),
        procedural_memory=getattr(prompt_builder, "procedural_memory", None),
        llm_adapter=llm_adapter,
        config=config,
    )
    return pipeline.get_tool_handler_defs(
        agent=primary_agent,
        account_name=ctx.account_id,
        context_name=ctx.context_name,
        prompt_text=message,
    )


def prepare_prompt_and_tools(
    *,
    config: Any,
    registry: Any,
    prompt_builder: Any,
    llm_adapter: Any,
    environment_messages: Callable[[], List[str]],
    resolve_tools: Callable[..., List[Dict[str, Any]]],
    measure_tokens: Callable[..., Dict[str, int]],
    ctx: ProcessorContext,
    primary_agent: Agent,
    message: str,
    image_ids: Optional[List[str]],
    file_ids: Optional[List[str]],
    supports_images: Optional[bool] = None,
    correlation_id: Optional[str] = None,
) -> _PromptSetupResult:
    if supports_images is None:
        supports_images = llm_adapter.supports_image_processing(ctx.model, ctx.provider)

    extra_system_messages = environment_messages()
    if "attachments" in (getattr(primary_agent, "allowed_tools", None) or []):
        extra_system_messages.append(
            "Images uploaded or generated earlier in this chat can be reused. "
            "When the user refers to an earlier image or asks to retry a video, "
            "use attachments to find the source image ID in the current conversation. "
            "Discover and activate attachments if needed. Do not invent IDs or ask "
            "for another upload before checking. If several images could match, ask "
            "which filename or image they mean; do not silently pick the latest. "
            "Pass the selected image_id to video_generate with the revised prompt, "
            "or put it in image_generate.image_ids for image editing."
        )
    if extra_system_messages:
        logging.debug("FunctionCallingProcessor: injecting %d environment system message(s) from environment_prompt_block", len(extra_system_messages))

    has_tool = getattr(registry, "has_tool", None)
    discovery_registered = (
        callable(has_tool)
        and has_tool("discover_tools")
        and has_tool("activate_tools")
    )
    if (
        discovery_registered
        and getattr(primary_agent, "tool_discovery_enabled", True)
    ):
        extra_system_messages.append(_TOOL_DISCOVERY_SYSTEM_MESSAGE)

    provider_name = ProviderRegistry.resolve_name(ctx.model, ctx.provider)
    provider_block = config.get("provider_prompt_blocks", {}).get(provider_name, "")
    if provider_block:
        extra_system_messages.append(provider_block)
        logging.debug("FunctionCallingProcessor: injecting provider prompt block for provider=%s (%d chars)", provider_name, len(provider_block))

    prompt_messages = prompt_builder.build_prompt(
        content_text=message,
        conversation_id=ctx.conversation_id,
        agent_name=ctx.agent_name,
        account_name=ctx.account_id,
        context_type=ctx.context_type,
        max_prompt_chars=6000,
        context_name=ctx.context_name,
        extra_system_messages=extra_system_messages,
        image_ids=image_ids,
        file_ids=file_ids,
        supports_images=supports_images,
    )

    filtered_function_defs = resolve_tools(
        primary_agent=primary_agent,
        ctx=ctx,
        message=message,
    )

    breakdown = measure_tokens(ctx, prompt_builder, filtered_function_defs)

    return _PromptSetupResult(
        prompt_messages=prompt_messages,
        filtered_function_defs=filtered_function_defs,
        supports_images=supports_images,
        prompt_breakdown=breakdown,
    )
