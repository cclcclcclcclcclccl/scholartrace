from datetime import UTC, datetime, timedelta

import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend import accounts, audit, database, recall, retrieval, store
from backend.app import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "library.sqlite3")
    monkeypatch.setattr(accounts, "AUTH_PATH", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(
        accounts, "path", lambda identifier: tmp_path / identifier / "library.sqlite3"
    )
    database.initialize()
    path = tmp_path / "recall.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((40, 60), "The experiment used 73 samples.")
        page.insert_text(
            (40, 150), "Controls: 173 samples, 73.5 percent and -73 units."
        )
        page.insert_text((40, 240), "The threshold was 0.73 and the change was -2.5%.")
        pdf.save(path)
    paper = store.import_pdf(path)
    note = audit.save_note(
        store.get_blocks(paper["id"])[0]["id"],
        "An observation <script>never run</script>\twith a tab",
    )
    return paper, note


def create(client, note):
    response = client.post(
        "/api/recall",
        json={
            "note_id": note["id"],
            "prompt": "How many samples, and under which conditions?",
        },
    )
    assert response.status_code == 200
    return response.json()["card"]


def test_card_snapshots_source_deduplicates_and_retains_updated_note(workspace):
    paper, note = workspace
    before = store.get_blocks(paper["id"])
    with TestClient(app) as client:
        card = create(client, note)
        again = client.post(
            "/api/recall",
            json={"note_id": note["id"], "prompt": "A different question"},
        ).json()
        assert again["already_exists"] and again["card"]["id"] == card["id"]
        assert again["card"]["prompt"] == card["prompt"]
        client.patch(f"/api/notes/{note['id']}", json={"note": "Updated observation"})
        saved = client.get("/api/recall").json()["cards"][0]
        assert saved["observation"] == note["note"] and saved["quote"] == note["quote"]
        assert saved["block_id"] == note["block_id"] and saved["due"]
        assert store.get_blocks(paper["id"]) == before


@pytest.mark.parametrize(
    "rating,delta",
    [
        ("again", timedelta(minutes=10)),
        ("hard", timedelta(days=1)),
        ("good", timedelta(days=3)),
    ],
)
def test_self_rating_schedule_and_double_submit_protection(
    workspace, monkeypatch, rating, delta
):
    moment = datetime(2026, 10, 20, 6, tzinfo=UTC)
    monkeypatch.setattr(recall, "now", lambda: moment)
    with TestClient(app) as client:
        card = create(client, workspace[1])
        body = {"revision": card["revision"], "rating": rating}
        result = client.post(f"/api/recall/{card['id']}/review", json=body)
        assert datetime.fromisoformat(result.json()["due_at"]) == moment + delta
        assert (
            client.post(f"/api/recall/{card['id']}/review", json=body).status_code
            == 409
        )
        deck = client.get("/api/recall").json()
        assert deck["due_count"] == 0 and deck["review_count"] == 1
        monkeypatch.setattr(recall, "now", lambda: moment + delta)
        assert client.get("/api/recall").json()["due_count"] == 1


def test_archive_hides_card_and_restore_preserves_progress(workspace):
    with TestClient(app) as client:
        card = create(client, workspace[1])
        client.patch(f"/api/notes/{workspace[1]['id']}", json={"archived": True})
        assert client.get("/api/recall").json()["hidden_count"] == 1
        assert (
            client.post(
                f"/api/recall/{card['id']}/review",
                json={"revision": 1, "rating": "good"},
            ).status_code
            == 422
        )
        assert client.get("/api/recall/export?format=json").json() == []
        client.patch(f"/api/notes/{workspace[1]['id']}", json={"archived": False})
        assert client.get("/api/recall").json()["cards"][0]["id"] == card["id"]


def test_exports_keep_source_and_escape_anki_html(workspace):
    with TestClient(app) as client:
        card = create(client, workspace[1])
        tsv = client.get("/api/recall/export?format=tsv").text
        assert "<script>" not in tsv and "&lt;script&gt;" in tsv
        row = tsv.splitlines()[-1]
        assert len(row.split("\t")) == 3
        assert card["block_id"] in tsv and "73 samples" in tsv
        markdown = client.get("/api/recall/export?format=md").text
        assert card["quote"] in markdown and card["block_id"] in markdown


def test_account_cannot_read_or_rate_other_space_card(workspace):
    with TestClient(app) as client:
        card = create(client, workspace[1])
        assert (
            client.post(
                "/api/account/register",
                json={"name": "recall-isolated", "password": "separate-account-test"},
            ).status_code
            == 200
        )
        assert client.get("/api/recall").json()["cards"] == []
        assert (
            client.post(
                f"/api/recall/{card['id']}/review",
                json={"revision": 1, "rating": "good"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/recall",
                json={"note_id": workspace[1]["id"], "prompt": "Other space note"},
            ).status_code
            == 404
        )


def test_card_refuses_unverified_source_quote(workspace):
    with store.connection() as conn:
        conn.execute(
            "UPDATE evidence_notes SET quote='Invented unrelated statement' WHERE id=?",
            (workspace[1]["id"],),
        )
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/recall",
                json={
                    "note_id": workspace[1]["id"],
                    "prompt": "Cannot use fabricated quote",
                },
            ).status_code
            == 422
        )


def test_numeric_only_search_is_literal_and_does_not_use_dense(workspace, monkeypatch):
    paper, _ = workspace
    monkeypatch.setattr(
        retrieval,
        "dense",
        lambda *args, **kwargs: pytest.fail(
            "Numeric literal should not use semantic neighbors"
        ),
    )
    result = retrieval.search("73", [paper["id"]])
    assert len(result) == 1 and "73 samples." in result[0]["text"]
    assert len(retrieval.search("0.73", [paper["id"]])) == 1
    assert len(retrieval.search("-2.5%", [paper["id"]])) == 1
    assert retrieval.search("99999", [paper["id"]]) == []
    assert retrieval.search("73", ["other-document"]) == []
    with store.connection() as conn:
        conn.execute("UPDATE documents SET archived=1 WHERE id=?", (paper["id"],))
    assert retrieval.search("73", [paper["id"]]) == []


def test_normal_question_terms_unchanged():
    assert store.numeric_literal("How many of the 73 samples were used?") is None
    assert store.numeric_literal("７３") == "73"
