"""Projects retain source identity and isolate scope, concurrent writes and accounts."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from backend import accounts, database, jobs, projects, research, store
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
        for identifier in ("a", "b", "c"):
            c.execute(
                "INSERT INTO documents(id,name,title,path,pages,chars,status,metadata) VALUES(?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    identifier + ".pdf",
                    "Paper " + identifier,
                    "test.pdf",
                    1,
                    20,
                    "ready",
                    "{}",
                ),
            )
            c.execute(
                "INSERT INTO blocks VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    identifier + "-block",
                    identifier,
                    1,
                    0,
                    "Original evidence " + identifier,
                    "[1,2,3,4]",
                    100,
                    100,
                    "text",
                ),
            )
        c.execute(
            "INSERT INTO evidence_notes(block_id,note,quote) VALUES('a-block','source note','Original evidence a')"
        )
    with TestClient(app) as client:
        yield client


def create(client, name="project", ids=None):
    response = client.post(
        "/api/projects",
        json={
            "title": name,
            "goal": "Compare real source conditions",
            "document_ids": ids if ids is not None else ["a", "b"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def edit_payload(p, **changes):
    return {
        "title": p["title"],
        "goal": p["goal"],
        "document_ids": p["document_ids"],
        "expected_revision": p["revision"],
        "artifact_ids": [a["id"] for a in p["artifacts"]],
        "archived": bool(p["archived"]),
        **changes,
    }


def test_many_projects_share_documents_and_derived_notes(client):
    p = create(client)
    q = create(client, "other", ["a"])
    assert p["notes"][0]["block_id"] == "a-block"
    assert q["notes"][0]["quote"] == "Original evidence a"
    changed = client.patch(
        "/api/projects/" + p["id"], json=edit_payload(p, document_ids=["b"])
    ).json()
    assert changed["notes"] == []
    assert (
        client.get("/api/projects/" + q["id"]).json()["notes"][0]["note"]
        == "source note"
    )
    assert len(store.list_documents()) == 3
    with store.connection() as c:
        assert c.execute("SELECT COUNT(*) FROM evidence_notes").fetchone()[0] == 1


def test_revision_conflict_and_invalid_membership_are_atomic(client):
    p = create(client)
    url = "/api/projects/" + p["id"]
    assert client.patch(url, json=edit_payload(p, title="new name")).status_code == 200
    assert (
        client.patch(url, json=edit_payload(p, title="stale overwrite")).status_code
        == 409
    )
    current = client.get(url).json()
    assert (
        client.patch(
            url, json=edit_payload(current, document_ids=["a", "missing"])
        ).status_code
        == 404
    )
    assert client.get(url).json() == current
    assert (
        client.patch(
            url, json=edit_payload(current, artifact_ids=["missing"])
        ).status_code
        == 404
    )
    assert client.get(url).json() == current
    assert client.post("/api/projects", json={"title": "  "}).status_code == 422
    assert (
        client.post(
            "/api/projects", json={"title": "invalid", "document_ids": ["missing"]}
        ).status_code
        == 404
    )
    assert len(client.get("/api/projects").json()) == 1


def test_archive_restore_and_export_do_not_delete_sources(client):
    p = create(client)
    url = "/api/projects/" + p["id"]
    archived = client.patch(url, json=edit_payload(p, archived=True)).json()
    assert archived["archived"] == 1
    assert (
        client.post(
            "/api/ask",
            json={"question": "test", "project_id": p["id"], "document_ids": ["a"]},
        ).status_code
        == 409
    )
    exported = client.get(url + "/export")
    assert (
        exported.status_code == 200
        and exported.json()["notes"][0]["quote"] == "Original evidence a"
    )
    restored = client.patch(url, json=edit_payload(archived, archived=False)).json()
    assert restored["document_ids"] == p["document_ids"]
    with store.connection() as c:
        c.execute("UPDATE documents SET archived=1 WHERE id='a'")
    assert (
        client.patch(
            url, json=edit_payload(restored, goal="keep historical membership")
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/projects", json={"title": "new", "document_ids": ["a"]}
        ).status_code
        == 422
    )


def test_project_answer_scope_and_auto_collection(client, monkeypatch):
    p = create(client, ids=["a"])
    calls = []

    async def fake(question, ids):
        calls.append(ids)
        return {
            "claims": [
                {
                    "text": "test claim",
                    "quote": "Original evidence a",
                    "block_id": "a-block",
                }
            ],
            "evidence": [],
        }

    monkeypatch.setattr(research, "grounded", fake)
    for ids in ([], ["b"]):
        assert (
            client.post(
                "/api/ask",
                json={"question": "test", "project_id": p["id"], "document_ids": ids},
            ).status_code
            == 422
        )
    assert calls == []
    result = client.post(
        "/api/ask",
        json={"question": "test", "project_id": p["id"], "document_ids": ["a"]},
    )
    assert result.status_code == 200
    identifier = result.json()["artifact_id"]
    saved = research.artifact(identifier)
    assert saved["content"]["project_context"]["source_document_ids"] == ["a"]
    assert (
        client.get("/api/projects/" + p["id"]).json()["artifacts"][0]["id"]
        == identifier
    )
    assert projects.current.get() is None
    plain = client.post(
        "/api/ask", json={"question": "plain", "document_ids": ["a"]}
    ).json()
    assert "project_context" not in research.artifact(plain["artifact_id"])["content"]
    assert len(client.get("/api/projects/" + p["id"]).json()["artifacts"]) == 1


def test_auto_output_conflicts_with_old_project_editor_and_can_be_unlinked(client):
    p = create(client)
    response = client.post(
        "/api/diagrams",
        json={
            "title": "Diagram",
            "code": "flowchart LR\n A-->B",
            "project_id": p["id"],
        },
    )
    assert response.status_code == 200
    identifier = response.json()["id"]
    assert (
        client.patch(
            "/api/projects/" + p["id"], json=edit_payload(p, title="old tab")
        ).status_code
        == 409
    )
    latest = client.get("/api/projects/" + p["id"]).json()
    assert latest["artifacts"][0]["id"] == identifier
    assert (
        client.patch(
            "/api/projects/" + p["id"], json=edit_payload(latest, artifact_ids=[])
        ).status_code
        == 200
    )
    assert client.get("/api/artifacts/" + identifier).status_code == 200
    assert projects.current.get() is None


def test_project_and_artifact_access_remain_account_local(client):
    p = create(client)
    output = research.save_artifact("diagram", "Local", {"code":"flowchart LR\n A-->B"})
    assert (
        client.post(
            "/api/account/register",
            json={"name": "project-user", "password": "project-pass-123"},
        ).status_code
        == 200
    )
    assert client.get("/api/projects").json() == []
    assert client.get("/api/projects/" + p["id"]).status_code == 404
    assert client.get("/api/projects/" + p["id"] + "/export").status_code == 404
    assert (
        client.post(
            "/api/projects", json={"title": "foreign document", "document_ids": ["a"]}
        ).status_code
        == 404
    )
    own = create(client, "own", [])
    assert (
        client.patch(
            "/api/projects/" + own["id"],
            json=edit_payload(own, artifact_ids=[output["id"]]),
        ).status_code
        == 404
    )


def test_background_job_context_isolated_and_persisted(client, monkeypatch):
    a = create(client, "first", ["a"])
    b = create(client, "second", ["b"])

    async def handler(ctx, payload):
        await asyncio.sleep(0.01)
        return research.save_artifact(
            "review", payload["topic"], {"seen": projects.current.get()["id"]}
        )

    monkeypatch.setitem(jobs.handlers, "review", handler)
    with store.connection() as c:
        for identifier, p in [("job-a", a), ("job-b", b)]:
            c.execute(
                "INSERT INTO jobs(id,kind,payload) VALUES(?,?,?)",
                (
                    identifier,
                    "review",
                    json.dumps(
                        {
                            "project_id": p["id"],
                            "document_ids": p["document_ids"],
                            "topic": p["title"],
                        }
                    ),
                ),
            )

    async def run_both():
        await asyncio.gather(jobs.run("job-a"), jobs.run("job-b"))

    asyncio.run(run_both())
    for identifier, p in [("job-a", a), ("job-b", b)]:
        assert jobs.get(identifier)["state"] == "completed"
        detail = client.get("/api/projects/" + p["id"]).json()
        assert len(detail["artifacts"]) == 1
        assert (
            research.artifact(detail["artifacts"][0]["id"])["content"]["seen"]
            == p["id"]
        )
        assert detail["jobs"][0]["id"] == identifier
    assert projects.current.get() is None


def test_project_job_does_not_fall_back_to_whole_library(client):
    p = create(client, ids=["a"])
    for ids in ([], ["b"]):
        response = client.post(
            "/api/jobs",
            json={
                "kind": "review",
                "payload": {
                    "topic": "Review",
                    "document_ids": ids,
                    "project_id": p["id"],
                },
            },
        )
        assert response.status_code == 422
    assert client.get("/api/jobs").json() == []
