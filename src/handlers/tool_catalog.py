"""Provider-neutral catalog metadata for Lucy tool discovery.

The catalog deliberately sits above HandlerRegistry. Existing handler execution,
agent allowlists, and context filtering remain authoritative; the catalog adds
source identity and compact discovery metadata without placing those fields in
OpenAI tool definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class ToolDescriptor:
    """Compact, provider-neutral description of one registered tool."""

    id: str
    name: str
    description: str
    source: str
    groups: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()

    @classmethod
    def from_tool_def(
        cls,
        tool_def: Mapping[str, Any],
        *,
        source: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> "ToolDescriptor":
        metadata = metadata or {}
        name = str(tool_def.get("name") or "").strip()
        if not name:
            raise ValueError("tool definition has no name")

        groups = metadata.get("groups")
        if groups is None and metadata.get("group"):
            groups = [metadata["group"]]

        return cls(
            id=f"{source}:{name}",
            name=name,
            description=str(tool_def.get("description") or ""),
            source=source,
            groups=_normalise_terms(groups),
            tags=_normalise_terms(metadata.get("tags")),
            aliases=_normalise_terms(metadata.get("aliases")),
            capabilities=_normalise_terms(metadata.get("capabilities")),
        )


@dataclass(frozen=True)
class ToolMatch:
    """A ranked descriptor plus transparent scoring evidence."""

    descriptor: ToolDescriptor
    score: int
    matched_on: tuple[str, ...]


class ToolProvider(Protocol):
    """A source that can describe tools and create their handlers."""

    source: str

    def descriptors(self) -> Sequence[ToolDescriptor]: ...

    def definition(self, tool_name: str) -> Mapping[str, Any] | None: ...

    def create(self, tool_name: str, **kwargs: Any) -> Any: ...


@dataclass
class RegistryToolProvider:
    """Expose all or a named subset of a HandlerRegistry as one tool source."""

    registry: Any
    source: str
    tool_names: frozenset[str] | None = None
    metadata: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def descriptors(self) -> list[ToolDescriptor]:
        descriptors: list[ToolDescriptor] = []
        for tool_def in self.registry.tools():
            name = str(tool_def.get("name") or "")
            if self.tool_names is not None and name not in self.tool_names:
                continue
            descriptors.append(
                ToolDescriptor.from_tool_def(
                    tool_def,
                    source=self.source,
                    metadata=self.metadata.get(name),
                )
            )
        return descriptors

    def definition(self, tool_name: str) -> Mapping[str, Any] | None:
        if self.tool_names is not None and tool_name not in self.tool_names:
            return None
        return next(
            (
                tool_def
                for tool_def in self.registry.tools()
                if tool_def.get("name") == tool_name
            ),
            None,
        )

    def create(self, tool_name: str, **kwargs: Any) -> Any:
        if self.tool_names is not None and tool_name not in self.tool_names:
            raise KeyError(f"{tool_name!r} is not provided by {self.source!r}")
        return self.registry.create(tool_name, **kwargs)


class ToolCatalog:
    """Aggregate descriptors from multiple local or remote providers.

    When multiple providers expose the same unqualified tool name the catalog
    prefers Lucy-owned implementations to avoid ambiguity when users or tests
    refer to tools by name only. The precedence is deterministic so tests can
    rely on the chosen provider.
    """

    def __init__(self, providers: Iterable[ToolProvider] = ()) -> None:
        self._providers: dict[str, ToolProvider] = {}
        for provider in providers:
            self.add_provider(provider)

    def add_provider(self, provider: ToolProvider) -> None:
        if provider.source in self._providers:
            raise ValueError(f"duplicate tool provider source: {provider.source}")
        self._providers[provider.source] = provider

    def _ordered_providers(self) -> list[ToolProvider]:
        # Deterministic precedence: Lucy first (if present), then remaining
        # providers in the order they were added.
        providers = list(self._providers.items())
        ordered: list[tuple[str, ToolProvider]] = []
        if "lucy" in self._providers:
            ordered.append(("lucy", self._providers["lucy"]))
        for src, prov in providers:
            if src == "lucy":
                continue
            ordered.append((src, prov))
        return [prov for _src, prov in ordered]

    def descriptors(self) -> list[ToolDescriptor]:
        # De-duplicate by unqualified tool name, preferring providers earlier
        # in the precedence order (Lucy first). Returns a stable, sorted list
        # by the descriptor.id for reproducible discovery output.
        by_name: dict[str, ToolDescriptor] = {}
        for provider in self._ordered_providers():
            for descriptor in provider.descriptors():
                if descriptor.name in by_name:
                    # Skip lower-precedence provider offering the same name.
                    continue
                by_name[descriptor.name] = descriptor
        return sorted(by_name.values(), key=lambda item: item.id)

    def get(self, tool_id: str) -> ToolDescriptor | None:
        # Accept either qualified ids (source:name) or unqualified names.
        if ":" in tool_id:
            return next((item for item in self.descriptors() if item.id == tool_id), None)
        return next((item for item in self.descriptors() if item.name == tool_id), None)

    def definition(self, tool_id: str) -> Mapping[str, Any] | None:
        # Support qualified ids and unqualified names; prefer Lucy when names
        # collide.
        source, separator, name = tool_id.partition(":")
        if separator and source and name:
            provider = self._providers.get(source)
            if provider is None:
                return None
            return provider.definition(name)

        # Unqualified: search ordered providers and return the first definition
        # that claims the name.
        for provider in self._ordered_providers():
            defn = provider.definition(tool_id)
            if defn is not None:
                return defn
        return None

    def create(self, tool_id: str, **kwargs: Any) -> Any:
        # Support qualified ids and unqualified names; raise KeyError on bad
        # input to mirror the original behaviour.
        source, separator, name = tool_id.partition(":")
        if separator and source and name:
            provider = self._providers.get(source)
            if provider is None:
                raise KeyError(f"unknown tool provider: {source!r}")
            return provider.create(name, **kwargs)

        # Unqualified: resolve using ordered providers and invoke create on the
        # first provider that exposes the name.
        for provider in self._ordered_providers():
            try:
                return provider.create(tool_id, **kwargs)
            except KeyError:
                continue
        raise KeyError(f"unknown tool: {tool_id!r}")

    def search(
        self,
        query: str = "",
        *,
        groups: Iterable[str] = (),
        tags: Iterable[str] = (),
        limit: int = 10,
    ) -> list[ToolDescriptor]:
        """Return descriptors ordered by transparent lexical relevance."""

        return [
            match.descriptor
            for match in self.search_matches(
                query,
                groups=groups,
                tags=tags,
                limit=limit,
            )
        ]

    def search_matches(
        self,
        query: str = "",
        *,
        groups: Iterable[str] = (),
        tags: Iterable[str] = (),
        limit: int = 10,
    ) -> list[ToolMatch]:
        """Rank meaningful matches; never pad results using conversational words."""

        required_groups = set(_normalise_terms(groups))
        required_tags = set(_normalise_terms(tags))
        # Ignore conversational filler so unrelated tools are not selected merely
        # because their descriptions contain words such as "an" or "to".
        query_terms = set(_tokenize(query)) - _QUERY_STOP_WORDS
        if query.strip() and not query_terms:
            return []

        ranked: list[tuple[int, str, ToolMatch]] = []
        for descriptor in self.descriptors():
            descriptor_groups = set(descriptor.groups)
            if required_groups and not required_groups.issubset(descriptor_groups):
                continue

            descriptor_tags = set(descriptor.tags)
            if required_tags and not required_tags.issubset(descriptor_tags):
                continue

            # Score basic lexical match metrics. Larger is a better match.
            score = 0
            matched_on: list[str] = []

            # Token sets for matching the optional query. When a query is
            # provided require at least one lexical match against the tool's
            # name, description, or tags; otherwise descriptors that only
            # match because of groups/tags would surface for unrelated queries.
            name_terms = set(_tokenize(descriptor.name))
            desc_terms = set(_tokenize(descriptor.description))
            tag_terms = set(descriptor.tags)

            if not query_terms:
                # No query: give a baseline score to make unfiltered results
                # appear in discovery lists while still allowing groups/tags
                # to influence ordering.
                score += 1
            else:
                # Require the query to match name, description, or tags.
                if query_terms & name_terms:
                    score += 10
                    matched_on.extend(sorted(query_terms & name_terms))

                if query_terms & desc_terms:
                    score += 5
                    matched_on.extend(sorted(query_terms & desc_terms))

                if query_terms & tag_terms:
                    # Treat tag matches as weaker evidence than name but
                    # stronger than description-only matches.
                    score += 6
                    matched_on.extend(sorted(query_terms & tag_terms))

                if score == 0:
                    # Query provided but no lexical match — skip this
                    # descriptor to avoid returning noisy results.
                    continue

            if descriptor_groups:
                score += 2
                matched_on.extend(sorted(descriptor_groups))

            if descriptor_tags:
                score += 1
                matched_on.extend(sorted(descriptor_tags))

            ranked.append((score, descriptor.id, ToolMatch(descriptor, score, tuple(matched_on))))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in ranked[:limit]]


_QUERY_STOP_WORDS = frozenset({
    "a", "an", "and", "are", "for", "in", "is", "of", "or", "related",
    "the", "to", "tool", "tools", "with",
})

_token_re = re.compile(r"[^a-z0-9]+")


def _tokenize(value: str) -> tuple[str, ...]:
    value = (value or "").lower().strip()
    if not value:
        return ()
    return tuple(filter(None, (_token_re.sub(" ", value).split())))


def _normalise_terms(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values.lower().strip(),)
    return tuple(sorted({str(v).lower().strip() for v in values if v}))
