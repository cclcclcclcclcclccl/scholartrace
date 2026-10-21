"""Replay the failed completeness pass without changing the user's question."""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import model

GUIDANCE = (
    " 对于是否排除/是否纳入的问题，还要检查已保留对象的实际处理方式是否交代完整："
    "如果原文明确同时说明了采样条件和该对象的用途，答案不能只说保留而遗漏用途。"
    "请把这种遗漏列入unanswered_parts，并用该原文补充一条简洁的中文claims。"
    "不要猜测概率值，不要附加原文未说的目的。"
)


async def main():
    folder = ROOT / "artifacts/attack-v17/completeness-diagnostic"
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
    cases = [
        {"id": "original_whisper", "prompt": call["args"][1]},
        {
            "id": "purpose_not_stated",
            "prompt": 'CURRENT PAPER: Test\nQUESTION: X类样本是否完全排除？\nCURRENT ANSWER: [{"evidence_id":"E1","text":"X类样本没有完全排除，以0.2的概率保留。"}]\nEXCERPTS:\n[E1] We retain type-X examples with probability 0.2.',
        },
        {
            "id": "already_complete",
            "prompt": 'CURRENT PAPER: Test\nQUESTION: X类样本是否完全排除？\nCURRENT ANSWER: [{"evidence_id":"E1","text":"X类样本以0.2的概率保留，并用于训练异常检测器。"}]\nEXCERPTS:\n[E1] We retain type-X examples with probability 0.2 and use these examples to train an anomaly detector.',
        },
    ]
    protocol = {
        "notice": "Exposed failed-call replay; not independent evaluation. Original question and evidence unchanged.",
        "guidance": GUIDANCE,
        "call": call,
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
        result = await model.complete(
            call["args"][0] + GUIDANCE, case["prompt"], **call["kwargs"]
        )
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
