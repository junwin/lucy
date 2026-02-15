import logging


def search_documents_impl(storage, data: dict):
    account_name = (data.get("account_name", "") or "").lower()
    query = data.get("question") or data.get("q") or ""
    kind = data.get("kind")
    tag = data.get("tag")
    limit = int(data.get("limit", 10))

    if not account_name:
        return {"error": "Missing account_name"}, 400
    if not query.strip():
        return {"error": "Missing query"}, 400

    try:
        if not hasattr(storage, "search_documents_poor_man"):
            return {"error": "Document search not supported by this storage backend"}, 501

        results = storage.search_documents_poor_man(
            account_name=account_name,
            query=query,
            kind=kind,
            limit=limit,
            tag=tag,
        )

        return [
            {
                "id": d.id,
                "account_name": d.account_name,
                "path": d.path,
                "kind": d.kind,
                "title": d.title,
                "tags": d.tags,
                "metadata": d.metadata,
            }
            for d in results
        ], 200
    except Exception as e:
        logging.exception("Error in /documents/search")
        return {"error": str(e)}, 500
