"""Replay exposed diagram intentions in a disposable database after reasoning changes."""

import asyncio
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import diagrams, model, store

FOLDER = ROOT / "artifacts/attack-v14/diagrams"


class Context:
    def progress(self, *args):
        pass


async def main():
    if FOLDER.exists():
        raise ValueError("Refuse to replace diagram evidence")
    FOLDER.mkdir(parents=True)
    cases = json.loads(
        (ROOT / "evaluation/module_quality_20261015-repair/protocol.json").read_text(
            "utf-8"
        )
    )["diagrams"]
    frozen = {
        "cases": cases,
        "backend_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "backend").glob("*.py"))
        },
    }
    (FOLDER / "freeze.json").write_text(
        json.dumps(frozen, ensure_ascii=False, indent=2), "utf-8"
    )
    with (
        sqlite3.connect(store.database_path()) as src,
        sqlite3.connect(FOLDER / "evaluation.sqlite3") as dst,
    ):
        src.backup(dst)
    token = store.database_override.set(FOLDER / "evaluation.sqlite3")
    report = {
        "notice": "Developer regression on exposed diagram prompts, isolated DB. Schema validity is not semantic correctness.",
        "cases": [],
        "calls": [],
        "complete": False,
    }
    original = model.complete

    async def traced(*args, **kwargs):
        call = {"args": args, "kwargs": kwargs}
        report["calls"].append(call)
        try:
            result = await original(*args, **kwargs)
            call["output"] = result
            return result
        except Exception as exc:
            call["error"] = str(exc)
            raise

    model.complete = traced
    try:
        for case in cases:
            row = dict(case)
            start = time.monotonic()
            try:
                result = await diagrams.generate(Context(), {"topic": case["topic"]})
                row["result"] = result
            except Exception as exc:  # noqa: BLE001 - preserve failed evaluation cases
                row["error"] = type(exc).__name__ + ": " + str(exc)
            row["seconds"] = round(time.monotonic() - start, 3)
            report["cases"].append(row)
            (FOLDER / "run.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), "utf-8"
            )
            print(
                case["id"],
                json.dumps(row.get("result", row.get("error")), ensure_ascii=False),
                flush=True,
            )
        report["complete"] = True
    finally:
        model.complete = original
        store.database_override.reset(token)
        (FOLDER / "run.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), "utf-8"
        )


if __name__ == "__main__":
    asyncio.run(main())
