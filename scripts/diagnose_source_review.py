"""Frozen contrast cases for evidence-first review; exposed diagnostic, not QA accuracy."""

import asyncio
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import model, store
from backend.claim_checks import support_passages

FOLDER = ROOT / "artifacts/attack-v15/reviewer-diagnostic"
GUIDANCE = (
    "FIRST select the shortest exact source passage relevant to the requested fact, then give the verdict. "
    "Resolve which named entity each number, pronoun and comparison belongs to. "
    "A source can state facts about a comparison baseline as well as its own method; "
    "the paper title is not the subject of every sentence. "
    "Negating use by one method does not negate use by another explicitly identified method. "
    "A claim about all conditions requires source support for that entire range and the same comparison targets. "
)


def prepare():
    traces = json.loads(
        (ROOT / "artifacts/proof-v15-known/model-calls.json").read_text("utf-8")
    )
    base = next(
        c
        for c in traces
        if c["case_id"] == "baseline_only"
        and "strict evidence reviewer" in c["args"][0]
    )
    payload = json.loads(base["args"][1].split("\nCLAIMS:\n")[1])[0]
    quote = payload["quote"]
    cases = []
    for id, question, claim, expected in [
        ("baseline_original", payload["subquestion"], payload["claim"], True),
        (
            "baseline_swapped",
            "CLIP是否用ImageNet的128万张图片训练？",
            "CLIP使用ImageNet的128万张训练图片进行训练。",
            False,
        ),
        (
            "baseline_count_swapped",
            payload["subquestion"],
            "ResNet-50基线在ImageNet上训练用了4亿张图片。",
            False,
        ),
        (
            "clip_pairs_valid",
            "CLIP预训练用了多少图文对？",
            "CLIP使用从互联网收集的4亿图文对进行预训练。",
            True,
        ),
    ]:
        cases.append(
            dict(
                id=id,
                question=question,
                claim=claim,
                quote=quote,
                paper_title=payload["paper_title"],
                expected_supported=expected,
            )
        )
    source = "We match the accuracy of ReferenceNet on Dataset-A without using any of the 2 million training examples it was trained on. Our model uses 80 million image-text pairs from a separate corpus."
    for id, claim, expected in [
        ("new_baseline", "ReferenceNet在Dataset-A上使用200万训练样本。", True),
        ("new_swapped", "本文模型在Dataset-A上使用200万训练样本。", False),
    ]:
        cases.append(
            dict(
                id=id,
                question="分别说明ReferenceNet与本文模型的训练样本。",
                claim=claim,
                quote=source,
                paper_title="OurModel",
                expected_supported=expected,
            )
        )
    source = "Method-A is faster than Method-B on sequences up to 512 tokens. For sequences beyond 1024 tokens, Method-B becomes faster."
    for id, claim, expected in [
        (
            "bounded_comparison",
            "在不超过512个token的序列上，Method-A比Method-B快。",
            True,
        ),
        ("universal_comparison", "在所有序列长度下，Method-A都比Method-B快。", False),
    ]:
        cases.append(
            dict(
                id=id,
                question="Method-A和Method-B的速度比较有什么条件？",
                claim=claim,
                quote=source,
                paper_title="Method-A",
                expected_supported=expected,
            )
        )
    return base, cases


async def main():
    if FOLDER.exists():
        raise ValueError("Refuse to replace a diagnostic")
    FOLDER.mkdir(parents=True)
    base, cases = prepare()
    protocol = {
        "notice": "Developer contrast diagnostic, not independent QA evaluation. Four existing-source cases and four synthetic cases frozen before inference.",
        "guidance": GUIDANCE,
        "cases": cases,
    }
    raw = json.dumps(protocol, ensure_ascii=False, indent=2)
    (FOLDER / "protocol.json").write_text(raw, "utf-8")
    report = {
        "protocol_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "rows": [],
        "complete": False,
    }
    for variant in ("baseline", "source_first"):
        for case in cases:
            schema = copy.deepcopy(base["kwargs"]["schema"])
            props = schema["properties"]["decisions"]["properties"]["0"]["properties"]
            props["support_span"]["enum"] = support_passages(case["quote"])
            if variant == "source_first":
                schema["properties"]["decisions"]["properties"]["0"]["properties"] = {
                    "support_span": props["support_span"],
                    "verdict": props["verdict"],
                }
                schema["properties"]["decisions"]["properties"]["0"]["required"] = [
                    "support_span",
                    "verdict",
                ]
            data = dict(
                index=0,
                claim=case["claim"],
                subquestion=case["question"],
                quote=case["quote"],
                paper_title=case["paper_title"],
                table_headers=[],
                table_fields=[],
            )
            prompt = (
                "CURRENT PAPER: "
                + case["paper_title"]
                + "\nQUESTION: "
                + case["question"]
                + "\nCLAIMS:\n"
                + json.dumps([data], ensure_ascii=False)
            )
            system = (GUIDANCE if variant == "source_first" else "") + base["args"][0]
            row = {
                "variant": variant,
                "id": case["id"],
                "system": system,
                "prompt": prompt,
                "schema": schema,
            }
            try:
                result = await model.complete(
                    system, prompt, max_tokens=1400, schema=schema
                )
                decision = result["decisions"]["0"]
                supported = (
                    decision["verdict"] == "supported_relevant"
                    and len(decision["support_span"]) >= 12
                    and store.quote_in_source(decision["support_span"], case["quote"])
                )
                row.update(
                    output=result,
                    correct=supported == case["expected_supported"],
                    false_accept=supported and not case["expected_supported"],
                )
            except Exception as exc:  # noqa: BLE001 - preserve all diagnostic failures
                row.update(error=str(exc), correct=False)
            report["rows"].append(row)
            (FOLDER / "run.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), "utf-8"
            )
            print(
                variant,
                case["id"],
                row.get("correct"),
                row.get("output", row.get("error")),
                flush=True,
            )
    report["complete"] = True
    (FOLDER / "run.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), "utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
