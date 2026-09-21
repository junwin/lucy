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

    def create(self, tool_name: str, **kwargs: Any) -> Any:
        if self.tool_names is not None and tool_name not in self.tool_names:
            raise KeyError(f"{tool_name!r} is not provided by {self.source!r}")
        return self.registry.create(tool_name, **kwargs)


class ToolCatalog:
    """Aggregate descriptors from multiple local or remote providers."""

    def __init__(self, providers: Iterable[ToolProvider] = ()) -> None:
        self._providers: dict[str, ToolProvider] = {}
        for provider in providers:
            self.add_provider(provider)

    def add_provider(self, provider: ToolProvider) -> None:
        if provider.source in self._providers:
            raise ValueError(f"duplicate tool provider source: {provider.source}")
        self._providers[provider.source] = provider

    def descriptors(self) -> list[ToolDescriptor]:
        by_id: dict[str, ToolDescriptor] = {}
        for provider in self._providers.values():
            for descriptor in provider.descriptors():
                if descriptor.id in by_id:
                    raise ValueError(f"duplicate tool id: {descriptor.id}")
                by_id[descriptor.id] = descriptor
        return sorted(by_id.values(), key=lambda item: item.id)

    def get(self, tool_id: str) -> ToolDescriptor | None:
        return next((item for item in self.descriptors() if item.id == tool_id), None)

    def create(self, tool_id: str, **kwargs: Any) -> Any:
        source, separator, name = tool_id.partition(":")
        if not separator or not source or not name:
            raise KeyError(f"invalid qualified tool id: {tool_id!r}")
        provider = self._providers.get(source)
        if provider is None:
            raise KeyError(f"unknown tool provider: {source!r}")
        return provider.create(name, **kwargs)

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
        query_terms = set(_tokenize(query))

        ranked: list[tuple[int, str, ToolMatch]] = []
        for descriptor in self.descriptors():
            descriptor_groups = set(descriptor.groups)
            descriptor_tags = set(descriptor.tags)
            if required_groups and not required_groups <= descriptor_groups:
                continue
            if required_tags and not required_tags <= descriptor_tags:
                continue

            fields = (
                ("name", 20, set(_tokenize(descriptor.name))),
                ("alias", 16, set(_tokenize(" ".join(descriptor.aliases)))),
                ("tag", 12, set(_tokenize(" ".join(descriptor.tags)))),
                ("group", 10, set(_tokenize(" ".join(descriptor.groups)))),
                ("capability", 8, set(_tokenize(" ".join(descriptor.capabilities)))),
                ("description", 3, set(_tokenize(descriptor.description))),
            )
            matched_on: list[str] = []
            score = 0
            for term in sorted(query_terms):
                for field_name, weight, field_terms in fields:
                    if term in field_terms:
                        score += weight
                        matched_on.append(f"{field_name}:{term}")

            if query_terms and score == 0:
                continue
            match = ToolMatch(
                descriptor=descriptor,
                score=score,
                matched_on=tuple(matched_on),
            )
            ranked.append((-score, descriptor.id, match))

        ranked.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in ranked[: max(0, limit)]]

_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "by",
        "can",
        "find",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "related",
        "that",
        "the",
        "this",
        "to",
        "tool",
        "tools",
        "with",
    }
)

_TERM_ALIASES = {
    "generated": "generate",
    "generates": "generate",
    "generating": "generate",
    "generation": "generate",
    "images": "image",
    "published": "publish",
    "publisher": "publish",
    "publishers": "publish",
    "publishes": "publish",
    "publishing": "publish",
}


def _tokenize(value: str) -> tuple[str, ...]:
    terms = []
    for raw in re.findall(r"[a-z0-9]+", value.lower()):
        term = _TERM_ALIASES.get(raw, raw)
        if term and term not in _STOP_WORDS:
            terms.append(term)
    return tuple(sorted(set(terms)))


def _normalise_terms(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = [values]
    return tuple(
        sorted(
            {
                str(value).strip().lower()
                for value in values
                if str(value).strip()
            }
        )
    )

