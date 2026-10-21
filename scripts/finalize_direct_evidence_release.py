"""Verify direct-evidence selection against v15 and package a separate snapshot."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_proof_v1 import digest, snapshot

from backend import store

FOLDER = ROOT / "artifacts/attack-v16"


def read(path):
    return json.loads((ROOT / path).read_text("utf-8"))


def main():
    target = FOLDER / "release-selection.json"
    if target.exists():
        raise ValueError("Refuse to overwrite release evidence")
    gates, evidence = {}, []
    for group in ("old", "known", "transfer"):
        path = f"artifacts/attack-v16/gate-{group}.json"
        gates[group] = read(path)
        assert gates[group]["eligible"]
        freeze = read(f"evaluation/proof_v16_{group}/freeze.json")
        assert all(digest(ROOT / p) == h for p, h in freeze["code_sha256"].items())
        run = read(f"artifacts/proof-v16-{group}/run.json")
        assert run["complete"] and run["original_data_unchanged"]
        trace = read(f"artifacts/proof-v16-{group}/model-calls.json")
        assert not any(c.get("error") for c in trace)
        evidence += [path] + [
            f"artifacts/proof-v16-{group}/{name}.json"
            for name in ("run", "agent-source-audit", "model-calls")
        ]
    browser = read("artifacts/attack-v16/browser.json")
    dashboard = read("artifacts/attack-v16/dashboard-browser.json")
    assert (
        len(browser["checks"]) >= 8
        and not browser.get("failure")
        and not browser["errors"]
    )
    assert not dashboard.get("failure") and not dashboard["errors"]
    tests = (FOLDER / "tests-final.log").read_text("utf-8")
    assert "308 passed" in tests and "FAILED" not in tests
    before = read("artifacts/proof-v16-known/original-before.json")
    after = snapshot(store.database_path())
    assert before == after and after["integrity"] == "ok"
    (FOLDER / "original-final.json").write_text(
        json.dumps(after, ensure_ascii=False, indent=2), "utf-8"
    )
    reload = read("artifacts/attack-v16/main-reload.json")
    assert (
        reload["after"]["server"]["pid"]
        == read("artifacts/runtime/server.process.json")["pid"]
    )
    with httpx.Client(trust_env=False, timeout=10) as client:
        health = client.get("http://127.0.0.1:8765/api/health").json()
        assert client.get("http://127.0.0.1:8765/").status_code == 200
    assert health["status"] == "ok" and health["model_available"]
    model_hash = digest(ROOT / "models/Qwen3-4B-Q4_K_M.gguf")
    assert model_hash == read("artifacts/proof-v16-old/run.json")["model_file_sha256"]
    paths = [ROOT / "README.md"]
    for directory in ("backend", "frontend/src", "scripts", "tests", "docs", "config"):
        paths += [
            p
            for p in (ROOT / directory).rglob("*")
            if p.is_file()
            and p.suffix in {".py", ".mjs", ".json", ".md", ".ts", ".tsx", ".css"}
        ]
    evidence += [
        "artifacts/attack-v16/" + name
        for name in (
            "browser.json",
            "browser-first-attempt.json",
            "browser-source-audit.json",
            "dashboard-browser.json",
            "tests.log",
            "tests-final.log",
            "original-final.json",
            "main-reload.json",
            "layout-diagnostic/protocol.json",
            "layout-diagnostic/run.json",
            "layout-reasoning-diagnostic/protocol.json",
            "layout-reasoning-diagnostic/run.json",
            "diagnostic-assessment.json",
        )
    ]
    decision = {
        "created_at": datetime.now(UTC).isoformat(),
        "adopted": "v16",
        "baseline": "v15",
        "notice": "Developer audit of exposed frozen cases; not independent evaluation or global accuracy. Layout-only review rejected (7/8 after span guards); reasoning review rejected (6/8, one false accept). Original review retained. Sampling condition recovered; VAD purpose still missing in composite answer. No weight training or official submission.",
        "gates": gates,
        "tests_passed": 308,
        "browser_checks": browser["checks"],
        "original_data_unchanged": True,
        "original_data": after,
        "health": health,
        "model_file_sha256": model_hash,
        "source_sha256": {
            p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths)
        },
        "evidence_sha256": {p: digest(ROOT / p) for p in evidence},
    }
    target.write_text(json.dumps(decision, ensure_ascii=False, indent=2), "utf-8")
    print(
        json.dumps(
            {"adopted": "v16", "data_unchanged": True, "tests": 308}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
