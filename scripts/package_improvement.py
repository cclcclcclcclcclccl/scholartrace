"""Package the improvement release separately; preserve the earlier PDF/video submission snapshot."""

import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/improvement-20261018"
EXCLUDE = {
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    ".git",
    "data",
    "models",
    "tools",
    "output",
    "artifacts",
}
EXT = {
    ".py",
    ".mjs",
    ".js",
    ".ts",
    ".tsx",
    ".css",
    ".json",
    ".html",
    ".md",
    ".txt",
    ".yml",
    ".yaml",
    ".svg",
    ".cmd",
    ".ps1",
    ".toml",
    ".ini",
    ".sh",
}


def main():
    if OUT.exists():
        raise ValueError("Refuse to overwrite an existing delivery")
    report = json.loads(
        (ROOT / "artifacts/improvement-v8/browser.json").read_text("utf-8")
    )
    assert (
        not report.get("failure")
        and not report["errors"]
        and len(report["checks"]) == 4
    )
    assert "285 passed" in (
        ROOT / "artifacts/improvement-v8-tests-final.log"
    ).read_text("utf-8")
    decision = json.loads(
        (ROOT / "artifacts/improvement-v8/release-selection.json").read_text("utf-8")
    )
    assert all(
        hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
        for p, h in decision["source_sha256"].items()
    )
    source = []
    for name in ["backend", "frontend", "scripts", "tests", "docs", ".github"]:
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
        assert not any(re.search(pattern, p.read_bytes()) for pattern in patterns), str(
            p
        )
    evidence = [
        p
        for p in (ROOT / "evaluation").rglob("*")
        if p.is_file() and p.suffix in {".json", ".html", ".md"}
    ]
    for name in [
        "proof-v6-qa",
        "proof-v8-baseline-new",
        "proof-v8-regression",
        "proof-v9-regression",
        "proof-v9-new",
        "improvement-v8",
    ]:
        evidence += [
            p
            for p in (ROOT / "artifacts" / name).rglob("*")
            if p.is_file() and p.suffix in {".json", ".png", ".py", ".md", ".log"}
        ]
    evidence += list((ROOT / "artifacts").glob("improvement-v8*.log"))
    evidence += [
        ROOT / "artifacts" / (name + "-console.log")
        for name in [
            "proof-v8-baseline-new",
            "proof-v8-regression",
            "proof-v9-regression",
            "proof-v9-new",
        ]
    ]
    OUT.mkdir(parents=True)
    archives = []
    for name, files in [
        ("ScholarTrace-source-improvement-20261018.zip", source),
        ("ScholarTrace-evidence-improvement-20261018.zip", evidence),
    ]:
        path = OUT / name
        entries = []
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(set(files)):
                data = p.read_bytes()
                arc = p.relative_to(ROOT).as_posix()
                z.writestr(arc, data)
                entries.append(
                    {
                        "path": arc,
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "bytes": len(data),
                    }
                )
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            assert all(
                hashlib.sha256(z.read(e["path"])).hexdigest() == e["sha256"]
                for e in entries
            )
        archives.append(
            {
                "path": name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "files": entries,
            }
        )
    for src, dest in [
        ("docs/持续改进与问答复验_2026-10-18.md", "本轮改进与采用决定.md"),
        ("evaluation/reliability/report.html", "全部运行记录.html"),
        ("evaluation/improvement/failure-ledger.json", "失败案例台账.json"),
        ("artifacts/improvement-v8/release-selection.json", "采用版本与代码指纹.json"),
    ]:
        (OUT / dest).write_bytes((ROOT / src).read_bytes())
    manifest = {
        "notice": "Separate improvement snapshot. Earlier submission PDF/video unchanged. No model weights trained, no official submission. Developer audits only; includes rejected candidates. No private databases, PDFs or model weights. Basic secret-pattern scan only.",
        "archives": archives,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "SHA256SUMS.txt").write_text(
        "\n".join(
            hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name
            for p in sorted(OUT.iterdir())
            if p.is_file()
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            [
                {k: v for k, v in a.items() if k != "files"}
                | {"file_count": len(a["files"])}
                for a in archives
            ],
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
