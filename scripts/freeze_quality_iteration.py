"""Freeze a QA iteration before inference without changing question wording or gold fields."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-protocol", required=True)
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--notice", required=True)
    args = parser.parse_args()
    source = (ROOT / args.source_protocol).resolve()
    target = (ROOT / args.target_dir).resolve()
    if not target.is_relative_to(ROOT / "evaluation"):
        raise ValueError("Frozen protocols must be inside evaluation/")
    if target.exists():
        raise ValueError("Refuse to overwrite an existing frozen iteration")
    original = source.read_bytes()
    protocol = json.loads(original)
    ids = [c["id"] for c in protocol["qa"]]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError("QA case IDs must be nonempty and unique")
    created = datetime.now(UTC).isoformat()
    protocol.update(created_at=created, notice=args.notice)
    target.mkdir(parents=True)
    path = target / "protocol.json"
    path.write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    freeze = {
        "created_at": created,
        "source_protocol_sha256": hashlib.sha256(original).hexdigest(),
        "protocol_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "code_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "backend").glob("*.py"))
        },
        "notice": "All question and expected-answer fields preserved; this freeze is not proof of correctness or independent evaluation.",
    }
    (target / "freeze.json").write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(str(target))


if __name__ == "__main__":
    main()
