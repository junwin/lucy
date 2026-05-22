"""
Tests for chat2 error classes.
"""

import pytest

from src.chat2.errors import (
    Chat2Error,
    CorruptEventLogError,
    CorruptMetaError,
    EventNotFoundError,
    SessionNotFoundError,
    StorageOperationError,
)


class TestChat2Error:
    """Base exception tests."""

    def test_is_exception(self):
        assert issubclass(Chat2Error, Exception)

    def test_can_raise_and_catch(self):
        with pytest.raises(Chat2Error):
            raise Chat2Error("test error")

    def test_message(self):
        err = Chat2Error("something went wrong")
        assert str(err) == "something went wrong"


class TestSessionNotFoundError:
    """SessionNotFoundError tests."""

    def test_has_session_id(self):
        err = SessionNotFoundError("abc-123")
        assert err.session_id == "abc-123"
        assert "abc-123" in str(err)

    def test_is_chat2_error(self):
        assert isinstance(SessionNotFoundError("x"), Chat2Error)

    def test_catch_base(self):
        with pytest.raises(Chat2Error):
            raise SessionNotFoundError("x")


class TestEventNotFoundError:
    """EventNotFoundError tests."""

    def test_has_event_id(self):
        err = EventNotFoundError("evt-456")
        assert err.event_id == "evt-456"
        assert "evt-456" in str(err)

    def test_is_chat2_error(self):
        assert isinstance(EventNotFoundError("x"), Chat2Error)


class TestCorruptEventLogError:
    """CorruptEventLogError tests."""

    def test_has_fields(self):
        err = CorruptEventLogError("sess-1", 42, "bad json")
        assert err.session_id == "sess-1"
        assert err.line_number == 42
        assert err.detail == "bad json"
        assert "sess-1" in str(err)
        assert "42" in str(err)
        assert "bad json" in str(err)

    def test_without_detail(self):
        err = CorruptEventLogError("sess-1", 5)
        assert err.detail == ""
        assert "bad json" not in str(err)

    def test_is_chat2_error(self):
        assert isinstance(CorruptEventLogError("x", 1), Chat2Error)


class TestCorruptMetaError:
    """CorruptMetaError tests."""

    def test_has_fields(self):
        err = CorruptMetaError("sess-1", "missing field")
        assert err.session_id == "sess-1"
        assert err.detail == "missing field"
        assert "sess-1" in str(err)
        assert "missing field" in str(err)

    def test_without_detail(self):
        err = CorruptMetaError("sess-1")
        assert err.detail == ""

    def test_is_chat2_error(self):
        assert isinstance(CorruptMetaError("x"), Chat2Error)


class TestStorageOperationError:
    """StorageOperationError tests."""

    def test_has_fields(self):
        err = StorageOperationError("write_text", "sessions/x/meta.json", "disk full")
        assert err.operation == "write_text"
        assert err.key == "sessions/x/meta.json"
        assert err.detail == "disk full"
        assert "write_text" in str(err)
        assert "sessions/x/meta.json" in str(err)
        assert "disk full" in str(err)

    def test_without_detail(self):
        err = StorageOperationError("delete", "sessions/x/events.jsonl")
        assert err.detail == ""

    def test_is_chat2_error(self):
        assert isinstance(StorageOperationError("r", "k"), Chat2Error)
