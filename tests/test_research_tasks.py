import io
import json
import zipfile

import pytest
import test_boundaries
from fastapi.testclient import TestClient

from backend import audit, database, store
from backend.app import app

workspace = test_boundaries.workspace
comparison = test_boundaries.comparison


@pytest.fixture
def setup(comparison):
    with TestClient(app) as c:
        table = c.post("/api/boundaries", json=test_boundaries.spec(comparison)).json()
        project = c.post(
            "/api/projects",
            json={
                "title": "Gap research project",
                "document_ids": [p["document_id"] for p in table["content"]["papers"]],
            },
        ).json()
        body = {
            "project_id": project["id"],
            "comparison_id": table["id"],
            "document_id": table["content"]["papers"][0]["document_id"],
            "field": "data",
            "comparison_revision": table["revision"],
        }
        response = c.post("/api/research-tasks", json=body)
        assert response.status_code == 200
        yield c, table, project, body, response.json(), comparison


def completion(task, note):
    return {
        "revision": task["revision"],
        "comparison_revision": task["comparison_revision"],
        "note_id": note["id"],
        "value": "73 evaluation samples; check study conditions",
        "quote": note["quote"],
    }


def test_creation_is_idempotent_and_exports_include_project_tasks(setup):
    c, table, project, body, task, _notes = setup
    assert c.post("/api/research-tasks", json=body).json() == task
    assert c.get(f"/api/research-tasks?project_id={project['id']}").json()["total"] == 1
    assert (
        c.get(f"/api/research-tasks?comparison_id={table['id']}").json()["items"][0][
            "id"
        ]
        == task["id"]
    )
    assert (
        c.get(f"/api/projects/{project['id']}/export").json()["research_tasks"][0]["id"]
        == task["id"]
    )
    bundle = c.get(f"/api/projects/{project['id']}/bundle")
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as z:
        assert (
            json.loads(z.read("research_tasks.json"))[0]["events"][0]["state"] == "todo"
        )
        assert json.loads(z.read("evidence_comparisons.json"))[0]["id"] == table["id"]


