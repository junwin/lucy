import logging
from typing import List, Optional

from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent
from src.message_processors.fcp_models import ProcessorContext
from src.message_processors.sse_events import SSEEvent


class Chat2Recorder:

    def __init__(self, chat2_store: Chat2Store = None) -> None:
        self.chat2_store = chat2_store

    def ensure_session(self, ctx: ProcessorContext) -> None:
        """Create a chat2 session if one doesn't exist for this conversation_id.

        Uses the existing conversation_id as the session_id so IDs stay
        consistent across storage layers.

        Best-effort: failures are logged but not propagated.
        """
        if self.chat2_store is None:
            return
        if self.chat2_store.session_exists(ctx.conversation_id):
            return
        try:
            self.chat2_store.create_session(
                user_id=ctx.account_id,
                account_name=ctx.account_id,
                agent_name=ctx.agent_name,
                session_id=ctx.conversation_id,
                friendly_name=ctx.context_name or None,
                context_name=ctx.context_name or None,
            )
            logging.info(
                "chat2: created session %s for account=%s agent=%s",
                ctx.conversation_id,
                ctx.account_id,
                ctx.agent_name,
            )
        except Exception:
            logging.exception(
                "chat2: failed to create session %s for account=%s",
                ctx.conversation_id,
                ctx.account_id,
            )


    def write_streaming_events(
        self,
        ctx: ProcessorContext,
        user_message: str,
        streamed_events: List[SSEEvent],
        correlation_id: Optional[str] = None,
    ) -> None:
        """Write streaming events to chat2 storage, preserving image and tool cards.

        When *correlation_id* is provided, every written event is linked to it
        in the correlation sidecar index. Falsy correlation ids write no links.

        Best-effort: failures are logged but not propagated.
        """
        if self.chat2_store is None:
            return
        try:
            self.ensure_session(ctx)
            chat_events: List[ChatEvent] = []

            # 1. User message
            chat_events.append(ChatEvent(
                role="user",
                actor=ctx.account_id,
                kind="user_message",
                payload=user_message,
                metadata={"agent": ctx.agent_name},
            ))

            # 2. Tool calls and results
            for ev in streamed_events:
                if ev.type == "tool_call":
                    chat_events.append(ChatEvent(
                        role="assistant",
                        actor=ctx.agent_name,
                        kind="assistant_tool_call",
                        payload={"tool_name": ev.tool_name, "call_id": ev.call_id},
                        metadata={"agent": ctx.agent_name, "call_id": ev.call_id},
                    ))
                elif ev.type == "tool_result":
                    payload = {"call_id": ev.call_id, "ok": ev.ok}
                    # Persist status so the frontend ticker can show warnings in history
                    if ev.status:
                        payload["status"] = ev.status
                    chat_events.append(ChatEvent(
                        role="tool",
                        actor="system",
                        kind="tool_result",
                        payload=payload,
                        metadata={"call_id": ev.call_id},
                    ))

            # 3. Assistant text (find the last text event)
            assistant_texts = [ev for ev in streamed_events if ev.type == "text" and ev.content]
            if assistant_texts:
                # Use the last text event as the assistant response
                chat_events.append(ChatEvent(
                    role="assistant",
                    actor=ctx.agent_name,
                    kind="assistant_message",
                    payload=assistant_texts[-1].content or "",
                    metadata={"agent": ctx.agent_name},
                ))

            # 4. Images (PNG and SVG)
            for ev in streamed_events:
                if ev.type == "image":
                    if ev.format == "svg":
                        chat_events.append(ChatEvent(
                            role="assistant",
                            actor=ctx.agent_name,
                            kind="generated_image",
                            payload={
                                "format": "svg",
                                "svg_markup": ev.svg_markup,
                                "alt": ev.alt or "",
                                "width": ev.width,
                                "height": ev.height,
                            },
                            metadata={"agent": ctx.agent_name, "format": "svg"},
                        ))
                    else:
                        chat_events.append(ChatEvent(
                            role="assistant",
                            actor=ctx.agent_name,
                            kind="generated_image",
                            payload={"image_url": ev.image_url, "alt": ev.alt or "", "format": "png"},
                            metadata={"agent": ctx.agent_name, "format": "png"},
                        ))

            self.chat2_store.add_events(ctx.conversation_id, chat_events)
            for event in chat_events:
                self.chat2_store.link_event(
                    correlation_id, ctx.conversation_id, event.event_id
                )
            logging.info(
                "chat2: wrote %d streaming events for session=%s (user+tool+text+image)",
                len(chat_events),
                ctx.conversation_id,
            )
        except Exception:
            logging.exception(
                "chat2: failed to write streaming events for session=%s",
                ctx.conversation_id,
            )
