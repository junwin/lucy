"""Lucy constructor adapter for galet-tools' reset_session handler."""

from galet_tools.tools.reset_session_handler import ResetSessionHandler as GaletResetSessionHandler


class ResetSessionHandler(GaletResetSessionHandler):
    def __init__(self, config):
        self.config = config
        super().__init__()


__all__ = ["ResetSessionHandler"]
