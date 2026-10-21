"""Actual local OCR on a controlled mixed PDF; all writes use a disposable DB."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import accounts, database, document_quality, parsing, store

FOLDER = ROOT / "artifacts/parsing-quality-20261020"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    target = FOLDER / "demo.sqlite3"
    if args.serve:
        assert target.exists()
        store.DB_PATH = target
        accounts.AUTH_PATH = FOLDER / "accounts.sqlite3"
        accounts.path = lambda identifier: (
            FOLDER / "accounts" / identifier / "library.sqlite3"
        )
        import uvicorn

        uvicorn.run("backend.app:app", host="127.0.0.1", port=8767)
        return
    if target.exists():
        raise ValueError("Refuse to overwrite OCR verification evidence")
    with sqlite3.connect(store.DB_PATH) as source, sqlite3.connect(target) as dest:
        source.backup(dest)
    store.DB_PATH = target
    database.initialize()
    path = FOLDER / "mixed-ocr-fixture.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((45, 65), "Mixed PDF coverage verification", fontsize=20)
        page.insert_text(
            (45, 110),
            "Page one has native text. Page two is a scanned image.",
            fontsize=14,
        )
        with pymupdf.open() as scan:
            page = scan.new_page()
            page.insert_text((45, 65), "Scanned research evidence", fontsize=22)
            page.insert_text(
                (45, 120), "The experiment used 48 samples for evaluation.", fontsize=16
            )
            page.insert_text(
                (45, 160),
                "The original page must remain available for review.",
                fontsize=16,
            )
            png = page.get_pixmap(dpi=150).tobytes("png")
        page = pdf.new_page()
        page.insert_image(page.rect, stream=png)
        pdf.new_page()  # A truly blank page must not become successful text extraction.
        pdf.save(path)
    record = store.import_pdf(path)
    native = store.get_blocks(record["id"], 1)
    before = document_quality.report(record["id"])
    assert record["status"] == "partial_ocr"
    assert before["retry_pages"] == [2, 3]
    results = [parsing.ocr_page(record, page) for page in (2, 3)]
    after = document_quality.report(record["id"])
    blocks = store.get_blocks(record["id"], 2)
    text = " ".join(b["text"] for b in blocks)
    assert "48" in text and "samples" in text.lower(), text
    assert store.get_blocks(record["id"], 1) == native
    assert after["retry_pages"] == [3]
    assert after["pages"][2]["state"] == "unrecognized"
    repeated = parsing.ocr_page(record, 2)
    assert repeated["preserved"] and store.get_blocks(record["id"], 2) == blocks
    for block in blocks:
        x0, y0, x1, y1 = block["bbox"]
        assert 0 <= x0 < x1 <= block["width"]
        assert 0 <= y0 < y1 <= block["height"]
    report = {
        "document_id": record["id"],
        "fixture": str(path.relative_to(ROOT)),
        "notice": "Real RapidOCR on generated native/image/blank PDF; controlled integration check, not independent OCR accuracy benchmark.",
        "before": before,
        "after": after,
        "results": results,
        "ocr_text": text,
        "repeat": repeated,
        "native_preserved": True,
        "coordinate_bounds_passed": True,
    }
    (FOLDER / "actual-ocr.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), "utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
