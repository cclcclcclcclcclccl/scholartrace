"""Separate browser fixture: copies the library and uses an isolated account store."""

import json
import sys

import pymupdf
import verify_recall_demo as demo

demo.FOLDER = demo.ROOT / "artifacts/boundaries-20261020"

if __name__ == "__main__":
    demo.main()
    if "--serve" not in sys.argv:
        from backend import audit, store

        fixture = json.loads((demo.FOLDER / "fixture.json").read_text("utf-8"))
        path = demo.FOLDER / "second-fixture.pdf"
        with pymupdf.open() as pdf:
            page = pdf.new_page()
            page.insert_text((40, 60), "Boundary Comparison Study B", fontsize=22)
            page.insert_text(
                (40, 140),
                "The study used 120 participants under laboratory conditions.",
                fontsize=14,
            )
            pdf.save(path)
        paper = store.import_pdf(path)
        block = next(
            b for b in store.get_blocks(paper["id"]) if "120 participants" in b["text"]
        )
        note = audit.save_note(block["id"], "验收证据B：120名参与者，实验室条件。")
        fixture["second"] = {
            "document_id": paper["id"],
            "title": paper["title"],
            "note": note,
            "block": block,
        }
        (demo.FOLDER / "fixture.json").write_text(
            json.dumps(fixture, ensure_ascii=False, indent=2), "utf-8"
        )
