import logging
from typing import Any, Dict, Tuple


def list_context_names_impl(storage, account_name: str) -> Tuple[Any, int]:
    if not account_name:
        return {"error": "Missing accountName"}, 400

    try:
        return storage.list_context_names(account_name), 200
    except Exception:
        logging.exception(
            "list_context_names_impl: failed to list context names for account=%s", account_name
        )
        return {"error": "An error occurred"}, 500


# TaskList CRUD implementations
def list_tasklists_impl(storage, account_name: str) -> Tuple[Any, int]:
    if not account_name:
        return {"error": "Missing accountName"}, 400

    try:
        ids = storage.list_tasklists(account_name)
        return ids, 200
    except Exception:
        logging.exception("list_tasklists_impl: failed to list tasklists for account=%s", account_name)
        return {"error": "An error occurred"}, 500


def get_tasklist_impl(storage, account_name: str, tasklist_name: str) -> Tuple[Any, int]:
    if not account_name:
        return {"error": "Missing accountName"}, 400

    try:
        tl = storage.get_tasklist(account_name, tasklist_name)
        if tl is None:
            return {"error": "TaskList not found"}, 404

        return tl.to_dict(), 200
    except ValueError as e:
        return {"error": str(e)}, 400
    except Exception as e:
        logging.exception(
            "get_tasklist_impl: failed to get tasklist for account=%s name=%s",
            account_name,
            tasklist_name,
        )
        return {"error": "An error occurred", "details": str(e)}, 500


def put_tasklist_impl(storage, account_name: str, tasklist_name: str, payload: Dict) -> Tuple[Any, int]:
    if not account_name:
        return {"error": "Missing accountName"}, 400

    if payload is None:
        return {"error": "Invalid JSON body"}, 400

    try:
        storage.save_tasklist(account_name, tasklist_name, payload)
        return {"ok": True}, 200
    except ValueError as e:
        return {"error": str(e)}, 400
    except Exception as e:
        logging.exception(
            "put_tasklist_impl: failed to save tasklist for account=%s name=%s",
            account_name,
            tasklist_name,
        )
        return {"error": "An error occurred", "details": str(e)}, 500


def delete_tasklist_impl(storage, account_name: str, tasklist_name: str) -> Tuple[Any, int]:
    if not account_name:
        return {"error": "Missing accountName"}, 400

    try:
        storage.delete_tasklist(account_name, tasklist_name)
        return {"ok": True}, 200
    except Exception:
        logging.exception(
            "delete_tasklist_impl: failed to delete tasklist for account=%s name=%s",
            account_name,
            tasklist_name,
        )
        return {"error": "An error occurred"}, 500
