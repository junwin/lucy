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


def search_documents_impl(storage, data: dict):
    account_name = (data.get("account_name", "") or "").lower()
    query = data.get("question") or data.get("q") or ""
    kind = data.get("kind")
    tag = data.get("tag")
    limit = int(data.get("limit", 10))

    if not account_name:
        return {"error": "Missing account_name"}, 400
    if not query.strip():
        return {"error": "Missing query"}, 400

    try:
        if not hasattr(storage, "search_documents_poor_man"):
            return {"error": "Document search not supported by this storage backend"}, 501

        results = storage.search_documents_poor_man(
            account_name=account_name,
            query=query,
            kind=kind,
            limit=limit,
            tag=tag,
        )

        return [
            {
                "id": d.id,
                "account_name": d.account_name,
                "path": d.path,
                "kind": d.kind,
                "title": d.title,
                "tags": d.tags,
                "metadata": d.metadata,
            }
            for d in results
        ], 200
    except Exception as e:
        logging.exception("Error in /documents/search")
        return {"error": str(e)}, 500
