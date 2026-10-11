import asyncio
import json
import sys
from pathlib import Path
import httpx
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import audit, store
from backend.review import review_change

async def main():
    target = next(d for d in store.list_documents() if d["name"] == "1706.03762v7.pdf")
    items = audit.audit_against(target["id"])["results"]
    item = next(r for r in items if "版本复核样例" in r["note"]["note"])
    async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
        class RecordingClient:
            async def post(self, *args, **kwargs):
                response = await client.post(*args, **kwargs)
                print("RAW", response.json()["choices"][0]["message"]["content"])
                return response
        result = await review_change(item, RecordingClient(), "http://127.0.0.1:8081/v1", "local")
        print("CHECKED", json.dumps(result, ensure_ascii=False))
        print("NEW SOURCE", item["candidate"]["text"])

asyncio.run(main())
