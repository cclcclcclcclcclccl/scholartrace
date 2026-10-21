"""Test the actual recovery path against frozen positive and negative claims."""

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import evidence_review, model


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default="artifacts/attack-v17/recovery-diagnostic")
    args = parser.parse_args()
    folder = ROOT / args.folder
    folder.mkdir(parents=True, exist_ok=False)
    cases = json.loads(
        (ROOT / "artifacts/attack-v17/indexed-diagnostic/protocol.json").read_text(
            "utf-8"
        )
    )["cases"]
    quote = "System-X uses 16-bit weights during training and 8-bit weights during inference. It takes 4 seconds per batch on Device-A. On Device-B, it takes 9 seconds per batch. We did not measure energy consumption."
    for id, claim, expected in [
        ("precision_valid", "System-X训练时使用16位权重，推理时使用8位权重。", True),
        ("precision_swapped", "System-X训练时使用8位权重，推理时使用16位权重。", False),
        ("hardware_valid", "System-X在Device-A上每批耗时4秒。", True),
        ("hardware_swapped", "System-X在Device-B上每批耗时4秒。", False),
        ("energy_invented", "System-X在Device-A上每批耗时4秒，且能耗更低。", False),
        ("energy_not_measured", "论文未测量能耗。", True),
    ]:
        cases.append(
            {
                "id": id,
                "claim": claim,
                "question": "说明System-X的权重精度、设备耗时与能耗测量。",
                "paper_title": "System-X",
                "quote": quote,
                "expected_supported": expected,
            }
        )
    protocol = {
        "notice": "Exposed developer diagnostic; twelve previous and six added contrast cases frozen before actual recovery calls. Not independent QA.",
        "cases": cases,
        "code_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT / "backend").glob("*.py")
        },
    }
    raw = json.dumps(protocol, ensure_ascii=False, indent=2)
    (folder / "protocol.json").write_text(raw, "utf-8")
    report = {
        "protocol_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "rows": [],
        "complete": False,
    }
    original = model.complete
    trace = []
    active = {"id": ""}

    async def traced(*args, **kwargs):
        row = {"case_id": active["id"], "args": args, "kwargs": kwargs}
        try:
            result = await original(*args, **kwargs)
            row["output"] = result
            return result
        except Exception as exc:
            row["error"] = str(exc)
            raise
        finally:
            trace.append(row)
            (folder / "model-calls.json").write_text(
                json.dumps(trace, ensure_ascii=False, indent=2), "utf-8"
            )

    model.complete = traced
    try:
        for case in cases:
            active["id"] = case["id"]
            row = {"id": case["id"]}
            try:
                result = await evidence_review.recover_support(
                    {"text": case["claim"], "quote": case["quote"]},
                    case["question"],
                    case["paper_title"],
                )
                row.update(
                    result=result,
                    correct=bool(result) == case["expected_supported"],
                    false_accept=bool(result) and not case["expected_supported"],
                )
            except Exception as exc:  # noqa: BLE001 - preserve failures
                row.update(error=str(exc), correct=False)
            report["rows"].append(row)
            (folder / "run.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), "utf-8"
            )
            print(row, flush=True)
    finally:
        model.complete = original
    report["complete"] = True
    (folder / "run.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), "utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
