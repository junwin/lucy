"""Record function-calling activity through the galet-memory interface."""

from src.episodic import LucyEpisodicStore

import logging
from dataclasses import replace
from typing import Dict, List, Optional

from galet_memory import NewEvent
from src.message_processors.fcp_models import ProcessorContext
from src.message_processors.sse_events import SSEEvent


class EpisodicRecorder:

    def __init__(self, episodic_store: Optional[LucyEpisodicStore] = None) -> None:
        self.episodic_store = episodic_store

    def ensure_session(self, ctx: ProcessorContext) -> None:
        """Create an episodic session if one doesn't exist for this conversation_id.

        Uses the existing conversation_id as the session_id so IDs stay
        consistent across storage layers.

        Best-effort: failures are logged but not propagated.
        """
        if self.episodic_store is None:
            return
        if self.episodic_store.get_session(account_name=ctx.account_id, session_id=ctx.conversation_id) is not None:
            return
        try:
            self.episodic_store.create_session(
                account_name=ctx.account_id,
                metadata={"default_agent": ctx.agent_name},
                session_id=ctx.conversation_id,
                friendly_name=ctx.context_name or None,
                context_name=ctx.context_name or None,
            )
            logging.info(
                "episodic: created session %s for account=%s agent=%s",
                ctx.conversation_id,
                ctx.account_id,
                ctx.agent_name,
            )
        except Exception:
            logging.exception(
                "episodic: failed to create session %s for account=%s",
                ctx.conversation_id,
                ctx.account_id,
            )


    def write_user_message(
        self,
        ctx: ProcessorContext,
        user_message: str,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Persist the user side of a streaming turn before response delivery starts."""
        if self.episodic_store is None:
            return
        try:
            self.ensure_session(ctx)
            self.episodic_store.append_event(
                account_name=ctx.account_id, session_id=ctx.conversation_id,
                event=NewEvent(
                    role="user",
                    actor=ctx.account_id,
                    kind="user_message",
                    content=user_message,
                    metadata={"agent": ctx.agent_name},
                    correlation_ids=(correlation_id,) if correlation_id else (),
                ),
            )
        except Exception:
            logging.exception(
                "episodic: failed to write streaming user message for session=%s",
                ctx.conversation_id,
            )

    def write_streaming_event(
        self,
        ctx: ProcessorContext,
        streamed_event: SSEEvent,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Persist one deliverable SSE event before it is yielded to the client."""
        if self.episodic_store is None:
            return

        ev = streamed_event
        event: Optional[NewEvent] = None
        if ev.type == "tool_call":
            event = NewEvent(
                role="assistant",
                actor=ctx.agent_name,
                kind="assistant_tool_call",
                content={"tool_name": ev.tool_name, "call_id": ev.call_id},
                metadata={"agent": ctx.agent_name, "call_id": ev.call_id},
            )
        elif ev.type == "tool_result":
            payload = {"call_id": ev.call_id, "ok": ev.ok}
            if ev.status:
                payload["status"] = ev.status
            event = NewEvent(
                role="tool",
                actor="system",
                kind="tool_result",
                content=payload,
                metadata={"call_id": ev.call_id},
            )
        elif ev.type == "text" and ev.content:
            event = NewEvent(
                role="assistant",
                actor=ctx.agent_name,
                kind="assistant_message",
                content=ev.content,
                metadata={"agent": ctx.agent_name},
            )
        elif ev.type == "image":
            if ev.format == "svg":
                content = {
                    "format": "svg",
                    "svg_markup": ev.svg_markup,
                    "alt": ev.alt or "",
                    "width": ev.width,
                    "height": ev.height,
                }
                image_format = "svg"
            else:
                content = {
                    "image_url": ev.image_url,
                    "image_id": ev.image_id,
                    "image_ref": ev.image_ref,
                    "download_url": ev.download_url,
                    "message_id": ev.message_id,
                    "mime_type": ev.mime_type,
                    "alt": ev.alt or "",
                    "format": "png",
                }
                image_format = "png"
            event = NewEvent(
                role="assistant",
                actor=ctx.agent_name,
                kind="generated_image",
                content=content,
                metadata={"agent": ctx.agent_name, "format": image_format},
            )
        elif ev.type == "video":
            event = NewEvent(
                role="assistant",
                actor=ctx.agent_name,
                kind="generated_video",
                content={
                    "video_url": ev.video_url,
                    "mime_type": ev.mime_type or "video/mp4",
                    "download_name": ev.download_name or "fashion-reel.mp4",
                    "video_id": ev.video_id,
                },
                metadata={"agent": ctx.agent_name, "format": "mp4"},
            )

        if event is None:
            return

        try:
            self.ensure_session(ctx)
            self.episodic_store.append_event(account_name=ctx.account_id, session_id=ctx.conversation_id, event=replace(event, correlation_ids=(correlation_id,) if correlation_id else ()))
        except Exception:
            logging.exception(
                "episodic: failed to write streaming event type=%s for session=%s",
                ev.type,
                ctx.conversation_id,
            )


    def write_streaming_events(
        self,
        ctx: ProcessorContext,
        user_message: str,
        streamed_events: List[SSEEvent],
        correlation_id: Optional[str] = None,
    ) -> None:
        """Write streaming events to episodic storage, preserving media and tool cards.

        When *correlation_id* is provided, every written event is linked to it
        atomically as part of the append. Falsy correlation ids write no links.

        Best-effort: failures are logged but not propagated.
        """
        if self.episodic_store is None:
            return
        try:
            self.ensure_session(ctx)
            chat_events: List[NewEvent] = []

            # 1. User message
            chat_events.append(NewEvent(
                role="user",
                actor=ctx.account_id,
                kind="user_message",
                content=user_message,
                metadata={"agent": ctx.agent_name},
            ))

            # 2. Tool calls and results
            for ev in streamed_events:
                if ev.type == "tool_call":
                    chat_events.append(NewEvent(
                        role="assistant",
                        actor=ctx.agent_name,
                        kind="assistant_tool_call",
                        content={"tool_name": ev.tool_name, "call_id": ev.call_id},
                        metadata={"agent": ctx.agent_name, "call_id": ev.call_id},
                    ))
                elif ev.type == "tool_result":
                    payload = {"call_id": ev.call_id, "ok": ev.ok}
                    # Persist status so the frontend ticker can show warnings in history
                    if ev.status:
                        payload["status"] = ev.status
                    chat_events.append(NewEvent(
                        role="tool",
                        actor="system",
                        kind="tool_result",
                        content=payload,
                        metadata={"call_id": ev.call_id},
                    ))

            # 3. Assistant text (find the last text event)
            assistant_texts = [ev for ev in streamed_events if ev.type == "text" and ev.content]
            if assistant_texts:
                # Use the last text event as the assistant response
                chat_events.append(NewEvent(
                    role="assistant",
                    actor=ctx.agent_name,
                    kind="assistant_message",
                    content=assistant_texts[-1].content or "",
                    metadata={"agent": ctx.agent_name},
                ))

            # 4. Images (PNG and SVG)
            for ev in streamed_events:
                if ev.type == "image":
                    if ev.format == "svg":
                        chat_events.append(NewEvent(
                            role="assistant",
                            actor=ctx.agent_name,
                            kind="generated_image",
                            content={
                                "format": "svg",
                                "svg_markup": ev.svg_markup,
                                "alt": ev.alt or "",
                                "width": ev.width,
                                "height": ev.height,
                            },
                            metadata={"agent": ctx.agent_name, "format": "svg"},
                        ))
                    else:
                        chat_events.append(NewEvent(
                            role="assistant",
                            actor=ctx.agent_name,
                            kind="generated_image",
                            content={"image_url": ev.image_url, "image_id": ev.image_id,
                                     "image_ref": ev.image_ref, "download_url": ev.download_url,
                                     "message_id": ev.message_id, "mime_type": ev.mime_type,
                                     "alt": ev.alt or "", "format": "png"},
                            metadata={"agent": ctx.agent_name, "format": "png"},
                        ))

            # 5. Generated videos
            for ev in streamed_events:
                if ev.type == "video":
                    chat_events.append(NewEvent(
                        role="assistant",
                        actor=ctx.agent_name,
                        kind="generated_video",
                        content={
                            "video_url": ev.video_url,
                            "mime_type": ev.mime_type or "video/mp4",
                            "download_name": ev.download_name or "fashion-reel.mp4",
                            "video_id": ev.video_id,
                        },
                        metadata={"agent": ctx.agent_name, "format": "mp4"},
                    ))

            self.episodic_store.append_events(
                account_name=ctx.account_id, session_id=ctx.conversation_id,
                events=[replace(event, correlation_ids=(correlation_id,) if correlation_id else ()) for event in chat_events],
            )
            logging.info(
                "episodic: wrote %d streaming events for session=%s (user+tool+text+image)",
                len(chat_events),
                ctx.conversation_id,
            )
        except Exception:
            logging.exception(
                "episodic: failed to write streaming events for session=%s",
                ctx.conversation_id,
            )


    def write_prompt_report(
        self,
        ctx: ProcessorContext,
        breakdown: Dict[str, int],
        correlation_id: Optional[str] = None,
    ) -> None:
        """Write a prompt token breakdown as a ``prompt_report`` system event.

        The event is attributed to the agent that built the prompt and, when
        *correlation_id* is provided, included in the append. Falsy correlation ids write no links.

        Best-effort: failures are logged but not propagated.
        """
        if self.episodic_store is None:
            return
        try:
            self.ensure_session(ctx)
            event = NewEvent(
                role="system",
                actor=ctx.agent_name,
                kind="prompt_report",
                content=breakdown,
            )
            self.episodic_store.append_event(account_name=ctx.account_id, session_id=ctx.conversation_id, event=replace(event, correlation_ids=(correlation_id,) if correlation_id else ()))
            logging.info(
                "episodic: wrote prompt_report for session=%s (correlation=%s)",
                ctx.conversation_id,
                correlation_id,
            )
        except Exception:
            logging.exception(
                "episodic: failed to write prompt_report for session=%s",
                ctx.conversation_id,
            )
