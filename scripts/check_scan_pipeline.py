"""Exercise the new OCR worker on a clean temporary workspace using official scans."""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import store, database, parsing, jobs


async def main():
    folder = store.ROOT / "artifacts/full-workbench/scan-test"
    folder.mkdir(parents=True, exist_ok=True)
    token = store.database_override.set(folder / "scan.sqlite3")
    try:
        database.initialize()
        record = store.import_pdf(
            store.ROOT / "data/competition/pdf/1706.03762v1_img.pdf"
        )
        started = time.monotonic()
        job = jobs.submit("ocr", {"document_id": record["id"]})
        while jobs.workers:
            await asyncio.sleep(2)
        record = store.get_document(record["id"])
        result = {
            "job": jobs.get(job["id"]),
            "seconds": round(time.monotonic() - started, 2),
            "status": record["status"],
            "pages": record["pages"],
            "quality": record["metadata"].get("ocr_quality", {}),
            "blocks": len(store.get_blocks(record["id"])),
        }
        (folder / "report.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            result["job"]["state"],
            result["status"],
            result["blocks"],
            result["seconds"],
            flush=True,
        )
    finally:
        store.database_override.reset(token)


if __name__ == "__main__":
    asyncio.run(main())
