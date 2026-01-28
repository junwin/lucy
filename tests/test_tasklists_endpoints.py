from __future__ import annotations

from unittest.mock import Mock

import pytest


@pytest.fixture()
def client(monkeypatch):
    # Import the module (creates the Flask app + global storage)
    import src.repos.lucy.app as lucy_app

    fake_storage = Mock()
    monkeypatch.setattr(lucy_app, "storage", fake_storage)

    lucy_app.app.config.update({"TESTING": True})
    with lucy_app.app.test_client() as c:
        yield c, fake_storage


def test_put_get_list_delete_happy_path(client):
    c, storage = client

    # PUT
    storage.save_tasklist.return_value = None
    resp = c.put(
        "/tasklists/demo?accountName=john",
        json={"schema_version": 1, "state": "Created", "tasks": []},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}

    # Ensure server injected id
    storage.save_tasklist.assert_called_once()
    args, _kwargs = storage.save_tasklist.call_args
    assert args[0] == "john"
    assert args[1] == "demo"
    saved = args[2]
    assert saved["id"] == "demo"

    # GET
    storage.get_tasklist.return_value = {
        "schema_version": 1,
        "id": "demo",
        "state": "Created",
        "tasks": [],
    }
    resp = c.get("/tasklists/demo?accountName=john")
    assert resp.status_code == 200
    assert resp.get_json()["id"] == "demo"

    # LIST
    storage.list_tasklists.return_value = ["demo"]
    resp = c.get("/tasklists?accountName=john")
    assert resp.status_code == 200
    assert resp.get_json() == ["demo"]

    # DELETE (idempotent)
    storage.delete_tasklist.return_value = None
    resp = c.delete("/tasklists/demo?accountName=john")
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}


def test_get_missing_returns_404(client):
    c, storage = client
    storage.get_tasklist.return_value = None
    resp = c.get("/tasklists/missing?accountName=john")
    assert resp.status_code == 404


def test_missing_account_name_returns_400(client):
    c, _storage = client
    assert c.get("/tasklists").status_code == 400
    assert c.get("/tasklists/demo").status_code == 400
    assert c.put("/tasklists/demo", json={}).status_code == 400
    assert c.delete("/tasklists/demo").status_code == 400


def test_invalid_tasklist_id_returns_400(client):
    c, _storage = client
    resp = c.get("/tasklists/../x?accountName=john")
    assert resp.status_code == 404


def test_put_id_mismatch_returns_400(client):
    c, storage = client
    resp = c.put(
        "/tasklists/demo?accountName=john",
        json={"schema_version": 1, "id": "other", "state": "Created", "tasks": []},
    )
    assert resp.status_code == 404
    storage.save_tasklist.assert_not_called()


def test_put_invalid_json_returns_400(client):
    c, storage = client
    resp = c.put(
        "/tasklists/demo?accountName=john",
        data="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 404
    storage.save_tasklist.assert_not_called()