def test_complete_adds_new_source_and_reopen_retains_cell_and_history(setup):
    c, table, _project, _body, task, notes = setup
    new = audit.save_note(notes[0]["block_id"], "New investigation evidence")
    payload = completion(task, new)
    r = c.post(f"/api/research-tasks/{task['id']}/complete", json=payload)
    assert r.status_code == 200
    done = r.json()
    assert done["state"] == "done" and len(done["events"]) == 2
    saved = c.get(f"/api/boundaries/{table['id']}").json()
    assert saved["revision"] == 2
    assert saved["content"]["papers"][0]["cells"]["data"]["note_id"] == new["id"]
    assert new["id"] in saved["content"]["note_ids"]
    assert (
        c.post(f"/api/research-tasks/{task['id']}/complete", json=payload).status_code
        == 409
    )
    reopened = c.patch(
        f"/api/research-tasks/{task['id']}", json={"revision": 2, "state": "todo"}
    ).json()
    assert reopened["evidence"] == done["evidence"] and len(reopened["events"]) == 3
    assert c.get(f"/api/boundaries/{table['id']}").json() == saved
    assert (
        c.post(
            f"/api/research-tasks/{task['id']}/complete", json=completion(reopened, new)
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "kind",
    [
        "wrong_paper",
        "forged",
        "empty",
        "archived_note",
        "stale_task",
        "stale_table",
        "filled_cell",
    ],
)
def test_bad_completion_never_partially_writes(setup, kind):
    c, table, project, body, task, notes = setup
    payload = completion(task, notes[0])
    if kind == "wrong_paper":
        payload.update(note_id=notes[1]["id"], quote=notes[1]["quote"])
    elif kind == "forged":
        payload["quote"] = "A result that does not exist"
    elif kind == "empty":
        payload["value"] = "   "
    elif kind == "archived_note":
        c.patch(f"/api/notes/{notes[0]['id']}", json={"archived": True})
    elif kind == "stale_task":
        c.patch(
            f"/api/research-tasks/{task['id']}",
            json={"revision": 1, "state": "working"},
        )
    else:
        c.patch(
            f"/api/boundaries/{table['id']}/cells/{body['document_id']}/data",
            json={
                "revision": 1,
                "value": "Another explanation",
                "quote": notes[0]["quote"],
                "note_id": notes[0]["id"],
            },
        )
        if kind == "filled_cell":
            payload["comparison_revision"] = 2
    before = c.get(f"/api/boundaries/{table['id']}").json()
    previous = c.get(f"/api/research-tasks?project_id={project['id']}").json()
    assert c.post(
        f"/api/research-tasks/{task['id']}/complete", json=payload
    ).status_code in {409, 422}
    assert c.get(f"/api/boundaries/{table['id']}").json() == before
    assert c.get(f"/api/research-tasks?project_id={project['id']}").json() == previous


def test_unresolved_close_requires_reason_and_keeps_gap(setup):
    c, table, _project, _body, task, _notes = setup
    url = f"/api/research-tasks/{task['id']}"
    assert c.patch(url, json={"revision": 1, "state": "dismissed"}).status_code == 422
    result = c.patch(
        url,
        json={
            "revision": 1,
            "state": "dismissed",
            "outcome": "No evidence found in selected passages",
        },
    ).json()
    assert result["state"] == "dismissed" and result["evidence"] is None
    assert c.get(f"/api/boundaries/{table['id']}").json() == table


@pytest.mark.parametrize(
    "kind", ["project_archived", "comparison_archived", "removed_source"]
)
def test_scope_changes_block_mutation_preserve_history(setup, kind):
    c, table, project, _body, task, notes = setup
    if kind == "comparison_archived":
        assert (
            c.patch(
                f"/api/boundaries/{table['id']}", json={"revision": 1, "archived": True}
            ).status_code
            == 200
        )
        assert c.get("/api/boundaries").json()["total"] == 0
        assert c.get("/api/boundaries?archived=true").json()["total"] == 1
    else:
        with store.connection() as conn:
            if kind == "project_archived":
                conn.execute(
                    "UPDATE projects SET archived=1 WHERE id=?", (project["id"],)
                )
            else:
                conn.execute(
                    "DELETE FROM project_documents WHERE project_id=?", (project["id"],)
                )
    assert (
        c.patch(
            f"/api/research-tasks/{task['id']}",
            json={"revision": 1, "state": "working"},
        ).status_code
        == 409
    )
    assert (
        c.post(
            f"/api/research-tasks/{task['id']}/complete",
            json=completion(task, notes[0]),
        ).status_code
        == 409
    )
    assert (
        c.get(f"/api/research-tasks?project_id={project['id']}").json()["items"][0][
            "events"
        ]
        == task["events"]
    )


def test_archive_migration_restore_and_conflicts(setup):
    c, table, _project, body, _task, _notes = setup
    with store.connection() as conn:
        conn.execute("ALTER TABLE evidence_comparisons DROP COLUMN archived")
        old = dict(conn.execute("SELECT * FROM evidence_comparisons").fetchone())
    database.initialize()
    database.initialize()
    with store.connection() as conn:
        new = dict(conn.execute("SELECT * FROM evidence_comparisons").fetchone())
        assert new.pop("archived") == 0 and new == old
    url = f"/api/boundaries/{table['id']}"
    archived = c.patch(url, json={"revision": 1, "archived": True}).json()
    assert c.patch(url, json={"revision": 1, "archived": False}).status_code == 409
    assert (
        c.patch(
            f"{url}/cells/{body['document_id']}/data", json={"revision": 2}
        ).status_code
        == 422
    )
    restored = c.patch(url, json={"revision": 2, "archived": False}).json()
    assert restored["content"] == archived["content"] == table["content"]


def test_other_account_cannot_access_or_complete_task(setup):
    c, _table, project, body, task, notes = setup
    assert (
        c.post(
            "/api/account/register",
            json={"name": "gap-private", "password": "separate-private-password"},
        ).status_code
        == 200
    )
    assert c.get(f"/api/research-tasks?project_id={project['id']}").status_code == 404
    assert c.post("/api/research-tasks", json=body).status_code == 404
    assert (
        c.patch(
            f"/api/research-tasks/{task['id']}",
            json={"revision": 1, "state": "working"},
        ).status_code
        == 404
    )
    assert (
        c.post(
            f"/api/research-tasks/{task['id']}/complete",
            json=completion(task, notes[0]),
        ).status_code
        == 404
    )
