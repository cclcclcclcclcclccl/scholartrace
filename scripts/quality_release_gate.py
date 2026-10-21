"""Compare complete, audited QA rounds; fail closed on missing evidence or regressions."""

import argparse
import json
from pathlib import Path

SAFE = {"complete_supported", "correct_abstention"}
COVERAGE = {
    "complete_supported": 3,
    "complete_with_unsupported_claim": 3,
    "partial_supported": 2,
    "partial_with_unsupported_qualifier": 2,
    "unsupported_and_incomplete": 1,
    "answerable_abstention": 0,
    "correct_abstention": 0,
}


def compare_runs(before, after, before_audit, after_audit, protocol):
    cases = {x["id"]: x for x in protocol["qa"]}
    if len(cases) != len(protocol["qa"]):
        raise ValueError("Duplicate case IDs")
    maps = []
    for run, audit in [(before, before_audit), (after, after_audit)]:
        if not run.get("complete") or not run.get("original_data_unchanged"):
            raise ValueError("Incomplete run or failed data preservation")
        answers = {x["id"]: x for x in run["qa"]}
        labels = {x["id"]: x for x in audit["cases"]}
        if (
            set(answers) != set(cases)
            or set(labels) != set(cases)
            or len(run["qa"]) != len(cases)
            or len(audit["cases"]) != len(cases)
        ):
            raise ValueError("Missing or duplicate answer/audit records")
        for id, row in answers.items():
            if row.get("question") != cases[id]["question"]:
                raise ValueError("Changed question: " + id)
            if (
                row.get("error")
                or row.get("model_call_errors")
                or row.get("response", {}).get("generation_failed")
            ):
                raise ValueError("Failed inference is not an abstention: " + id)
            claims = row.get("response", {}).get("model_answer") or []
            if claims and row.get("screen", {}).get("source_valid") is not True:
                raise ValueError("Invalid or unchecked citation: " + id)
            support = labels[id]["claim_supported_by_full_quote"]
            if len(claims) != len(support) or any(type(x) is not bool for x in support):
                raise ValueError(
                    "Every final claim needs an explicit support label: " + id
                )
            verdict = labels[id]["verdict"]
            if verdict not in SAFE | {
                "partial_supported",
                "partial_with_unsupported_qualifier",
                "answerable_abstention",
                "unsupported_and_incomplete",
                "complete_with_unsupported_claim",
            }:
                raise ValueError("Unknown audit verdict: " + id)
            if verdict == "complete_supported" and (
                not claims or not all(support) or cases[id]["unanswerable"]
            ):
                raise ValueError("Inconsistent complete label: " + id)
            if verdict == "correct_abstention" and (
                claims or not cases[id]["unanswerable"]
            ):
                raise ValueError("Inconsistent abstention label: " + id)
        maps.append((answers, labels))
    regressions, improvements, failures = [], [], []
    for id, case in cases.items():
        old, new = maps[0][1][id], maps[1][1][id]
        if old["verdict"] in SAFE and new["verdict"] not in SAFE:
            regressions.append(
                {
                    "id": id,
                    "reason": "Previously complete/safe case became incomplete or unsafe",
                }
            )
        if all(old["claim_supported_by_full_quote"]) and not all(
            new["claim_supported_by_full_quote"]
        ):
            regressions.append({"id": id, "reason": "New unsupported claim"})
        if (
            not case["unanswerable"]
            and COVERAGE[new["verdict"]] < COVERAGE[old["verdict"]]
        ):
            regressions.append(
                {"id": id, "reason": "Previously covered requested fields were lost"}
            )
        if new["claim_supported_by_full_quote"].count(False) > old[
            "claim_supported_by_full_quote"
        ].count(False):
            regressions.append(
                {"id": id, "reason": "Unsupported claim count increased"}
            )
        if case["unanswerable"] and (
            maps[1][0][id].get("response", {}).get("model_answer") or []
        ):
            regressions.append(
                {"id": id, "reason": "Invented experiment received an answer"}
            )
        if old["verdict"] not in SAFE and new["verdict"] in SAFE:
            improvements.append(id)
        if new["verdict"] not in SAFE:
            failures.append(
                {"id": id, "verdict": new["verdict"], "reason": new["rationale"]}
            )
    return {
        "eligible": not regressions,
        "regressions": regressions,
        "improvements": improvements,
        "remaining_failures": failures,
        "case_count": len(cases),
        "notice": "Developer-labelled release gate, not independent accuracy. Passing requires complete records and no observed safe-to-unsafe regression; it does not establish global reliability.",
    }


def read_traced_run(folder):
    """Do not mistake API fallback or a swallowed model failure for a safe answer."""
    run = json.loads((folder / "run.json").read_text("utf-8"))
    trace = json.loads((folder / "model-calls.json").read_text("utf-8"))
    for row in run["qa"]:
        calls = [c for c in trace if c.get("case_id") == row["id"]]
        if not calls:
            raise ValueError("Missing model trace: " + row["id"])
        row["model_call_errors"] = [c["error"] for c in calls if c.get("error")]
    return run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    def read(p):
        return json.loads(Path(p).read_text("utf-8"))

    old, new = Path(args.before), Path(args.after)
    try:
        result = compare_runs(
            read_traced_run(old),
            read_traced_run(new),
            read(old / "agent-source-audit.json"),
            read(new / "agent-source-audit.json"),
            read(args.protocol),
        )
    except ValueError as exc:
        # Invalid traces are a reviewable rejection, not a missing decision file.
        result = {
            "eligible": False,
            "validation_error": str(exc),
            "notice": "Invalid or failed inference records cannot pass the release gate. No success rate inferred from fallback responses.",
        }
    target = Path(args.output)
    if target.exists():
        raise ValueError("Refuse to overwrite a release decision")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["eligible"] else 2)


if __name__ == "__main__":
    main()
