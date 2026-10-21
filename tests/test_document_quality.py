import asyncio
from types import SimpleNamespace

import httpx
import numpy as np
import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend import (
    accounts,
    database,
    discovery,
    document_quality,
    jobs,
    parsing,
    store,
)
from backend.app import app


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "library.sqlite3")
    monkeypatch.setattr(accounts, "AUTH_PATH", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(
        accounts, "path", lambda identifier: tmp_path / identifier / "library.sqlite3"
    )
    database.initialize()
    return tmp_path


def make_pdf(folder, mixed=True):
    path = folder / "mixed.pdf"
    with pymupdf.open() as pdf:
        if mixed:
            pdf.new_page().insert_text(
                (40, 70), "Native text must remain available for research and citation."
            )
        pdf.new_page()
        pdf.save(path)
    return path


def empty_ocr(_):
    return SimpleNamespace(boxes=None, txts=None, scores=None)


def text_ocr(_):
    return SimpleNamespace(
        boxes=np.array([[[40, 70], [350, 70], [350, 100], [40, 100]]]),
        txts=["Recognized evidence with enough characters for testing."],
        scores=[0.72],
    )


def test_mixed_upload_queues_ocr_and_text_only_queues_index(isolated, monkeypatch):
    submitted = []
    monkeypatch.setattr(
        jobs, "submit", lambda kind, payload: submitted.append((kind, payload))
    )
    path = make_pdf(isolated)
    with TestClient(app) as client:
        response = client.post(
            "/api/documents",
            files={"file": ("mixed.pdf", path.read_bytes(), "application/pdf")},
        )
        assert response.status_code == 200
        record = response.json()
        assert record["status"] == "partial_ocr"
        assert submitted == [("ocr", {"document_id": record["id"]})]
        report = client.get(f"/api/documents/{record['id']}/text-quality").json()
        assert [p["state"] for p in report["pages"]] == ["native", "pending"]
        assert report["retry_pages"] == [2]
        # Reimport does not enqueue an additional OCR job.
        client.post(
            "/api/documents",
            files={"file": ("again.pdf", path.read_bytes(), "application/pdf")},
        )
        assert len(submitted) == 1
        with pymupdf.open(path) as pdf:
            pdf.delete_page(1)
            text_pdf = pdf.tobytes()
        response = client.post(
            "/api/documents", files={"file": ("text.pdf", text_pdf, "application/pdf")}
        )
        assert response.json()["status"] == "text_ready"
        assert submitted[-1][0] == "index"


def test_blank_ocr_records_zero_without_crash_or_false_completion(
    isolated, monkeypatch
):
    record = store.import_pdf(make_pdf(isolated, mixed=False))
    monkeypatch.setattr(parsing, "_ocr", empty_ocr)
    result = parsing.ocr_page(record, 1)
    assert result["lines"] == 0
    updated = store.get_document(record["id"])
    assert updated["chars"] == 0
    assert updated["status"] == "partial_ocr"
    assert updated["metadata"]["ocr_pages"] == []
    report = document_quality.report(record["id"])
    assert report["pages"][0]["state"] == "unrecognized"
    assert report["retry_pages"] == [1]
    parsing.ocr_page(record, 1)
    assert store.get_blocks(record["id"]) == []


def test_ocr_recovery_preserves_native_and_saved_evidence(isolated, monkeypatch):
    record = store.import_pdf(make_pdf(isolated))
    native = store.get_blocks(record["id"], 1)
    monkeypatch.setattr(parsing, "_ocr", text_ocr)
    parsing.ocr_page(record, 2)
    blocks = store.get_blocks(record["id"])
    assert store.get_blocks(record["id"], 1) == native
    report = document_quality.report(record["id"])
    assert report["text_pages"] == 2
    assert report["attention_pages"] == [2]
    assert report["pages"][1]["state"] == "review"
    assert report["retry_pages"] == []
    monkeypatch.setattr(
        parsing, "_ocr", lambda _: pytest.fail("Existing OCR must not be replaced")
    )
    assert parsing.ocr_page(record, 2)["preserved"]
    assert store.get_blocks(record["id"]) == blocks
    with store.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM block_search").fetchone()[0] == len(
            blocks
        )


def test_report_does_not_trust_legacy_ready_status(isolated):
    record = store.import_pdf(make_pdf(isolated))
    with store.connection() as conn:
        conn.execute(
            "UPDATE documents SET status='text_ready' WHERE id=?", (record["id"],)
        )
    assert document_quality.report(record["id"])["attention_pages"] == [2]
    assert store.get_document(record["id"])["status"] == "text_ready"


def test_quality_endpoint_obeys_account_scope(isolated):
    record = store.import_pdf(make_pdf(isolated))
    url = f"/api/documents/{record['id']}/text-quality"
    with TestClient(app) as client:
        assert client.get(url).status_code == 200
        assert (
            client.post(
                "/api/account/register",
                json={"name": "quality-scope", "password": "isolated-password"},
            ).status_code
            == 200
        )
        assert client.get(url).status_code == 404


def test_ocr_job_reports_blank_pages_and_queues_index(isolated, monkeypatch):
    record = store.import_pdf(make_pdf(isolated))
    monkeypatch.setattr(parsing, "_ocr", empty_ocr)
    submitted = []
    monkeypatch.setattr(
        jobs, "submit", lambda kind, payload: submitted.append((kind, payload))
    )
    context = SimpleNamespace(progress=lambda *args: None)
    result = asyncio.run(parsing.ocr(context, {"document_id": record["id"]}))
    assert result["unrecognized_pages"] == [2]
    assert submitted == [("index", {"document_ids": [record["id"]]})]


@pytest.mark.parametrize("mixed", [True, False])
def test_download_routes_missing_text_to_ocr(isolated, monkeypatch, mixed):
    path = make_pdf(isolated)
    with pymupdf.open(path) as pdf:
        if not mixed:
            pdf.delete_page(1)
        content = pdf.tobytes()
    monkeypatch.setattr(
        discovery,
        "remote",
        lambda _: {
            "pdf_url": "https://arxiv.org/pdf/1706.03762",
            "title": "Download coverage fixture",
        },
    )
    factory = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=content)
    )
    monkeypatch.setattr(
        discovery.httpx,
        "AsyncClient",
        lambda **kwargs: factory(transport=transport, **kwargs),
    )
    submitted = []
    monkeypatch.setattr(
        jobs, "submit", lambda kind, payload: submitted.append((kind, payload))
    )
    context = SimpleNamespace(progress=lambda *args: None, check=lambda: None)
    record = asyncio.run(discovery.download(context, {"paper_id": "fixture"}))
    expected = (
        [("ocr", {"document_id": record["id"]})]
        if mixed
        else [("index", {"document_ids": [record["id"]]})]
    )
    assert submitted == expected
