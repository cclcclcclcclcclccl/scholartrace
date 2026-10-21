"""Build a blind-label local study page from the frozen first-pass results."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--protocol-dir", default="evaluation/proof_v1")
parser.add_argument("--report", default="artifacts/proof-v1-first-run/run.json")
args = parser.parse_args()
folder = ROOT / args.protocol_dir
protocol = json.loads((folder / "protocol.json").read_text(encoding="utf-8"))
freeze = json.loads((folder / "freeze.json").read_text(encoding="utf-8"))
report = json.loads((ROOT / args.report).read_text(encoding="utf-8"))
assert report["complete"]
assert (
    freeze["protocol_sha256"]
    == hashlib.sha256((folder / "protocol.json").read_bytes()).hexdigest()
)
lookup = {r["id"]: r for r in report["controlled_review"]}
counts = {}
cases = []
for case in protocol["controlled_review"]:
    source = lookup[case["id"]]["input"]
    assert source["note"]["quote"] == case["old"]
    assert source["candidate"]["text"] == case["new"]
    assert source["note"]["note"] == case["observation"]
    label = case["expected"]
    i = counts.get(label, 0)
    counts[label] = i + 1
    result = lookup[case["id"]].get("result", {})
    title = {
        "same_claim": "初判未变",
        "claim_changed": "初判变化",
        "unclear": "含义不确定",
        "unavailable": "没有取得判断",
    }.get(lookup[case["id"]]["prediction"], "没有取得判断")
    cases.append(
        {k: case[k] for k in ["id", "observation", "old", "new"]}
        | {
            "balance_index": i,
            "hint": title + "。" + result.get("reason", "请直接核对两版原文。"),
        }
    )
data = json.dumps(
    {
        "protocol_sha256": freeze["protocol_sha256"],
        "model_run_sha256": hashlib.sha256(
            (ROOT / args.report).read_bytes()
        ).hexdigest(),
        "cases": cases,
    },
    ensure_ascii=False,
).replace("<", "\\u003c")
page = (
    (ROOT / "evaluation/proof_v1/human-study.template.html")
    .read_text(encoding="utf-8-sig")
    .replace("__DATA__", data)
)
(folder / "human-study.html").write_text(page, encoding="utf-8")
print("Created local human study; no participant results collected.")
