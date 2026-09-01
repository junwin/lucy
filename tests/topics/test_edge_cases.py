"""
Edge-case coverage for the standalone topics component (issue #129).

Covers the review-required edge cases across the component:

- empty account        -> queries are empty; lazy creation works; accounts
                          are isolated from each other; empty account names
                          are rejected
- duplicate slugs      -> deterministic suffix progression (-2, -3, ...),
                          truncation at the 64-char limit, uniqueness scoped
                          per account
- merge chains         -> A -> B then B -> C: the chain collapses into C,
                          intermediate topics freeze, archived sources cannot
                          be merged again
- archive write rejection -> the frozen stream rejects writes at the store
                          level (StreamArchivedError) and the mutation level
                          (TopicArchivedError), including across fresh
                          store/index instances (state derived from the log)
- unicode/weird slug input -> normalization handles emoji, CJK, accents,
                          control chars, newlines, unicode dashes, long
                          proposals; proposals that normalize to nothing or
                          to an out-of-contract shape raise ValueError
- concurrent appends to one topic stream -> many threads appending through
                          separate store instances to a single stream leave a
                          valid, complete, parseable log (O_APPEND atomicity)

Plus the standalone guardrail (decision 4): **zero** FCP/agent imports in
``src/topics`` and ``tests/topics`` - the only allowed ``src.*`` dependency
is the ``src.storage.interfaces`` seam (``EventStore`` / ``TopicStore``).

Standalone (decision 4): no FCP/agent imports anywhere in this file.
"""

from __future__ import annotations

import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import pytest

from src.topics.mutation import TopicArchivedError
from src.topics.queries import TopicStoreImpl
from src.topics.schemas import (
    INBOX_STREAM,
    KIND_TOPIC_CREATED,
    KIND_TOPIC_LINK,
    TopicEvent,
    TopicLinkPayload,
)
from src.topics.streams import JsonlEventStore, StreamArchivedError

ACCOUNT = "junwin"
OTHER_ACCOUNT = "other"

T0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> JsonlEventStore:
    return JsonlEventStore(tmp_path)


@pytest.fixture
def impl(store: JsonlEventStore) -> TopicStoreImpl:
    return TopicStoreImpl(store)


def _link_event(
    slug: str,
    event_ids: List[str],
    *,
    event_id: str | None = None,
    agent: str = "lucy",
    ts: datetime | None = None,
) -> TopicEvent:
    """A resolvable member-able event for a topic stream (v1 stand-in)."""
    return TopicEvent(
        event_id=event_id if event_id is not None else f"{slug}-{event_ids[0]}",
        kind=KIND_TOPIC_LINK,
        agent=agent,
        account=ACCOUNT,
        stream=slug,
        ts=ts if ts is not None else T0,
        payload=TopicLinkPayload(topic=slug, event_ids=event_ids),
    )


def _raw_lines(store: JsonlEventStore, stream: str) -> List[str]:
    """Raw JSONL lines of a stream file (the bytes as appended)."""
    path = store._data_root / f"topics/{ACCOUNT}/{stream}.jsonl"
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _read_all(data_root: Path, account: str, stream: str) -> List[TopicEvent]:
    """Read every event in a stream through a *fresh* store instance."""
    fresh = JsonlEventStore(data_root)
    return list(fresh.stream_events(account, stream))


# ---------------------------------------------------------------------------
# Edge case 1: empty account
# ---------------------------------------------------------------------------


