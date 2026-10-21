"""Replay the final narrow boundary change without calling or retuning the model."""

import hashlib
import json
import sys
import types
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.quantity_roles import named_update_count_mismatch

FOLDER = ROOT / "artifacts/coverage-quality-20261020"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pairs(value, path="root"):
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            for key in ("quote", "support_span"):
                if isinstance(value.get(key), str) and value[key]:
                    yield path + "." + key, value["text"], value[key]
        for key, child in value.items():
            yield from pairs(child, path + "." + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from pairs(child, path + f"[{index}]")


def main():
    before = types.ModuleType("backend.quantity_roles_before")
    before.__package__ = "backend"
    with zipfile.ZipFile(FOLDER / "candidate4-source.zip") as archive:
        raw = archive.read("backend/quantity_roles.py")
    frozen = read(ROOT / "evaluation/coverage_accepted_regression_20261020/freeze.json")
    assert (
        hashlib.sha256(raw).hexdigest()
        == frozen["code_sha256"]["backend\\quantity_roles.py"]
    )
    exec(compile(raw, "candidate4/quantity_roles.py", "exec"), before.__dict__)  # noqa: S102 -- own archived module verified against frozen source hash
    changed = [
        name
        for name, sha in frozen["code_sha256"].items()
        if digest(ROOT / name) != sha
    ]
    assert changed == ["backend\\quantity_roles.py"], changed
    records = []
    for label in (
        "candidate4-diagnostic",
        "candidate4-confirmation",
        "accepted-regression",
    ):
        run = read(FOLDER / label / "run.json")
        assert run["complete"]
        rows = []
        for filename in ("run.json", "model-calls.json"):
            path = FOLDER / label / filename
            for location, claim, quote in pairs(read(path)):
                old = before.named_update_count_mismatch(claim, quote)
                new = named_update_count_mismatch(claim, quote)
                rows.append(
                    {"input": filename + ":" + location, "old": old, "new": new}
                )
        assert rows and all(row["old"] == row["new"] for row in rows), label
        records.append(
            {
                "label": label,
                "source_hashes": {
                    n: digest(FOLDER / label / n)
                    for n in ("run.json", "model-calls.json")
                },
                "pairs": len(rows),
                "results": rows,
            }
        )
    observed = []
    for location, claim, quote in pairs(
        read(FOLDER / "candidate3-confirmation/run.json")
    ):
        if named_update_count_mismatch(claim, quote):
            observed.append({"location": location, "claim": claim, "quote": quote})
    assert observed, "The actually observed swapped-role failure must be caught"
    report = {
        "notice": "Deterministic replay of recorded claim/quote and claim/support_span pairs. Same model outputs, no new inference and no new unseen tasks. Final code differs from 27-task run only in third-name boundary guard; observed decisions unchanged on all recorded pairs. This is not general semantic verification.",
        "final_code_sha256": {
            name: digest(ROOT / name) for name in frozen["code_sha256"]
        },
        "compared_module_sha256": hashlib.sha256(raw).hexdigest(),
        "traces": records,
        "observed_candidate3_rejections": observed,
        "complete": True,
    }
    (FOLDER / "guard-replay.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "pairs": sum(r["pairs"] for r in records),
                "changed_decisions": 0,
                "observed_swaps_rejected": len(observed),
            }
        )
    )


if __name__ == "__main__":
    main()
