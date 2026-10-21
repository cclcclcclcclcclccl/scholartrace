"""Create an additional source/evidence snapshot without replacing earlier deliveries."""

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

from build_reliability_report import ROUNDS
from package_improvement import EXCLUDE, EXT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/quality-attack-20261019"


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-dir", required=True)
    parser.add_argument("--output-dir", default="output/quality-attack-20261019")
    parser.add_argument("--notes", default="docs/问答质量攻坚与复现记录_2026-10-19.md")
    parser.add_argument("--extra-evidence", action="append", default=[])
    parser.add_argument("--stamp", default="20261019")
    args = parser.parse_args()
    if not re.fullmatch(r"\d{8}", args.stamp):
        raise ValueError("Archive date must use YYYYMMDD")
    OUT = (ROOT / args.output_dir).resolve()
    assert OUT.is_relative_to(ROOT / "output")
    if OUT.exists():
        raise ValueError("Refuse to overwrite a delivery")
    evidence_root = (ROOT / args.decision_dir).resolve()
    assert evidence_root.is_relative_to(ROOT / "artifacts")
    decision = json.loads((evidence_root / "release-selection.json").read_text("utf-8"))
    browser = json.loads((evidence_root / "browser.json").read_text("utf-8"))
    assert not browser.get("failure") and not browser["errors"]
    assert len(browser["checks"]) >= 7
    assert decision["original_data_unchanged"]
    assert decision["tests_passed"]
    assert all(gate["eligible"] for gate in decision["gates"].values())
    assert all(
        hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
        for p, h in decision["evidence_sha256"].items()
    )
    assert all(
        hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
        for p, h in decision["source_sha256"].items()
    )
    source = []
    for name in [
        "backend",
        "frontend",
        "scripts",
        "tests",
        "docs",
        "config",
        ".github",
    ]:
        source += [
            p
            for p in (ROOT / name).rglob("*")
            if p.is_file()
            and p.suffix.lower() in EXT
            and not any(part in EXCLUDE for part in p.relative_to(ROOT).parts)
        ]
    source += [
        p
        for p in ROOT.iterdir()
        if p.is_file()
        and (
            p.suffix.lower()
            in {".md", ".txt", ".cmd", ".yml", ".yaml", ".toml", ".ini"}
            or p.name
            in {
                ".env.example",
                ".gitignore",
                ".dockerignore",
                "Dockerfile",
                "Dockerfile.model",
            }
        )
    ]
    patterns = [
        rb"sk-[A-Za-z0-9_-]{32,}",
        rb"ghp_[A-Za-z0-9]{30,}",
        rb"AKIA[0-9A-Z]{16}",
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    ]
    for p in source:
        assert not any(re.search(pattern, p.read_bytes()) for pattern in patterns), p
    evidence = [
        p
        for p in (ROOT / "evaluation").rglob("*")
        if p.is_file() and p.suffix in {".json", ".html", ".md"}
    ]
    for name in dict.fromkeys(
        [row[3] for row in ROUNDS]
        + ["attack-v10", "attack-v12", "attack-v13", "attack-v14"]
        + args.extra_evidence
    ):
        evidence += [
            p
            for p in (ROOT / "artifacts" / name).rglob("*")
            if p.is_file()
            and p.suffix
            in {".json", ".html", ".md", ".py", ".mjs", ".png", ".svg", ".log"}
            and "demo" not in p.relative_to(ROOT / "artifacts" / name).parts
        ]
        log = ROOT / "artifacts" / (name + "-console.log")
        if log.exists():
            evidence.append(log)
    OUT.mkdir(parents=True)
    archives = []
    for label, files in [("source", source), ("evidence", evidence)]:
        target = OUT / f"ScholarTrace-{label}-{args.stamp}.zip"
        entries = []
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for p in sorted(set(files)):
                data, name = p.read_bytes(), p.relative_to(ROOT).as_posix()
                archive.writestr(name, data)
                entries.append(
                    {
                        "path": name,
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                )
        with zipfile.ZipFile(target) as archive:
            assert archive.testzip() is None
            assert all(
                hashlib.sha256(archive.read(e["path"])).hexdigest() == e["sha256"]
                for e in entries
            )
        archives.append(
            {
                "path": target.name,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "files": entries,
            }
        )
    for src, dest in [
        (args.notes, "本轮改进与未解决问题.md"),
        ("evaluation/reliability/report.html", "全部运行记录.html"),
        ("evaluation/reliability/summary.json", "summary.json"),
        ("evaluation/reliability_study/human-study.html", "human-study.html"),
        ("evaluation/improvement/failure-ledger.json", "失败案例台账.json"),
        (evidence_root / "release-selection.json", "采用决定与代码指纹.json"),
    ]:
        (OUT / dest).write_bytes((ROOT / src).read_bytes())
    page = OUT / "全部运行记录.html"
    page.write_text(
        page.read_text("utf-8").replace(
            "../reliability_study/human-study.html", "human-study.html"
        ),
        "utf-8",
    )
    (OUT / "manifest.json").write_text(
        json.dumps(
            {
                "notice": "Additional engineering evidence snapshot. Earlier PDF/video untouched; no official submission. No private DBs, PDFs or model weights. All completed rounds and rejected candidates retained. Developer audits only. Secret scan checks common patterns, not a complete security review.",
                "archives": archives,
            },
            ensure_ascii=False,
            indent=2,
        ),
        "utf-8",
    )
    (OUT / "SHA256SUMS.txt").write_text(
        "\n".join(
            hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name
            for p in sorted(OUT.iterdir())
            if p.is_file()
        )
        + "\n",
        "utf-8",
    )
    print(
        json.dumps(
            [
                {k: v for k, v in a.items() if k != "files"}
                | {"file_count": len(a["files"])}
                for a in archives
            ]
        )
    )


if __name__ == "__main__":
    main()
