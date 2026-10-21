"""Isolated browser fixture and server for evidence recall; never write original data."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import accounts, audit, database, store

FOLDER = ROOT / "artifacts/recall-20261020"


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
    path = FOLDER / "recall-fixture.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((40, 60), "Evidence Recall Verification", fontsize=22)
        page.insert_text(
            (40, 140), "The experiment used 73 samples for evaluation.", fontsize=15
        )
        page.insert_text(
            (40, 220), "The control used 173 examples, not 73.5 examples.", fontsize=15
        )
        pdf.save(path)
    record = store.import_pdf(path)
    block = next(
        b for b in store.get_blocks(record["id"]) if "used 73 samples" in b["text"]
    )
    note = audit.save_note(block["id"], "验收证据：评估样本量，注意与对照组区别。")
    (FOLDER / "fixture.json").write_text(
        json.dumps(
            {"document_id": record["id"], "note": note, "block": block},
            ensure_ascii=False,
            indent=2,
        ),
        "utf-8",
    )
    print("Isolated fixture prepared")


if __name__ == "__main__":
    main()
