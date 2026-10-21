"""Package conservative coverage fixes; preserve failed experiments and prior releases."""

import difflib
import hashlib
import json
import zipfile
from pathlib import Path

from package_improvement import EXCLUDE, EXT
from transfer_study import snapshot

from backend import store

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/coverage-quality-20261020"
OUT = ROOT / "output/coverage-quality-20261020"


def data(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    assert not OUT.exists(), "Never replace a delivered release"
    assert "404 passed" in (ART / "tests-final-404.log").read_text(encoding="utf-8")
    assert "All checks passed" in (ART / "lint-changed.log").read_text(encoding="utf-8")
    replay = data(ART / "guard-replay.json")
    assert replay["complete"] and all(
        digest(ROOT / name) == sha for name, sha in replay["final_code_sha256"].items()
    )
    for name in (
        "main-browser.json",
        "notice-browser.json",
        "workflow/first-browser.json",
    ):
        result = data(ART / name)
        assert result["complete"] and not result["errors"]
    assert data(ART / "main-reload.json")["model_preserved"]
    current = snapshot(store.database_path())
    assert current == data(ART / "candidate4-diagnostic/original-before.json")
    write(ART / "original-after-release.json", current)
    run = data(ART / "accepted-regression/run.json")
    assert run["complete"] and run["original_data_unchanged"] and len(run["qa"]) == 27
    assert not any(row.get("error") for row in run["qa"])
    cases = {
        c["id"]: c
        for c in data(
            ROOT / "evaluation/coverage_accepted_regression_20261020/protocol.json"
        )["qa"]
    }
    failures = []
    for row in run["qa"]:
        if cases[row["id"]]["unanswerable"]:
            assert row["screen"]["abstained"]
        else:
            assert row["screen"]["source_valid"] and row["screen"]["nonempty"]
            if not row["screen"]["pattern_screen"]:
                failures.append(row["id"])
    assert failures == ["zero_states"], failures
    notes = {
        "ln_batch": ("complete", "单样本可用与训练测试一致均保留。"),
        "preln_scope": (
            "partial",
            "保留Pre-LN初始化与适用结构；Post-LN大梯度及训练不稳机制仍漏答，译法和重复未解决。",
        ),
        "llava_stages": (
            "complete",
            "两个阶段的视觉编码器、投影层及LLM冻结更新正确区分。",
        ),
        "rwkv_modes": (
            "partial",
            "补回WKV时间依赖，但训练矩阵乘法和serial scan机制仍未完整说明；支持片段未单独覆盖首条的全部训练解释。",
        ),
        "llava_training_numbers": (
            "complete",
            "两阶段epoch、学习率和batch数值有同源支持。",
        ),
        "cross_normalization": (
            "partial",
            "补回均值方差与实验范围；重复且仍缺Pre-LN结构位置和初始化条件，不算整题机制完整。",
        ),
        "llava_missing_hardware": (
            "correct_abstention",
            "未编造单张4090的显存实测值。",
        ),
    }
    seven = []
    for split in ("diagnostic", "confirmation"):
        result = data(ART / f"candidate4-{split}/run.json")
        assert result["complete"] and result["original_unchanged"]
        for row in result["rows"]:
            assert not row.get("error")
            status, note = notes[row["case_id"]]
            seven.append(
                {
                    "case_id": row["case_id"],
                    "status": status,
                    "developer_note": note,
                    "answer": row["answer"],
                }
            )
    assert len(seven) == 7
    with zipfile.ZipFile(ART / "workflow/first-project-export.zip") as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read("manifest.json"))
        for entry in manifest["files"]:
            raw = archive.read(entry["name"])
            assert (
                len(raw) == entry["bytes"]
                and hashlib.sha256(raw).hexdigest() == entry["sha256"]
            )
    previous = ROOT / "output/transfer-comparison-20261020"
    for line in (previous / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        sha, name = line.split("  ", 1)
        assert digest(previous / name) == sha
    source = []
    for directory in ("backend", "frontend", "scripts", "tests", "docs", ".github"):
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
            p.suffix in {".md", ".txt", ".cmd", ".yaml", ".toml", ".ini"}
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
    (ART / "accepted-changes.patch").write_text("".join(patch), encoding="utf-8")
    decision = {
        "adopted": "有限数字归属拒绝、无据缺失断言过滤、同源换序去重、单问遗漏提示及实际生成来源按钮",
        "notice": "七题和27旧题均已暴露，不是独立准确率。最终第三名称边界用保存轨迹重放验证；没有真人试用、权重训练或官方提交。",
        "tests": 404,
        "old_regression": {
            "total": 27,
            "calls": len(data(ART / "accepted-regression/model-calls.json")),
            "keyword_pass": "21/22",
            "unmodified_keyword_failures": failures,
            "semantic_note": "ZeRO英文optimizer states/gradients/parameters对应原要求；原中文关键词失败保留。另有重复或额外信息，不宣称措辞完美。",
            "correct_abstention": "5/5",
        },
        "seven_exposed_repeats": seven,
        "deterministic_replay_pairs": sum(t["pairs"] for t in replay["traces"]),
        "real_browser_steps": 35,
        "synthetic_ui_checks": 4,
        "formal_tables_unchanged": len(current["tables"]),
        "prior_archives_verified": True,
        "export_manifest_files_verified": len(manifest["files"]),
        "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in source},
    }
    write(ART / "release-selection.json", decision)
    evidence = sorted(
        p
        for p in ART.rglob("*")
        if p.is_file()
        and p.suffix in {".json", ".log", ".png", ".md", ".patch", ".zip"}
    )
    for folder in (
        ROOT / "evaluation/transfer_comparison_20261020",
        ROOT / "evaluation/coverage_regression_20261020",
        ROOT / "evaluation/coverage_accepted_regression_20261020",
        ROOT / "artifacts/transfer-comparison-20261020/coverage-candidate1",
    ):
        evidence.extend(p for p in folder.glob("*.json"))
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
            assert all(
                hashlib.sha256(archive.read(name)).hexdigest() == sha
                for name, sha in entries.items()
            )
        archives.append(
            {"name": target.name, "sha256": digest(target), "entries": entries}
        )
    write(OUT / "质量验收.json", decision)
    (OUT / "改进与使用说明.md").write_bytes(
        (ROOT / "docs/回答覆盖与数字归属核验_2026-10-20.md").read_bytes()
    )
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
