"""Lucy composition for account-scoped, history-preserving context reset."""
from galet_tools.tools.reset_session_handler import ResetSessionHandler as GaletResetSessionHandler


class ResetSessionHandler(GaletResetSessionHandler):
    def __init__(self, config):
        self.config = config
        super().__init__()

    def execute(self, args, *, account_name="auto", **context):
        try:
            if context.get("curation_service") is None:
                from src.curation.container_factory import get_curation_service
                context["curation_service"] = get_curation_service()
            return super().execute(args, account_name=account_name, **context)
        except Exception as exc:
            return {"action": self.NAME, "ok": False, "error": str(exc)}


__all__ = ["ResetSessionHandler"]
