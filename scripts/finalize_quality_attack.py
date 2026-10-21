"""Record a checked local release; never infer acceptance from a successful build."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_proof_v1 import digest, snapshot

from backend import store

FOLDER = ROOT / "artifacts/attack-v14"


def read(path):
    return json.loads((ROOT / path).read_text("utf-8"))


def main():
    target = FOLDER / "release-selection.json"
    if target.exists():
        raise ValueError("Refuse to replace a release decision")
    gates = {}
    evidence = []
    for group in ("old", "known", "transfer"):
        path = f"artifacts/attack-v14/gate-{group}.json"
        gates[group] = read(path)
        assert gates[group]["eligible"], gates[group]
        evidence += [
            path,
            f"artifacts/proof-v14-{group}/agent-source-audit.json",
            f"artifacts/proof-v14-{group}/run.json",
            f"artifacts/proof-v14-{group}/model-calls.json",
        ]
        freeze = read(f"evaluation/proof_v14_{group}/freeze.json")
        assert all(digest(ROOT / p) == h for p, h in freeze["code_sha256"].items())
    browser = read("artifacts/attack-v14/browser.json")
    dashboard = read("artifacts/attack-v14/dashboard-browser.json")
    assert (
        not browser.get("failure")
        and not browser["errors"]
        and len(browser["checks"]) >= 8
    )
    assert not dashboard.get("failure") and not dashboard["errors"]
    diagrams = read("artifacts/attack-v14/diagrams/intent-audit.json")
    run = read("artifacts/attack-v14/diagrams/run.json")
    assert run["complete"] and len(run["cases"]) == len(diagrams["cases"]) == 3
    assert all(not c.get("error") for c in run["cases"] + run["calls"])
    assert all(c["intent_satisfied"] for c in diagrams["cases"])
    rendering = read("artifacts/attack-v14/diagrams/render.json")
    assert (
        not rendering.get("failure")
        and not rendering["errors"]
        and len(rendering["checks"]) == 3
    )
    reload = read("artifacts/attack-v14/main-reload.json")
    assert (
        reload["after"]["server"]["pid"]
        == read("artifacts/runtime/server.process.json")["pid"]
    )
    tests = (FOLDER / "tests.log").read_text("utf-8")
    assert "304 passed" in tests and "FAILED" not in tests
    original = read("artifacts/proof-v12-old/original-before.json")
    current = snapshot(store.database_path())
    assert current == original and current["integrity"] == "ok"
    (FOLDER / "original-final.json").write_text(
        json.dumps(current, ensure_ascii=False, indent=2), "utf-8"
    )
    with httpx.Client(trust_env=False, timeout=15) as client:
        health = client.get("http://127.0.0.1:8765/api/health").json()
        models = client.get("http://127.0.0.1:8081/v1/models").json()
    assert (
        health["status"] == "ok"
        and health["service"] == "scholartrace"
        and health["model_available"]
    )
    model_hash = digest(ROOT / "models/Qwen3-4B-Q4_K_M.gguf")
    assert model_hash == read("artifacts/proof-v14-old/run.json")["model_file_sha256"]
    paths = []
    for directory in ("backend", "frontend/src", "scripts", "tests", "docs", "config"):
        paths.extend(
            p
            for p in (ROOT / directory).rglob("*")
            if p.is_file()
            and p.suffix in {".py", ".mjs", ".json", ".md", ".ts", ".tsx", ".css"}
        )
    paths.append(ROOT / "README.md")
    source_hashes = {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths)}
    evidence += [
        "artifacts/attack-v14/browser.json",
        "artifacts/attack-v14/dashboard-browser.json",
        "artifacts/attack-v14/diagrams/run.json",
        "artifacts/attack-v14/diagrams/intent-audit.json",
        "artifacts/attack-v14/diagrams/render.json",
        "artifacts/attack-v14/main-reload.json",
        "artifacts/attack-v13/frontend-build.log",
        "artifacts/attack-v14/tests.log",
        "artifacts/attack-v14/original-final.json",
    ]
    decision = {
        "created_at": datetime.now(UTC).isoformat(),
        "adopted": "v14",
        "notice": "Local engineering acceptance on exposed development cases. Not independent evaluation, global accuracy, trained weights or official contest submission. Remaining partial/unsupported answers retained in gates.",
        "gates": gates,
        "tests_passed": 304,
        "browser_checks": browser["checks"],
        "diagram_cases_passed": 3,
        "original_data_unchanged": True,
        "original_data": current,
        "health": health,
        "models": models,
        "model_file_sha256": model_hash,
        "source_sha256": source_hashes,
        "evidence_sha256": {p: digest(ROOT / p) for p in evidence},
        "historical_candidates": "v11 model/planner, v12 reasoning-only, v13 broad date handling rejected; all recorded.",
    }
    target.write_text(json.dumps(decision, ensure_ascii=False, indent=2), "utf-8")
    print(
        json.dumps(
            {
                "adopted": decision["adopted"],
                "tests": 304,
                "data_unchanged": True,
                "source_files": len(source_hashes),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
