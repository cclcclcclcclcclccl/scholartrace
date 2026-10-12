"""Conservative version audit: source changes require review, not automatic retraction."""

from __future__ import annotations
import json
import re
from .store import connection, content_similarity, get_blocks, get_document
from .alignment import SourceAligner, EXPLANATIONS


def notes(archived=False) -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            """SELECT n.*,b.document_id,b.page,b.bbox,d.title,d.version
                               FROM evidence_notes n JOIN blocks b ON b.id=n.block_id
                               JOIN documents d ON d.id=b.document_id WHERE n.archived=? ORDER BY n.id DESC""",
            (int(archived),),
        )
        return [{**dict(row), "bbox": json.loads(row["bbox"])} for row in rows]


def save_note(block_id: str, note: str) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT * FROM blocks WHERE id=?", (block_id,)).fetchone()
        if not row:
            raise KeyError(block_id)
        existing = conn.execute(
            "SELECT id FROM evidence_notes WHERE block_id=? AND note=? AND quote=?",
            (block_id, note.strip(), row["text"]),
        ).fetchone()
        if existing:
            note_id = existing["id"]
            conn.execute("UPDATE evidence_notes SET archived=0 WHERE id=?", (note_id,))
        else:
            cursor = conn.execute(
                "INSERT INTO evidence_notes(block_id,note,quote) VALUES(?,?,?)",
                (block_id, note.strip(), row["text"]),
            )
            note_id = cursor.lastrowid
    return next(n for n in notes() if n["id"] == note_id)


def audit_against(target_id: str) -> dict:
    target = get_document(target_id)
    blocks = get_blocks(target_id)
    aligner = SourceAligner(blocks)
    relations = {}
    results = []
    for note in notes():
        source_id = note["document_id"]
        if source_id == target_id:
            continue
        if source_id not in relations:
            relations[source_id] = content_similarity(source_id, target_id)
        if not relations[source_id]["likely_same_paper"]:
            continue
        aligned = aligner.locate(note["quote"])
        best = aligned["candidate"]
        state = aligned["status"]
        old_numbers = set(re.findall(r"(?<!\w)[+-]?\d+(?:\.\d+)?\b", note["quote"]))
        new_numbers = (
            old_numbers
            if state == "retained"
            else set(re.findall(r"(?<!\w)[+-]?\d+(?:\.\d+)?\b", best["text"]))
            if best
            else set()
        )
        results.append(
            {
                "note": note,
                **aligned,
                "numbers_only_in_old": sorted(old_numbers - new_numbers),
                "numbers_only_in_new": sorted(new_numbers - old_numbers),
                "explanation": EXPLANATIONS[state],
            }
        )
    return {
        "target": {
            "id": target_id,
            "title": target["title"],
            "version": target["version"],
        },
        "results": results,
        "method": "quote alignment across up to four adjacent blocks; not semantic entailment or scientific validity verification",
    }