class TestEmptyAccount:
    def test_queries_on_never_used_account_are_empty(self, impl: TopicStoreImpl) -> None:
        assert impl.get_topic(ACCOUNT, "anything") is None
        assert impl.list_topics(ACCOUNT) == []
        assert impl.topics_by_kind(ACCOUNT, "explicit") == []
        assert impl.events_in_topic(ACCOUNT, "anything") == []
        assert impl.event_ids(ACCOUNT, "anything") == []
        assert impl.topic_ids(ACCOUNT) == []
        assert impl.is_archived(ACCOUNT, "anything") is False

    def test_create_works_on_fresh_account(self, impl: TopicStoreImpl) -> None:
        slug = impl.create_topic(ACCOUNT, "First", "first-topic", agent="lucy")
        assert slug == "first-topic"
        assert impl.get_topic(ACCOUNT, "first-topic") is not None
        assert impl.topic_ids(ACCOUNT) == ["first-topic"]

    def test_accounts_are_isolated(self, impl: TopicStoreImpl) -> None:
        impl.create_topic(ACCOUNT, "Mine", "mine", agent="lucy")
        impl.create_topic(OTHER_ACCOUNT, "Theirs", "theirs", agent="lucy")
        # No cross-account leakage in any query surface.
        assert impl.topic_ids(ACCOUNT) == ["mine"]
        assert impl.topic_ids(OTHER_ACCOUNT) == ["theirs"]
        assert impl.get_topic(ACCOUNT, "theirs") is None
        assert impl.get_topic(OTHER_ACCOUNT, "mine") is None
        assert impl.topics_by_kind(OTHER_ACCOUNT, "explicit")[0].topic_id == "theirs"

    def test_empty_account_name_rejected(self, impl: TopicStoreImpl) -> None:
        with pytest.raises(ValueError, match="account"):
            impl.create_topic("", "Bad", "bad", agent="lucy")

    def test_events_in_topic_on_empty_account(self, impl: TopicStoreImpl) -> None:
        # No index, no streams: the query is a clean empty result, not an error.
        assert impl.events_in_topic(ACCOUNT, "ghost", limit=5) == []


# ---------------------------------------------------------------------------
# Edge case 2: duplicate slugs
# ---------------------------------------------------------------------------


class TestDuplicateSlugs:
    def test_suffix_progression(self, impl: TopicStoreImpl) -> None:
        slugs = [
            impl.create_topic(ACCOUNT, f"Alpha {i}", "alpha", agent="lucy")
            for i in range(5)
        ]
        assert slugs == ["alpha", "alpha-2", "alpha-3", "alpha-4", "alpha-5"]

    def test_suffix_skips_free_slots(self, impl: TopicStoreImpl) -> None:
        impl.create_topic(ACCOUNT, "A", "topic", agent="lucy")
        impl.create_topic(ACCOUNT, "B", "topic", agent="lucy")  # topic-2
        impl.create_topic(ACCOUNT, "C", "topic", agent="lucy")  # topic-3
        # An archived topic still owns its slug (uniqueness includes archived).
        impl.archive_topic(ACCOUNT, "topic-2", agent="lucy")
        assert impl.create_topic(ACCOUNT, "D", "topic", agent="lucy") == "topic-4"

    def test_truncation_at_64_char_limit(self, impl: TopicStoreImpl) -> None:
        base = "a" * 63
        first = impl.create_topic(ACCOUNT, "Long 1", base, agent="lucy")
        assert first == base and len(first) == 63
        second = impl.create_topic(ACCOUNT, "Long 2", base, agent="lucy")
        assert second == "a" * 62 + "-2"  # 64 chars, suffix fits, contract holds
        assert len(second) == 64
        third = impl.create_topic(ACCOUNT, "Long 3", base, agent="lucy")
        assert third == "a" * 62 + "-3"

    def test_exactly_64_char_proposal_accepted(self, impl: TopicStoreImpl) -> None:
        proposal = "b" * 64
        assert impl.create_topic(ACCOUNT, "Max", proposal, agent="lucy") == proposal

    def test_uniqueness_is_per_account(self, impl: TopicStoreImpl) -> None:
        # The slug contract scopes uniqueness to the account: the same
        # proposal resolves to the same slug in two different accounts.
        assert impl.create_topic(ACCOUNT, "Notes", "notes", agent="lucy") == "notes"
        assert (
            impl.create_topic(OTHER_ACCOUNT, "Notes", "notes", agent="lucy")
            == "notes"
        )
        # And a collision inside one account still suffixes.
        assert impl.create_topic(ACCOUNT, "Notes 2", "notes", agent="lucy") == "notes-2"

    def test_rename_does_not_free_slug(self, impl: TopicStoreImpl) -> None:
        impl.create_topic(ACCOUNT, "Old Name", "fixed-slug", agent="lucy")
        impl.rename_topic(ACCOUNT, "fixed-slug", "New Name", agent="lucy")
        # Rename is label-only: the slug stays reserved, so a re-create with
        # the same proposal still suffixes (identity model, decision 8).
        assert impl.create_topic(ACCOUNT, "New Topic", "fixed-slug", agent="lucy") == (
            "fixed-slug-2"
        )


