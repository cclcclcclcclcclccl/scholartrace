import asyncio
from types import SimpleNamespace

import numpy as np
import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend import (
    accounts,
    database,
    document_quality,
    jobs,
    ocr_supplement,
    parsing,
    store,
)
from backend.app import app


@pytest.fixture
def paper(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "library.sqlite3")
    monkeypatch.setattr(accounts, "AUTH_PATH", tmp_path / "accounts.sqlite3")
    database.initialize()
    path = tmp_path / "supplement.pdf"
    with pymupdf.open() as pdf:
        for _ in range(2):
            page = pdf.new_page()
            page.insert_text(
                (40, 70), "Native caption must remain unchanged.", fontsize=16
            )
        pdf.save(path)
    return store.import_pdf(path)


def engine(record, confidence=0.65, duplicate_only=False):
    native = store.get_blocks(record["id"], 1)[0]
    with pymupdf.open(record["path"]) as pdf:
        pix = pdf[0].get_pixmap(dpi=150)
        sx, sy = pix.width / pdf[0].rect.width, pix.height / pdf[0].rect.height
    boxes, texts, scores = [], [], []
    for bbox, text, score in [(native["bbox"], native["text"].strip(), 0.99)] + (
        []
        if duplicate_only
        else [([40, 200, 420, 222], "Hidden experiment used 73 samples.", confidence)]
    ):
        x0, y0, x1, y1 = bbox
        boxes.append(
            [
                [x0 * sx, y0 * sy],
                [x1 * sx, y0 * sy],
                [x1 * sx, y1 * sy],
                [x0 * sx, y1 * sy],
            ]
        )
        texts.append(text)
        scores.append(score)
    return lambda _: SimpleNamespace(boxes=np.array(boxes), txts=texts, scores=scores)


def test_selected_page_adds_hidden_text_preserves_native_and_title(paper, monkeypatch):
    before = store.get_blocks(paper["id"])
    monkeypatch.setattr(parsing, "_ocr", engine(paper))
    submitted = []
    monkeypatch.setattr(jobs, "submit", lambda *args: submitted.append(args))
    result = asyncio.run(
        parsing.ocr(
            SimpleNamespace(progress=lambda *args: None),
            {"document_id": paper["id"], "page": 1},
        )
    )
    assert [p["page"] for p in result["pages"]] == [1]
    assert result["pages"][0]["duplicates_skipped"] == 1
    assert result["pages"][0]["added_lines"] == 1
    after = store.get_blocks(paper["id"])
    assert [b for b in after if b["method"] == "native"] == before
    assert store.get_document(paper["id"])["title"] == paper["title"]
    assert store.get_blocks(paper["id"], 2) == [b for b in before if b["page"] == 2]
    assert store.search("73 samples", [paper["id"]])
    quality = document_quality.report(paper["id"])
    assert quality["pages"][0]["state"] == "review"
    assert quality["pages"][0]["confidence"] == 0.65
    assert submitted == [("index", {"document_ids": [paper["id"]]})]
    assert parsing.ocr_page(paper, 1)["preserved"]
    assert store.get_blocks(paper["id"]) == after


def test_duplicate_only_page_does_not_create_blocks_or_false_ocr_state(
    paper, monkeypatch
):
    before = store.get_blocks(paper["id"])
    monkeypatch.setattr(parsing, "_ocr", engine(paper, duplicate_only=True))
    result = parsing.ocr_page(paper, 1)
    assert result["added_lines"] == 0 and result["duplicates_skipped"] == 1
    assert store.get_blocks(paper["id"]) == before
    assert store.get_document(paper["id"])["status"] == "text_ready"
    assert document_quality.report(paper["id"])["pages"][0]["ocr_warning"]
    with store.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM block_search").fetchone()[0] == len(
            before
        )


def test_high_confidence_supplement_is_mixed(paper, monkeypatch):
    monkeypatch.setattr(parsing, "_ocr", engine(paper, confidence=0.95))
    parsing.ocr_page(paper, 1)
    assert document_quality.report(paper["id"])["pages"][0]["state"] == "mixed"


@pytest.mark.parametrize("page", [0, -1, 3])
def test_api_rejects_out_of_range_before_enqueue(paper, monkeypatch, page):
    monkeypatch.setattr(
        jobs, "submit", lambda *args: pytest.fail("Invalid page queued")
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/jobs",
            json={"kind": "ocr", "payload": {"document_id": paper["id"], "page": page}},
        )
        assert response.status_code == 422


def test_duplicate_requires_both_location_and_text_and_handles_rotation():
    native = [{"bbox": [20, 40, 140, 60], "text": "Native evidence sentence."}]
    identity = pymupdf.Matrix(1, 1)
    assert ocr_supplement.duplicates_native(
        {"bbox": [20, 40, 140, 60], "text": "Native evidence sentence."},
        native,
        identity,
    )
    assert not ocr_supplement.duplicates_native(
        {"bbox": [20, 200, 140, 220], "text": "Native evidence sentence."},
        native,
        identity,
    )
    assert not ocr_supplement.duplicates_native(
        {"bbox": [20, 40, 140, 60], "text": "Different evidence sentence."},
        native,
        identity,
    )
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.set_rotation(90)
        rotated = list(pymupdf.Rect(native[0]["bbox"]) * page.rotation_matrix)
        assert ocr_supplement.duplicates_native(
            {"bbox": rotated, "text": native[0]["text"]}, native, page.rotation_matrix
        )


def test_queued_api_preserves_selected_page(paper, monkeypatch):
    queued = []
    monkeypatch.setattr(
        jobs,
        "submit",
        lambda kind, payload: queued.append((kind, payload)) or {"id": "test"},
    )
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/jobs",
                json={
                    "kind": "ocr",
                    "payload": {"document_id": paper["id"], "page": 2},
                },
            ).status_code
            == 200
        )
    assert queued[0][1]["page"] == 2
