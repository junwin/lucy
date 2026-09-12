from unittest.mock import Mock

from src.handlers.reset_session_handler import ResetSessionHandler


def test_reset_session_uses_episodic_store():
    memory = Mock()
    handler = ResetSessionHandler(config=Mock())

    result = handler.execute(
        {},
        account_name="acct",
        conversation_id="session-1",
        episodic_store=memory,
    )

    assert result == {"action": "reset_session", "ok": True}
    memory.reset_session.assert_called_once_with("session-1")


def test_reset_session_requires_episodic_store():
    handler = ResetSessionHandler(config=Mock())

    result = handler.execute({}, conversation_id="session-1")

    assert result == {
        "action": "reset_session",
        "ok": False,
        "error": "episodic_store not available",
    }
