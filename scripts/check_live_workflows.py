"""Real model/network integration, preserving raw responses as development evidence."""

import asyncio
import json
import time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
V1 = "0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476"
folder = ROOT / "artifacts/full-workbench"
folder.mkdir(parents=True, exist_ok=True)


async def main():
    report = {}
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8765", timeout=180, trust_env=False
    ) as client:

        async def post(path, payload):
            response = await client.post(path, json=payload)
            response.raise_for_status()
            return response.json()

        async def task(kind, payload):
            start = time.monotonic()
            job = await post("/api/jobs", {"kind": kind, "payload": payload})
            while job["state"] in {"queued", "running", "interrupted"}:
                await asyncio.sleep(2)
                response = await client.get("/api/jobs/" + job["id"])
                response.raise_for_status()
                job = response.json()
            job["elapsed_seconds"] = round(time.monotonic() - start, 2)
            return job

        checks = [
            (
                "gpu_answer",
                lambda: post(
                    "/api/ask", {"question": "训练用了哪些 GPU？", "document_ids": [V1]}
                ),
            ),
            (
                "unanswerable",
                lambda: post(
                    "/api/ask",
                    {
                        "question": "训练时购买每张 GPU 的人民币价格是多少？",
                        "document_ids": [V1],
                    },
                ),
            ),
            (
                "translation",
                lambda: post(
                    "/api/translate/text",
                    {
                        "text": "We trained our models on one machine with 8 NVIDIA P100 GPUs.",
                        "language": "zh",
                    },
                ),
            ),
            (
                "academic_english",
                lambda: post(
                    "/api/translate/text",
                    {
                        "text": "我们计划比较两种检索方法，并在 20 篇论文上评估引用是否能够支持生成的结论。实验尚未开展。",
                        "language": "en",
                    },
                ),
            ),
            (
                "arxiv",
                lambda: post(
                    "/api/discover/search",
                    {"query": 'ti:"Attention Is All You Need"', "source": "arxiv"},
                ),
            ),
            (
                "crossref",
                lambda: post(
                    "/api/discover/search",
                    {"query": "Attention Is All You Need", "source": "crossref"},
                ),
            ),
            ("parse", lambda: task("parse", {"document_id": V1})),
            (
                "translate_page",
                lambda: task(
                    "translate", {"document_id": V1, "page": 7, "language": "zh"}
                ),
            ),
            (
                "review",
                lambda: task(
                    "review",
                    {
                        "document_ids": [V1],
                        "topic": "Transformer architecture and training efficiency",
                    },
                ),
            ),
            (
                "agent",
                lambda: task(
                    "agent",
                    {
                        "document_ids": [V1],
                        "goal": "检索这篇论文的训练硬件证据，并给出需要核验的出处。只需要检索，不要综述。",
                    },
                ),
            ),
        ]
        for name, action in checks:
            start = time.monotonic()
            try:
                report[name] = {
                    "result": await action(),
                    "seconds": round(time.monotonic() - start, 2),
                }
                print(name, "finished", flush=True)
            except Exception as exc:
                report[name] = {"error": str(exc)}
                print(name, "ERROR", str(exc)[:200], flush=True)
            (folder / "live-report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    print("Report:", folder / "live-report.json", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
