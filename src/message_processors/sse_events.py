"""SSE Event model for streaming /ask responses.

Phase 1 emits: text, tool_call, tool_result, done, error.
Phase 2: action.
Phase 3: image (PNG via image_url, SVG via svg_markup + format).
"""

from pydantic import BaseModel
from typing import Literal, Optional


class SSEEvent(BaseModel):
    """A single Server-Sent Event for the /ask streaming path."""

    type: Literal["text", "tool_call", "tool_result", "image", "action", "done", "error"]

    # --- text ---
    content: Optional[str] = None  # full message in Phase 1, deltas in Phase 4
    message_id: Optional[str] = None  # stable id for in-place updates (Phase 4)

    # --- tool_call / tool_result ---
    tool_name: Optional[str] = None
    call_id: Optional[str] = None
    ok: Optional[bool] = None

    # --- image (Phase 3) ---
    # PNG images: image_url is a data URI (e.g. data:image/png;base64,...)
    image_url: Optional[str] = None
    alt: Optional[str] = None

    # SVG images: svg_markup is the raw SVG string, format is "svg"
    svg_markup: Optional[str] = None
    format: Optional[str] = None  # "png" or "svg"
    width: Optional[int] = None
    height: Optional[int] = None

    # --- action (Phase 2) ---
    action: Optional[str] = None  # "reset_session" | "redirect" | ...
    action_payload: Optional[dict] = None

    # --- done ---
    conversation_id: Optional[str] = None

    # --- error ---
    message: Optional[str] = None

    def to_sse(self) -> str:
        """Serialize to SSE wire format: data: <json>\n\n"""
        return f"data: {self.model_dump_json(exclude_none=True)}\n\n"