# ---------------------------------------------------------------------------
# Edge case 3: merge chains
# ---------------------------------------------------------------------------


class TestMergeChains:
    def test_two_hop_chain_collapses_into_target(self, impl: TopicStoreImpl) -> None:
        # A -> B, then B -> C: C ends up with everyone's ids.
        impl.create_topic(ACCOUNT, "Alpha", "alpha", agent="lucy")
        impl.create_topic(ACCOUNT, "Bravo", "bravo", agent="lucy")
        impl.create_topic(ACCOUNT, "Charlie", "charlie", agent="lucy")
        impl.link_events(ACCOUNT, "alpha", ["e1"], agent="lucy")
        impl.link_events(ACCOUNT, "bravo", ["e2"], agent="lucy")
        impl.link_events(ACCOUNT, "charlie", ["e3"], agent="lucy")

        impl.merge_topics(ACCOUNT, "alpha", "bravo", agent="lucy")
        impl.merge_topics(ACCOUNT, "bravo", "charlie", agent="lucy")

        target = impl.get_topic(ACCOUNT, "charlie")
        assert target is not None
        assert target.archived is False
        assert target.event_ids == ["e1", "e2", "e3"]  # chain collapsed into C

        # Both hops froze: alpha (archived by hop 1) and bravo (by hop 2).
        alpha = impl.get_topic(ACCOUNT, "alpha")
        bravo = impl.get_topic(ACCOUNT, "bravo")
        assert alpha is not None and alpha.archived is True
        assert bravo is not None and bravo.archived is True
        # Design: no unlink on merge - intermediate topics keep their derived
        # ids and stay queryable while archived (faithful replay).
        assert bravo.event_ids == ["e1", "e2"]
        assert impl.topic_ids(ACCOUNT) == ["charlie"]

    def test_merged_source_cannot_be_merged_again(self, impl: TopicStoreImpl) -> None:
        impl.create_topic(ACCOUNT, "Alpha", "alpha", agent="lucy")
        impl.create_topic(ACCOUNT, "Bravo", "bravo", agent="lucy")
        impl.create_topic(ACCOUNT, "Charlie", "charlie", agent="lucy")
        impl.merge_topics(ACCOUNT, "alpha", "bravo", agent="lucy")
        # alpha is archived by the merge; re-merging it raises.
        with pytest.raises(TopicArchivedError):
            impl.merge_topics(ACCOUNT, "alpha", "charlie", agent="lucy")

    def test_chain_into_archived_target_rejected(self, impl: TopicStoreImpl) -> None:
        impl.create_topic(ACCOUNT, "Alpha", "alpha", agent="lucy")
        impl.create_topic(ACCOUNT, "Bravo", "bravo", agent="lucy")
        impl.archive_topic(ACCOUNT, "bravo", agent="lucy")
        with pytest.raises(TopicArchivedError):
            impl.merge_topics(ACCOUNT, "alpha", "bravo", agent="lucy")

    def test_chain_via_log_replay(self, tmp_path: Path) -> None:
        # The chain must be derivable from the log alone: a fresh store +
        # index over the same data root sees the same collapsed state.
        impl1 = TopicStoreImpl(JsonlEventStore(tmp_path))
        impl1.create_topic(ACCOUNT, "Alpha", "alpha", agent="lucy")
        impl1.create_topic(ACCOUNT, "Bravo", "bravo", agent="lucy")
        impl1.create_topic(ACCOUNT, "Charlie", "charlie", agent="lucy")
        impl1.merge_topics(ACCOUNT, "alpha", "bravo", agent="lucy")
        impl1.merge_topics(ACCOUNT, "bravo", "charlie", agent="lucy")

        impl2 = TopicStoreImpl(JsonlEventStore(tmp_path))
        rec = impl2.get_topic(ACCOUNT, "charlie")
        assert rec is not None and rec.archived is False
        assert impl2.get_topic(ACCOUNT, "alpha").archived is True
        assert impl2.get_topic(ACCOUNT, "bravo").archived is True
        assert impl2.topic_ids(ACCOUNT) == ["charlie"]


