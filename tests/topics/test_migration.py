"""
Migration smoke test (issue #129, task t-migration).

Covers the t-migration DoD:
- every chat2 session yields exactly one topic_created + topic stream +
  provenance-marked events + topic_link events
- re-running migration skips already-migrated sessions (idempotent)
- old digests and embeddings unchanged
- pytest tests/topics/test_migration.py -q green

Also covers: slug-from-session-name per the slug contract (deterministic
suffix on collision), session_id as legacy metadata only (decision 1),
agent as metadata (decision 7), and the query-side integration
(events_in_topic over migrated events, newest first by original ts).

Standalone (decision 4): no FCP/agent imports anywhere in this file.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from src.topics.migration import (
    Chat2ReadError,
    MigrationReport,
    TopicMigrator,
    scan_chat2_sessions,
)
from src.topics.queries import TopicStoreImpl
from src.topics.schemas import (
    KIND_CHAT2_EVENT,
    KIND_TOPIC_CREATED,
    KIND_TOPIC_LINK,
    MIGRATION_SOURCE_CHAT2,
    TopicEvent,
    stream_path,
)
from src.topics.streams import JsonlEventStore

ACCOUNT = "junwin"
OTHER_ACCOUNT = "ziggy"

T0 = datetime(2026, 8, 31, 3, 20, 10, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> JsonlEventStore:
    return JsonlEventStore(tmp_path)


@pytest.fixture
def migrator(store: JsonlEventStore) -> TopicMigrator:
    return TopicMigrator(store)


def _chat2_event(
    event_id: str,
    *,
    ts: datetime,
    role: str = "user",
    actor: str = "junwin",
    kind: str = "user_message",
    payload: Any = "hello",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "ts": ts.isoformat(),
        "role": role,
        "actor": actor,
        "kind": kind,
        "payload": payload,
        "metadata": metadata or {},
    }


def _write_session(
    chat2_root: Path,
    session_id: str,
    *,
    account: str = ACCOUNT,
    friendly_name: Optional[str] = None,
    events: Optional[List[Dict[str, Any]]] = None,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Path:
    """Write a legacy chat2 session (meta.json + events.jsonl)."""
    session_dir = chat2_root / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "session_id": session_id,
        "user_id": account,
        "account_name": account,
        "agent_name": "lucy",
        "participants": [],
        "session_type": "user",
        "friendly_name": friendly_name,
        "context_name": None,
        "created_at": "2026-08-31T03:17:14.173919",
        "updated_at": "2026-08-31T03:57:32.617550",
        "tags": [],
        "links": None,
        "metadata": {},
    }
    if extra_meta:
        meta.update(extra_meta)
    (session_dir / "meta.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    if events is not None:
        lines = [json.dumps(ev) for ev in events]
        (session_dir / "events.jsonl").write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )
    return session_dir


def _two_sessions(chat2_root: Path) -> Dict[str, str]:
    """Two sessions (dreams, lucid) with 3 events each; returns id->slug."""
    s1 = "da58d2ea-0bd9-44d6-b1c4-08003a058d23"
    s2 = "aa583815-4256-41aa-9269-9ce03a15a38a"
    _write_session(
        chat2_root,
        s1,
        friendly_name="Dreams",
        events=[
            _chat2_event("e1-1", ts=T0, role="system", actor="lucy", kind="prompt_report", payload={"total": 100}),
            _chat2_event("e1-2", ts=T0 + timedelta(minutes=1), role="user", actor="junwin", kind="user_message", payload="a dream"),
            _chat2_event("e1-3", ts=T0 + timedelta(minutes=2), role="assistant", actor="lucy", kind="assistant_message", payload="nice poem"),
        ],
    )
    _write_session(
        chat2_root,
        s2,
        friendly_name="Lucid",
        events=[
            _chat2_event("e2-1", ts=T0, role="user", actor="junwin", kind="user_message", payload="lucid?"),
            _chat2_event("e2-2", ts=T0 + timedelta(minutes=1), role="assistant", actor="lucy", kind="assistant_message", payload="yes"),
            _chat2_event("e2-3", ts=T0 + timedelta(minutes=2), role="user", actor="junwin", kind="user_message", payload="thanks"),
        ],
    )
    return {s1: "dreams", s2: "lucid"}


def _stream_lines(store: JsonlEventStore, stream: str) -> List[str]:
    path = store._data_root / stream_path(ACCOUNT, stream)
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def _stream_kinds(store: JsonlEventStore, stream: str) -> List[str]:
    return [TopicEvent.model_validate_json(line).kind for line in _stream_lines(store, stream)]


def _stream_events(store: JsonlEventStore, stream: str) -> List[TopicEvent]:
    return [TopicEvent.model_validate_json(line) for line in _stream_lines(store, stream)]


# ---------------------------------------------------------------------------
# DoD 1: every session -> one topic_created + stream + marked events + link
# ---------------------------------------------------------------------------


class TestEverySessionMigrates:
    def test_one_topic_per_session(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        id_to_slug = _two_sessions(tmp_path / "chat2")
        report = migrator.migrate(tmp_path / "chat2", ACCOUNT)

        assert sorted(report.migrated) == sorted(id_to_slug)
        assert report.errors == []
        assert report.ok

        for session_id, slug in id_to_slug.items():
            assert store.stream_exists(ACCOUNT, slug), slug
            kinds = _stream_kinds(store, slug)
            assert kinds[0] == KIND_TOPIC_CREATED  # exactly one, first
            assert kinds.count(KIND_TOPIC_CREATED) == 1
            assert kinds.count(KIND_CHAT2_EVENT) == 3
            assert kinds.count(KIND_TOPIC_LINK) == 1
            assert kinds[-1] == KIND_TOPIC_LINK  # link appended last

    def test_topic_created_uses_session_name(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        created = _stream_events(store, "dreams")[0]
        assert created.payload.name == "Dreams"
        assert created.payload.slug == "dreams"

    def test_link_carries_all_original_event_ids(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        link = _stream_events(store, "dreams")[-1]
        assert link.kind == KIND_TOPIC_LINK
        assert link.payload.topic == "dreams"
        assert link.payload.event_ids == ["e1-1", "e1-2", "e1-3"]
        assert link.payload.reason == "migration"

    def test_exactly_one_topic_created_across_all_streams(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        total = sum(
            kinds.count(KIND_TOPIC_CREATED)
            for kinds in (_stream_kinds(store, s) for s in store.list_streams(ACCOUNT))
        )
        assert total == 2  # one per session, no more


# ---------------------------------------------------------------------------
# DoD 1 (continued): provenance markers on every copied event
# ---------------------------------------------------------------------------


class TestProvenanceMarkers:
    def test_every_copied_event_carries_provenance(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        for event in _stream_events(store, "dreams"):
            if event.kind != KIND_CHAT2_EVENT:
                continue
            prov = event.payload.provenance
            assert prov.source == MIGRATION_SOURCE_CHAT2
            assert prov.session_id == "da58d2ea-0bd9-44d6-b1c4-08003a058d23"
            assert prov.migrated_at is not None

    def test_original_envelope_preserved_in_payload(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        copied = [e for e in _stream_events(store, "dreams") if e.kind == KIND_CHAT2_EVENT]
        by_id = {e.event_id: e for e in copied}
        assert by_id["e1-1"].payload.role == "system"
        assert by_id["e1-1"].payload.actor == "lucy"
        assert by_id["e1-1"].payload.source_kind == "prompt_report"
        assert by_id["e1-1"].payload.payload == {"total": 100}
        assert by_id["e1-2"].payload.payload == "a dream"
        assert by_id["e1-3"].payload.role == "assistant"
        assert by_id["e1-3"].payload.actor == "lucy"

    def test_original_ts_and_event_id_preserved_on_envelope(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        copied = [e for e in _stream_events(store, "dreams") if e.kind == KIND_CHAT2_EVENT]
        assert [e.event_id for e in copied] == ["e1-1", "e1-2", "e1-3"]
        assert [e.ts for e in copied] == [
            T0,
            T0 + timedelta(minutes=1),
            T0 + timedelta(minutes=2),
        ]
        assert all(e.account == ACCOUNT for e in copied)
        assert all(e.stream == "dreams" for e in copied)
        assert all(e.agent == "migration" for e in copied)  # the writer (metadata)

    def test_empty_session_yields_topic_created_only(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        sid = "00000000-0000-4000-8000-000000000001"
        _write_session(tmp_path / "chat2", sid, friendly_name="Empty")
        report = migrator.migrate(tmp_path / "chat2", ACCOUNT)
        assert report.migrated == [sid]
        kinds = _stream_kinds(store, "empty")
        # No link event: the schema requires topic_link to carry >= 1 id and
        # there is nothing to link for an empty session.
        assert kinds == [KIND_TOPIC_CREATED]
        assert store.stream_exists(ACCOUNT, "empty")


# ---------------------------------------------------------------------------
# DoD 2: idempotent re-run skips already-migrated sessions
# ---------------------------------------------------------------------------


class TestIdempotent:
    def _snapshot(self, store: JsonlEventStore) -> Dict[str, bytes]:
        return {
            stream: (store._data_root / stream_path(ACCOUNT, stream)).read_bytes()
            for stream in store.list_streams(ACCOUNT)
        }

    def test_rerun_skips_already_migrated(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        id_to_slug = _two_sessions(tmp_path / "chat2")
        first = migrator.migrate(tmp_path / "chat2", ACCOUNT)
        assert sorted(first.migrated) == sorted(id_to_slug)
        snapshot = self._snapshot(store)

        second = migrator.migrate(tmp_path / "chat2", ACCOUNT)
        assert second.migrated == []
        assert sorted(second.skipped) == sorted(id_to_slug)
        assert second.ok
        assert self._snapshot(store) == snapshot  # log byte-identical

    def test_rerun_after_new_session_migrates_only_the_new_one(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        id_to_slug = _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        snapshot = self._snapshot(store)

        s3 = "f03bf5a7-addf-4cb5-a7fd-3a8b6480e209"
        _write_session(
            tmp_path / "chat2",
            s3,
            friendly_name="New Session",
            events=[_chat2_event("e3-1", ts=T0)],
        )
        report = migrator.migrate(tmp_path / "chat2", ACCOUNT)
        assert report.migrated == [s3]
        assert sorted(report.skipped) == sorted(id_to_slug)
        # The two original streams are untouched; only the new topic exists.
        for slug in id_to_slug.values():
            assert self._snapshot(store)[slug] == snapshot[slug]
        assert store.stream_exists(ACCOUNT, "new-session")

    def test_fresh_migrator_instance_sees_existing_markers(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        # A brand-new migrator over the same store must skip everything too:
        # idempotency is derived from the log, not from instance memory.
        fresh = TopicMigrator(store)
        report = fresh.migrate(tmp_path / "chat2", ACCOUNT)
        assert report.migrated == []
        assert len(report.skipped) == 2


# ---------------------------------------------------------------------------
# DoD 3: old digests and embeddings unchanged
# ---------------------------------------------------------------------------


class TestDigestsAndEmbeddingsUntouched:
    def test_digest_and_embedding_files_unchanged(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        # Pre-existing digest + embedding files under the same data root
        # (the migration must never write outside topics/<account>/).
        digest = tmp_path / "digests" / ACCOUNT / "d1.json"
        digest.parent.mkdir(parents=True)
        digest.write_text('{"digest_id": "d1"}', encoding="utf-8")
        embedding = tmp_path / "embeddings" / ACCOUNT / "vol_1" / "v1.json"
        embedding.parent.mkdir(parents=True)
        embedding.write_text('{"vector": [1, 2, 3]}', encoding="utf-8")
        before = {
            "digest": digest.read_bytes(),
            "embedding": embedding.read_bytes(),
        }

        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)

        assert digest.read_bytes() == before["digest"]
        assert embedding.read_bytes() == before["embedding"]
        # No new files appeared under digests/ or embeddings/.
        assert sorted(p.name for p in (tmp_path / "digests" / ACCOUNT).iterdir()) == ["d1.json"]
        assert sorted(p.name for p in (tmp_path / "embeddings" / ACCOUNT / "vol_1").iterdir()) == [
            "v1.json"
        ]

    def test_only_topics_dir_created(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        # Only the topics/ dir was created by migration (plus the chat2 root
        # the test itself put in tmp_path).
        assert sorted(p.name for p in tmp_path.iterdir()) == ["chat2", "topics"]


# ---------------------------------------------------------------------------
# Slugs: session name -> slug contract (decision 8, deterministic)
# ---------------------------------------------------------------------------


class TestSlugFromSessionName:
    def test_slug_from_friendly_name(self, tmp_path: Path, migrator: TopicMigrator) -> None:
        _write_session(
            tmp_path / "chat2",
            "10000000-0000-4000-8000-000000000001",
            friendly_name="My Dream Journal",
            events=[_chat2_event("e1", ts=T0)],
        )
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        store = migrator._store
        assert store.stream_exists(ACCOUNT, "my-dream-journal")

    def test_colliding_names_get_deterministic_suffixes(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        s1 = "20000000-0000-4000-8000-000000000001"
        s2 = "20000000-0000-4000-8000-000000000002"
        _write_session(tmp_path / "chat2", s1, friendly_name="Dreams", events=[_chat2_event("e1", ts=T0)])
        _write_session(tmp_path / "chat2", s2, friendly_name="Dreams", events=[_chat2_event("e2", ts=T0)])
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        # Processed in session_id order: s1 -> dreams, s2 -> dreams-2.
        assert store.stream_exists(ACCOUNT, "dreams")
        assert store.stream_exists(ACCOUNT, "dreams-2")
        assert _stream_events(store, "dreams")[0].payload.name == "Dreams"
        assert _stream_events(store, "dreams-2")[0].payload.name == "Dreams"

    def test_name_falls_back_to_session_id(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        sid = "30000000-0000-4000-8000-000000000001"
        _write_session(tmp_path / "chat2", sid, friendly_name="", events=[_chat2_event("e1", ts=T0)])
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        assert store.stream_exists(ACCOUNT, sid)  # uuid is a valid slug
        created = _stream_events(store, sid)[0]
        assert created.payload.name == sid


# ---------------------------------------------------------------------------
# Reading edge cases
# ---------------------------------------------------------------------------


class TestReading:
    def test_account_filtering(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _write_session(tmp_path / "chat2", "a-1", friendly_name="Mine", events=[_chat2_event("e1", ts=T0)])
        _write_session(
            tmp_path / "chat2",
            "a-2",
            account=OTHER_ACCOUNT,
            friendly_name="Theirs",
            events=[_chat2_event("e2", ts=T0)],
        )
        report = migrator.migrate(tmp_path / "chat2", ACCOUNT)
        assert report.migrated == ["a-1"]
        assert report.other_account == 1
        assert store.stream_exists(ACCOUNT, "mine")
        assert not store.stream_exists(ACCOUNT, "theirs")

    def test_missing_meta_counts_as_unreadable(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        (tmp_path / "chat2" / "sessions" / "orphan").mkdir(parents=True)
        report = migrator.migrate(tmp_path / "chat2", ACCOUNT)
        assert report.migrated == []
        assert report.unreadable == 1
        assert store.list_streams(ACCOUNT) == []

    def test_corrupt_events_raise_before_any_write(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        session_dir = _write_session(
            tmp_path / "chat2",
            "b-1",
            friendly_name="Broken",
            events=[_chat2_event("e1", ts=T0)],
        )
        # Corrupt the events file after writing the valid session.
        (session_dir / "events.jsonl").write_text("{not json}\n", encoding="utf-8")
        with pytest.raises(Chat2ReadError, match="Broken|b-1"):
            migrator.migrate(tmp_path / "chat2", ACCOUNT)
        # Fail-fast at the read stage: the log is untouched.
        assert store.list_streams(ACCOUNT) == []

    def test_scan_returns_sorted_sessions(
        self, tmp_path: Path
    ) -> None:
        s2 = "50000000-0000-4000-8000-000000000002"
        s1 = "50000000-0000-4000-8000-000000000001"
        _write_session(tmp_path / "chat2", s2, friendly_name="B", events=[])
        _write_session(tmp_path / "chat2", s1, friendly_name="A", events=[])
        scan = scan_chat2_sessions(tmp_path / "chat2", account=ACCOUNT)
        assert [s.session_id for s in scan.sessions] == [s1, s2]


# ---------------------------------------------------------------------------
# Query-side integration: migrated events are real members, newest first
# ---------------------------------------------------------------------------


class TestQueryIntegration:
    def test_events_in_topic_newest_first(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        impl = TopicStoreImpl(store)
        events = impl.events_in_topic(ACCOUNT, "dreams")
        # Newest first by original ts (preserved on the envelope).
        assert [e.event_id for e in events] == ["e1-3", "e1-2", "e1-1"]
        assert all(e.kind == KIND_CHAT2_EVENT for e in events)
        # Limit + event-date filter work over migrated events (decision 5).
        assert [e.event_id for e in impl.events_in_topic(ACCOUNT, "dreams", limit=2)] == [
            "e1-3",
            "e1-2",
        ]
        filtered = impl.events_in_topic(
            ACCOUNT,
            "dreams",
            start_ts=T0 + timedelta(minutes=1),
            end_ts=T0 + timedelta(minutes=1),
        )
        assert [e.event_id for e in filtered] == ["e1-2"]

    def test_index_derives_membership(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        impl = TopicStoreImpl(store)
        rec = impl.get_topic(ACCOUNT, "dreams")
        assert rec is not None
        assert rec.name == "Dreams"
        assert rec.event_ids == ["e1-1", "e1-2", "e1-3"]  # derived (decision 1)
        assert rec.archived is False


# ---------------------------------------------------------------------------
# Guardrails (decisions 1, 7, 9)
# ---------------------------------------------------------------------------


class TestGuardrails:
    def test_events_never_carry_topic_id(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        for stream in store.list_streams(ACCOUNT):
            for line in _stream_lines(store, stream):
                assert '"topic_id"' not in line  # decision 1

    def test_session_id_only_as_legacy_metadata(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        for line in _stream_lines(store, "dreams"):
            top = json.loads(line)
            # Not on the envelope; only inside payload.provenance.
            assert "session_id" not in top
            if top["kind"] == KIND_CHAT2_EVENT:
                prov = top["payload"]["provenance"]
                assert prov["session_id"] == "da58d2ea-0bd9-44d6-b1c4-08003a058d23"
            else:
                # Lifecycle/link events carry no provenance (they are not copies).
                assert "provenance" not in top["payload"]

    def test_agent_is_metadata_not_partition_key(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        # Every appended event names the migration as the writer; the
        # original producers live in the payloads (role/actor).
        for event in _stream_events(store, "dreams"):
            assert event.agent == "migration"
        copied = [e for e in _stream_events(store, "dreams") if e.kind == KIND_CHAT2_EVENT]
        assert {e.payload.actor for e in copied} == {"junwin", "lucy"}

    def test_no_project_context_or_external_refs(
        self, tmp_path: Path, store: JsonlEventStore, migrator: TopicMigrator
    ) -> None:
        _two_sessions(tmp_path / "chat2")
        migrator.migrate(tmp_path / "chat2", ACCOUNT)
        for stream in store.list_streams(ACCOUNT):
            for line in _stream_lines(store, stream):
                assert "project_context" not in line  # decision 9
                assert "external_refs" not in line  # decision 9


# ---------------------------------------------------------------------------
# Seam
# ---------------------------------------------------------------------------


class TestReport:
    def test_report_shape(self) -> None:
        report = MigrationReport()
        assert report.migrated == []
        assert report.skipped == []
        assert report.other_account == 0
        assert report.unreadable == 0
        assert report.errors == []
        assert report.ok is True
