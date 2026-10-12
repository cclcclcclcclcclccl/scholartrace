import asyncio, json, time
from pathlib import Path
import httpx

FOLDER = Path(__file__).resolve().parents[1] / "artifacts/full-workbench"


async def main():
    original = json.loads((FOLDER / "extended-report.json").read_text(encoding="utf-8"))
    report = {}
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8765", timeout=180, trust_env=False
    ) as client:
        for _ in range(30):
            try:
                ready = await client.get("/api/health")
                if ready.status_code == 200:
                    break
            except httpx.TransportError:
                pass
            await asyncio.sleep(1)
        for key in ["full_translation", "future"]:
            identifier = original[key]["result"]["id"]
            started = time.monotonic()
            current = (await client.get("/api/jobs/" + identifier)).json()
            if current["state"] == "completed":
                report[key] = {"job": current, "seconds": 0, "cached_completed": True}
                continue
            response = await client.post("/api/jobs/" + identifier + "/retry")
            response.raise_for_status()
            job = response.json()
            while job["state"] in {"queued", "running", "interrupted"}:
                await asyncio.sleep(3)
                job = (await client.get("/api/jobs/" + identifier)).json()
                if int(time.monotonic() - started) % 30 < 3:
                    print(key, job["state"], job["message"], flush=True)
            report[key] = {"job": job, "seconds": round(time.monotonic() - started, 2)}
            print(key, job["state"], job.get("error"), flush=True)
            (FOLDER / "retry-report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )


if __name__ == "__main__":
    asyncio.run(main())
