"""Check a bounded reasoning budget on an exposed failure; not an accuracy benchmark."""

import asyncio
import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "artifacts/attack-v12/reasoning-budget-diagnostic.json"


async def main():
    if TARGET.exists():
        raise ValueError("Refuse to overwrite diagnostic")
    prior = json.loads(
        (ROOT / "artifacts/attack-v10/reproducibility.json").read_text("utf-8")
    )
    payload = {**prior["payload"], "reasoning_budget_tokens": 512}
    report = {
        "notice": "Previously exposed failure, repeated three times with an unrelated intervening prompt. Diagnostic excluded from accuracy denominator.",
        "payload": payload,
        "attempts": [],
    }
    async with httpx.AsyncClient(timeout=150, trust_env=False) as client:
        for index in range(3):
            start = time.monotonic()
            response = await client.post(
                "http://127.0.0.1:8081/v1/chat/completions", json=payload
            )
            response.raise_for_status()
            data = response.json()
            choice = data["choices"][0]
            item = {
                "index": index,
                "seconds": round(time.monotonic() - start, 3),
                "finish_reason": choice.get("finish_reason"),
                "content": choice["message"].get("content"),
                "usage": data.get("usage"),
                "reasoning_chars": len(
                    choice["message"].get("reasoning_content") or ""
                ),
            }
            report["attempts"].append(item)
            TARGET.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
            print(json.dumps(item, ensure_ascii=False), flush=True)
            distractor = await client.post(
                "http://127.0.0.1:8081/v1/chat/completions",
                json={
                    "model": "local",
                    "messages": [{"role": "user", "content": "只回复：完成。"}],
                    "temperature": 0,
                    "max_tokens": 30,
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            )
            distractor.raise_for_status()
    report["all_finished_normally"] = all(
        a["finish_reason"] == "stop" for a in report["attempts"]
    )
    report["identical_answers"] = len({a["content"] for a in report["attempts"]}) == 1
    TARGET.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")


if __name__ == "__main__":
    asyncio.run(main())
