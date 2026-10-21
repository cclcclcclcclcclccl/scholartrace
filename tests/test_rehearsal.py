import uuid

import pytest
import test_recall
from fastapi.testclient import TestClient

from backend import database, store
from backend.app import app

workspace = test_recall.workspace
create_card = test_recall.create


def spec(note):
    return {
        "request_id": str(uuid.uuid4()),
        "title": "Evidence rehearsal",
        "note_ids": [note["id"]],
    }


def test_snapshot_idempotence_and_export(workspace):
    note = workspace[1]
    with TestClient(app) as c:
        body = spec(note)
        first = c.post("/api/rehearsal", json=body).json()
        assert c.post("/api/rehearsal", json=body).json() == first
        assert (
            c.post(
                "/api/rehearsal", json={**body, "title": "Changed title"}
            ).status_code
            == 409
        )
        rounds = first["content"]["rounds"]
        assert len(rounds) == 3
        assert all(
            r["source"]["quote"] == note["quote"] and r["answer"] == "" for r in rounds
        )
        c.patch(
            f"/api/notes/{note['id']}",
            json={"note": "Changed observation", "archived": True},
        )
        assert c.get(f"/api/rehearsal/{first['id']}").json() == first
        md = c.get(f"/api/rehearsal/{first['id']}/export").text
        assert note["quote"] in md and note["block_id"] in md and "尚未填写" in md
        assert c.get(f"/api/rehearsal/{first['id']}/export?format=json").json() == first


def test_save_round_conflicts_and_validation(workspace):
    with TestClient(app) as c:
        session = c.post("/api/rehearsal", json=spec(workspace[1])).json()
        url = f"/api/rehearsal/{session['id']}/rounds/1"
        body = {
            "revision": 1,
            "answer": "73 samples; generalization unknown",
            "checks": ["source", "source"],
        }
        saved = c.patch(url, json=body).json()
        assert saved["revision"] == 2
        assert saved["content"]["rounds"][1]["checks"] == ["source"]
        assert saved["content"]["rounds"][0] == session["content"]["rounds"][0]
        assert (
            c.patch(url, json={**body, "answer": "stale overwrite"}).status_code == 409
        )
        assert c.get(f"/api/rehearsal/{session['id']}").json() == saved
        for changes in (
            {"checks": ["correctness"]},
            {"answer": "x" * 6001},
            {"revision": 0},
        ):
            assert c.patch(url, json={**body, **changes}).status_code == 422
        assert c.patch(url[:-1] + "9", json={**body, "revision": 2}).status_code == 422


@pytest.mark.parametrize(
    "kind", ["missing", "archived", "forged", "duplicates", "empty", "too_many"]
)
def test_invalid_sources_are_rejected(workspace, kind):
    note = workspace[1]
    with TestClient(app) as c:
        body = spec(note)
        if kind == "missing":
            body["note_ids"] = [9999999]
        elif kind == "archived":
            c.patch(f"/api/notes/{note['id']}", json={"archived": True})
        elif kind == "forged":
            with store.connection() as conn:
                conn.execute(
                    "UPDATE evidence_notes SET quote=? WHERE id=?",
                    ("A fabricated finding", note["id"]),
                )
        elif kind == "duplicates":
            body["note_ids"] *= 2
        elif kind == "empty":
            body["note_ids"] = []
        elif kind == "too_many":
            body["note_ids"] *= 4
        assert c.post("/api/rehearsal", json=body).status_code == (
            404 if kind == "missing" else 422
        )
        assert c.get("/api/rehearsal").json()["total"] == 0


def test_account_isolation_for_read_write_export_and_cards(workspace):
    with TestClient(app) as c:
        session = c.post("/api/rehearsal", json=spec(workspace[1])).json()
        card = create_card(c, workspace[1])
        assert (
            c.post(
                "/api/account/register",
                json={"name": "rehearsal-private", "password": "separate-password"},
            ).status_code
            == 200
        )
        assert c.get("/api/rehearsal").json()["total"] == 0
        for suffix in ("", "/export"):
            assert c.get(f"/api/rehearsal/{session['id']}{suffix}").status_code == 404
        assert (
            c.patch(
                f"/api/rehearsal/{session['id']}/rounds/0",
                json={"revision": 1, "answer": "overwrite"},
            ).status_code
            == 404
        )
        assert (
            c.patch(
                f"/api/recall/{card['id']}", json={"revision": 1, "archived": True}
            ).status_code
            == 404
        )


def test_card_edit_archive_restore_preserves_evidence_and_schedule(workspace):
    with TestClient(app) as c:
        card = create_card(c, workspace[1])
        c.post(
            f"/api/recall/{card['id']}/review", json={"revision": 1, "rating": "good"}
        )
        before = c.get("/api/recall").json()["cards"][0]
        url = f"/api/recall/{card['id']}"
        assert (
            c.patch(
                url,
                json={
                    "revision": 2,
                    "prompt": "A revised evidence question",
                    "archived": True,
                },
            ).status_code
            == 200
        )
        deck = c.get("/api/recall").json()
        assert deck["cards"] == [] and len(deck["archived_cards"]) == 1
        assert c.get("/api/recall/export?format=json").json() == []
        assert (
            c.post(url + "/review", json={"revision": 3, "rating": "good"}).status_code
            == 422
        )
        assert (
            c.patch(url, json={"revision": 2, "prompt": "stale change"}).status_code
            == 409
        )
        assert create_card(c, workspace[1])["archived"] == 1
        assert c.patch(url, json={"revision": 3, "archived": False}).status_code == 200
        after = c.get("/api/recall").json()["cards"][0]
        for key in (
            "quote",
            "observation",
            "due_at",
            "reviews",
            "interval_days",
            "last_rating",
        ):
            assert after[key] == before[key]
        assert after["prompt"] == "A revised evidence question"
        assert c.patch(url, json={"revision": 4, "prompt": "   "}).status_code == 422


def test_previous_schema_migrates_without_changing_cards_or_reviews(workspace):
    with TestClient(app) as c:
        card = create_card(c, workspace[1])
        c.post(
            f"/api/recall/{card['id']}/review", json={"revision": 1, "rating": "hard"}
        )
    with store.connection() as conn:
        conn.execute("ALTER TABLE recall_cards DROP COLUMN archived")
        old = dict(conn.execute("SELECT * FROM recall_cards").fetchone())
        reviews = [dict(r) for r in conn.execute("SELECT * FROM recall_reviews")]
    database.initialize()
    database.initialize()
    with store.connection() as conn:
        new = dict(conn.execute("SELECT * FROM recall_cards").fetchone())
        assert new.pop("archived") == 0 and new == old
        assert reviews == [
            dict(r) for r in conn.execute("SELECT * FROM recall_reviews")
        ]
