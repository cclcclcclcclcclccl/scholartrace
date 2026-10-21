"""Prefer explicit user-requested PDF locations using source layout, not model guesses."""

import re

from . import store


def abstract_blocks(blocks):
    """Conservatively find same-column paragraphs below an explicit abstract heading.

    Missing headings/geometry yield no special candidates. This is a bounded
    layout hint, not a claim that every PDF abstract has been fully extracted.
    """
    result = []
    for heading in blocks:
        if not re.fullmatch(r"abstract|摘\s*要", heading["text"].strip(), re.I):
            continue
        box = heading.get("bbox")
        if not box or len(box) != 4:
            continue
        center = (box[0] + box[2]) / 2
        column = sorted(
            (
                b
                for b in blocks
                if b.get("bbox")
                and b["bbox"][0] <= center <= b["bbox"][2]
                and b["bbox"][1] >= box[3] - 2
            ),
            key=lambda b: b["bbox"][1],
        )
        bottom = box[3]
        for block in column:
            text = block["text"].strip()
            if (
                block["bbox"][1] - bottom > 40
                or re.match(
                    r"^(?:\d+[.\s]+)?(?:introduction|keywords|index terms|引言|关键词)\b",
                    text,
                    re.I,
                )
                or re.match(r"^\d+\.?\s+[A-Z]", text)
            ):
                break
            if len(text) < 45 or len(text) > 4000:
                break
            result.append(block)
            bottom = block["bbox"][3]
            if len(result) >= 4:
                return result
    return result


def explicit_scope_evidence(question, ids):
    if len(ids) != 1:
        return []
    pages = {
        int(a or b)
        for a, b in re.findall(r"第\s*(\d+)\s*页|\bpage\s+(\d+)\b", question, re.I)
    }
    abstract = bool(re.search(r"摘要|\babstract\b", question, re.I))
    if not pages and not abstract:
        return []
    doc = store.get_document(ids[0])
    if not doc:
        return []
    chosen = []
    if abstract:
        chosen = abstract_blocks(store.get_blocks(ids[0], 1))
    if not chosen and len(pages) == 1:
        rows = store.get_blocks(ids[0], next(iter(pages)))
        terms = set(re.findall(r"[a-z]{3,}", question.lower()))
        rows = [b for b in rows if 45 <= len(b["text"]) <= 2400]
        rows.sort(
            key=lambda b: -len(terms & set(re.findall(r"[a-z]{3,}", b["text"].lower())))
        )
        chosen = rows[:6]
    return [
        {
            **b,
            "title": doc["title"],
            "name": doc["name"],
            "version": doc.get("version"),
            "retrieval_context": "explicit user location (PDF layout); verify scope in source",
        }
        for b in chosen
    ]