# ---------------------------------------------------------------------------
# Edge case 4: archive write rejection
# ---------------------------------------------------------------------------


class TestArchiveWriteRejection:
    def test_store_rejects_direct_append_after_archive(
        self, store: JsonlEventStore, impl: TopicStoreImpl
    ) -> None:
        impl.create_topic(ACCOUNT, "Done", "done-topic", agent="lucy")
        impl.archive_topic(ACCOUNT, "done-topic", agent="lucy")
        with pytest.raises(StreamArchivedError):
            store.append_event(
                ACCOUNT, "done-topic", _link_event("done-topic", ["e9"])
            )

    def test_mutations_rejected_on_archived(self, impl: TopicStoreImpl) -> None:
        impl.create_topic(ACCOUNT, "Done", "done-topic", agent="lucy")
        impl.archive_topic(ACCOUNT, "done-topic", agent="lucy")
        with pytest.raises(TopicArchivedError):
            impl.link_events(ACCOUNT, "done-topic", ["e1"], agent="lucy")
        with pytest.raises(TopicArchivedError):
            impl.unlink_events(ACCOUNT, "done-topic", ["e1"], agent="lucy")
        with pytest.raises(TopicArchivedError):
            impl.rename_topic(ACCOUNT, "done-topic", "Renamed", agent="lucy")
        with pytest.raises(TopicArchivedError):
            impl.archive_topic(ACCOUNT, "done-topic", agent="lucy")

    def test_archived_state_derived_from_log_across_instances(
        self, tmp_path: Path
    ) -> None:
        # Archive state must survive a restart: a fresh store + index over
        # the same data root rejects writes without any shared memory.
        impl1 = TopicStoreImpl(JsonlEventStore(tmp_path))
        impl1.create_topic(ACCOUNT, "Done", "done-topic", agent="lucy")
        impl1.archive_topic(ACCOUNT, "done-topic", agent="lucy")

        store2 = JsonlEventStore(tmp_path)
        impl2 = TopicStoreImpl(store2)
        assert impl2.is_archived(ACCOUNT, "done-topic") is True
        with pytest.raises(TopicArchivedError):
            impl2.link_events(ACCOUNT, "done-topic", ["e1"], agent="lucy")
        with pytest.raises(StreamArchivedError):
            store2.append_event(
                ACCOUNT, "done-topic", _link_event("done-topic", ["e9"])
            )

    def test_archived_stream_still_readable(self, impl: TopicStoreImpl) -> None:
        # Archive = event + freeze (v1): the freeze blocks writes, never reads.
        impl.create_topic(ACCOUNT, "Done", "done-topic", agent="lucy")
        impl.archive_topic(ACCOUNT, "done-topic", agent="lucy")
        rec = impl.get_topic(ACCOUNT, "done-topic")
        assert rec is not None and rec.archived is True
        assert impl.events_in_topic(ACCOUNT, "done-topic") == []
        assert impl.topics_by_kind(ACCOUNT, "explicit", include_archived=True) == [
            rec
        ]


# ---------------------------------------------------------------------------
# Edge case 5: unicode / weird slug input
# ---------------------------------------------------------------------------


