"""OCR image-only pages, preserving coordinates in original PDF point units."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
import pymupdf
from rapidocr import RapidOCR

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    parser.add_argument("--pages", type=int, default=0, help="0 processes all image-only pages")
    args = parser.parse_args()
    store.initialize()
    record = store.import_pdf(args.file)
    record = store.get_document(record["id"])
    metadata = record["metadata"]
    missing = metadata["pages_without_text"]
    if args.pages:
        missing = missing[:args.pages]
    engine = RapidOCR(params={"Global.text_score": 0.5})
    report = {"document": record["name"], "pages": [], "method": "RapidOCR; line groups are a baseline, formulas/tables not semantically reconstructed"}
    done = set(metadata.get("ocr_pages", []))
    with pymupdf.open(args.file) as doc:
        for number in missing:
            started = perf_counter()
            page = doc[number-1]
            pix = page.get_pixmap(dpi=150, alpha=False)
            array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            result = engine(array)
            if result.boxes is None or not result.txts:
                print(f"Page {number}: no OCR text", flush=True)
                continue
            lines = []
            for box, text, confidence in zip(result.boxes, result.txts, result.scores):
                coords = np.asarray(box)
                x0, y0 = coords.min(axis=0)
                x1, y1 = coords.max(axis=0)
                lines.append({"text": text, "confidence": float(confidence), "bbox": [float(x0)*page.rect.width/pix.width, float(y0)*page.rect.height/pix.height, float(x1)*page.rect.width/pix.width, float(y1)*page.rect.height/pix.height]})
            lines.sort(key=lambda line: (round(line["bbox"][1]/10), line["bbox"][0]))
            groups = []
            current = []
            for line in lines:
                if current and (line["bbox"][1] - current[-1]["bbox"][3] > 12 or abs(line["bbox"][0]-current[-1]["bbox"][0]) > page.rect.width*0.3 or len(current)>=7):
                    groups.append(current); current = []
                current.append(line)
            if current:
                groups.append(current)
            rows = []
            for index, group in enumerate(groups):
                bbox = [min(l["bbox"][0] for l in group), min(l["bbox"][1] for l in group), max(l["bbox"][2] for l in group), max(l["bbox"][3] for l in group)]
                identifier = hashlib.sha256(f"{record['id']}:{number}:ocr:{index}".encode()).hexdigest()[:24]
                text = "\n".join(l["text"] for l in group)
                rows.append((identifier, record["id"], number, index, text, json.dumps(bbox), page.rect.width, page.rect.height, "rapidocr"))
            with store.connection() as conn:
                old = [r[0] for r in conn.execute("SELECT id FROM blocks WHERE document_id=? AND page=? AND method='rapidocr'", (record["id"], number))]
                # Preserve historical evidence: do not silently reparse already indexed OCR pages.
                if old:
                    print(f"Page {number}: already indexed, preserved", flush=True)
                    done.add(number)
                    continue
                conn.executemany("INSERT INTO blocks VALUES(?,?,?,?,?,?,?,?,?)", rows)
                conn.executemany("INSERT INTO block_search(block_id,document_id,text) VALUES(?,?,?)", [(r[0], r[1], r[4]) for r in rows])
                done.add(number)
                metadata["ocr_pages"] = sorted(done)
                metadata["ocr_method"] = "RapidOCR at 150 dpi; original PDF unchanged"
                new_chars = conn.execute("SELECT COALESCE(SUM(LENGTH(text)),0) FROM blocks WHERE document_id=?", (record["id"],)).fetchone()[0]
                status = "ocr_ready" if set(metadata["pages_without_text"]) <= done else "partial_ocr"
                conn.execute("UPDATE documents SET status=?,chars=?,metadata=? WHERE id=?", (status, new_chars, json.dumps(metadata, ensure_ascii=False), record["id"]))
                if number == 1:
                    title_lines = [l for l in lines if 20 < l["bbox"][1] < page.rect.height*0.35 and len(l["text"])>10]
                    if title_lines:
                        title_line = max(title_lines, key=lambda l: l["bbox"][3]-l["bbox"][1])
                        conn.execute("UPDATE documents SET title=? WHERE id=?", (title_line["text"], record["id"]))
                    arxiv = re.search(r"arxiv\s*:\s*(\d{4}\.\d{4,5})\s*v(\d+)", " ".join(l["text"] for l in lines), re.I)
                    if arxiv:
                        conn.execute("UPDATE documents SET arxiv_id=?,version=? WHERE id=?", (arxiv.group(1), int(arxiv.group(2)), record["id"]))
            item = {"page": number, "lines": len(lines), "blocks": len(rows), "seconds": round(perf_counter()-started,2), "mean_confidence": round(float(np.mean(result.scores)),4)}
            report["pages"].append(item)
            print(json.dumps(item), flush=True)
    (ROOT / "artifacts/inspection/ocr-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
