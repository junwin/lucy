"""
Tests for src/topics/schemas.py - the single source of truth for topic event
payloads, the event envelope, stream layout, and the slug contract.

Standalone (decision 4): no FCP/agent imports anywhere in this file.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from src.topics.schemas import (
    EVENT_LOG_SCHEMA_VERSION,
    INBOX_STREAM,
    KIND_CHAT2_EVENT,
    KIND_TOPIC_ARCHIVED,
    KIND_TOPIC_CREATED,
    KIND_TOPIC_LINK,
    KIND_TOPIC_MERGED,
    KIND_TOPIC_RENAMED,
    KIND_TOPIC_UNLINK,
    MIGRATION_SOURCE_CHAT2,
    SLUG_MAX_LENGTH,
    SLUG_MIN_LENGTH,
    Chat2EventPayload,
    EventProvenance,
    TopicArchivedPayload,
    TopicCreatedPayload,
    TopicEvent,
    TopicLinkPayload,
    TopicMergedPayload,
    TopicRenamedPayload,
    TopicUnlinkPayload,
    inbox_path,
    is_valid_slug,
    normalize_slug,
    resolve_slug,
    stream_path,
    validate_slug,
)


# ---------------------------------------------------------------------------
# Slug contract (decision 8, pinned 2026-09-01)
# ---------------------------------------------------------------------------


class TestSlugNormalization:
    def test_lowercases_and_replaces_spaces(self) -> None:
        assert normalize_slug("My New Topic!") == "my-new-topic"

    def test_underscores_become_hyphens(self) -> None:
        assert normalize_slug("my_topic_name") == "my-topic-name"

    def test_nfkc_fullwidth_to_ascii(self) -> None:
        assert normalize_slug("ｔｅｓｔ") == "test"

    def test_strips_disallowed_chars(self) -> None:
        # é / ä / ö / & are not in [a-z0-9-] -> stripped after NFKC+lower.
        assert normalize_slug("Café & Bäckerei") == "caf-bckerei"

    def test_collapses_hyphen_runs(self) -> None:
        assert normalize_slug("a---b") == "a-b"

    def test_trims_leading_trailing_hyphens(self) -> None:
        assert normalize_slug("--topic--") == "topic"

    def test_handles_mixed_garbage(self) -> None:
        # Spaces -> '-', then '/' and '!' are stripped (joining 'alpha'+'beta').
        assert normalize_slug("  Project  Alpha/Beta!!  ") == "project-alphabeta"


class TestSlugValidity:
    def test_accepts_contract_forms(self) -> None:
        assert is_valid_slug("abc")
        assert is_valid_slug("my-topic")
        assert is_valid_slug("my-topic-2")
        assert is_valid_slug("a" * SLUG_MIN_LENGTH)
        assert is_valid_slug("a" * SLUG_MAX_LENGTH)
        assert is_valid_slug("a" + "-" * 62 + "b")  # 64 chars, alnum ends

    def test_rejects_bad_forms(self) -> None:
        assert not is_valid_slug("")                     # empty
        assert not is_valid_slug("ab")                   # too short (2)
        assert not is_valid_slug("a")                    # too short (1)
        assert not is_valid_slug("a" * (SLUG_MAX_LENGTH + 1))  # too long
        assert not is_valid_slug("-abc")                 # leading hyphen
        assert not is_valid_slug("abc-")                 # trailing hyphen
        assert not is_valid_slug("ABC")                  # uppercase
        assert not is_valid_slug("a b")                  # space
        assert not is_valid_slug("a/b")                  # slash
        assert not is_valid_slug("a..b")                 # dots
        assert not is_valid_slug("snowman-☃")            # unicode

    def test_validate_slug_raises_with_message(self) -> None:
        with pytest.raises(ValueError, match="slug contract"):
            validate_slug("Bad Slug!")


class TestSlugResolution:
    def test_no_collision_uses_base(self) -> None:
        assert resolve_slug("My Topic", ["other"]) == "my-topic"

    def test_collision_appends_deterministic_suffix(self) -> None:
        assert resolve_slug("my-topic", ["my-topic"]) == "my-topic-2"
        assert resolve_slug("my-topic", ["my-topic", "my-topic-2"]) == "my-topic-3"

    def test_suffix_stays_deterministic_across_calls(self) -> None:
        existing = ["alpha", "alpha-2", "alpha-3", "alpha-4"]
        assert resolve_slug("alpha", existing) == "alpha-5"

    def test_suffixed_slug_respects_max_length(self) -> None:
        base = "x" * SLUG_MAX_LENGTH  # 64 chars, already taken
        result = resolve_slug(base, {base})
        assert len(result) <= SLUG_MAX_LENGTH
        assert result == "x" * 62 + "-2"
        assert is_valid_slug(result)

    def test_unusable_proposal_raises(self) -> None:
        # Normalizes to fewer than 3 chars -> cannot satisfy the contract.
        with pytest.raises(ValueError, match="slug contract"):
            resolve_slug("ab", [])


# ---------------------------------------------------------------------------
# Payload models (topic_* kinds)
# ---------------------------------------------------------------------------


class TestTopicCreatedPayload:
    def test_valid_with_required_fields(self) -> None:
        p = TopicCreatedPayload(name="My Topic", slug="my-topic")
        assert p.name == "My Topic"
        assert p.slug == "my-topic"
        assert p.description is None

    def test_description_optional(self) -> None:
        p = TopicCreatedPayload(name="T", slug="t-opic", description="d")
        assert p.description == "d"

    def test_rejects_invalid_slug(self) -> None:
        with pytest.raises(ValidationError):
            TopicCreatedPayload(name="T", slug="Not A Slug!")

    def test_rejects_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            TopicCreatedPayload(name="", slug="t-opic")


class TestTopicRenamedPayload:
    def test_valid(self) -> None:
        p = TopicRenamedPayload(old_name="Old", new_name="New")
        assert (p.old_name, p.new_name) == ("Old", "New")

    def test_requires_both_names(self) -> None:
        with pytest.raises(ValidationError):
            TopicRenamedPayload(old_name="Old", new_name="")


class TestTopicMergedPayload:
    def test_valid(self) -> None:
        p = TopicMergedPayload(source="a-topic", target="b-topic")
        assert (p.source, p.target) == ("a-topic", "b-topic")

    def test_rejects_invalid_slugs(self) -> None:
        with pytest.raises(ValidationError):
            TopicMergedPayload(source="Bad Slug", target="b-topic")


class TestTopicArchivedPayload:
    def test_valid_without_reason(self) -> None:
        assert TopicArchivedPayload().reason is None

    def test_valid_with_reason(self) -> None:
        assert TopicArchivedPayload(reason="merged away").reason == "merged away"


class TestTopicLinkPayload:
    def test_valid(self) -> None:
        p = TopicLinkPayload(topic="my-topic", event_ids=["e1", "e2"])
        assert p.event_ids == ["e1", "e2"]
        assert p.reason is None

    def test_reason_optional(self) -> None:
        p = TopicLinkPayload(topic="my-topic", event_ids=["e1"], reason="inferred")
        assert p.reason == "inferred"

    def test_rejects_empty_event_ids(self) -> None:
        with pytest.raises(ValidationError):
            TopicLinkPayload(topic="my-topic", event_ids=[])

    def test_rejects_invalid_topic_slug(self) -> None:
        with pytest.raises(ValidationError):
            TopicLinkPayload(topic="../evil", event_ids=["e1"])


class TestTopicUnlinkPayload:
    def test_valid(self) -> None:
        p = TopicUnlinkPayload(topic="my-topic", event_ids=["e1"])
        assert p.topic == "my-topic"

    def test_rejects_empty_event_ids(self) -> None:
        with pytest.raises(ValidationError):
            TopicUnlinkPayload(topic="my-topic", event_ids=[])


class TestNoTopicIdOnEvents:
    """Decision 1: events never carry topic_id; payloads reject it."""

    def test_no_topic_id_field_on_any_payload(self) -> None:
        for model in (
            TopicCreatedPayload,
            TopicRenamedPayload,
            TopicMergedPayload,
            TopicArchivedPayload,
            TopicLinkPayload,
            TopicUnlinkPayload,
            Chat2EventPayload,
        ):
            assert "topic_id" not in model.model_fields, model.__name__

    def test_payload_rejects_topic_id_extra_field(self) -> None:
        with pytest.raises(ValidationError):
            TopicCreatedPayload(name="T", slug="t-opic", topic_id="t-opic")


# ---------------------------------------------------------------------------
# Event envelope
# ---------------------------------------------------------------------------


def _event(**overrides) -> TopicEvent:
    base = dict(
        kind=KIND_TOPIC_CREATED,
        agent="lucy",
        account="junwin",
        stream=INBOX_STREAM,
        payload=TopicCreatedPayload(name="My Topic", slug="my-topic"),
    )
    base.update(overrides)
    return TopicEvent(**base)


class TestEnvelope:
    def test_valid_topic_created_event(self) -> None:
        ev = _event()
        assert ev.kind == KIND_TOPIC_CREATED
        assert ev.agent == "lucy"
        assert ev.account == "junwin"
        assert ev.stream == INBOX_STREAM
        assert isinstance(ev.payload, TopicCreatedPayload)
        assert ev.event_id  # auto-generated

    def test_event_id_can_be_supplied(self) -> None:
        ev = _event(event_id="legacy-id-1")
        assert ev.event_id == "legacy-id-1"

    def test_kind_payload_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requires payload"):
            _event(
                kind=KIND_TOPIC_CREATED,
                payload=TopicRenamedPayload(old_name="a", new_name="b"),
            )

    def test_unknown_kind_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _event(kind="not_a_topic_kind")

    def test_stream_must_be_inbox_or_slug(self) -> None:
        assert _event(stream="my-topic").stream == "my-topic"
        with pytest.raises(ValidationError):
            _event(stream="Not A Stream!")
        with pytest.raises(ValidationError):
            _event(stream="a/b")

    def test_agent_and_account_required(self) -> None:
        with pytest.raises(ValidationError):
            _event(agent="")
        with pytest.raises(ValidationError):
            _event(account="")

    def test_account_rejects_path_separators(self) -> None:
        with pytest.raises(ValidationError):
            _event(account="junwin/other")
        with pytest.raises(ValidationError):
            _event(account="../junwin")

    def test_ts_normalized_to_utc(self) -> None:
        ev = _event(ts=datetime(2026, 9, 1, 12, 0, 0))  # naive assumed UTC
        assert ev.ts.tzinfo == timezone.utc
        assert ev.ts == datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_ts_converts_other_timezones(self) -> None:
        ev = _event(
            ts=datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=2)))
        )
        assert ev.ts == datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _event(topic_id="my-topic")  # decision 1: no topic_id on events
        with pytest.raises(ValidationError):
            _event(session_id="sess-1")  # sessions retired as stored entity

    def test_json_roundtrip(self) -> None:
        ev = _event()
        raw = ev.model_dump_json()
        assert "topic_id" not in raw
        restored = TopicEvent.model_validate_json(raw)
        assert restored == ev

    def test_json_roundtrip_all_kinds(self) -> None:
        """Every topic_* kind round-trips through JSON losslessly."""
        events = [
            _event(),
            _event(
                kind=KIND_TOPIC_RENAMED,
                stream="my-topic",
                payload=TopicRenamedPayload(old_name="A", new_name="B"),
            ),
            _event(
                kind=KIND_TOPIC_MERGED,
                stream="b-topic",
                payload=TopicMergedPayload(source="a-topic", target="b-topic"),
            ),
            _event(
                kind=KIND_TOPIC_ARCHIVED,
                stream="my-topic",
                payload=TopicArchivedPayload(reason="done"),
            ),
            _event(
                kind=KIND_TOPIC_LINK,
                stream="my-topic",
                payload=TopicLinkPayload(topic="my-topic", event_ids=["e1"]),
            ),
            _event(
                kind=KIND_TOPIC_UNLINK,
                stream="my-topic",
                payload=TopicUnlinkPayload(topic="my-topic", event_ids=["e1"]),
            ),
            _event(
                kind=KIND_CHAT2_EVENT,
                stream="my-topic",
                payload=Chat2EventPayload(
                    role="user",
                    actor="junwin",
                    source_kind="user_message",
                    payload="hello",
                    metadata={"agent": "lucy"},
                    provenance=EventProvenance(
                        source=MIGRATION_SOURCE_CHAT2,
                        session_id="sess-1",
                        migrated_at=datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc),
                    ),
                ),
            ),
        ]
        for ev in events:
            restored = TopicEvent.model_validate_json(ev.model_dump_json())
            assert restored == ev
            assert type(restored.payload) is type(ev.payload)

    def test_unlink_roundtrip_not_misread_as_link(self) -> None:
        """Regression: link/unlink payloads are structurally ambiguous
        (unlink = link minus the optional reason); the envelope kind must
        disambiguate so topic_unlink survives a JSON round-trip."""
        ev = _event(
            kind=KIND_TOPIC_UNLINK,
            stream="my-topic",
            payload=TopicUnlinkPayload(topic="my-topic", event_ids=["e1"]),
        )
        restored = TopicEvent.model_validate_json(ev.model_dump_json())
        assert isinstance(restored.payload, TopicUnlinkPayload)
        assert not isinstance(restored.payload, TopicLinkPayload)

    def test_link_without_reason_roundtrips_as_link(self) -> None:
        ev = _event(
            kind=KIND_TOPIC_LINK,
            stream="my-topic",
            payload=TopicLinkPayload(topic="my-topic", event_ids=["e1"]),
        )
        restored = TopicEvent.model_validate_json(ev.model_dump_json())
        assert isinstance(restored.payload, TopicLinkPayload)

    def test_envelope_has_agent_metadata_field(self) -> None:
        assert "agent" in TopicEvent.model_fields


# ---------------------------------------------------------------------------
# Stream layout
# ---------------------------------------------------------------------------


class TestStreamLayout:
    def test_inbox_path(self) -> None:
        assert inbox_path("junwin") == "topics/junwin/inbox.jsonl"

    def test_topic_stream_path(self) -> None:
        assert stream_path("junwin", "my-topic") == "topics/junwin/my-topic.jsonl"

    def test_stream_path_rejects_leading_slash(self) -> None:
        with pytest.raises(ValueError):
            stream_path("junwin", "/etc/passwd")

    def test_stream_path_rejects_dotdot(self) -> None:
        with pytest.raises(ValueError):
            stream_path("junwin", "../evil")

    def test_stream_path_rejects_bad_account(self) -> None:
        with pytest.raises(ValueError):
            stream_path("", "inbox")
        with pytest.raises(ValueError):
            stream_path("../x", "inbox")
        with pytest.raises(ValueError):
            stream_path("a/b", "inbox")

    def test_stream_path_rejects_non_slug_stream(self) -> None:
        with pytest.raises(ValueError):
            stream_path("junwin", "my topic")

    def test_schema_version_bumped_to_2(self) -> None:
        assert EVENT_LOG_SCHEMA_VERSION == 2


class TestAgentIsNotAPartitionKey:
    """Decision 7: agent is metadata, never a partition key."""

    def test_stream_path_has_no_agent_parameter(self) -> None:
        sig = inspect.signature(stream_path)
        assert "agent" not in sig.parameters

    def test_two_agents_share_one_stream_file(self) -> None:
        path = stream_path("junwin", "shared-topic")
        ev_lucy = _event(agent="lucy", stream="shared-topic")
        ev_ziggy = _event(agent="ziggy", stream="shared-topic")
        # Same logical stream for both agents -> same file.
        assert stream_path("junwin", ev_lucy.stream) == path
        assert stream_path("junwin", ev_ziggy.stream) == path
        assert ev_lucy.agent != ev_ziggy.agent  # but metadata differs


class TestKindConstants:
    def test_all_kinds_defined(self) -> None:
        assert KIND_TOPIC_CREATED == "topic_created"
        assert KIND_TOPIC_RENAMED == "topic_renamed"
        assert KIND_TOPIC_MERGED == "topic_merged"
        assert KIND_TOPIC_ARCHIVED == "topic_archived"
        assert KIND_TOPIC_LINK == "topic_link"
        assert KIND_TOPIC_UNLINK == "topic_unlink"
        assert KIND_CHAT2_EVENT == "chat2_event"
        assert MIGRATION_SOURCE_CHAT2 == "chat2"


# ---------------------------------------------------------------------------
# Migration provenance marker (review gap #3, pinned 2026-09-01)
# ---------------------------------------------------------------------------


class TestMigrationProvenanceMarker:
    """The provenance envelope is defined in t-schemas so the migration
    smoke test (and the design's "provenance-marked events") has a pinned
    contract: source + legacy session_id (metadata only) + migrated_at."""

    def test_chat2_event_payload_requires_provenance(self) -> None:
        with pytest.raises(ValidationError):
            Chat2EventPayload(role="user", actor="junwin", source_kind="user_message")

    def test_provenance_fields(self) -> None:
        prov = EventProvenance(
            source=MIGRATION_SOURCE_CHAT2,
            session_id="sess-1",
            migrated_at=datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc),
        )
        assert prov.source == "chat2"
        assert prov.session_id == "sess-1"
        assert prov.migrated_at.tzinfo == timezone.utc

    def test_provenance_rejects_empty_source_or_session(self) -> None:
        with pytest.raises(ValidationError):
            EventProvenance(source="", session_id="sess-1")
        with pytest.raises(ValidationError):
            EventProvenance(source="chat2", session_id="")

    def test_chat2_event_payload_roundtrip(self) -> None:
        ev = _event(
            kind=KIND_CHAT2_EVENT,
            stream="my-topic",
            payload=Chat2EventPayload(
                role="assistant",
                actor="lucy",
                source_kind="assistant_message",
                payload={"text": "hi"},
                metadata={"agent": "lucy"},
                provenance=EventProvenance(
                    source=MIGRATION_SOURCE_CHAT2,
                    session_id="sess-1",
                    migrated_at=datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc),
                ),
            ),
        )
        restored = TopicEvent.model_validate_json(ev.model_dump_json())
        assert isinstance(restored.payload, Chat2EventPayload)
        assert restored.payload.provenance.session_id == "sess-1"
        assert restored.payload.payload == {"text": "hi"}

    def test_session_id_is_legacy_metadata_not_envelope_field(self) -> None:
        ev = _event(
            kind=KIND_CHAT2_EVENT,
            stream="my-topic",
            payload=Chat2EventPayload(
                provenance=EventProvenance(
                    source=MIGRATION_SOURCE_CHAT2, session_id="sess-1"
                ),
            ),
        )
        raw = ev.model_dump_json()
        assert '"session_id"' in raw  # inside payload.provenance
        assert '"topic_id"' not in raw  # decision 1

    def test_chat2_event_never_carries_topic_id(self) -> None:
        with pytest.raises(ValidationError):
            Chat2EventPayload(
                role="user",
                provenance=EventProvenance(
                    source=MIGRATION_SOURCE_CHAT2, session_id="sess-1"
                ),
                topic_id="my-topic",
            )