class TestUnicodeWeirdSlugs:
    def test_emoji_stripped(self, impl: TopicStoreImpl) -> None:
        assert impl.create_topic(ACCOUNT, "Party", "🎉 Party 🎉", agent="lucy") == "party"

    def test_cjk_stripped_to_empty_raises(self, impl: TopicStoreImpl) -> None:
        with pytest.raises(ValueError, match="slug"):
            impl.create_topic(ACCOUNT, "主题", "主题", agent="lucy")

    def test_accents_stripped(self, impl: TopicStoreImpl) -> None:
        # é is not [a-z0-9-]; normalization strips it -> "caf".
        assert impl.create_topic(ACCOUNT, "Café", "Café", agent="lucy") == "caf"

    def test_fullwidth_normalized(self, impl: TopicStoreImpl) -> None:
        # NFKC maps fullwidth ＮＯＴＥＳ -> NOTES -> notes.
        assert impl.create_topic(ACCOUNT, "Notes", "ＮＯＴＥＳ", agent="lucy") == "notes"

    def test_control_chars_and_newlines(self, impl: TopicStoreImpl) -> None:
        assert impl.create_topic(ACCOUNT, "T", "my\n\ttopic", agent="lucy") == "my-topic"
        with pytest.raises(ValueError, match="slug"):
            impl.create_topic(ACCOUNT, "Bad", "\x00\x01\x02", agent="lucy")

    def test_unicode_dash_removed(self, impl: TopicStoreImpl) -> None:
        # The em dash U+2014 is not the ASCII hyphen; it is stripped, and the
        # remaining letters collapse into one token.
        assert impl.create_topic(ACCOUNT, "T", "my—topic", agent="lucy") == "mytopic"

    def test_mixed_punctuation_and_spaces(self, impl: TopicStoreImpl) -> None:
        assert (
            impl.create_topic(ACCOUNT, "T", "  Hello, World!  ", agent="lucy")
            == "hello-world"
        )
        assert impl.create_topic(ACCOUNT, "T", "a--b", agent="lucy") == "a-b"
        assert impl.create_topic(ACCOUNT, "T", "-abc-", agent="lucy") == "abc"

    def test_overlong_proposal_raises(self, impl: TopicStoreImpl) -> None:
        with pytest.raises(ValueError, match="slug"):
            impl.create_topic(ACCOUNT, "Too long", "x" * 200, agent="lucy")

    def test_name_may_be_long_but_proposal_validated(self, impl: TopicStoreImpl) -> None:
        # The mutable label has no length ceiling; only the slug proposal is
        # governed by the contract.
        long_name = "n" * 500
        assert impl.create_topic(ACCOUNT, long_name, "short-slug", agent="lucy") == (
            "short-slug"
        )

    def test_weird_proposal_never_creates_a_stream(self, impl: TopicStoreImpl) -> None:
        # A rejected proposal must not leave any side effects behind.
        with pytest.raises(ValueError):
            impl.create_topic(ACCOUNT, "Bad", "!!!", agent="lucy")
        assert impl.list_topics(ACCOUNT) == []
        assert impl.topic_ids(ACCOUNT) == []


# ---------------------------------------------------------------------------
# Edge case 6: concurrent appends to one topic stream
# ---------------------------------------------------------------------------


