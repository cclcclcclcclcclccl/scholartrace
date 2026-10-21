import asyncio

import pytest
from fastapi.testclient import TestClient

from backend import (
    accounts,
    background_answers,
    database,
    jobs,
    projects,
    research,
    store,
)
from backend.app import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "main.sqlite3")
    monkeypatch.setattr(accounts, "AUTH_PATH", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(
        accounts, "path", lambda identifier: tmp_path / identifier / "library.sqlite3"
    )
    database.initialize()
    with store.connection() as c:
        for identifier in ["a", "b"]:
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
    return tmp_path


def pending(payload):
    import json

    with store.connection() as c:
        c.execute(
            "INSERT INTO jobs(id,kind,payload) VALUES('job','ask',?)",
            (json.dumps(payload),),
        )
    return "job"


def result(identifier):
    return {
        "claims": [],
        "evidence": [],
        "subquestions": [
            {
                "id": "Q1",
                "question": "Missing?",
                "status": "unresolved",
                "claim_count": 0,
            }
        ],
        "limitations": "No supported answer",
        "document_id": identifier,
    }


def test_retry_resumes_completed_papers_and_links_final_project(workspace, monkeypatch):
    project = projects.create(
        projects.ProjectInput(title="Project", document_ids=["a", "b"])
    )
    payload = {
        "question": "Question?",
        "document_ids": ["a", "b"],
        "project_id": project["id"],
    }
    identifier = pending(payload)
    calls = []

    async def grounded(question, ids, ctx):
        calls.append(ids[0])
        ctx.log("checking actual stage")
        if ids == ["b"] and calls.count("b") == 1:
            raise ValueError("model temporarily unavailable")
        return result(ids[0])

    monkeypatch.setattr(research, "grounded", grounded)
    asyncio.run(jobs.run(identifier))
    assert jobs.get(identifier)["state"] == "failed"
    assert [p["document_id"] for p in background_answers.checkpoints(identifier)] == [
        "a"
    ]
    with store.connection() as c:
        c.execute("UPDATE jobs SET state='queued' WHERE id=?", (identifier,))
    asyncio.run(jobs.run(identifier))
    job = jobs.get(identifier)
    assert job["state"] == "completed"
    assert calls == ["a", "b", "b"]
    output = research.artifact(job["result"]["id"])
    assert [s["document_id"] for s in output["content"]["sections"]] == ["a", "b"]
    assert output["content"]["project_context"]["id"] == project["id"]
    assert projects.detail(project["id"])["artifacts"][0]["id"] == output["id"]
    # Simulate worker loss after final artifact was saved, before completion update.
    with store.connection() as c:
        c.execute(
            "UPDATE jobs SET state='interrupted',result=NULL WHERE id=?", (identifier,)
        )
    asyncio.run(jobs.run(identifier))
    assert jobs.get(identifier)["result"]["id"] == output["id"]
    assert calls == ["a", "b", "b"]
    with store.connection() as c:
        assert c.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 1


def test_cancel_keeps_completed_paper_for_restart(workspace, monkeypatch):
    identifier = pending({"question": "Question?", "document_ids": ["a", "b"]})
    calls = []

    async def grounded(question, ids, ctx):
        calls.append(ids[0])
        with store.connection() as c:
            c.execute("UPDATE jobs SET cancel_requested=1 WHERE id=?", (identifier,))
        return result(ids[0])

    monkeypatch.setattr(research, "grounded", grounded)
    asyncio.run(jobs.run(identifier))
    assert jobs.get(identifier)["state"] == "cancelled"
    assert calls == ["a"]
    assert len(background_answers.checkpoints(identifier)) == 1


def test_background_api_rejects_empty_outside_archived_and_reuses_pending(
    workspace, monkeypatch
):
    monkeypatch.setattr(jobs, "schedule", lambda _: None)
    with TestClient(app) as client:
        project = client.post(
            "/api/projects", json={"title": "test", "document_ids": ["a"]}
        ).json()
        base = {
            "kind": "ask",
            "payload": {
                "question": "Question?",
                "document_ids": ["a"],
                "project_id": project["id"],
            },
        }
        for payload in [
            {"question": " ", "document_ids": ["a"]},
            {"question": "Question?", "document_ids": []},
            {
                "question": "Question?",
                "document_ids": ["b"],
                "project_id": project["id"],
            },
        ]:
            assert (
                client.post(
                    "/api/jobs", json={"kind": "ask", "payload": payload}
                ).status_code
                == 422
            )
        first = client.post("/api/jobs", json=base)
        assert first.status_code == 200
        assert client.post("/api/jobs", json=base).json()["id"] == first.json()["id"]
        assert (
            client.get("/api/jobs/" + first.json()["id"] + "/answer-parts").json() == []
        )
        with store.connection() as c:
            c.execute("UPDATE documents SET archived=1 WHERE id='b'")
        assert (
            client.post(
                "/api/jobs",
                json={
                    "kind": "ask",
                    "payload": {"question": "Question?", "document_ids": ["b"]},
                },
            ).status_code
            == 422
        )


def test_checkpoints_are_account_scoped(workspace, monkeypatch):
    identifier = pending({"question": "Question?", "document_ids": ["a"]})
    with store.connection() as c:
        c.execute(
            "INSERT INTO answer_checkpoints VALUES(?,?,?,CURRENT_TIMESTAMP)",
            (identifier, "a", '{"document_id":"a"}'),
        )
    assert background_answers.checkpoints(identifier)
    token = store.database_override.set(workspace / "other.sqlite3")
    try:
        database.initialize()
        with pytest.raises(KeyError):
            background_answers.checkpoints(identifier)
    finally:
        store.database_override.reset(token)
