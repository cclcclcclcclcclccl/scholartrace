"""Frozen real omission and synthetic no-purpose/already-covered controls."""

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.answer_completeness import SYSTEM, handling_use


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder", default="artifacts/attack-v17/handling-use-diagnostic"
    )
    args = parser.parse_args()
    folder = ROOT / args.folder
    folder.mkdir(parents=True, exist_ok=False)
    calls = json.loads(
        (ROOT / "artifacts/proof-v17-old/model-calls.json").read_text("utf-8")
    )
    call = [
        c
        for c in calls
        if c["case_id"] == "whisper_segments"
        and c["args"][0].startswith("Compare EVERY")
    ][-1]
    prompt = call["args"][1]
    cases = [
        {
            "id": "original_whisper",
            "question": prompt.split("\nQUESTION: ")[1].split("\nCURRENT ANSWER:")[0],
            "claims": json.loads(
                prompt.split("\nCURRENT ANSWER: ")[1].split("\nEXCERPTS:")[0]
            ),
            "evidence": prompt.split("\nEXCERPTS:\n")[1],
            "evidence_count": 2,
        },
        {
            "id": "purpose_not_stated",
            "question": "X类样本是否完全排除？",
            "claims": [
                {"evidence_id": "E1", "text": "X类样本没有完全排除，以0.2的概率保留。"}
            ],
            "evidence": "[E1] We retain type-X examples with probability 0.2.",
            "evidence_count": 1,
        },
        {
            "id": "already_complete",
            "question": "X类样本是否完全排除？",
            "claims": [
                {
                    "evidence_id": "E1",
                    "text": "X类样本以0.2的概率保留，并用于训练异常检测器。",
                }
            ],
            "evidence": "[E1] We retain type-X examples with probability 0.2 and use these examples to train an anomaly detector.",
            "evidence_count": 1,
        },
    ]
    protocol = {
        "notice": "Exposed real failed-case replay plus synthetic contrast controls. Not independent QA.",
        "system": SYSTEM,
        "cases": cases,
    }
    raw = json.dumps(protocol, ensure_ascii=False, indent=2)
    (folder / "protocol.json").write_text(raw, "utf-8")
    report = {
        "protocol_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "rows": [],
        "complete": False,
    }
    for case in cases:
        result = await handling_use(**{k: v for k, v in case.items() if k != "id"})
        report["rows"].append({"id": case["id"], "output": result})
        (folder / "run.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), "utf-8"
        )
        print(case["id"], json.dumps(result, ensure_ascii=False), flush=True)
    report["complete"] = True
    (folder / "run.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), "utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
