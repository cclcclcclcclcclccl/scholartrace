import uuid

import pymupdf
import pytest
import test_recall
from fastapi.testclient import TestClient

from backend import audit, store
from backend.app import app

workspace = test_recall.workspace


@pytest.fixture
def comparison(workspace, tmp_path):
    path = tmp_path / "second.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text(
            (40, 80),
            "A different experiment used 120 participants under laboratory conditions.",
        )
        pdf.save(path)
    paper = store.import_pdf(path)
    second = audit.save_note(
        store.get_blocks(paper["id"])[0]["id"], "Second study conditions"
    )
    return workspace[1], second


def spec(notes):
    return {
        "request_id": str(uuid.uuid4()),
        "title": "Boundary verification",
        "note_ids": [n["id"] for n in notes],
    }


def test_create_snapshot_and_idempotence(comparison):
    with TestClient(app) as c:
        body = spec(comparison)
        response = c.post("/api/boundaries", json=body)
        assert response.status_code == 200
        table = response.json()
        assert c.post("/api/boundaries", json=body).json() == table
        assert (
            c.post("/api/boundaries", json={**body, "title": "Other title"}).status_code
            == 409
        )
        assert len(table["content"]["papers"]) == 2
        assert all(
            v is None for p in table["content"]["papers"] for v in p["cells"].values()
        )
        c.patch(
            f"/api/notes/{comparison[0]['id']}",
            json={"note": "Changed", "archived": True},
        )
        assert c.get(f"/api/boundaries/{table['id']}").json() == table


def test_cell_save_clear_and_conflict_preserve_other_values(comparison):
    with TestClient(app) as c:
        table = c.post("/api/boundaries", json=spec(comparison)).json()
        p = table["content"]["papers"][0]
        url = f"/api/boundaries/{table['id']}/cells/{p['document_id']}/data"
        body = {
            "revision": 1,
            "value": "73 evaluation samples",
            "quote": comparison[0]["quote"],
            "note_id": comparison[0]["id"],
        }
        saved = c.patch(url, json=body).json()
        assert (
            saved["revision"] == 2
            and saved["content"]["papers"][0]["cells"]["data"]["value"] == body["value"]
        )
        assert saved["content"]["papers"][1] == table["content"]["papers"][1]
        assert (
            c.patch(url, json={**body, "value": "stale overwrite"}).status_code == 409
        )
        assert c.get(f"/api/boundaries/{table['id']}").json() == saved
        cleared = c.patch(url, json={"revision": 2}).json()
        assert cleared["content"]["papers"][0]["cells"]["data"] is None


@pytest.mark.parametrize(
    "kind", ["fabrication", "wrong_source", "no_quote", "bad_field", "bad_document"]
)
def test_invalid_cell_does_not_change_table(comparison, kind):
    with TestClient(app) as c:
        table = c.post("/api/boundaries", json=spec(comparison)).json()
        doc = table["content"]["papers"][0]["document_id"]
        field = "data"
        body = {
            "revision": 1,
            "value": "73 samples",
            "quote": comparison[0]["quote"],
            "note_id": comparison[0]["id"],
        }
        if kind == "fabrication":
            body["quote"] = "An invented finding never reported."
        elif kind == "wrong_source":
            body["note_id"] = comparison[1]["id"]
            body["quote"] = comparison[1]["quote"]
        elif kind == "no_quote":
            body["quote"] = ""
        elif kind == "bad_field":
            field = "invented"
        else:
            doc = "missing"
        assert c.patch(
            f"/api/boundaries/{table['id']}/cells/{doc}/{field}", json=body
        ).status_code == (404 if kind == "bad_document" else 422)
        assert c.get(f"/api/boundaries/{table['id']}").json() == table


@pytest.mark.parametrize(
    "kind", ["same_paper", "duplicate", "missing", "archived", "forged"]
)
def test_creation_requires_valid_sources_from_distinct_papers(comparison, kind):
    with TestClient(app) as c:
        body = spec(comparison)
        if kind == "same_paper":
            note = audit.save_note(comparison[0]["block_id"], "Another observation")
            body["note_ids"] = [comparison[0]["id"], note["id"]]
        elif kind == "duplicate":
            body["note_ids"] = [comparison[0]["id"]] * 2
        elif kind == "missing":
            body["note_ids"][-1] = 9999999
        elif kind == "archived":
            c.patch(f"/api/notes/{comparison[0]['id']}", json={"archived": True})
        else:
            with store.connection() as conn:
                conn.execute(
                    "UPDATE evidence_notes SET quote=? WHERE id=?",
                    ("Forged evidence", comparison[0]["id"]),
                )
        assert c.post("/api/boundaries", json=body).status_code == (
            404 if kind == "missing" else 422
        )
        assert c.get("/api/boundaries").json()["total"] == 0


def test_export_keeps_missing_and_account_isolation(comparison):
    with TestClient(app) as c:
        table = c.post("/api/boundaries", json=spec(comparison)).json()
        p = table["content"]["papers"][0]
        url = f"/api/boundaries/{table['id']}"
        save = c.patch(
            f"{url}/cells/{p['document_id']}/data",
            json={
                "revision": 1,
                "value": "73 samples",
                "quote": comparison[0]["quote"],
                "note_id": comparison[0]["id"],
            },
        )
        assert save.status_code == 200
        md = c.get(url + "/export").text
        assert (
            comparison[0]["quote"] in md
            and comparison[0]["block_id"] in md
            and "待补查（不代表论文未报告）" in md
        )
        assert c.get(url + "/export?format=json").json() == save.json()
        assert (
            c.post(
                "/api/account/register",
                json={"name": "boundary-private", "password": "separate-private-test"},
            ).status_code
            == 200
        )
        assert c.get("/api/boundaries").json()["total"] == 0
        for suffix in ("", "/export"):
            assert c.get(url + suffix).status_code == 404
        assert (
            c.patch(
                f"{url}/cells/{p['document_id']}/data", json={"revision": 2}
            ).status_code
            == 404
        )
