"""Account/session-scoped access to active episodic events."""
from dataclasses import asdict
from typing import Any

from galet_memory import EpisodicConcurrencyError, EpisodicSessionNotFoundError
from src.episodic import LucyEpisodicStore


DEFAULT_EVENT_COUNT = 10
MAX_EVENT_COUNT = 1000


def _scope(account_name: str, session_id: str) -> tuple[str, str]:
    if not isinstance(account_name, str) or not account_name.strip():
        raise ValueError("Missing accountName")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("Missing sessionId")
    return account_name.strip().lower(), session_id.strip()


def get_events_impl(
    store: LucyEpisodicStore, *, account_name: str, session_id: str,
    count: Any = DEFAULT_EVENT_COUNT,
) -> tuple[dict, int]:
    try:
        account_name, session_id = _scope(account_name, session_id)
        if isinstance(count, bool) or not isinstance(count, (str, int)):
            raise ValueError("count must be an integer")
        try:
            count = int(count)
        except ValueError:
            raise ValueError("count must be an integer") from None
        if not 0 <= count <= MAX_EVENT_COUNT:
            raise ValueError(f"count must be between 0 and {MAX_EVENT_COUNT}")
        page = store.get_recent_events(account_name=account_name, session_id=session_id, count=count)
    except EpisodicSessionNotFoundError:
        return {"error": "Session not found"}, 404
    except ValueError as ex:
        return {"error": str(ex)}, 400

    events = []
    for event in page.events:
        data = asdict(event)
        for key in ("created_at", "stored_at"):
            data[key] = data[key].isoformat() if data[key] is not None else None
        data["correlation_ids"] = list(event.correlation_ids)
        events.append(data)
    return {"account_name": account_name, "session_id": session_id,
            "events": events, "count": len(events),
            "last_event_id": page.last_event_id}, 200


def deactivate_events_impl(
    store: LucyEpisodicStore, *, account_name: str, session_id: str,
    correlation_id: str,
) -> tuple[dict, int]:
    try:
        account_name, session_id = _scope(account_name, session_id)
        if not isinstance(correlation_id, str) or not correlation_id.strip():
            raise ValueError("Missing correlation_id")
        result = store.invalidate_exchange(
            account_name=account_name, session_id=session_id,
            correlation_id=correlation_id.strip(),
        )
    except EpisodicSessionNotFoundError:
        return {"error": "Session not found"}, 404
    except EpisodicConcurrencyError:
        return {"error": "Session changed; retry deactivation"}, 409
    except ValueError as ex:
        return {"error": str(ex)}, 400
    body = {"ok": result.status != "not_found", "account_name": account_name,
            **asdict(result), "event_count": result.event_count}
    return body, 404 if result.status == "not_found" else 200
