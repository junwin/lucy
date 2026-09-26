"""Lucy composition adapter for galet-tools' curate_chat handler.

The advertised tool contract is galet-tools' digest/archive contract. Legacy
Lucy calls that request filtering, publication, or friendly-name resolution
still use Lucy's application curation engine during the transition.
"""

from __future__ import annotations

from typing import Any

from galet_memory.curation import CurationService, DigestGenerationRequest
from galet_tools.tools.curate_chat_handler import CurateChatHandler as GaletCurateChatHandler

from src.curation.container_factory import get_curation_engine
from src.curation.summarizer import summarize_session


class LucyDigestGenerator:
    def __init__(self, engine):
        self.engine = engine

    def generate(self, request: DigestGenerationRequest) -> str:
        return summarize_session(
            list(request.events),
            llm_api=self.engine.llm_api,
            model=self.engine.llm_model,
            friendly_name=request.friendly_name,
            session_id=request.session_id,
            account=request.account_name,
            max_chars=request.max_chars,
        )


class CurateChatHandler(GaletCurateChatHandler):
    def __init__(self, config, engine=None, service=None):
        self.config = config
        self.engine = engine
        self.service = service

    def _engine(self, context):
        return context.get("curation_engine") or self.engine or get_curation_engine()

    def execute(self, args: dict[str, Any], *, account_name: str = "auto", **context):
        mode = str(args.get("mode") or "digest").strip().lower()
        session_id = str(args.get("session_id") or "").strip()
        friendly_name = str(args.get("friendly_name") or "").strip()
        account = str(args.get("account") or account_name or "").strip()

        # Lucy's old filter and Markdown publication features have no equivalent
        # in CurationService. Preserve those explicit legacy calls for now.
        if mode == "filter" or args.get("publish") or (friendly_name and not session_id):
            engine = self._engine(context)
            try:
                raw = args.get("curation_rules") or ""
                if isinstance(raw, str):
                    import json
                    rules = json.loads(raw) if raw else {}
                else:
                    rules = raw
                result = engine.curate(
                    session_id=session_id or None,
                    friendly_name=friendly_name or None,
                    account=account,
                    mode=mode,
                    preview=bool(args.get("preview", True)),
                    publish=bool(args.get("publish", False)),
                    template_name=str(args.get("template_name") or "default"),
                    curation_rules=rules,
                    max_chars=int(args.get("max_chars", self.config.get("curation_max_chars", 32000))),
                )
                return {"ok": result.get("status") != "error", "tool": self.NAME, **result}
            except Exception as exc:
                return {
                    "ok": False, "tool": self.NAME, "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }

        # Old preview=True on archive requested a digest without changing the
        # session. The new schema omits preview, so archive means archive.
        if mode == "summarize" or (mode == "archive" and args.get("preview") is True):
            mode = "digest"
        engine = None
        service = context.get("curation_service") or self.service
        if service is None:
            engine = self._engine(context)
            service = CurationService(
                engine.episodic_store, LucyDigestGenerator(engine)
            )
        delegate = GaletCurateChatHandler(service)
        max_chars = args.get("max_chars", self.config.get("curation_max_chars", 32000))
        result = delegate.execute(
            {
                "session_id": session_id,
                "mode": mode,
                "max_chars": max_chars,
                "idempotency_key": args.get("idempotency_key", ""),
            },
            account_name=account,
        )
        if result.get("ok"):
            result["note_text"] = result["digest"]
            result["output_path"] = None
        return result


__all__ = ["CurateChatHandler", "LucyDigestGenerator"]
