from typing import Any, Tuple
import logging

from src.prompt_builders.prompt_builder import PromptBuilder


def build_prompt_impl(agent_manager, storage, container, config, payload: dict) -> Tuple[Any, int]:
    question = payload.get("query", "")
    agentName = (payload.get("agentName", "") or "").lower()
    accountName = (payload.get("accountName", "") or "").lower()
    # keep request field name for now, but map to context_type
    context_type = payload.get("selectType", "") or payload.get("contextType", "")
    conversationId = payload.get("conversationId", "")

    # Optional: None means "no storage-based context"
    context_name = payload.get("contextName") or payload.get("context_name")
    if context_name is not None:
        context_name = str(context_name).strip() or None

    # allow optional list of extra system messages
    extra_system_messages = payload.get("extraSystemMessages") or ["my system Message"]
    if not isinstance(extra_system_messages, list):
        extra_system_messages = [str(extra_system_messages)]

    if not question or not agentName or not accountName:
        return {"error": "Missing query, agentName, or accountName"}, 400

    if not agent_manager.is_valid(agentName):
        return {"error": "Invalid agentName"}, 400

    my_agent = agent_manager.get_agent(agentName)
    if not context_type:
        # default from agent config
        context_type = my_agent.context_type if my_agent else "hybrid"

    try:
        # PromptBuilder is DI-based and requires agent_manager/config/storage.
        # Resolve it from the container (preferred) or construct with deps.
        prompt_builder = container.get(PromptBuilder)
    except Exception:
        prompt_builder = PromptBuilder(agent_manager=agent_manager, config=config, storage=storage)

    try:
        prompt = prompt_builder.build_prompt(
            content_text=question,
            conversation_id=conversationId,
            agent_name=agentName,
            account_name=accountName,
            context_type=context_type,
            max_prompt_chars=payload.get("maxPromptChars", 6000),
            context_name=context_name,
            extra_system_messages=extra_system_messages,
        )
        return prompt, 200
    except Exception as e:
        logging.exception("Error in /prompt_builder")
        return {"error": str(e)}, 500
