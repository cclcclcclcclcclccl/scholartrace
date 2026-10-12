"""Attach the actual table header to numeric PDF rows, keeping both source anchors."""

import re

from . import store


def expand_neighbors(blocks, limit=14):
    """Recover a nearby definition/specification separated by PDF layout, as its own citation."""
    output, seen, pages = [], set(), {}
    for rank, block in enumerate(blocks):
        if block["id"] not in seen:
            output.append(block)
            seen.add(block["id"])
        if rank >= 4:
            continue
        key = (block["document_id"], block["page"])
        if key not in pages:
            pages[key] = store.get_blocks(*key)
        for neighbor in pages[key]:
            box = neighbor["bbox"]
            old = block["bbox"]
            if (
                neighbor["id"] in seen
                or len(neighbor["text"]) < 45
                or len(neighbor["text"]) > 1800
            ):
                continue
            if (
                abs(box[0] - old[0]) < 12
                and abs(box[2] - old[2]) < 35
                and -1 <= box[1] - old[3] <= 12
            ):
                output.append(
                    {
                        **neighbor,
                        "title": block["title"],
                        "version": block.get("version"),
                        "name": block.get("name"),
                        "retrieval_context": "adjacent paragraph",
                    }
                )
                seen.add(neighbor["id"])
                break
    return output[:limit]


def numeric_row(lines):
    return (
        len(lines) >= 4
        and sum(bool(re.match(r"^[+−-]?\d", line)) for line in lines)
        >= len(lines) * 0.6
    )


def attach_table_headers(blocks):
    pages = {}
    output = []
    for block in blocks:
        block = dict(block)
        fields = block["text"].splitlines()
        if numeric_row(fields):
            key = (block["document_id"], block["page"])
            if key not in pages:
                pages[key] = store.get_blocks(*key)
            preceding = [
                b
                for b in pages[key]
                if b["bbox"][3] <= block["bbox"][1] + 2
                and 0 < block["bbox"][1] - b["bbox"][1] < 250
            ]
            for header in reversed(preceding):
                labels = header["text"].splitlines()
                if (
                    not labels
                    or len(fields) % len(labels) != 0
                    or any(len(label) > 60 for label in labels)
                    or numeric_row(labels)
                ):
                    continue
                if (
                    sum(bool(re.search("[A-Za-z]", label)) for label in labels)
                    < len(labels) * 0.75
                ):
                    continue
                if (
                    abs(header["bbox"][0] - block["bbox"][0]) > 15
                    or abs(header["bbox"][2] - block["bbox"][2]) > 30
                ):
                    continue
                intervening = [b for b in preceding if b["bbox"][1] > header["bbox"][1]]
                if any(
                    not numeric_row(b["text"].splitlines())
                    or len(b["text"].splitlines()) % len(labels) != 0
                    for b in intervening
                ):
                    continue
                block["source_context"] = [header]
                rows = [
                    fields[i : i + len(labels)]
                    for i in range(0, len(fields), len(labels))
                ]
                if len(rows) > 1 and (
                    len(labels) < 3
                    or any(
                        not re.search(r"[A-Za-z]", row[0])
                        or sum(bool(re.match(r"^[+−-]?\d", v)) for v in row[1:])
                        < (len(labels) - 1) * 0.75
                        for row in rows
                    )
                ):
                    block.pop("source_context", None)
                    continue
                block["table_fields"] = [
                    {
                        "field": (row[0] + " · " if len(rows) > 1 else "") + label,
                        "value": value,
                    }
                    for row in rows
                    for label, value in zip(labels, row)
                ]
                break
        output.append(block)
    return output


def prompt_text(block):
    text = store.quote_normalize(block["text"])
    for header in block.get("source_context", []):
        text += (
            "\nTABLE HEADER (same PDF page, exact source): "
            + store.quote_normalize(header["text"])
        )
    if block.get("table_fields"):
        text += "\nColumns matched by PDF row order: " + "; ".join(
            f"{p['field']} = {p['value']}" for p in block["table_fields"]
        )
        text += "\nDo not confuse model dimension (dmodel) with head dimension (dhead) or head count (nheads)."
    return text
