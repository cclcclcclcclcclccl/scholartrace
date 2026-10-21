"""Stabilization regressions use isolated account databases, never the user library."""

import asyncio
import copy
import hashlib
import importlib
import io
import json
import zipfile

from test_projects import client as project_client
from test_projects import create, edit_payload

from backend import features, jobs, research, store

client = project_client


def insert_job(identifier, kind="ask", payload=None, state="completed"):
    with store.connection() as conn:
        conn.execute(
            "INSERT INTO jobs(id,kind,payload,state) VALUES(?,?,?,?)",
            (identifier, kind, json.dumps(payload or {}), state),
        )


def test_old_ask_not_hidden_by_other_tasks_and_cursor_stable(client):
    for i in range(65):
        insert_job(f"ask-{i}")
    for i in range(110):
        insert_job(f"other-{i}", "review")
    first = client.get("/api/jobs-page?kind=ask").json()
    assert len(first["items"]) == 50
    assert first["items"][0]["id"] == "ask-64"
    insert_job("new-ask")
    second = client.get(
        "/api/jobs-page", params={"kind": "ask", "before": first["next_before"]}
    ).json()
    ids = [j["id"] for j in first["items"] + second["items"]]
    assert len(ids) == len(set(ids)) == 65
    assert second["next_before"] is None
    assert client.get("/api/jobs-page?before=-1").status_code == 422
    assert (
        client.post(
            "/api/account/register",
            json={"name": "history-user", "password": "long-password-123"},
        ).status_code
        == 200
    )
    assert client.get("/api/jobs-page").json()["items"] == []


def test_dedup_uses_all_active_jobs_and_ignores_cancelling(client, monkeypatch):
    body = features.TaskRequest(
        kind="ask", payload={"question": "What is the method?", "document_ids": ["a"]}
    )
    payload = body.payload.model_dump(exclude_none=True)
    insert_job("old-active", "ask", payload, "running")
    for i in range(110):
        insert_job(f"new-{i}", "review")
    monkeypatch.setattr(
        jobs,
        "submit",
        lambda *args: (_ for _ in ()).throw(AssertionError("duplicate submitted")),
    )
    response = client.post("/api/jobs", json=body.model_dump())
    assert response.status_code == 200, response.text
    assert response.json()["id"] == "old-active"
    with store.connection() as c:
        c.execute("UPDATE jobs SET cancel_requested=1 WHERE id='old-active'")
    assert jobs.matching_active("ask", payload) is None


def test_note_conflict_preserves_quote_history_and_saved_text(client):
    assert (
        client.patch(
            "/api/notes/1",
            json={"note": "new observation", "expected_note": "source note"},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            "/api/notes/1", json={"note": "stale draft", "expected_note": "source note"}
        ).status_code
        == 409
    )
    with store.connection() as conn:
        note = dict(conn.execute("SELECT * FROM evidence_notes WHERE id=1").fetchone())
        history = [dict(r) for r in conn.execute("SELECT * FROM note_history")]
    assert note["note"] == "new observation"
    assert note["quote"] == "Original evidence a"
    assert len(history) == 1 and history[0]["previous_text"] == "source note"
    assert (
        client.patch("/api/notes/1", json={"note": "legacy client"}).status_code == 200
    )


def test_bundle_full_outputs_notes_history_jobs_hashes_and_isolation(client):
    project = create(client)
    content = {
        "draft": {"text": "saved manuscript", "revision": 2},
        "draft_history": [{"text": "first draft"}],
    }
    item = research.save_artifact("writing", "Test", content)
    assert (
        client.patch(
            "/api/projects/" + project["id"],
            json=edit_payload(project, artifact_ids=[item["id"]]),
        ).status_code
        == 200
    )
    assert (
        client.patch(
            "/api/notes/1", json={"note": "revised", "archived": True}
        ).status_code
        == 200
    )
    for i in range(31):
        insert_job(f"project-{i}", payload={"project_id": project["id"]})
    insert_job("unrelated", payload={"project_id": "another"})
    with store.connection() as conn:
        conn.execute("UPDATE documents SET archived=1 WHERE id='a'")
    response = client.get("/api/projects/" + project["id"] + "/bundle")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        assert z.testzip() is None
        manifest = json.loads(z.read("manifest.json"))
        assert manifest["artifact_count"] == 1 and manifest["job_count"] == 31
        for f in manifest["files"]:
            data = z.read(f["name"])
            assert (
                len(data) == f["bytes"]
                and hashlib.sha256(data).hexdigest() == f["sha256"]
            )
        assert json.loads(z.read("artifacts/0001.json"))["content"] == content
        notes = json.loads(z.read("notes.json"))
        assert (
            notes[0]["archived"] == 1
            and notes[0]["history"][0]["previous_text"] == "source note"
        )
        exported = json.loads(z.read("project.json"))
        assert "a" in exported["document_ids"]
        assert all("path" not in d for d in exported["documents"])
        assert len(json.loads(z.read("jobs.json"))) == 31
    assert (
        client.post(
            "/api/account/register",
            json={"name": "bundle-user", "password": "long-password-123"},
        ).status_code
        == 200
    )
    assert client.get("/api/projects/" + project["id"] + "/bundle").status_code == 404


