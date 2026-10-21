"""Replay one already observed failure across unrelated intervening prompts.

This is a diagnostic of output stability, excluded from accuracy scores.
"""

import asyncio
import hashlib
import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/attack-v10/reproducibility.json"


async def main():
    if OUT.exists():
        raise ValueError("Refuse to overwrite a diagnostic")
    calls = json.loads(
        (ROOT / "artifacts/proof-v10-old/model-calls.json").read_text("utf-8")
    )
    original = next(
        c
        for c in calls
        if c["case_id"] == "whisper_segments" and c["args"][0].startswith("Use ONLY")
    )
    options = original["kwargs"]
    payload = {
        "model": "local",
        "messages": [
            {"role": "system", "content": original["args"][0]},
            {"role": "user", "content": original["args"][1]},
        ],
        "temperature": 0,
        "seed": 0,
        "cache_prompt": False,
        "max_tokens": options["max_tokens"],
        "chat_template_kwargs": {"enable_thinking": options.get("reasoning", False)},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "result",
                "strict": True,
                "schema": options["schema"],
            },
        },
    }
    report = {
        "notice": "Diagnostic, not held-out accuracy. Same previously exposed input repeated with unrelated intervening prompts. No claim of universal determinism.",
        "endpoint": "http://127.0.0.1:8081/v1",
        "payload": payload,
        "attempts": [],
    }
    async with httpx.AsyncClient(timeout=150, trust_env=False) as client:
        for i in range(3):
            start = time.monotonic()
            response = await client.post(
                report["endpoint"] + "/chat/completions", json=payload
            )
            response.raise_for_status()
            result = response.json()
            choice = result["choices"][0]
            content = choice["message"].get("content")
            report["attempts"].append(
                {
                    "index": i,
                    "finish_reason": choice.get("finish_reason"),
                    "content": content,
                    "content_sha256": hashlib.sha256(
                        (content or "").encode()
                    ).hexdigest(),
                    "usage": result.get("usage"),
                    "seconds": round(time.monotonic() - start, 3),
                }
            )
            OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
            print(i, choice.get("finish_reason"), content, flush=True)
            unrelated = await client.post(
                report["endpoint"] + "/chat/completions",
                json={
                    "model": "local",
                    "messages": [{"role": "user", "content": "只回复：测试完成。"}],
                    "temperature": 0,
                    "seed": 0,
                    "cache_prompt": False,
                    "max_tokens": 30,
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            )
            unrelated.raise_for_status()
        report["same_output_all_three"] = (
            len({a["content_sha256"] for a in report["attempts"]}) == 1
        )
        report["all_finished_normally"] = all(
            a["finish_reason"] == "stop" for a in report["attempts"]
        )
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
        assert report["same_output_all_three"] and report["all_finished_normally"]


if __name__ == "__main__":
    asyncio.run(main())
