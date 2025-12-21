# FILE: src/message_processors/guided_conversation_processor.py

import logging
from datetime import datetime
from dateutil.parser import parse
import pytz
import yaml

from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.context.context_manager import ContextManager
from src.context.context import Context
from src.message_processors.message_processor import MessageProcessor
from src.message_processors.function_calling_processor import FunctionCallingProcessor

from src.completion.completion_store import CompletionStore
from src.container_config import container
from src.agent_manager import AgentManager
from src.config_manager import ConfigManager


class GuidedConversationProcessor(MessageProcessorInterface):
    """
    Orchestrates a guided conversation between:
      - primary agent (empathetic / BA / etc.) e.g. Glinda, Debo
      - SME agent (coach / engineer / etc.) e.g. Dorothy, Colin

    Shared context lives in:
      data/context/<account>/<context_name>.json
    where context_name is typically "<primary>_<sme>" passed in by app.py.
    """

    def __init__(self):
        self.agent_manager = container.get(AgentManager)
        self.config = container.get(ConfigManager)

        # SME calls: keep it simple (no tool loop)
        self.simple_processor = MessageProcessor()

        # Primary calls: allow tools/function calls
        self.primary_processor = FunctionCallingProcessor()

    def process_message(
        self,
        agent_name: str,
        account_name: str,
        message: str,
        conversationId: str = "0",
        context_name: str = "",
        second_agent_name: str = "",
        extra_system_messages=None,
    ) -> str:
        logging.info(
            "GuidedConversation: inbound agent=%s sme=%s msg=%s",
            agent_name,
            second_agent_name,
            (message or "")[:200],
        )

        if not context_name or context_name in ("none", "new"):
            context_name = f"{agent_name}_{second_agent_name}".strip("_")

        # --- Load/create shared context ---
        context_mgr = ContextManager(self.config)
        context = context_mgr.get_context(account_name, context_name)

        first_session = False
        new_session = False

        if context is None:
            context = Context(
                name=context_name,
                description="guided conversation",
                current_node_id="",
                state="none",
                account_name=account_name,
                conversation_id=conversationId,
            )
            context.add_action("First Session", "", "")
            context_mgr.post_context(context)
            first_session = True

        # --- Determine whether this is a "new session" based on last completion timestamp ---
        primary_agent = self.agent_manager.get_agent(agent_name)

        completion_store = container.get(CompletionStore)
        cm = completion_store.get_completion_manager(
            agent_name, account_name, primary_agent.get("language_code", "en")[:2]
        )
        latest_ids = cm.find_latest_completion_Ids(1)

        if latest_ids:
            latest = cm.get_completion(latest_ids[0])
            try:
                utc_ts = parse(latest.utc_timestamp)
                elapsed = (datetime.now(pytz.utc) - utc_ts).total_seconds()
                new_session_time = self.config.get("elapsed_new_session_seconds")
                if new_session_time and elapsed > float(new_session_time):
                    context.add_action("New Session", "", "")
                    new_session = True
                    first_session = False
            except Exception:
                # If timestamp parsing fails, don't break the flow.
                pass

        # --- Add transcript to context (if available) ---
        if latest_ids:
            try:
                transcript = cm.get_transcript(
                    latest_ids,
                    ["user", "assistant"],
                    account_name,
                    agent_name,
                )
                if transcript:
                    context.add_transcript_item(account_name, transcript)
                    context_mgr.post_context(context)
            except Exception as ex:
                logging.warning("GuidedConversation: transcript load failed: %s", ex)

        # --- Build SME request message ---
        if first_session:
            sme_input = "First session.\n" f"User({account_name}) says: {message}\n"
        elif new_session:
            sme_input = "New session. Review context carefully.\n" f"User({account_name}) says: {message}\n"
        else:
            sme_input = "Latest user message.\n" f"User({account_name}) says: {message}\n"

        # --- SME analysis (Dorothy / Colin) ---
        sme_response = self.simple_processor.process_message(
            second_agent_name,
            account_name,
            sme_input,
            conversationId,
            context_name,
        )

        # --- Parse SME output ---
        # Expected: ONE fenced ```yaml block containing:
        #   conversation_state: {Background:..., ...}
        #   recommendations: [...]
        parsed = self._extract_single_yaml_payload(sme_response)

        if parsed:
            conv_state = parsed.get("conversation_state")
            recs = parsed.get("recommendations")

            if conv_state:
                context.conversation_state = self._to_fenced_yaml(conv_state)
            if recs is not None:
                # store as YAML too (keeps structure; primary agent can render it however)
                context.recomendations = self._to_fenced_yaml({"recommendations": recs})

            context_mgr.post_context(context)
        else:
            # Fall back: store raw SME response (better than losing it)
            context.recomendations = (sme_response or "").strip()
            context_mgr.post_context(context)

        # --- Guidance block to inject into primary agent system ---
        guidance_block = context.context_formated_text2("compact").strip()
        guidance_system = (
            "Guidance from your SME partner and shared conversation state "
            f"(context: {context_name}). Follow it.\n\n{guidance_block}"
        )

        # Merge any upstream extra system messages (rare, but supported)
        extra_sys = []
        if extra_system_messages:
            extra_sys.extend(extra_system_messages)
        extra_sys.append(guidance_system)

        # --- Primary agent response via FunctionCallingProcessor ---
        # IMPORTANT: pass context_name="" so FunctionCallingProcessor does NOT reload the shared context again.
        primary_response = self.primary_processor.process_message(
            agent_name=agent_name,
            account_name=account_name,
            message=message,
            conversationId=conversationId,
            context_name="",  # prevent double context injection
            second_agent_name="",
            extra_system_messages=extra_sys,
        )

        return primary_response

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_single_yaml_payload(self, text: str):
        """
        Extract the first fenced code block (```yaml ... ```) and parse it.
        Returns dict or None.
        """
        if not text:
            return None

        start = text.find("```")
        if start == -1:
            return None

        end = text.find("```", start + 3)
        if end == -1:
            return None

        block = text[start + 3 : end].strip()
        # allow ```yaml or ```YAML
        if block.lower().startswith("yaml"):
            block = block[4:].strip()

        try:
            data = yaml.safe_load(block)
            return data if isinstance(data, dict) else None
        except Exception as ex:
            logging.warning("GuidedConversation: YAML parse failed: %s", ex)
            return None

    def _to_fenced_yaml(self, obj) -> str:
        try:
            dumped = yaml.safe_dump(obj, sort_keys=False, allow_unicode=True).rstrip()
        except Exception:
            dumped = str(obj).rstrip()
        return f"```yaml\n{dumped}\n```"