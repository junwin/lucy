"""Process-owned galet-memory runtime shared by Lucy prompts, tools and curation."""
from __future__ import annotations

import atexit
from dataclasses import replace
import logging
import os
from pathlib import Path
from threading import RLock
from types import SimpleNamespace

from galet_memory import build_memory, load_memory_config, ResourceLocation
from galet_memory.ports import EmbeddingResource, EmbeddingMatch
from galet_memory.semantic import SemanticMemory, SemanticMemoryRequest
from galet_memory.publication import EmbeddingDigestPublisher, FilesystemDigestStore
from galet_memory import EmbeddingDigestRecall

logger = logging.getLogger(__name__)
_lock = RLock()
_services = {}
_owners = {}


class ConfiguredSemanticMemory(SemanticMemory):
    """Adapt Lucy/prompt requests to the configured embedding space."""
    def __init__(self, runtime):
        self.runtime = runtime
        self.embedding_model = runtime.config.embedding_profiles[runtime.config.semantic.embedding_profile].model

    def recall(self, request):
        return self.runtime.semantic.recall(SemanticMemoryRequest(
            account_name=request.account_name, query=request.query,
            use_embeddings=request.use_embeddings, namespaces=list(request.namespaces or []),
            top_k=request.top_k, max_chars=request.max_chars,
            score_threshold=request.score_threshold, embedding_model=self.embedding_model,
            source_type=getattr(request, 'source_type', None),
        ))

    def list_namespaces(self, account_name):
        return self.runtime.semantic.list_namespaces(account_name)

    def embed(self, texts, *, model=None):
        selected = model or self.embedding_model
        vectors = self.runtime.ingestion.embeddings.embed(texts, model=selected)
        return SimpleNamespace(model=selected, embeddings=vectors)


class ConfinedDigestStore(FilesystemDigestStore):
    def __init__(self, runtime):
        self.runtime = runtime
        self.location = runtime.config.episodic.digests_directory
        super().__init__(runtime.resolver.resolve(self.location, directory=True))

    def path_for(self, account_name, session_id, digest_id=None):
        path = super().path_for(account_name, session_id, digest_id)
        authorized_root = self.runtime.resolver.resolve(self.location, directory=True)
        if not path.resolve().is_relative_to(authorized_root):
            raise PermissionError('digest path escapes configured digest directory')
        return path


class ConfiguredDigestIndex:
    """Publish V3 locators and reauthorize digest sources before each read."""
    def __init__(self, runtime):
        self.runtime = runtime
        self.index = runtime.ingestion.index
        self.location = runtime.config.episodic.digests_directory
        self.root = runtime.resolver.resolve(self.location, directory=True)

    def upsert(self, embedding):
        if self.runtime.config.semantic.metadata_version == 3:
            metadata = dict(embedding.metadata)
            path = self.runtime.resolver.authorize_path(metadata['path'])
            relative = path.relative_to(self.root).as_posix()
            prefix = self.location.relative_path
            resource_path = relative if prefix == '.' else prefix.rstrip('/') + '/' + relative
            resource = EmbeddingResource(
                'digest', self.location.external_root, resource_path,
                session_id=metadata['session_id'], digest_id=metadata.get('digest_id') or 'published',
                source_event_ids=tuple(metadata.get('source_event_ids', ())), representation='digest',
            )
            keywords = self.runtime.ingestion.keyword_extractor.extract(path.read_text(encoding='utf-8'))
            embedding = replace(embedding, resource=resource, keywords=list(keywords))
        self.index.upsert(embedding)

    def query(self, *, account_name, namespaces, vector, limit, filters=None):
        selected = []
        for match in self.index.query(account_name=account_name, namespaces=namespaces,
                                      vector=vector, limit=limit, filters=filters):
            metadata = dict(match.record.metadata)
            resource = match.record.resource
            if self.runtime.config.semantic.metadata_version == 3:
                if resource is None or resource.resource_type != 'digest':
                    continue
                metadata.update(session_id=resource.session_id, digest_id=resource.digest_id,
                                source_event_ids=list(resource.source_event_ids))
                try:
                    path = self.runtime.resolver.resolve(ResourceLocation(resource.external_root, resource.relative_path))
                    if not path.is_relative_to(self.root):
                        continue
                except (OSError, ValueError):
                    continue
            else:
                try:
                    path = self.runtime.resolver.authorize_path(metadata.get('path', ''))
                except (OSError, ValueError):
                    continue
            session_id = metadata.get('session_id') or match.record.source_id
            if not self.runtime.episodic.is_digest_valid(
                account_name=account_name, session_id=session_id,
                digest_id=metadata.get('digest_id'), source_event_ids=metadata.get('source_event_ids'),
            ):
                continue
            metadata['path'] = str(path)
            selected.append(EmbeddingMatch(replace(match.record, source_id=session_id, metadata=metadata), match.score))
        return selected


class LucyMemoryServices:
    def __init__(self, path):
        settings = load_memory_config(path=path)
        for kind in ('semantic', 'episodic', 'procedural'):
            if getattr(settings, kind) is None:
                raise ValueError(f'Lucy shared memory config must enable {kind}')
        if settings.episodic.digests_directory is None:
            raise ValueError('Lucy shared episodic config must declare digests_directory')
        self.runtime = build_memory(settings)
        self.closed = False
        try:
            self.semantic = ConfiguredSemanticMemory(self.runtime)
            index = ConfiguredDigestIndex(self.runtime)
            self.digests_root = index.root
            profile = settings.embedding_profiles[settings.semantic.embedding_profile]
            self.digest_publisher = EmbeddingDigestPublisher(
                ConfinedDigestStore(self.runtime), self.runtime.ingestion.embeddings, index,
                model=profile.model, provider=profile.provider,
            )
            self.runtime.episodic.digest_search = EmbeddingDigestRecall(
                embeddings=self.runtime.ingestion.embeddings, index=index,
                text_loader=self.runtime.semantic.text_loader, embedding_model=profile.model,
            )
            logger.info('lucy_memory_ready config=%s metadata_version=%s episodic_database=%s',
                        path, settings.semantic.metadata_version, self.runtime.episodic.db_path)
        except BaseException:
            self.runtime.close()
            raise

    def close(self):
        self.runtime.close()
        self.closed = True


def shared_memory_path(config):
    selected = config.get('memory_config_path') or os.environ.get('GALET_MEMORY_CONFIG_PATH')
    if selected is None or selected == '':
        return None
    if not isinstance(selected, str) or not selected.strip():
        raise ValueError('memory_config_path must be a nonempty absolute path')
    path = Path(selected).expanduser()
    if not path.is_absolute():
        raise ValueError('memory_config_path must be absolute')
    return str(path.resolve())


def get_shared_memory(config):
    """Explicit shared config wins; an invalid selected config never falls back."""
    path = shared_memory_path(config)
    config_file = getattr(config, 'file_name', None)
    owner = str(Path(config_file).resolve()) if isinstance(config_file, str) else None
    with _lock:
        if owner in _owners and _owners[owner] != path:
            raise ValueError('changing memory_config_path requires a Lucy process restart')
        if path is None:
            if owner is not None:
                _owners[owner] = None
            return None
        services = _services.get(path)
        if services is None or services.closed:
            services = LucyMemoryServices(path)
            _services[path] = services
        if owner is not None:
            _owners[owner] = path
        return services


def close_shared_memory():
    """Process shutdown, not Flask request teardown."""
    with _lock:
        for services in _services.values():
            services.close()
        _services.clear()
        _owners.clear()


atexit.register(close_shared_memory)
