"""Run fixed questions once, preserving exact answers and limited mechanical checks."""

import hashlib
import json
from pathlib import Path
import re
import sys
import time
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import store

dataset = ROOT / "tests/acceptance_questions_v1.json"
raw = dataset.read_bytes()
cases = json.loads(raw)["cases"]
papers = {p["name"]: p for p in store.list_documents()}
suffix = "after-fix-3" if "--after-fix-3" in sys.argv else "after-fix-2" if "--after-fix-2" in sys.argv else "after-fix" if "--after-fix" in sys.argv else "v1"
if "--final-regression" in sys.argv:
    suffix = "after-fix-final"
output = ROOT / f"artifacts/full-workbench/acceptance-{suffix}.json"
if output.exists():
    raise SystemExit(
        "First-run report exists; do not overwrite it. Use a new version to record a later evaluation."
    )
report = {
    "dataset_sha256": hashlib.sha256(raw).hexdigest(),
    "model": "Qwen3-4B Q4_K_M; llama.cpp b11552 Vulkan; 8192 context",
    "source_code_sha256": {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT / "backend").glob("*.py")
    },
    "notice": (
        "Post-fix development regression on the same exposed questions, not independent acceptance."
        if suffix.startswith("after-fix")
        else "8 agent-authored questions. Mechanical answer completeness and quote checks only; not official or human-reviewed accuracy. No tuning or reruns included in this first report."
    ),
    "results": [],
}
with httpx.Client(
    base_url="http://127.0.0.1:8765", timeout=180, trust_env=False
) as client:
    for case in cases:
        start = time.monotonic()
        response = client.post(
            "/api/ask",
            json={
                "question": case["question"],
                "document_ids": [papers[case["file"]]["id"]],
            },
        )
        response.raise_for_status()
        result = response.json()
        claims = result.get("model_answer") or []
        text = " ".join(c["text"] for c in claims)
        if case.get("unanswerable"):
            checks = {"abstained": len(claims) == 0}
        else:
            checks = {
                "nonempty": bool(claims),
                "expected_source_retrieved": any(
                    b["id"] == case["source_block"] for b in result["evidence"]
                ),
                "required_patterns_present": all(
                    re.search(p, text, re.I) for p in case["required_patterns"]
                ),
            }
        checks["quotes_exist"] = all(
            store.quote_in_source(
                c["quote"],
                next(b["text"] for b in result["evidence"] if b["id"] == c["block_id"]),
            )
            for c in claims
        )
        report["results"].append(
            {
                "id": case["id"],
                "question": case["question"],
                "checks": checks,
                "seconds": round(time.monotonic() - start, 2),
                "response": result,
            }
        )
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8"
        )
        print(case["id"], checks, flush=True)
report["mechanical_pass_count"] = sum(
    all(r["checks"].values()) for r in report["results"]
)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
print("Mechanical checks", report["mechanical_pass_count"], "/", len(cases))
