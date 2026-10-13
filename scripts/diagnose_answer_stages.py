"""Capture local generation/review stages without overwriting prior evidence."""

import argparse
import asyncio
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import model, research, store


async def run(args):
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    original = model.complete
    calls = []

    async def traced(system, prompt, **kwargs):
        result = await original(system, prompt, **kwargs)
        calls.append(
            {"system": system, "prompt": prompt, "result": copy.deepcopy(result)}
        )
        return result

    model.complete = traced
    papers = {p["name"]: p["id"] for p in store.list_documents()}
    records = []
    try:
        for dataset in args.dataset:
            cases = json.loads(Path(dataset).read_text("utf8"))["cases"]
            for case in cases:
                if case["id"] not in args.cases:
                    continue
                calls.clear()
                answer = await research.grounded(
                    case["question"], [papers[p] for p in case["files"]]
                )
                records.append(
                    {"id": case["id"], "calls": copy.deepcopy(calls), "answer": answer}
                )
                output.write_text(
                    json.dumps(records, ensure_ascii=False, indent=2), encoding="utf8"
                )
                print(
                    case["id"],
                    json.dumps([c["result"] for c in calls], ensure_ascii=False),
                    flush=True,
                )
    finally:
        model.complete = original


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", action="append", required=True)
    parser.add_argument("--cases", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    asyncio.run(run(parser.parse_args()))
