"""Read-only page coverage diagnostics, never a semantic accuracy score."""

from . import store


def report(identifier):
    record = store.get_document(identifier)
    with store.connection() as conn:
        rows = conn.execute(
            "SELECT page,method,SUM(LENGTH(TRIM(text))) AS chars,"
            "MAX(width) AS width,MAX(height) AS height FROM blocks "
            "WHERE document_id=? GROUP BY page,method",
            (identifier,),
        ).fetchall()
    by_page = {}
    for row in rows:
        by_page.setdefault(row["page"], {})[row["method"]] = dict(row)
    quality = record["metadata"].get("ocr_quality", {})
    pages = []
    for number in range(1, record["pages"] + 1):
        sources = by_page.get(number, {})
        native = sources.get("native", {}).get("chars", 0)
        ocr = sources.get("rapidocr", {}).get("chars", 0)
        attempt = quality.get(str(number))
        confidence = attempt.get("confidence") if attempt else None
        if ocr:
            state = (
                "review"
                if ocr < 20 or (confidence is not None and confidence < 0.8)
                else "mixed"
                if native
                else "ocr"
            )
        elif native >= 20:
            state = "native"
        elif attempt is not None:
            state = "unrecognized"
        else:
            state = "pending"
        geometry = next(iter(sources.values()), {})
        pages.append(
            {
                "page": number,
                "state": state,
                "native_chars": native,
                "ocr_chars": ocr,
                "confidence": confidence,
                "ocr_attempted": attempt is not None,
                "ocr_warning": attempt.get("warning") if attempt else None,
                "duplicates_skipped": attempt.get("duplicates_skipped", 0)
                if attempt
                else 0,
                "width": geometry.get("width", 1),
                "height": geometry.get("height", 1),
            }
        )
    return {
        "document_id": identifier,
        "pages": pages,
        "text_pages": sum(p["native_chars"] + p["ocr_chars"] > 0 for p in pages),
        "attention_pages": [
            p["page"]
            for p in pages
            if p["state"] in {"pending", "review", "unrecognized"}
        ],
        "retry_pages": [
            p["page"] for p in pages if p["state"] in {"pending", "unrecognized"}
        ],
        "notice": "有文字仅表示已提取字符，不代表全文完整、语义索引完成或识别准确。少于20字符或OCR平均置信度低于0.8的页提示核对；置信度不是正确率。空白页、图页与识别失败需查看原图区分。",
    }
