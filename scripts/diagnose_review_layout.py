"""Controlled replay of PDF layout normalization and direct-evidence selection."""

import argparse
import asyncio
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import model, store
from backend.claim_checks import semantic_overreach, support_passages
from backend.numeric_evidence import unsupported_numbers
from scripts.diagnose_source_review import prepare

FOLDER = ROOT / "artifacts/attack-v16/layout-diagnostic"
DIRECT = (
    "优先选择直接陈述所问事实的段落，而不是需要从其他行为间接推断答案的段落。"
    "判断是否排除、是否使用或是否适用时，必须保留原文直接给出的例外、概率和用途。"
)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reasoning", action="store_true")
    args = parser.parse_args()
    folder = (
        FOLDER.with_name("layout-reasoning-diagnostic") if args.reasoning else FOLDER
    )
    folder.mkdir(parents=True, exist_ok=False)
    base, cases = prepare()
    calls = json.loads(
        (ROOT / "artifacts/proof-v15-old/model-calls.json").read_text("utf-8")
    )
    selectors = [
        c
        for c in calls
        if c["case_id"] == "whisper_segments" and "子问题选原文" in c["args"][0]
    ]
    protocol = {
        "notice": "Exposed developer diagnostic, not independent accuracy. Supported verdict alone does not prove span entailment; inspect full outputs.",
        "reasoning": args.reasoning,
        "cases": cases,
        "selector_guidance": DIRECT,
        "selectors": selectors,
    }
    raw = json.dumps(protocol, ensure_ascii=False, indent=2)
    (folder / "protocol.json").write_text(raw, "utf-8")
    report = {
        "protocol_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "rows": [],
        "complete": False,
    }
    for case in cases:
        schema = copy.deepcopy(base["kwargs"]["schema"])
        schema["properties"]["decisions"]["properties"]["0"]["properties"][
            "support_span"
        ]["enum"] = support_passages(case["quote"])
        data = {
            "index": 0,
            "claim": case["claim"],
            "subquestion": case["question"],
            "quote": store.quote_normalize(case["quote"]),
            "paper_title": case["paper_title"],
            "table_headers": [],
            "table_fields": [],
        }
        prompt = (
            "CURRENT PAPER: "
            + case["paper_title"]
            + "\nQUESTION: "
            + case["question"]
            + "\nCLAIMS:\n"
            + json.dumps([data], ensure_ascii=False)
        )
        row = {
            "id": case["id"],
            "system": base["args"][0],
            "prompt": prompt,
            "schema": schema,
        }
        try:
            result = await model.complete(
                row["system"],
                prompt,
                max_tokens=1400,
                schema=schema,
                reasoning=args.reasoning,
            )
            d = result["decisions"]["0"]
            supported = (
                d["verdict"] == "supported_relevant"
                and len(d["support_span"]) >= 12
                and store.quote_in_source(d["support_span"], case["quote"])
            )
            supported = (
                supported
                and not unsupported_numbers(case["claim"], d["support_span"])
                and not semantic_overreach(case["claim"], d["support_span"])
            )
            row.update(
                output=result,
                correct=supported == case["expected_supported"],
                false_accept=supported and not case["expected_supported"],
            )
        except Exception as exc:  # noqa: BLE001 - preserve diagnostic failures
            row.update(error=str(exc), correct=False)
        report["rows"].append(row)
        (folder / "run.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), "utf-8"
        )
        print(
            row["id"],
            row.get("correct"),
            row.get("output", row.get("error")),
            flush=True,
        )
    for i, call in enumerate(selectors):
        system = DIRECT + call["args"][0]
        row = {
            "id": f"selector_{i}",
            "system": system,
            "prompt": call["args"][1],
            "kwargs": call["kwargs"],
        }
        try:
            row["output"] = await model.complete(system, row["prompt"], **row["kwargs"])
        except Exception as exc:  # noqa: BLE001 - preserve diagnostic failures
            row["error"] = str(exc)
        report["rows"].append(row)
        print(row["id"], row.get("output", row.get("error")), flush=True)
    report["complete"] = True
    (folder / "run.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), "utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
