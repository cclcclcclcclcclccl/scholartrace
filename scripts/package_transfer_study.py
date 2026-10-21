"""Deliver the tested candidate with all first-pass and repair evidence intact."""

import difflib
import hashlib
import json
import zipfile
from pathlib import Path

from package_improvement import EXCLUDE, EXT
from transfer_study import (
    ARTIFACTS,
    PROTOCOL,
    ROOT,
    code_hashes,
    digest,
    snapshot,
    write,
)

from backend import store


def read(path):
    return Path(path).read_text("utf-8")


def data(path):
    return json.loads(read(path))


def main():
    out = ROOT / "output/transfer-comparison-20261020"
    assert not out.exists(), "Never replace a delivered release"
    assert "392 passed" in read(ARTIFACTS / "tests-final.log")
    assert "All checks passed" in read(ARTIFACTS / "lint-changed.log")
    for path in [
        "main-browser.json",
        "report-browser.json",
        "workflow/first-browser.json",
    ]:
        value = data(ARTIFACTS / path)
        assert value["complete"] and not value["errors"]
    candidate = data(ARTIFACTS / "diagnostic-candidate1/run.json")
    confirmation = data(ARTIFACTS / "confirmation-first/run.json")
    assert code_hashes() == candidate["code_sha256"] == confirmation["code_sha256"]
    assert snapshot(store.database_path()) == data(
        ARTIFACTS / "diagnostic-first/original-before.json"
    )
    regression = data(ARTIFACTS / "old-regression/run.json")
    assert regression["complete"] and regression["original_data_unchanged"]
    assert len(regression["qa"]) == 27 and not any(
        r.get("error") for r in regression["qa"]
    )
    cases = {
        c["id"]: c
        for c in data(ROOT / "evaluation/transfer_regression_20261020/protocol.json")[
            "qa"
        ]
    }
    failures, reviewed = [], []
    for row in regression["qa"]:
        case = cases[row["id"]]
        if case["unanswerable"]:
            assert row["screen"]["abstained"]
        else:
            assert row["screen"]["source_valid"] and row["screen"]["nonempty"]
            if not row["screen"]["pattern_screen"]:
                failures.append(row["id"])
        reviewed.append(
            {
                "id": row["id"],
                "expected": case["expected"],
                "answer": [
                    c["text"] for c in row["response"].get("model_answer") or []
                ],
                "mechanical_screen": row["screen"],
                "developer_note": "英文optimizer states/gradients/parameters与标准语义等价；中文关键词失败保留。"
                if row["id"] == "zero_states"
                else "已对照原始预期及引用复核；机械通过不等于任意问题的正确率，措辞与重复仍有改进空间。",
            }
        )
    assert failures == ["zero_states"]
    write(
        ARTIFACTS / "regression-review.json",
        {
            "notice": "同一开发助手复核。原关键词失败不改写。",
            "answerable": 22,
            "mechanical_complete": 21,
            "abstentions": 5,
            "reviewed": reviewed,
        },
    )
    with zipfile.ZipFile(ARTIFACTS / "workflow/first-project-export.zip") as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert archive.testzip() is None
        for item in manifest["files"]:
            content = archive.read(item["name"])
            assert (
                len(content) == item["bytes"]
                and hashlib.sha256(content).hexdigest() == item["sha256"]
            )
    write(
        ARTIFACTS / "workflow/export-verification.json",
        {
            "manifest_hashes_match": True,
            "files": len(manifest["files"]),
            "source_pdfs_included": False,
        },
    )
    previous = ROOT / "output/research-tasks-20261020"
    for line in read(previous / "SHA256SUMS.txt").splitlines():
        expected, name = line.split("  ", 1)
        assert digest(previous / name) == expected
    source = []
    for directory in [
        "backend",
        "frontend",
        "scripts",
        "tests",
        "docs",
        "config",
        ".github",
    ]:
        source.extend(
            p
            for p in (ROOT / directory).rglob("*")
            if p.is_file()
            and p.suffix.lower() in EXT
            and not any(x in EXCLUDE for x in p.relative_to(ROOT).parts)
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
            old = archive.read(name).decode("utf-8") if name in names else ""
            current = read(path)
            if old != current:
                patch.extend(
                    difflib.unified_diff(
                        old.splitlines(True),
                        current.splitlines(True),
                        fromfile="previous/" + name,
                        tofile="current/" + name,
                    )
                )
    (ARTIFACTS / "changes.patch").write_text("".join(patch), "utf-8")
    evidence = sorted(
        p
        for p in ARTIFACTS.rglob("*")
        if p.is_file()
        and p.suffix in {".json", ".log", ".png", ".md", ".html", ".patch", ".zip"}
    )
    for folder in [PROTOCOL.parent, ROOT / "evaluation/transfer_regression_20261020"]:
        evidence.extend(folder.glob("*.json"))
    decision = {
        "adopted": "格式要求归并、同源阶段标题连续核验、合法空选段有界补检",
        "notice": "7题为开发者小样本，含4道调试题。保留确认题产品2/3、普通RAG3/3。没有真人研究、模型权重训练或官方提交。",
        "tests_passed": 392,
        "existing_qa": {
            "total": 27,
            "calls": len(data(ARTIFACTS / "old-regression/model-calls.json")),
            "mechanical_answerable_pass": "21/22",
            "semantic_equivalent_english_case": "zero_states",
            "correct_abstention": "5/5",
        },
        "original_library_tables_unchanged": 29,
        "old_delivery_preserved": True,
        "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in source},
        "evidence_sha256": {
            p.relative_to(ROOT).as_posix(): digest(p) for p in evidence
        },
    }
    write(ARTIFACTS / "release-selection.json", decision)
    evidence.append(ARTIFACTS / "release-selection.json")
    out.mkdir()
    archives = []
    for label, paths in [("source", source), ("evidence", evidence)]:
        target = out / f"ScholarTrace-{label}-20261020.zip"
        entries = {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in paths:
                archive.write(path, path.relative_to(ROOT).as_posix())
        with zipfile.ZipFile(target) as archive:
            assert archive.testzip() is None
            assert all(
                hashlib.sha256(archive.read(name)).hexdigest() == value
                for name, value in entries.items()
            )
        archives.append(
            {
                "name": target.name,
                "sha256": digest(target),
                "entry_count": len(entries),
                "entries": entries,
            }
        )
    (out / "对照结果与操作说明.md").write_bytes(
        (ROOT / "docs/新题对照与开发者走查_2026-10-20.md").read_bytes()
    )
    (out / "逐题对照报告.html").write_bytes((ARTIFACTS / "report.html").read_bytes())
    (out / "采用决定.json").write_bytes(
        (ARTIFACTS / "release-selection.json").read_bytes()
    )
    write(out / "manifest.json", {"archives": archives, "notice": decision["notice"]})
    (out / "SHA256SUMS.txt").write_text(
        "\n".join(
            f"{digest(p)}  {p.name}" for p in sorted(out.iterdir()) if p.is_file()
        )
        + "\n",
        "utf-8",
    )
    print(
        json.dumps(
            {
                "out": str(out),
                "archives": [
                    {k: a[k] for k in ["name", "sha256", "entry_count"]}
                    for a in archives
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
