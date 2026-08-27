from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.keywords.keywords import Keywords
from src.storage.models import DocumentRef


class DocumentsMixin:
    """Document methods extracted from JsonFileStorage.

    Mixin: relies on self.storage_paths, self._load_json, self._ensure_dir,
    and self._atomic_write provided by the composing class.
    """

    def list_documents(
        self,
        account_name: str,
        kind: Optional[str] = None,
        tag: Optional[str] = None,
        select_limit: int = 100,
    ) -> List[DocumentRef]:

        logging.debug("list_documents called: account=%s kind=%s tag=%r select_limit=%s", account_name, kind, tag, select_limit)

        doc_dir = self.storage_paths.documents / account_name
        if not doc_dir.exists():
            return []

        docs = []
        for doc_file in doc_dir.glob("*.json"):
            data = self._load_json(doc_file)
            if not data:
                continue

            if kind and data.get("kind") != kind:
                continue
            # If tag is provided (could be empty string), strictly require it to be present
            if tag is not None and tag not in data.get("tags", []):
                continue

            docs.append(self._doc_dict_to_ref(data))

        return docs[:select_limit]

    def get_document(self, document_id: str) -> Optional[DocumentRef]:
        docs_dir = self.storage_paths.documents
        if not docs_dir.exists():
            return None

        for account_dir in docs_dir.iterdir():
            if not account_dir.is_dir():
                continue

            doc_path = account_dir / f"{document_id}.json"
            if doc_path.exists():
                data = self._load_json(doc_path)
                if data:
                    return self._doc_dict_to_ref(data)

        return None

    def upsert_document(self, doc: DocumentRef) -> None:
        path = self.storage_paths.documents / doc.account_name
        self._ensure_dir(path)

        data = {
            "id": doc.id,
            "account_name": doc.account_name,
            "path": doc.path,
            "kind": doc.kind,
            "title": doc.title,
            "tags": doc.tags,
            "metadata": doc.metadata,
        }

        self._atomic_write(path / f"{doc.id}.json", data)

    def _doc_dict_to_ref(self, data: Dict[str, Any]) -> DocumentRef:
        return DocumentRef(
            id=data["id"],
            account_name=data["account_name"],
            path=data["path"],
            kind=data["kind"],
            title=data.get("title"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )

    def search_documents_poor_man(
        self,
        account_name: str,
        query: str,
        kind: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 10,
    ) -> List[DocumentRef]:
        """Simple keyword-based search over documents for an account.

        This is intentionally "quick and dirty": it scores documents based on
        how many times the query terms appear in title, tags, and metadata.
        """

        # Reuse existing listing logic to get candidate docs
        docs = self.list_documents(
            account_name=account_name,
            kind=kind,
            tag=tag,
            select_limit=100,  # upper bound of candidates to score
        )

        myKwUtil = Keywords()

        terms = myKwUtil.extract_keywords(query, top_n=20)   

        # Tokenize query into lowercase terms
        # terms = [t for t in query.lower().split() if t.strip()]
        if not terms:
            return []

        scored: List[Tuple[DocumentRef, int]] = []

        for doc in docs:
            # Build a simple text blob from title, tags, and metadata values
            title_text = (doc.title or "").lower()
            tags_text = " ".join(doc.tags).lower()
            metadata_text = " ".join(
                str(v).lower() for v in (doc.metadata or {}).values()
            )

        
            blob = " ".join([title_text, tags_text, metadata_text])
            blob = myKwUtil.extract_keywords(blob, top_n=50)    

            # Score = sum of term occurrences
            #score = sum(blob.count(term) for term in terms)
            score = len(set(blob) & set(terms))


            if score > 0:
                scored.append((doc, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return [doc for doc, _ in scored[:limit]]
