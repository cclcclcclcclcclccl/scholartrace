"""Real competition corpus integration checks, with isolated temporary databases."""
from pathlib import Path
import shutil

import pytest
from fastapi.testclient import TestClient

from backend import store, audit
from backend.app import app

CORPUS = Path(__file__).resolve().parents[1] / "data/competition/pdf"


@pytest.fixture()
def corpus(tmp_path, monkeypatch):
    if not (CORPUS / "1706.03762v1.pdf").exists():
        pytest.skip("User-supplied competition corpus is required")
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.sqlite3")
    store.initialize()
    first = store.import_pdf(CORPUS / "1706.03762v1.pdf")
    newer = store.import_pdf(CORPUS / "1706.03762v7.pdf")
    return first, newer


def test_duplicate_is_hash_based_even_after_rename(corpus, tmp_path):
    original, _ = corpus
    renamed = tmp_path / "unrelated_name.pdf"
    shutil.copyfile(CORPUS / "1706.03762v1.pdf", renamed)
    duplicate = store.import_pdf(renamed)
    assert duplicate["already_exists"] is True
    assert duplicate["id"] == original["id"]
    assert len(store.list_documents()) == 2


def test_version_is_inferred_from_content(corpus, tmp_path):
    first, newer = corpus
    assert first["version"] == 1
    assert newer["version"] == 7
    match = store.content_similarity(first["id"], newer["id"])
    assert match["likely_same_paper"]
    assert match["recommended_version_id"] == newer["id"]


def test_retrieval_has_real_gpu_evidence_and_geometry(corpus):
    first, newer = corpus
    results = store.search("训练用了哪些 GPU？", [first["id"]])
    assert results
    assert any("P100" in block["text"] and ("eight" in block["text"].lower() or "8 NVIDIA" in block["text"]) for block in results)
    assert all(b["document_id"] == first["id"] for b in results)
    for block in results:
        x0, y0, x1, y1 = block["bbox"]
        assert x0 < x1 <= block["width"] + 1
        assert y0 < y1 <= block["height"] + 1
        assert 1 <= block["page"] <= first["pages"]


def test_scan_is_not_mislabeled_as_parsed(corpus):
    scan = store.import_pdf(CORPUS / "1706.03762v1_img.pdf")
    assert scan["status"] == "needs_ocr"
    assert not store.get_blocks(scan["id"])


def test_unrelated_query_does_not_get_a_fabricated_answer(corpus):
    first, _ = corpus
    assert not store.search("zxqvnonexistentquantumplatypus", [first["id"]])
    with TestClient(app) as client:
        response = client.post("/api/ask", json={"question": "zxqvnonexistentquantumplatypus", "document_ids": [first["id"]]})
    assert response.status_code == 200
    assert response.json()["model_answer"] is None
    assert response.json()["evidence"] == []


def test_persistent_note_and_version_review_preserve_original(corpus):
    first, newer = corpus
    block = next(b for b in store.search("Adam optimizer", [first["id"]]) if "Adam" in b["text"])
    note = audit.save_note(block["id"], "核对优化器参数")
    before = note["quote"]
    reviewed = audit.audit_against(newer["id"])
    assert len(reviewed["results"]) == 1
    assert reviewed["results"][0]["note"]["quote"] == before
    assert reviewed["results"][0]["status"] in {"retained", "review_required", "unlocated"}
    assert audit.notes()[0]["quote"] == before
    assert audit.notes()[0]["document_id"] == first["id"]


def test_no_cross_paper_audit(corpus):
    first, _ = corpus
    bert = store.import_pdf(CORPUS / "N19-1423.pdf")
    audit.save_note(store.get_blocks(first["id"])[0]["id"], "test")
    assert not audit.audit_against(bert["id"])["results"]
    assert not store.content_similarity(first["id"], bert["id"])["likely_same_paper"]


def test_invalid_upload_and_missing_source(corpus):
    with TestClient(app) as client:
        assert client.post("/api/documents", files={"file": ("fake.pdf", b"not a pdf", "application/pdf")}).status_code == 400
        assert client.get("/api/documents/no-such-document/pdf").status_code == 404
        assert client.post("/api/notes", json={"block_id": "missing", "note": "test"}).status_code == 404
        assert client.post("/api/search", json={"question": "anything", "document_ids": ["missing"]}).status_code == 404


def test_pdf_worker_has_executable_javascript_mime(corpus):
    assets = Path(__file__).resolve().parents[1] / "frontend/dist/assets"
    workers = list(assets.glob("pdf.worker*.mjs"))
    if not workers:
        pytest.skip("Build the frontend before testing worker delivery")
    with TestClient(app) as client:
        response = client.get("/assets/" + workers[0].name)
    assert response.status_code == 200
    assert response.headers["content-type"].split(";")[0] in {"text/javascript", "application/javascript"}
