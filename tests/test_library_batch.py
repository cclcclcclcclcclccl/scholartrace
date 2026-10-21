"""Atomic library edits, undo conflicts, and account boundary regression checks."""

import json

import pytest
from fastapi.testclient import TestClient

from backend import accounts, database, store
from backend.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "main.sqlite3")
    monkeypatch.setattr(accounts, "AUTH_PATH", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(
        accounts, "path", lambda identifier: tmp_path / identifier / "library.sqlite3"
    )
    database.initialize()
    with store.connection() as c:
        for identifier in ["paper-a", "paper-b"]:
            c.execute(
                "INSERT INTO documents(id,name,title,path,pages,chars,status,metadata) VALUES(?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    identifier + ".pdf",
                    identifier,
                    "fixture.pdf",
                    1,
                    20,
                    "ready",
                    json.dumps(
                        {
                            "source": {"preserve": True},
                            "tags": ["original"],
                            "collection": "",
                            "reading_status": "unread",
                        }
                    ),
                ),
            )
    with TestClient(app) as client:
        yield client


def item(identifier, **updates):
    current = {"tags": ["original"], "collection": "", "reading_status": "unread"}
    return {"id": identifier, "expected": current, "value": {**current, **updates}}


def metadata(identifier):
    return store.get_document(identifier)["metadata"]


def test_atomic_edit_and_undo_preserves_other_metadata(client):
    response = client.patch(
        "/api/library/organization/batch",
        json={
            "items": [
                item(
                    "paper-a", tags=["original", " new ", "new"], collection=" project "
                ),
                item("paper-b", reading_status="read"),
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 2
    assert metadata("paper-a")["tags"] == ["original", "new"]
    assert metadata("paper-a")["collection"] == "project"
    assert metadata("paper-a")["source"] == {"preserve": True}
    reverse = [
        {"id": c["id"], "expected": c["value"], "value": c["previous"]}
        for c in response.json()["changes"]
    ]
    assert (
        client.patch(
            "/api/library/organization/batch", json={"items": reverse}
        ).status_code
        == 200
    )
    assert metadata("paper-a")["tags"] == ["original"]
    assert metadata("paper-b")["reading_status"] == "unread"


@pytest.mark.parametrize("failure", ["missing", "stale", "archived", "invalid_tags"])
def test_late_failure_rolls_back_entire_batch(client, failure):
    second = item("paper-b", reading_status="read")
    expected_code = 409
    if failure == "missing":
        second["id"] = "missing"
        expected_code = 404
    elif failure == "stale":
        second["expected"]["collection"] = "old snapshot"
    elif failure == "archived":
        with store.connection() as c:
            c.execute("UPDATE documents SET archived=1 WHERE id='paper-b'")
    else:
        second["value"]["tags"] = ["x" * 41]
        expected_code = 422
    response = client.patch(
        "/api/library/organization/batch",
        json={"items": [item("paper-a", reading_status="read"), second]},
    )
    assert response.status_code == expected_code
    assert metadata("paper-a")["reading_status"] == "unread"


def test_undo_rejects_intervening_edit(client):
    changed = client.patch(
        "/api/library/organization/batch",
        json={"items": [item("paper-a", reading_status="read")]},
    ).json()["changes"][0]
    client.patch(
        "/api/documents/paper-a/organization", json={"collection": "new decision"}
    )
    response = client.patch(
        "/api/library/organization/batch",
        json={
            "items": [
                {
                    "id": "paper-a",
                    "expected": changed["value"],
                    "value": changed["previous"],
                }
            ]
        },
    )
    assert response.status_code == 409
    assert metadata("paper-a")["collection"] == "new decision"


def test_batch_account_isolation_and_payload_validation(client):
    assert (
        client.patch(
            "/api/library/organization/batch",
            json={"items": [item("paper-a"), item("paper-a")]},
        ).status_code
        == 422
    )
    assert (
        client.patch("/api/library/organization/batch", json={"items": []}).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/library/organization/batch",
            json={"items": [item("paper-a", reading_status="invented")]},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/account/register",
            json={"name": "batch-user", "password": "test-password-123"},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            "/api/library/organization/batch",
            json={"items": [item("paper-a", reading_status="read")]},
        ).status_code
        == 404
    )
    assert metadata("paper-a")["reading_status"] == "unread"
