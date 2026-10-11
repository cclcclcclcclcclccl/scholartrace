"""Inventory supplied PDFs and inspect every page without modifying sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from time import perf_counter

import pymupdf

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main() -> None:
    started = perf_counter()
    records = []
    for path in sorted((ROOT / "data/competition").rglob("*.pdf")):
        record = {"file": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                  "sha256": digest(path)}
        try:
            with pymupdf.open(path) as doc:
                counts = [len(page.get_text().strip()) for page in doc]
                record.update(pages=len(doc), text_characters=sum(counts),
                              pages_without_text=[i + 1 for i, count in enumerate(counts) if count < 20],
                              metadata=doc.metadata, first_page_excerpt=doc[0].get_text()[:1200],
                              outline_entries=len(doc.get_toc()))
        except Exception as error:
            record["error"] = str(error)
        records.append(record)
        print(f"{path.name}: {record.get('pages')} pages, {record.get('text_characters')} chars", flush=True)
    archive = ROOT / "科研小助手.rar"
    report = {"source": "user-supplied competition archive", "archive_sha256": digest(archive),
              "files": records, "elapsed_seconds": round(perf_counter() - started, 2)}
    output = ROOT / "artifacts/inspection/corpus-manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 赛事资料实际检查", "", "来源：用户提供的科研小助手.rar。日期：2026-10-11。",
             "", f"压缩包 SHA-256：`{report['archive_sha256']}`", "",
             "逐页读取原生文本；无文本层不代表 OCR 已完成。书籍页数以实际文件为准。", "",
             "| 文件 | 页数 | 原生文本字符 | 缺少文本页数 |", "| --- | ---: | ---: | ---: |"]
    for item in records:
        lines.append(f"| {Path(item['file']).name} | {item.get('pages', '错误')} | "
                     f"{item.get('text_characters', 0)} | {len(item.get('pages_without_text', []))} |")
    lines.extend(["", "详细页号、元数据、SHA-256 见本机 `artifacts/inspection/corpus-manifest.json`。",
                  "原始 PDF 保持不变，未默认再分发到代码仓库。"])
    (ROOT / "docs/赛事资料检查.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
