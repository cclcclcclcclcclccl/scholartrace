"""Bounded comparison of local reasoning on identical captured inputs."""

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import model


async def run():
    output = Path("artifacts/quality-round7/reasoning-comparison.json")
    if output.exists():
        raise FileExistsError(output)
    records = []
    async with httpx.AsyncClient(timeout=150, trust_env=False) as client:
        for case in json.loads(
            Path("artifacts/quality-round7/before-stages.json").read_text("utf8")
        ):
            for call in case["calls"]:
                if not call["system"].startswith("Use ONLY"):
                    continue
                start = time.monotonic()
                response = await client.post(
                    model.URL + "/chat/completions",
                    json={
                        "model": model.NAME,
                        "messages": [
                            {"role": "system", "content": call["system"]},
                            {"role": "user", "content": call["prompt"]},
                        ],
                        "temperature": 0,
                        "max_tokens": 3600,
                        "response_format": {"type": "json_object"},
                        "chat_template_kwargs": {"enable_thinking": True},
                    },
                )
                response.raise_for_status()
                result = response.json()
                records.append(
                    {
                        "id": case["id"],
                        "prompt": call["prompt"],
                        "before": call["result"],
                        "raw_response": result,
                        "seconds": time.monotonic() - start,
                    }
                )
                output.write_text(
                    json.dumps(records, ensure_ascii=False, indent=2), encoding="utf8"
                )
                choice = result["choices"][0]
                print(
                    case["id"],
                    choice["finish_reason"],
                    choice["message"].get("content"),
                    flush=True,
                )


if __name__ == "__main__":
    asyncio.run(run())