class TestConcurrentAppends:
    def test_many_threads_one_topic_stream(self, tmp_path: Path) -> None:
        """Concurrent appends through separate store instances stay intact.

        Each thread opens its own ``JsonlEventStore`` over the same data
        root and appends to the same topic stream. The log must come out
        complete (no lost writes) and parseable line-by-line (no interleaved
        or partial lines) - the O_APPEND guarantee the stream store relies on.
        """
        n_threads, per_thread = 8, 25
        # Create the topic stream up front (single writer), then race appends.
        setup = TopicStoreImpl(JsonlEventStore(tmp_path))
        setup.create_topic(ACCOUNT, "Hot", "hot-stream", agent="lucy")

        def worker(t: int) -> List[str]:
            local = JsonlEventStore(tmp_path)
            ids = []
            for i in range(per_thread):
                eid = f"t{t}-e{i:02d}"
                local.append_event(
                    ACCOUNT,
                    "hot-stream",
                    _link_event("hot-stream", [eid], event_id=eid, agent=f"a{t}"),
                )
                ids.append(eid)
            return ids

        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            per_worker = list(pool.map(worker, range(n_threads)))

        expected = {eid for ids in per_worker for eid in ids}
        assert len(expected) == n_threads * per_thread  # ids are unique

        # Fresh store: every line parses, every id present exactly once.
        # The stream also holds the setup's topic_created lifecycle event.
        events = _read_all(tmp_path, ACCOUNT, "hot-stream")
        kinds = [e.kind for e in events]
        assert kinds.count(KIND_TOPIC_CREATED) == 1
        assert kinds.count(KIND_TOPIC_LINK) == n_threads * per_thread
        assert len(events) == n_threads * per_thread + 1
        assert {e.event_id for e in events if e.kind == KIND_TOPIC_LINK} == expected
        assert len({e.event_id for e in events}) == len(events)  # no dupes
        # JSONL integrity: no blank/partial lines.
        for line in _raw_lines(JsonlEventStore(tmp_path), "hot-stream"):
            assert line.strip()

        # The derived index over the raced log sees every member (lifecycle
        # events are never members, decision 1).
        fresh = TopicStoreImpl(JsonlEventStore(tmp_path))
        rec = fresh.get_topic(ACCOUNT, "hot-stream")
        assert rec is not None
        assert set(rec.event_ids) == expected
        assert len(fresh.events_in_topic(ACCOUNT, "hot-stream")) == n_threads * per_thread

    def test_many_threads_inbox_first_write(self, tmp_path: Path) -> None:
        """The inbox's create-on-first-write path is also race-safe.

        Every thread appends to the inbox through its own store instance;
        the inbox file comes into existence during the race. The result must
        still be a complete, parseable log.
        """
        n_threads, per_thread = 8, 10
        barrier = threading.Barrier(n_threads)

        def worker(t: int) -> List[str]:
            local = JsonlEventStore(tmp_path)
            barrier.wait()  # maximize contention on the create-on-write path
            ids = []
            for i in range(per_thread):
                eid = f"in{t}-e{i:02d}"
                local.append_event(
                    ACCOUNT,
                    INBOX_STREAM,
                    TopicEvent(
                        event_id=eid,
                        kind=KIND_TOPIC_LINK,
                        agent=f"a{t}",
                        account=ACCOUNT,
                        stream=INBOX_STREAM,
                        ts=T0,
                        payload=TopicLinkPayload(
                            topic=INBOX_STREAM, event_ids=[f"{eid}-ref"]
                        ),
                    ),
                )
                ids.append(eid)
            return ids

        errors: List[BaseException] = []

        def guarded(t: int) -> List[str]:
            try:
                return worker(t)
            except BaseException as exc:  # pragma: no cover - failure path
                errors.append(exc)
                return []

        threads = [
            threading.Thread(target=lambda t=t: guarded(t)) for t in range(n_threads)
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert not errors, f"concurrent inbox appends raised: {errors}"

        events = _read_all(tmp_path, ACCOUNT, INBOX_STREAM)
        expected = n_threads * per_thread
        assert len(events) == expected
        assert len({e.event_id for e in events}) == expected  # unique, complete

    def test_concurrent_appends_never_touch_other_streams(
        self, tmp_path: Path
    ) -> None:
        # Racing appends to one topic stream must not disturb the inbox or
        # another topic's stream (account/topic scoping holds under load).
        setup = TopicStoreImpl(JsonlEventStore(tmp_path))
        setup.create_topic(ACCOUNT, "Quiet", "quiet-stream", agent="lucy")
        setup.create_topic(ACCOUNT, "Hot", "hot-stream", agent="lucy")

        def worker(t: int) -> None:
            local = JsonlEventStore(tmp_path)
            for i in range(10):
                eid = f"h{t}-e{i}"
                local.append_event(
                    ACCOUNT,
                    "hot-stream",
                    _link_event("hot-stream", [eid], event_id=eid, agent="lucy"),
                )

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(worker, range(8)))

        quiet = _read_all(tmp_path, ACCOUNT, "quiet-stream")
        assert [e.kind for e in quiet] == ["topic_created"]  # untouched
        assert _read_all(tmp_path, ACCOUNT, INBOX_STREAM) == []  # untouched


