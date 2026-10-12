"""Conservative version audit: source changes require review, not automatic retraction."""

from __future__ import annotations
import json
import re
from difflib import SequenceMatcher

from .store import connection, content_similarity, get_blocks, get_document, normalize


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
    normalized_blocks = [(b, normalize(b["text"]).lower()) for b in blocks]
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
        quote = normalize(note["quote"]).lower()
        candidates = []
        quote_tokens = set(re.findall(r"\w+", quote))
        for block, text in normalized_blocks:
            words = set(re.findall(r"\w+", text))
            overlap = len(words & quote_tokens) / max(1, len(words | quote_tokens))
            candidates.append((overlap, block, text))
        best = None
        best_score = 0.0
        for _, block, text in sorted(candidates, key=lambda c: c[0], reverse=True)[:8]:
            score = SequenceMatcher(None, quote, text, autojunk=False).ratio()
            if quote == text:
                score = 1.0
            if score > best_score:
                best, best_score = block, score
        state = (
            "retained"
            if best_score >= 0.999
            else "review_required"
            if best_score >= 0.4
            else "unlocated"
        )
        old_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", quote))
        new_numbers = (
            set(re.findall(r"\b\d+(?:\.\d+)?\b", best["text"])) if best else set()
        )
        results.append(
            {
                "note": note,
                "status": state,
                "similarity": round(best_score, 4),
                "candidate": best,
                "numbers_only_in_old": sorted(old_numbers - new_numbers),
                "numbers_only_in_new": sorted(new_numbers - old_numbers),
                "explanation": {
                    "retained": "找到相同原文块；仍需结合新版上下文判断适用性。",
                    "review_required": "相近原文块有变化，请对照复核；不代表原结论已错误。",
                    "unlocated": "未可靠定位到对应原文，可能存在拆段、改写或删除，需要人工核验。",
                }[state],
            }
        )
    return {
        "target": {
            "id": target_id,
            "title": target["title"],
            "version": target["version"],
        },
        "results": results,
        "method": "lexical alignment baseline; not semantic entailment or scientific validity verification",
    }
