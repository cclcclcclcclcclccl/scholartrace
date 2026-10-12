"""Resume local semantic indexing without depending on the web process."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import database, jobs, retrieval


async def main():
    database.initialize()
    job = jobs.submit("index", {})
    print(job["id"], flush=True)
    while jobs.workers:
        await asyncio.sleep(10)
        current = jobs.get(job["id"])
        print(current["state"], current["message"], flush=True)
    print(retrieval.status(), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
