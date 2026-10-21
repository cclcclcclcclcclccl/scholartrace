"""Controlled native-caption plus image-body OCR verification on a disposable store."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import accounts, database, document_quality, parsing, store

FOLDER = ROOT / "artifacts/page-ocr-20261020"


def fixture(path):
    with pymupdf.open() as pdf:
        for index in range(2):
            page = pdf.new_page()
            page.insert_text(
                (45, 65), "Native caption for supplemental OCR", fontsize=20
            )
            with pymupdf.open() as image:
                scan = image.new_page(width=500, height=180)
                scan.insert_text(
                    (15, 45),
                    f"The hidden experiment used {73 + index} samples.",
                    fontsize=17,
                )
                scan.insert_text(
                    (15, 85),
                    "The evidence must remain linked to its original page.",
                    fontsize=14,
                )
                png = scan.get_pixmap(dpi=150).tobytes("png")
            page.insert_image(pymupdf.Rect(45, 160, 545, 340), stream=png)
        pdf.save(path)


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
        raise ValueError("Refuse to overwrite verification database")
    with sqlite3.connect(store.DB_PATH) as source, sqlite3.connect(target) as dest:
        source.backup(dest)
    store.DB_PATH = target
    database.initialize()
    path = FOLDER / "native-caption-image-body.pdf"
    fixture(path)
    record = store.import_pdf(path)
    native = store.get_blocks(record["id"])
    assert record["metadata"]["pages_without_text"] == []
    assert not store.search("hidden experiment samples", [record["id"]])
    before = document_quality.report(record["id"])
    result = parsing.ocr_page(record, 1)
    after = document_quality.report(record["id"])
    all_blocks = store.get_blocks(record["id"])
    assert [b for b in all_blocks if b["method"] == "native"] == native
    assert store.get_document(record["id"])["title"] == record["title"]
    assert result["duplicates_skipped"] == 1
    assert result["added_lines"] == 2
    assert all(b["method"] == "native" for b in store.get_blocks(record["id"], 2))
    matches = store.search("hidden experiment samples", [record["id"]])
    assert any("73 samples" in b["text"] for b in matches)
    assert after["pages"][0]["state"] == "mixed"
    repeated = parsing.ocr_page(record, 1)
    assert repeated["preserved"] and store.get_blocks(record["id"]) == all_blocks
    for block in all_blocks:
        x0, y0, x1, y1 = block["bbox"]
        assert 0 <= x0 < x1 <= block["width"] and 0 <= y0 < y1 <= block["height"]
    report = {
        "notice": "Actual local OCR on a generated fixture, not independent PDF accuracy or new model QA evaluation.",
        "document_id": record["id"],
        "before": before,
        "after": after,
        "result": result,
        "repeat": repeated,
        "native_preserved": True,
        "title_preserved": True,
        "unselected_page_preserved": True,
        "coordinate_bounds_passed": True,
        "new_text_searchable": True,
        "blocks": all_blocks,
    }
    (FOLDER / "actual-ocr.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), "utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"blocks", "before", "after"}},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
