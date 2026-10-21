"""Independent source/evidence package, with retained failed browser attempt."""

import difflib
import hashlib
import json
import zipfile
from pathlib import Path

from package_improvement import EXCLUDE, EXT
from transfer_study import snapshot

from backend import store

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/research-polish-20261021"
OUT = ROOT / "output/research-polish-20261021"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    assert not OUT.exists(), "Do not overwrite deliveries"
    assert "412 passed" in (ART / "tests-final.log").read_text(encoding="utf-8")
    assert "All checks passed" in (ART / "lint.log").read_text(encoding="utf-8")
    assert data(ART / "checklist-replay.json")["generation_body_unchanged"]
    assert not data(ART / "workflow/first-browser.json")["complete"]
    for name in (
        "workflow/second-browser.json",
        "guide-browser.json",
        "main-browser.json",
    ):
        report = data(ART / name)
        assert report["complete"] and not report["errors"]
    assert data(ART / "main-reload.json")["model_preserved"]
    current = snapshot(store.database_path())
    assert current == data(ART / "formal-data.json")["snapshot"]
    write(ART / "formal-final.json", current)
    assert data(ART / "export-check.json")["readiness_in_project_export"]
    previous = ROOT / "output/coverage-quality-20261020"
    for line in (previous / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        sha, name = line.split("  ", 1)
        assert digest(previous / name) == sha
    source = []
    for folder in ("backend", "frontend", "scripts", "tests", "docs", ".github"):
        source.extend(
            p
            for p in (ROOT / folder).rglob("*")
            if p.is_file()
            and p.suffix.lower() in EXT
            and not any(part in EXCLUDE for part in p.relative_to(ROOT).parts)
        )
    source.extend(
        p
        for p in ROOT.iterdir()
        if p.is_file()
        and (
            p.suffix in {".md", ".txt", ".cmd", ".toml", ".yaml", ".ini"}
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
            old = archive.read(name).decode("utf-8") if name in names else ""
            new = path.read_text(encoding="utf-8")
            if old != new:
                patch.extend(
                    difflib.unified_diff(
                        old.splitlines(True),
                        new.splitlines(True),
                        fromfile="previous/" + name,
                        tofile="current/" + name,
                    )
                )
    (ART / "changes.patch").write_text("".join(patch), encoding="utf-8")
    decision = {
        "adopted": "回答核对清单、比较前检查、单篇补问范围修复与八步真实论文演示",
        "tests": 412,
        "real_workflow_steps": 38,
        "other_ui_groups": 4,
        "formal_tables_unchanged": len(current["tables"]),
        "notice": "没有新增独立准确率、真人研究或模型训练。比较与清单是阅读辅助，不是语义正确率或可比性评分。保留首轮范围错误及修复后验证。",
        "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in source},
    }
    write(ART / "release-selection.json", decision)
    evidence = sorted(
        p
        for p in ART.rglob("*")
        if p.is_file()
        and "dist" not in p.relative_to(ART).parts
        and p.suffix in {".json", ".log", ".png", ".md", ".html", ".patch", ".zip"}
    )
    OUT.mkdir()
    archives = []
    for label, paths in (("source", source), ("evidence", evidence)):
        target = OUT / f"ScholarTrace-{label}-20261021.zip"
        entries = {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in paths:
                archive.write(path, path.relative_to(ROOT).as_posix())
        with zipfile.ZipFile(target) as archive:
            assert archive.testzip() is None
            assert all(
                hashlib.sha256(archive.read(name)).hexdigest() == sha
                for name, sha in entries.items()
            )
        archives.append(
            {"name": target.name, "sha256": digest(target), "entries": entries}
        )
    for name, path in {
        "演示指南.html": ART / "演示指南.html",
        "演示讲稿.md": ROOT / "docs/真实论文演示讲稿_2026-10-21.md",
        "验收与使用说明.md": ROOT / "docs/三方向打磨与验收_2026-10-21.md",
        "质量验收.json": ART / "release-selection.json",
    }.items():
        (OUT / name).write_bytes(path.read_bytes())
    write(OUT / "manifest.json", {"archives": archives, "notice": decision["notice"]})
    (OUT / "SHA256SUMS.txt").write_text(
        "\n".join(
            f"{digest(p)}  {p.name}" for p in sorted(OUT.iterdir()) if p.is_file()
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(OUT),
                "archives": [
                    {
                        "name": a["name"],
                        "sha256": a["sha256"],
                        "entries": len(a["entries"]),
                    }
                    for a in archives
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