# ---------------------------------------------------------------------------
# Guardrail (decision 4): zero FCP/agent imports in src/topics + tests/topics
# ---------------------------------------------------------------------------


class TestStandaloneGuardrail:
    #: The only ``src.*`` module the standalone component may import: the
    #: storage seam (EventStore / TopicStore ABCs) plus itself.
    _ALLOWED_SRC_PREFIXES = ("src.topics", "src.storage.interfaces")
    #: FCP/agent surface that must never appear (decision 4).
    _FORBIDDEN = (
        "src.agent",
        "src.agent_manager",
        "src.message_processors",
        "src.handlers",
        "src.http_endpoints",
        "src.message_endpoints",
        "src.prompt_builders",
        "src.tool_selection",
        "src.curation",
        "src.embeddings",
        "src.metrics",
        "src.injector",
        "src.request_context",
        "src.chat2",
        "src.config_manager",
        "src.container_config",
        "src.api_key",
        "src.keywords",
        "src.utils",
    )

    @staticmethod
    def _imported_src_modules(path: Path) -> List[str]:
        """Return the ``src.*`` module names imported by a file (static scan)."""
        found: List[str] = []
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("from src."):
                found.append(line.split()[1])
            elif line.startswith("import src."):
                found.append(line.split()[1])
        return found

    def test_no_fcp_or_agent_imports_in_src_topics(self) -> None:
        src_dir = Path(__file__).resolve().parents[2] / "src" / "topics"
        offenders = []
        for path in sorted(src_dir.glob("*.py")):
            for module in self._imported_src_modules(path):
                if not module.startswith(self._ALLOWED_SRC_PREFIXES):
                    offenders.append(f"{path.name}: {module}")
        assert not offenders, f"src/topics imports outside the seam: {offenders}"

    def test_no_fcp_or_agent_imports_in_tests_topics(self) -> None:
        tests_dir = Path(__file__).resolve().parent
        offenders = []
        for path in sorted(tests_dir.glob("*.py")):
            for module in self._imported_src_modules(path):
                if not module.startswith(self._ALLOWED_SRC_PREFIXES):
                    offenders.append(f"{path.name}: {module}")
        assert not offenders, f"tests/topics imports outside the seam: {offenders}"

    def test_forbidden_modules_never_imported(self) -> None:
        """The forbidden surface is explicit and enforced by name."""
        dirs = [
            Path(__file__).resolve().parents[2] / "src" / "topics",
            Path(__file__).resolve().parent,
        ]
        for d in dirs:
            for path in sorted(d.glob("*.py")):
                for module in self._imported_src_modules(path):
                    for forbidden in self._FORBIDDEN:
                        assert not module.startswith(forbidden), (
                            f"{path.name} imports forbidden FCP/agent module "
                            f"{module!r} (decision 4)"
                        )

    def test_component_imports_only_schemas_from_package_root(self) -> None:
        """The package root re-exports schemas only (documented cycle rule)."""
        init_text = (
            Path(__file__).resolve().parents[2] / "src" / "topics" / "__init__.py"
        ).read_text(encoding="utf-8")
        # Every `from .` / `from src.topics` import in __init__ is schemas.
        for line in init_text.splitlines():
            line = line.strip()
            if line.startswith("from .") or line.startswith("from src.topics"):
                imported = line.split()[1]
                assert imported.endswith("schemas") or imported == "src.topics.schemas", (
                    f"__init__ re-exports non-schemas module: {imported}"
                )

    def test_no_dynamic_fcp_imports(self) -> None:
        """No importlib/lazy imports of the FCP surface either.

        Only actual import statements are scanned (docstrings/comments may
        mention the machinery without importing anything).
        """
        dirs = [
            Path(__file__).resolve().parents[2] / "src" / "topics",
            Path(__file__).resolve().parent,
        ]
        for d in dirs:
            for path in sorted(d.glob("*.py")):
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not (line.startswith("import ") or line.startswith("from ")):
                        continue
                    assert "importlib" not in line and "__import__" not in line, (
                        f"{path.name} uses dynamic imports: {line}"
                    )
