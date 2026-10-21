"""Preserve first-run answers, document coverage, real quote checks and mechanical gaps."""

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import store

parser = argparse.ArgumentParser()
parser.add_argument(
    "--output", default="artifacts/quality-round2/questions-first-run.json"
)
parser.add_argument("--regression", action="store_true")
parser.add_argument("--dataset", default="tests/acceptance_questions_v2.json")
parser.add_argument("--cases", nargs="+", help="Run selected case IDs for diagnosis")
args = parser.parse_args()
output = ROOT / args.output
if output.exists():
    raise SystemExit("Refusing to overwrite a previous report")
dataset = ROOT / args.dataset
report = {
    "selected_cases": args.cases,
    "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
    "development_regression": args.regression,
    "notice": "Mechanical coverage and quote existence, not semantic correctness or official accuracy.",
    "code_hashes": {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT / "backend").glob("*.py")
    },
    "results": [],
}
papers = {p["name"]: p for p in store.list_documents()}
report["document_aliases"] = {
    name: p.get("aliases", []) for name, p in papers.items() if p.get("aliases")
}
with httpx.Client(
    base_url="http://127.0.0.1:8765", timeout=240, trust_env=False
) as client:
    for case in json.loads(dataset.read_text("utf8"))["cases"]:
        if args.cases and case["id"] not in args.cases:
            continue
        start = time.monotonic()
        response = client.post(
            "/api/ask",
            json={
                "question": case["question"],
                "document_ids": [papers[n]["id"] for n in case["files"]],
            },
        )
        response.raise_for_status()
        answer = response.json()
        claims = answer.get("model_answer") or []
        text = " ".join(c["text"] for c in claims)
        checks = (
            {"abstained": not claims}
            if case.get("unanswerable")
            else {
                "answered": bool(claims),
                "required_patterns": all(
                    re.search(p, text, re.IGNORECASE) for p in case["required_patterns"]
                ),
                "all_labeled_sources_retrieved": set(case["source_blocks"]).issubset(
                    {b["id"] for b in answer["evidence"]}
                ),
            }
        )
        for file, patterns in case.get("per_file_patterns", {}).items():
            own = " ".join(
                c["text"] for c in claims if c["document_id"] == papers[file]["id"]
            )
            checks["coverage:" + file] = all(
                re.search(p, own, re.IGNORECASE) for p in patterns
            )
        for file, patterns in case.get("per_file_forbidden_patterns", {}).items():
            own = " ".join(
                c["text"] for c in claims if c["document_id"] == papers[file]["id"]
            )
            checks["no_cross_attribution:" + file] = not any(
                re.search(p, own, re.IGNORECASE) for p in patterns
            )
        if case.get("expected_parts"):
            for file in case["files"]:
                row = next(
                    (
                        r
                        for r in answer.get("comparison", [])
                        if r["document_id"] == papers[file]["id"]
                    ),
                    {},
                )
                parts = (
                    row.get("subquestions", [])
                    if len(case["files"]) > 1
                    else answer.get("subquestions", [])
                )
                checks["original_parts:" + file] = len(parts) == case["expected_parts"]
                for part_id in case.get("unresolved_parts", []):
                    checks[f"unresolved:{file}:{part_id}"] = any(
                        p["id"] == part_id and p["status"] == "unresolved"
                        for p in parts
                    )
        real_blocks = {
            b["id"]: b
            for file in case["files"]
            for b in store.get_blocks(papers[file]["id"])
        }
        checks["quotes_in_original_database"] = all(
            c["block_id"] in real_blocks
            and store.quote_in_source(c["quote"], real_blocks[c["block_id"]]["text"])
            for c in claims
        )
        if case.get("forbidden_patterns"):
            checks["no_forbidden_claims"] = not any(
                re.search(p, text, re.IGNORECASE) for p in case["forbidden_patterns"]
            )
        report["results"].append(
            {
                "id": case["id"],
                "question": case["question"],
                "checks": checks,
                "seconds": round(time.monotonic() - start, 2),
                "response": answer,
            }
        )
        report["mechanical_pass_count"] = sum(
            all(r["checks"].values()) for r in report["results"]
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8"
        )
        print(case["id"], checks, round(time.monotonic() - start, 1), flush=True)