def test_audit_continuation_checks_requested_only_and_rejects_foreign(
    client, monkeypatch
):
    module = importlib.import_module("backend.app")
    rows = [
        {"note": {"id": i, "quote": "evidence", "note": "observation"}}
        for i in range(1, 16)
    ]
    monkeypatch.setattr(
        module.audit, "audit_against", lambda _: {"results": copy.deepcopy(rows)}
    )
    called = []

    async def review(item, *args):
        called.append(item["note"]["id"])
        return {"status": "checked", "decision": "same_claim"}

    monkeypatch.setattr(module, "review_change", review)
    response = client.post(
        "/api/versions/audit",
        json={"target_document_id": "a", "note_ids": [13, 14, 15]},
    )
    assert response.status_code == 200, response.text
    assert called == [13, 14, 15]
    assert all(
        row["semantic_review"]["status"] == "not_checked"
        for row in response.json()["results"][:12]
    )
    called.clear()
    assert (
        client.post(
            "/api/versions/audit", json={"target_document_id": "a", "note_ids": [100]}
        ).status_code
        == 422
    )
    assert called == []
    for invalid in [[], [-1], list(range(1, 14))]:
        assert (
            client.post(
                "/api/versions/audit",
                json={"target_document_id": "a", "note_ids": invalid},
            ).status_code
            == 422
        )


def test_audit_budget_returns_completed_and_unchecked_rows(client, monkeypatch):
    module = importlib.import_module("backend.app")
    monkeypatch.setattr(
        module.audit,
        "audit_against",
        lambda _: {"results": [{"note": {"id": 1}}, {"note": {"id": 2}}]},
    )

    async def review(item, *args):
        if item["note"]["id"] == 2:
            raise TimeoutError()
        return {"status": "checked", "decision": "same_claim"}

    monkeypatch.setattr(module, "review_change", review)
    result = asyncio.run(
        module.audit_version(module.AuditTarget(target_document_id="a"))
    )
    assert result["time_budget_exhausted"]
    assert result["results"][0]["semantic_review"]["status"] == "checked"
    assert result["results"][1]["semantic_review"]["status"] == "not_checked"


def test_impact_continues_original_snapshot_without_new_artifact_drift(
    client, monkeypatch
):
    from backend import impact

    with store.connection() as conn:
        conn.execute("UPDATE documents SET arxiv_id='1234.5678' WHERE id IN ('a','b')")
    claims = [
        {
            "block_id": "a-block",
            "document_id": "a",
            "text": f"claim {i}",
            "quote": "Original evidence a",
            "page": 1,
        }
        for i in range(35)
    ]
    research.save_artifact("review", "Initial review", {"claims": claims})

    class Context:
        def progress(self, *args):
            pass

    def align(claim, *args):
        return {
            "note": claim,
            "candidate": None,
            "status": "unresolved",
            "explanation": "not aligned",
        }

    monkeypatch.setattr(impact, "align", align)
    first = asyncio.run(impact.impact(Context(), {"document_id": "b"}))
    first = research.artifact(first["id"])
    assert first["content"]["checked"] == 30
    assert len(first["content"]["pending_dependencies"]) == 5
    research.save_artifact(
        "review",
        "New unrelated-to-snapshot output",
        {"claims": [dict(claims[0], text="later claim")]},
    )
    second = asyncio.run(
        impact.impact(Context(), {"document_id": "b", "impact_from": first["id"]})
    )
    second = research.artifact(second["id"])
    assert (
        second["content"]["checked"] == 5 and second["content"]["checked_before"] == 30
    )
    assert second["content"]["total_dependencies"] == 35
    assert second["content"]["pending_dependencies"] == []
    checked = [
        i["note"]["text"] for r in (first, second) for i in r["content"]["impact"]
    ]
    assert len(set(checked)) == 35 and "later claim" not in checked
    assert (
        client.post(
            "/api/jobs",
            json={
                "kind": "impact",
                "payload": {"document_id": "c", "impact_from": first["id"]},
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/jobs",
            json={
                "kind": "impact",
                "payload": {"document_id": "b", "impact_from": second["id"]},
            },
        ).status_code
        == 422
    )
