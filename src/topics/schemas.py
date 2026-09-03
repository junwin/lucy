"""
Topic event schemas and stream layout - single source of truth (issue #129).

This module is the normative reference for:

- the event envelope (``ts``, ``event_id``, ``kind``, ``agent``, ``account``,
  ``stream``)
- the ``topic_*`` payload kinds (``topic_created``, ``topic_renamed``,
  ``topic_merged``, ``topic_archived``, ``topic_link``, ``topic_unlink``)
- the migrated-conversation kind (``chat2_event``) and its provenance
  marker (pinned 2026-09-01, review gap #3): ``EventProvenance`` carries
  ``source``, the legacy ``session_id`` (metadata only) and ``migrated_at``
- the stream layout + filename rules (inbox + one file per explicit topic)
- the slug contract (format, normalization, uniqueness, stability)
- the event-log ``schema_version`` (1 -> 2 with the topics release)

Guardrails encoded here, per ``design/topics.md`` (issue #129):

- **Events never carry ``topic_id``** (decision 1). Topic membership is a
  derived index rebuilt from the log. The only topic references on events are
  the ``topic_link`` / ``topic_unlink`` payloads, which carry the *target
  topic slug* as re-tagging instructions - not a membership field.
- **``agent`` is event metadata, never a partition key** (decision 7).
  Streams are partitioned by topic (inbox + one per explicit topic); any
  agent's events append to the same stream.
- **``stream`` on the envelope is physical placement only** - the stream the
  event was appended to, decided at write time. It is *not* topic membership;
  the two never have to agree (re-tagging never moves an event).
- **Slug contract** (decision 8, pinned 2026-09-01): format ``[a-z0-9-]``,
  3-64 chars, alphanumeric start/end; normalization pipeline; uniqueness per
  account with a deterministic numeric suffix; slug immutable after creation.
- **Identity model** (pinned 2026-09-01): ``topic_id`` = the immutable slug;
  ``name`` = the mutable label; rename mutates ``name`` only.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection
from datetime import datetime, timezone
from typing import Any, List, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Event-log schema version
# ---------------------------------------------------------------------------

#: Adding ``topic_*`` kinds bumps the event-log schema 1 -> 2 (review #13).
#: Recorded in design/append-only-event-store.md.
EVENT_LOG_SCHEMA_VERSION = 2

# ---------------------------------------------------------------------------
# Event kinds
# ---------------------------------------------------------------------------

KIND_TOPIC_CREATED = "topic_created"
KIND_TOPIC_RENAMED = "topic_renamed"
KIND_TOPIC_MERGED = "topic_merged"
KIND_TOPIC_ARCHIVED = "topic_archived"
KIND_TOPIC_LINK = "topic_link"
KIND_TOPIC_UNLINK = "topic_unlink"
KIND_CHAT2_EVENT = "chat2_event"

#: Provenance ``source`` value for events copied from the legacy chat2
#: store by migration (pinned 2026-09-01, review gap #3).
MIGRATION_SOURCE_CHAT2 = "chat2"

TOPIC_KINDS = frozenset(
    {
        KIND_TOPIC_CREATED,
        KIND_TOPIC_RENAMED,
        KIND_TOPIC_MERGED,
        KIND_TOPIC_ARCHIVED,
        KIND_TOPIC_LINK,
        KIND_TOPIC_UNLINK,
        KIND_CHAT2_EVENT,
    }
)

TopicKind = Literal[
    "topic_created",
    "topic_renamed",
    "topic_merged",
    "topic_archived",
    "topic_link",
    "topic_unlink",
    "chat2_event",
]

# ---------------------------------------------------------------------------
# Stream layout
# ---------------------------------------------------------------------------

#: Directory under the data root that holds topic streams.
TOPICS_DIR = "topics"

#: Stream name for the account inbox (default destination for unattributed
#: events, migration leftovers, and future inferred topics).
INBOX_STREAM = "inbox"

#: File suffix for stream files (JSON Lines).
STREAM_FILE_SUFFIX = ".jsonl"


# ---------------------------------------------------------------------------
# Slug contract (decision 8, pinned 2026-09-01)
# ---------------------------------------------------------------------------

SLUG_MIN_LENGTH = 3
SLUG_MAX_LENGTH = 64

#: Format: lowercase ASCII [a-z0-9] and '-' only; 3-64 chars; must start and
#: end with an alphanumeric. First char + at least one middle char + last char
#: enforces the 3-char minimum; {1,62} enforces the 64-char maximum.
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")


def normalize_slug(proposal: str) -> str:
    """Normalize an LLM slug proposal per the slug contract.

    Pipeline: NFKC -> lowercase -> spaces/underscores to '-' -> strip
    disallowed chars -> collapse '-{2,}' -> trim leading/trailing '-'.
    """
    if not isinstance(proposal, str):
        raise TypeError(f"slug proposal must be a str, got {type(proposal)}")
    s = unicodedata.normalize("NFKC", proposal)
    s = s.lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-{2,}", "-", s)
    s = s.strip("-")
    return s


def is_valid_slug(slug: str) -> bool:
    """Return True if *slug* already satisfies the slug contract format."""
    return bool(SLUG_PATTERN.match(slug)) if isinstance(slug, str) else False


def validate_slug(slug: str, *, field: str = "slug") -> str:
    """Validate *slug* against the slug contract; raise ValueError otherwise."""
    if not is_valid_slug(slug):
        raise ValueError(
            f"{field} must match the slug contract "
            f"([a-z0-9-], {SLUG_MIN_LENGTH}-{SLUG_MAX_LENGTH} chars, "
            f"alphanumeric start/end), got {slug!r}"
        )
    return slug


def resolve_slug(proposal: str, existing: Collection[str]) -> str:
    """Resolve a proposed slug to a unique stored slug per the slug contract.

    The proposal is a hint (decision 8). The stored slug is the deterministic
    resolution: normalize -> if free, use it; else append a deterministic
    numeric suffix (``-2``, ``-3``, ...) until free. The base is truncated as
    needed so the suffixed slug still satisfies the 64-char maximum.
    """
    base = normalize_slug(proposal)
    validate_slug(base, field="normalized slug proposal")
    existing_set = set(existing)
    if base not in existing_set:
        return base
    n = 2
    while True:
        suffix = f"-{n}"
        candidate = base[: SLUG_MAX_LENGTH - len(suffix)] + suffix
        if candidate not in existing_set:
            return candidate
        n += 1


# ---------------------------------------------------------------------------
# Payload models (topic_* kinds)
# ---------------------------------------------------------------------------

# Payload models forbid extra fields so a stray ``topic_id`` can never sneak
# onto an event (decision 1).
_PAYLOAD_CONFIG = ConfigDict(extra="forbid")


class TopicCreatedPayload(BaseModel):
    """``topic_created`` - create an explicit topic (and its stream).

    ``slug`` is the *stored* slug - already resolved per the slug contract by
    the mutation layer (the LLM proposal is a hint; the stored slug is the
    deterministic resolution). ``name`` is the mutable human-readable label.
    """

    model_config = _PAYLOAD_CONFIG

    name: str = Field(min_length=1)
    slug: str
    description: Optional[str] = None

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        return validate_slug(v, field="topic_created.slug")


class TopicRenamedPayload(BaseModel):
    """``topic_renamed`` - rename mutates ``name`` only (identity model).

    The slug/``topic_id`` never changes; the payload carries the label delta.
    """

    model_config = _PAYLOAD_CONFIG

    old_name: str = Field(min_length=1)
    new_name: str = Field(min_length=1)


class TopicMergedPayload(BaseModel):
    """``topic_merged`` - merge source into target (lifecycle semantics).

    ``source`` is frozen and archived; its event ids are re-linked to
    ``target`` (events never move). Both are slugs.
    """

    model_config = _PAYLOAD_CONFIG

    source: str
    target: str

    @field_validator("source", "target")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        return validate_slug(v, field="topic_merged.<slug>")


class TopicArchivedPayload(BaseModel):
    """``topic_archived`` - archive a topic (event + freeze only in v1).

    The stream rejects new writes; existing events stay queryable. Physical
    copy+marker is out of scope for v1.
    """

    model_config = _PAYLOAD_CONFIG

    reason: Optional[str] = None


class TopicLinkPayload(BaseModel):
    """``topic_link`` - re-tag event ids into a topic (decision 1).

    Carries the target topic slug + the referenced event ids. Membership
    changes; events never move. ``reason`` is optional (e.g. inferred topics
    in Phase 2, or merge re-linking).
    """

    model_config = _PAYLOAD_CONFIG

    topic: str
    event_ids: List[str] = Field(min_length=1)
    reason: Optional[str] = None

    @field_validator("topic")
    @classmethod
    def _validate_topic(cls, v: str) -> str:
        return validate_slug(v, field="topic_link.topic")

    @field_validator("event_ids")
    @classmethod
    def _validate_event_ids(cls, v: List[str]) -> List[str]:
        if any(not isinstance(eid, str) or not eid for eid in v):
            raise ValueError("topic_link.event_ids must be non-empty strings")
        return v


class TopicUnlinkPayload(BaseModel):
    """``topic_unlink`` - remove event ids from a topic (decision 1).

    Same shape as ``topic_link`` minus the reason. Appending unlink events is
    how re-tagging stays append-only.
    """

    model_config = _PAYLOAD_CONFIG

    topic: str
    event_ids: List[str] = Field(min_length=1)

    @field_validator("topic")
    @classmethod
    def _validate_topic(cls, v: str) -> str:
        return validate_slug(v, field="topic_unlink.topic")

    @field_validator("event_ids")
    @classmethod
    def _validate_event_ids(cls, v: List[str]) -> List[str]:
        if any(not isinstance(eid, str) or not eid for eid in v):
            raise ValueError("topic_unlink.event_ids must be non-empty strings")
        return v


class EventProvenance(BaseModel):
    """Provenance marker on migrated events (review gap #3, pinned 2026-09-01).

    ``source`` names the legacy store ("chat2"); ``session_id`` is the legacy
    chat2 session id, kept as **legacy metadata only** (never a topic
    reference); ``migrated_at`` is when migration appended the copy (UTC).
    """

    model_config = _PAYLOAD_CONFIG

    source: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    migrated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class Chat2EventPayload(BaseModel):
    """A chat2 session event copied into the topic log by migration.

    Wraps the original chat2 envelope (``role``, ``actor``,
    ``source_kind``, the opaque original ``payload`` and ``metadata``)
    plus a provenance marker. The ``TopicEvent`` envelope preserves the
    original ``ts`` and ``event_id``. Events never carry ``topic_id``
    (decision 1): membership is derived (stream binding + ``topic_link``),
    never stored on the event.
    """

    model_config = _PAYLOAD_CONFIG

    role: str = ""
    actor: str = ""
    source_kind: str = ""
    # Opaque original chat2 payload (dict or str today; kept permissive so
    # legacy events of any shape migrate without loss).
    payload: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: EventProvenance


TopicPayload = Union[
    TopicCreatedPayload,
    TopicRenamedPayload,
    TopicMergedPayload,
    TopicArchivedPayload,
    TopicLinkPayload,
    TopicUnlinkPayload,
    Chat2EventPayload,
]

_KIND_TO_PAYLOAD = {
    KIND_TOPIC_CREATED: TopicCreatedPayload,
    KIND_TOPIC_RENAMED: TopicRenamedPayload,
    KIND_TOPIC_MERGED: TopicMergedPayload,
    KIND_TOPIC_ARCHIVED: TopicArchivedPayload,
    KIND_TOPIC_LINK: TopicLinkPayload,
    KIND_TOPIC_UNLINK: TopicUnlinkPayload,
    KIND_CHAT2_EVENT: Chat2EventPayload,
}


# ---------------------------------------------------------------------------
# Event envelope
# ---------------------------------------------------------------------------


def _validate_account_name(account: str) -> None:
    """StoreKey-compatible account validation: no leading '/', no '..'."""
    if not isinstance(account, str) or not account:
        raise ValueError("account must be a non-empty string")
    if account.startswith("/"):
        raise ValueError(f"account must not start with '/': {account!r}")
    if "/" in account:
        raise ValueError(f"account must not contain '/': {account!r}")
    if ".." in account.split("/"):
        raise ValueError(f"account must not contain '..': {account!r}")


def _validate_stream_name(stream: str) -> None:
    """Validate a stream name: 'inbox' or a valid slug + StoreKey rules."""
    if not isinstance(stream, str) or not stream:
        raise ValueError("stream must be a non-empty string")
    if stream == INBOX_STREAM:
        return
    if not SLUG_PATTERN.match(stream):
        raise ValueError(
            f"stream must be '{INBOX_STREAM}' or a valid slug "
            f"([a-z0-9-], {SLUG_MIN_LENGTH}-{SLUG_MAX_LENGTH} chars), got {stream!r}"
        )
    # Defense in depth: slugs are [a-z0-9-] so these cannot occur, but the
    # stream name is used in a path, so enforce StoreKey rules anyway.
    if stream.startswith("/") or ".." in stream.split("/"):
        raise ValueError(f"stream is not StoreKey-compatible: {stream!r}")


class TopicEvent(BaseModel):
    """An event in a topic stream (append-only; never mutated).

    Envelope: ``ts``, ``event_id``, ``kind``, ``agent``, ``account``,
    ``stream`` + typed ``payload``.

    - ``stream`` = physical placement at write time (inbox or a topic slug),
      *not* topic membership (decision 1 / gap note in topics.md).
    - ``agent`` = who produced the event (metadata). Streams are never
      partitioned by agent (decision 7).
    - Events never carry ``topic_id`` (decision 1); extra fields are rejected.
    """

    model_config = ConfigDict(extra="forbid")

    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    kind: TopicKind
    agent: str = Field(min_length=1)
    account: str = Field(min_length=1)
    stream: str
    payload: TopicPayload

    @model_validator(mode="before")
    @classmethod
    def _coerce_payload_by_kind(cls, data: Any) -> Any:
        """Disambiguate payload dicts by the envelope's ``kind``.

        ``topic_link`` and ``topic_unlink`` are structurally identical except
        for link's optional ``reason``, so a bare payload dict is ambiguous to
        the plain union (pydantic would always pick the first match -
        ``TopicLinkPayload`` - and ``topic_unlink`` events would fail to
        round-trip from JSON). The envelope's ``kind`` disambiguates:
        validate the payload against the kind's own model before the union
        sees it. The after-validator below still enforces the exact payload
        type.
        """
        if not isinstance(data, dict):
            return data
        kind = data.get("kind")
        payload = data.get("payload")
        if kind in _KIND_TO_PAYLOAD and isinstance(payload, dict):
            payload_cls = _KIND_TO_PAYLOAD[kind]
            data = {**data, "payload": payload_cls.model_validate(payload)}
        return data

    @field_validator("ts")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        """Normalize to timezone-aware UTC (naive datetimes are assumed UTC)."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @field_validator("account")
    @classmethod
    def _validate_account(cls, v: str) -> str:
        _validate_account_name(v)
        return v

    @field_validator("stream")
    @classmethod
    def _validate_stream(cls, v: str) -> str:
        _validate_stream_name(v)
        return v

    @model_validator(mode="after")
    def _check_kind_payload(self) -> "TopicEvent":
        expected = _KIND_TO_PAYLOAD.get(self.kind)
        if expected is None or not isinstance(self.payload, expected):
            got = type(self.payload).__name__
            raise ValueError(
                f"kind {self.kind!r} requires payload {expected.__name__ if expected else '<none>'}, "
                f"got {got}"
            )
        return self


# ---------------------------------------------------------------------------
# Derived topic record (projection, NOT an event)
# ---------------------------------------------------------------------------


class TopicRecord(BaseModel):
    """A derived topic: the projection over ``topic_*`` events.

    This is a *record*, not an event, so it legitimately carries
    ``topic_id``. Built by the index (src/topics/index.py) from replay; never
    stored in the log itself.

    - ``topic_id`` = the immutable slug (decision 8 / identity model).
    - ``name`` = the mutable label; ``topic_renamed`` events change it.
    - ``event_ids`` = derived membership (decision 1).
    """

    model_config = ConfigDict(extra="forbid")

    topic_id: str
    kind: Literal["explicit", "temporal", "inferred"] = "explicit"
    name: str = Field(min_length=1)
    description: Optional[str] = None
    archived: bool = False
    event_ids: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("topic_id")
    @classmethod
    def _validate_topic_id(cls, v: str) -> str:
        return validate_slug(v, field="topic_id")


# ---------------------------------------------------------------------------
# Stream layout helpers
# ---------------------------------------------------------------------------


def stream_path(account: str, stream: str) -> str:
    """Return the logical JSONL path for a stream, relative to the data root.

    Layout (per design/topics.md):
      inbox:  ``topics/<account>/inbox.jsonl``
      topic:  ``topics/<account>/<slug>.jsonl``   (slug already sanitized)

    The result is StoreKey-compatible (no leading '/', no '..' segments).
    ``agent`` is deliberately not part of the path: streams are partitioned by
    topic, never by agent (decision 7).
    """
    _validate_account_name(account)
    _validate_stream_name(stream)
    return f"{TOPICS_DIR}/{account}/{stream}{STREAM_FILE_SUFFIX}"


def inbox_path(account: str) -> str:
    """Return the logical path of an account's inbox stream."""
    return stream_path(account, INBOX_STREAM)


__all__ = [
    "EVENT_LOG_SCHEMA_VERSION",
    "TOPICS_DIR",
    "INBOX_STREAM",
    "STREAM_FILE_SUFFIX",
    "KIND_TOPIC_CREATED",
    "KIND_TOPIC_RENAMED",
    "KIND_TOPIC_MERGED",
    "KIND_TOPIC_ARCHIVED",
    "KIND_TOPIC_LINK",
    "KIND_TOPIC_UNLINK",
    "KIND_CHAT2_EVENT",
    "MIGRATION_SOURCE_CHAT2",
    "TOPIC_KINDS",
    "TopicKind",
    "SLUG_MIN_LENGTH",
    "SLUG_MAX_LENGTH",
    "SLUG_PATTERN",
    "normalize_slug",
    "is_valid_slug",
    "validate_slug",
    "resolve_slug",
    "TopicCreatedPayload",
    "TopicRenamedPayload",
    "TopicMergedPayload",
    "TopicArchivedPayload",
    "TopicLinkPayload",
    "TopicUnlinkPayload",
    "Chat2EventPayload",
    "EventProvenance",
    "TopicPayload",
    "TopicEvent",
    "TopicRecord",
    "stream_path",
    "inbox_path",
]
