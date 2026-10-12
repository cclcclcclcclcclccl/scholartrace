"""Post-fix live checks including durable full translation, artifacts and version impact."""

import asyncio
import json
import time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "artifacts/full-workbench"
V1 = "0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476"
V7 = "bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697"


async def main():
    report = {}
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8765", timeout=200, trust_env=False
    ) as client:

        async def post(path, payload):
            r = await client.post(path, json=payload)
            r.raise_for_status()
            return r.json()

        async def task(kind, payload):
            j = await post("/api/jobs", {"kind": kind, "payload": payload})
            while j["state"] in {"queued", "running", "interrupted"}:
                await asyncio.sleep(2)
                r = await client.get("/api/jobs/" + j["id"])
                r.raise_for_status()
                j = r.json()
            return j

        docs = (await client.get("/api/documents")).json()
        book = next(d["id"] for d in docs if d["pages"] == 541)
        bert = next(d["id"] for d in docs if d["name"] == "N19-1423.pdf")
        checks = [
            (
                "full_translation",
                lambda: task("translate", {"document_id": V1, "language": "zh"}),
            ),
            ("reparse", lambda: task("parse", {"document_id": V1})),
            ("longbook_parse", lambda: task("parse", {"document_id": book})),
            (
                "multi_paper",
                lambda: post(
                    "/api/ask",
                    {
                        "question": "比较 BERT 与 Transformer 原论文使用的编码器架构。每篇分别给出证据。",
                        "document_ids": [V1, bert],
                    },
                ),
            ),
            (
                "writing",
                lambda: task(
                    "writing",
                    {
                        "document_ids": [V1, bert],
                        "topic": "设计一个可核验引用并追踪论文版本变化的科研助手。只提出实验方案，不声称已经取得实验结果。",
                    },
                ),
            ),
            (
                "future",
                lambda: task(
                    "future",
                    {
                        "document_id": V1,
                        "topic": "future research directions",
                        "query": "sparse attention long sequences",
                    },
                ),
            ),
            (
                "agent_constrained",
                lambda: task(
                    "agent",
                    {
                        "document_ids": [V1],
                        "goal": "只需要检索本文训练硬件的原文证据，不要综述。",
                    },
                ),
            ),
            ("impact", lambda: task("impact", {"document_id": V7})),
            (
                "arxiv_download",
                lambda: task("download", {"paper_id": "arxiv:1706.03762v7"}),
            ),
        ]
        for name, action in checks:
            start = time.monotonic()
            try:
                result = await action()
                report[name] = {
                    "result": result,
                    "seconds": round(time.monotonic() - start, 2),
                }
                print(
                    name,
                    result.get("state", "returned"),
                    result.get("error", ""),
                    flush=True,
                )
            except Exception as exc:
                report[name] = {"error": str(exc)}
                print(name, "ERROR", str(exc)[:200], flush=True)
            FOLDER.mkdir(parents=True, exist_ok=True)
            (FOLDER / "extended-report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )


if __name__ == "__main__":
    asyncio.run(main())
