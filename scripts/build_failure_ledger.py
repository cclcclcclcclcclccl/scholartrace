"""Keep every observed QA failure visible; this is a developer review queue, not training labels."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_reliability_report import ROUNDS


def main():
    cases = {}
    for key, label, protocol_dir, result_dir in reversed(ROUNDS):
        protocol = json.loads(
            (ROOT / "evaluation" / protocol_dir / "protocol.json").read_text("utf-8")
        )
        folder = ROOT / "artifacts" / result_dir
        run = json.loads((folder / "run.json").read_text("utf-8"))
        audit = json.loads((folder / "agent-source-audit.json").read_text("utf-8"))
        trace = json.loads((folder / "model-calls.json").read_text("utf-8"))
        answers = {r["id"]: r for r in run["qa"]}
        labels = {r["id"]: r for r in audit["cases"]}
        for case in protocol["qa"]:
            if not run["complete"] and case["id"] not in answers:
                continue
            identity = (case["id"], case["question"])
            entry = cases.setdefault(
                identity,
                {
                    "case_id": case["id"],
                    "question": case["question"],
                    "expected": case["expected"],
                    "files": case["files"],
                    "source_ids": [s["id"] for s in case["sources"]],
                    "history": [],
                },
            )
            a, response = labels[case["id"]], answers[case["id"]]
            causes = []
            if a["verdict"] == "answerable_abstention":
                causes.append("answerable_but_abstained")
            if (
                a["verdict"].startswith("partial")
                or a["verdict"] == "unsupported_and_incomplete"
            ):
                causes.append("missing_requested_fields")
            if not all(a["claim_supported_by_full_quote"]):
                causes.append("unsupported_claims")
            if response.get("error"):
                causes.append("execution_failed")
            errors = [
                c["error"]
                for c in trace
                if c.get("case_id") == case["id"] and c.get("error")
            ]
            if errors:
                causes.append("model_call_failed_or_fallback")
            entry["history"].append(
                {
                    "round": key,
                    "round_complete": run["complete"],
                    "label": label,
                    "verdict": a["verdict"],
                    "causes": causes,
                    "model_call_errors": errors,
                    "rationale": a["rationale"],
                    "claim_support": a["claim_supported_by_full_quote"],
                    "answer_seconds": response.get("answer_seconds"),
                    "evidence_folder": "artifacts/" + result_dir,
                }
            )
    failures = [v for v in cases.values() if any(h["causes"] for h in v["history"])]
    result = {
        "notice": "Developer-agent review queue. No model weights were trained; labels are not independent human annotations. Historical candidate results are not the deployed release. Keep failed candidates and original source evidence.",
        "case_count": len(cases),
        "ever_failed_case_count": len(failures),
        "cases": failures,
    }
    folder = ROOT / "evaluation/improvement"
    folder.mkdir(exist_ok=True)
    (folder / "failure-ledger.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"cases": len(cases), "ever_failed": len(failures)}))


if __name__ == "__main__":
    main()
