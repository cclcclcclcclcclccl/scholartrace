"""Package the selected-source release without replacing earlier deliveries."""

import difflib
import hashlib
import json
import zipfile
from pathlib import Path

from package_improvement import EXCLUDE, EXT
from transfer_study import snapshot

from backend import store

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/source-followup-20261021"
OUT = ROOT / "output/source-followup-20261021"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    assert not OUT.exists(), "Do not overwrite deliveries"
    assert "420 passed" in (ART / "tests.log").read_text(encoding="utf-8")
    assert "All checks passed" in (ART / "lint.log").read_text(encoding="utf-8")
    protocol = data(ART / "protocol.json")
    assert protocol["validation_body_unchanged"]
    assert all(digest(ROOT / n) == h for n, h in protocol["code_sha256"].items())
    run = data(ART / "run.json")
    assert run["complete"] and run["formal_data_unchanged"]
    assert len(run["rows"]) == 4 and len(data(ART / "model-calls.json")) == 11
    for name in ("browser.json", "main-browser.json"):
        report = data(ART / name)
        assert report["complete"] and not report["errors"]
    assert data(ART / "main-reload.json")["model_preserved"]
    current = snapshot(store.database_path())
    assert current == data(ART / "original-before.json")
    write(ART / "formal-final.json", current)
    previous = ROOT / "output/research-polish-20261021"
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
    with zipfile.ZipFile(previous / "ScholarTrace-source-20261021.zip") as archive:
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
        "adopted": "限定原文追问、完整选段校验、失败不扩大检索、范围保存导出与教程",
        "tests": 420,
        "real_developer_cases": 4,
        "real_model_calls": 11,
        "browser_groups": 4,
        "formal_tables_unchanged": len(current["tables"]),
        "notice": "开发者预选段落的已暴露问题检查，非独立准确率。聚焦机制问答有据；原复杂问题仍部分回答，中英混杂仍在。没有真人验证或权重训练。",
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
        "验收与使用说明.md": ROOT / "docs/限定原文追问与验收_2026-10-21.md",
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
