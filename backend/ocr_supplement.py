"""Bound page selection and suppress only spatially matching native OCR duplicates."""

import pymupdf

from . import store


def selected_pages(record, page=None):
    if page is None:
        return record["metadata"].get("pages_without_text", [])
    if (
        isinstance(page, bool)
        or not isinstance(page, int)
        or not 1 <= page <= record["pages"]
    ):
        raise ValueError("OCR 页码超出文献范围")
    return [page]


def duplicates_native(line, native, rotation_matrix):
    text = store.quote_normalize(line["text"]).casefold()
    if len(text) < 3:
        return False
    box = pymupdf.Rect(line["bbox"])
    if box.is_empty:
        return False
    for block in native:
        native_box = pymupdf.Rect(block["bbox"]) * rotation_matrix
        if (box & native_box).get_area() / box.get_area() < 0.6:
            continue
        if text in store.quote_normalize(block["text"]).casefold():
            return True
    return False
