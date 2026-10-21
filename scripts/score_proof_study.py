"""Validate exported pilot sessions; never count UI automation as human evidence."""

import argparse
import hashlib
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sessions", nargs="*")
    parser.add_argument("--protocol-dir", default="evaluation/proof_v1")
    parser.add_argument(
        "--output", default="artifacts/proof-v1-first-run/human-study-summary.json"
    )
    args = parser.parse_args()
    protocol_path = ROOT / args.protocol_dir / "protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    expected = {c["id"]: c["expected"] for c in protocol["controlled_review"]}
    sha = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    report = {
        "notice": "Pilot descriptive results only; unequal task difficulties and developer labels limit interpretation. No overall productivity claim.",
        "protocol_sha256": sha,
        "accepted": [],
        "excluded": [],
    }
    seen = set()
    for name in args.sessions:
        try:
            data = json.loads(Path(name).read_text(encoding="utf-8-sig"))
            pid = data["participant"]
            if pid.upper().startswith("UI_AUTOMATED"):
                raise ValueError("automated interface check, not a human participant")
            if pid in seen:
                raise ValueError("duplicate participant export")
            if data["protocol_sha256"] != sha or not data.get("consent"):
                raise ValueError("protocol or consent mismatch")
            if not data.get("complete") or len(data["results"]) != len(expected):
                raise ValueError(
                    "incomplete session; retain but exclude from complete-case pilot"
                )
            if {r["case_id"] for r in data["results"]} != set(expected):
                raise ValueError("missing or duplicate cases")
            assignments = {r["id"]: r["condition"] for r in data["order"]}
            for row in data["results"]:
                if row["condition"] not in {"manual", "assisted"} or row[
                    "condition"
                ] != assignments.get(row["case_id"]):
                    raise ValueError("condition mismatch")
                if row["decision"] not in {"same_claim", "claim_changed", "unclear"}:
                    raise ValueError("invalid decision")
                if (
                    not 0 <= row["active_ms"] <= row["wall_ms"]
                    or not row["reason"].strip()
                ):
                    raise ValueError("invalid time or missing rationale")
            seen.add(pid)
            part = {"participant": pid, "conditions": {}}
            for condition in ["manual", "assisted"]:
                rows = [r for r in data["results"] if r["condition"] == condition]
                if len(rows) * 2 != len(expected):
                    raise ValueError("condition not balanced")
                part["conditions"][condition] = {
                    "n": len(rows),
                    "correct": sum(
                        r["decision"] == expected[r["case_id"]] for r in rows
                    ),
                    "median_active_seconds": median(r["active_ms"] for r in rows)
                    / 1000,
                    "median_wall_seconds": median(r["wall_ms"] for r in rows) / 1000,
                    "hidden_count": sum(r["hidden_count"] for r in rows),
                    "by_label": {
                        label: {
                            "n": sum(expected[r["case_id"]] == label for r in rows),
                            "correct": sum(
                                expected[r["case_id"]] == label
                                and r["decision"] == label
                                for r in rows
                            ),
                        }
                        for label in ["same_claim", "claim_changed", "unclear"]
                    },
                }
            report["accepted"].append(part)
        except (ValueError, KeyError, TypeError) as exc:
            report["excluded"].append({"file": str(name), "reason": str(exc)})
    report["human_participants"] = len(report["accepted"])
    report["time_saving_proven"] = False
    output = ROOT / args.output
    output.parent.mkdir(exist_ok=True, parents=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
