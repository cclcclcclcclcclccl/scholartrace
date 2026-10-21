"""Freeze project research tasks, source backfill and comparison management."""

import difflib
import json
import sys
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from package_improvement import EXCLUDE, EXT
from run_proof_v1 import digest, snapshot

from backend import store

FOLDER = ROOT / "artifacts/research-tasks-20261020"
OUT = ROOT / "output/research-tasks-20261020"
NOTES = ROOT / "docs/研究补查待办与对照管理验收_2026-10-20.md"


def read(path):
    return json.loads(path.read_text("utf-8"))


def main():
    if OUT.exists() or (FOLDER / "release-selection.json").exists():
        raise ValueError("Refuse to overwrite an existing delivery")
    browser = read(FOLDER / "browser.json")
    assert (
        len(browser["checks"]) == 8
        and not browser.get("failure")
        and not browser["errors"]
    )
    assert read(FOLDER / "main-browser.json")["loaded"]
    assert read(FOLDER / "project-export-verification.json")["manifest_hashes_match"]
    assert "385 passed" in (FOLDER / "tests-final.log").read_text("utf-8")
    after = snapshot(store.database_path())
    assert after == read(FOLDER / "before.json")["original"]
    assert after["integrity"] == "ok"
    with store.connection() as conn:
        actual = {}
        for table in (
            "recall_cards",
            "recall_reviews",
            "rehearsal_sessions",
            "evidence_comparisons",
        ):
            rows = [
                dict(r) for r in conn.execute("SELECT * FROM " + table + " ORDER BY id")
            ]
            if table == "evidence_comparisons":
                for row in rows:
                    assert row.pop("archived") == 0
            actual[table] = rows
        assert actual == read(FOLDER / "before.json")["extras"]
        assert conn.execute("SELECT COUNT(*) FROM research_tasks").fetchone()[0] == 0
    (FOLDER / "original-final.json").write_text(json.dumps(after, indent=2), "utf-8")
    frozen = read(ROOT / "artifacts/boundaries-20261020/release-selection.json")[
        "source_sha256"
    ]
    changed = {
        p
        for p, h in frozen.items()
        if p.startswith("backend/") and digest(ROOT / p) != h
    }
    assert changed == {
        "backend/app.py",
        "backend/database.py",
        "backend/boundaries.py",
        "backend/projects.py",
    }, changed
    health = httpx.get("http://127.0.0.1:8765/api/health", trust_env=False).json()
    assert health["status"] == "ok" and health["model_available"]
    reload = read(FOLDER / "main-reload.json")
    assert reload["after"]["server"] == read(
        ROOT / "artifacts/runtime/server.process.json"
    )
    assert reload["after"]["model"] == read(
        ROOT / "artifacts/runtime/model.process.json"
    )
    previous = ROOT / "output/boundaries-20261020"
    for line in (previous / "SHA256SUMS.txt").read_text("utf-8").splitlines():
        expected, name = line.split("  ", 1)
        assert digest(previous / name) == expected
    source = []
    for directory in (
        "backend",
        "frontend",
        "scripts",
        "tests",
        "docs",
        "config",
        ".github",
    ):
        source.extend(
            p
            for p in (ROOT / directory).rglob("*")
            if p.is_file()
            and p.suffix.lower() in EXT
            and not any(part in EXCLUDE for part in p.relative_to(ROOT).parts)
        )
    source.extend(
        p
        for p in ROOT.iterdir()
        if p.is_file()
        and (
            p.suffix in {".md", ".txt", ".cmd", ".yaml", ".ini"}
            or p.name
            in {
                ".env.example",
                ".gitignore",
                ".dockerignore",
                "Dockerfile",
                "Dockerfile.model",
            }
        )
    )
    source = sorted(set(source))
    patch = []
    with zipfile.ZipFile(previous / "ScholarTrace-source-20261020.zip") as archive:
        names = set(archive.namelist())
        for path in source:
            name = path.relative_to(ROOT).as_posix()
            before = archive.read(name).decode("utf-8") if name in names else ""
            current = path.read_text("utf-8")
            if current != before:
                patch.extend(
                    difflib.unified_diff(
                        before.splitlines(True),
                        current.splitlines(True),
                        fromfile="previous-boundaries/" + name,
                        tofile="current/" + name,
                    )
                )
    (FOLDER / "changes-from-boundaries.patch").write_text("".join(patch), "utf-8")
    evidence = sorted(
        p
        for p in FOLDER.iterdir()
        if p.is_file()
        and p.suffix in {".json", ".log", ".png", ".patch", ".md", ".zip"}
    )
    decision = {
        "adopted": "Project research tasks with atomic evidence backfill and comparison archiving",
        "notice": "Fifteen new isolated regression cases; eight browser flows plus main-site checks and project bundle verification. Completion means source-backed cell backfill, not scientific correctness. Two browser attempts retained. No new model benchmark, weight training, human study or official submission. Existing Mermaid size warnings remain.",
        "tests_passed": 385,
        "browser_checks": browser["checks"],
        "original_data_unchanged": True,
        "previous_delivery_unchanged": True,
        "previous_existing_backend_files_changed": sorted(changed),
        "health": health,
        "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in source},
        "evidence_sha256": {
            p.relative_to(ROOT).as_posix(): digest(p) for p in evidence
        },
    }
    selection = FOLDER / "release-selection.json"
    selection.write_text(json.dumps(decision, ensure_ascii=False, indent=2), "utf-8")
    evidence.append(selection)
    OUT.mkdir()
    archives = []
    for label, paths in (("source", source), ("evidence", evidence)):
        target = OUT / f"ScholarTrace-{label}-20261020.zip"
        entries = {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in paths:
                archive.write(path, path.relative_to(ROOT).as_posix())
        with zipfile.ZipFile(target) as archive:
            assert archive.testzip() is None
            import hashlib

            assert all(
                hashlib.sha256(archive.read(name)).hexdigest() == expected
                for name, expected in entries.items()
            )
        archives.append(
            {"path": target.name, "sha256": digest(target), "entries": entries}
        )
    (OUT / "本轮改进与使用说明.md").write_bytes(NOTES.read_bytes())
    (OUT / "采用决定与代码指纹.json").write_bytes(selection.read_bytes())
    (OUT / "manifest.json").write_text(
        json.dumps(
            {"archives": archives, "notice": decision["notice"]},
            ensure_ascii=False,
            indent=2,
        ),
        "utf-8",
    )
    (OUT / "SHA256SUMS.txt").write_text(
        "".join(f"{digest(p)}  {p.name}\n" for p in sorted(OUT.iterdir())), "utf-8"
    )
    print(
        json.dumps(
            [
                {"file": a["path"], "sha256": a["sha256"], "files": len(a["entries"])}
                for a in archives
            ]
        )
    )


if __name__ == "__main__":
    main()
