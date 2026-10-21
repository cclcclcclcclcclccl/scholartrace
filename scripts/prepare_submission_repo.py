"""Preserve true history and stage an allowlisted, scanned public-source snapshot."""

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "artifacts/submission-20261021/repository"
PATTERNS = [rb"sk-[A-Za-z0-9_-]{32,}", rb"gh[pousr]_[A-Za-z0-9]{30,}", rb"AKIA[0-9A-Z]{16}", rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"]
EXCLUDE = {"node_modules", "dist", "__pycache__", ".pytest_cache", ".git", "data", "models", "tools", "output", "artifacts"}
EXT = {".py", ".mjs", ".js", ".ts", ".tsx", ".css", ".json", ".html", ".md", ".txt", ".yaml", ".yml", ".svg", ".cmd", ".ps1", ".toml", ".ini", ".sh"}


def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", "-c", f"safe.directory={cwd.as_posix()}", *args], cwd=cwd)


def main():
    if TARGET.exists():
        raise SystemExit("Do not overwrite staged repository")
    blobs = set()
    for commit in git("rev-list", "--all").decode().splitlines():
        for line in git("ls-tree", "-r", commit).splitlines():
            meta, name = line.split(b"\t", 1)
            if meta.split()[1] == b"blob":
                blobs.add(meta.split()[2].decode())
                if name.endswith((b".sqlite3", b".gguf", b".env")):
                    raise ValueError("Unexpected private file in history")
    for oid in blobs:
        if any(re.search(rx, git("cat-file", "blob", oid)) for rx in PATTERNS):
            raise ValueError("Secret-like historical object; do not publish")
    files = []
    for name in ("backend", "frontend", "scripts", "tests", "docs", ".github", "submission-site"):
        for p in (ROOT / name).rglob("*"):
            if p.is_file() and not any(x in EXCLUDE for x in p.relative_to(ROOT).parts):
                if p.suffix.lower() in EXT or (name == "submission-site" and p.suffix == ".png") or p.name == ".nojekyll":
                    files.append(p)
    for p in ROOT.iterdir():
        if p.is_file() and (p.suffix in {".md", ".txt", ".cmd", ".yaml", ".ini"} or p.name in {".env.example", ".gitignore", ".dockerignore", "Dockerfile", "Dockerfile.model", "LICENSE"}):
            files.append(p)
    credential = json.loads((ROOT / "artifacts/public-review-20261021/review-access.json").read_text(encoding="utf-8"))["password"].encode()
    for p in files:
        content = p.read_bytes()
        if credential in content or any(re.search(rx, content) for rx in PATTERNS):
            raise ValueError(f"Credential-like content: {p.relative_to(ROOT)}")
    git("clone", "--no-local", "--no-hardlinks", str(ROOT), str(TARGET))
    git("remote", "remove", "origin", cwd=TARGET)
    git("checkout", "-B", "main", cwd=TARGET)
    for p in files:
        dest = TARGET / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    report = {"existing_commits": len(git("rev-list", "--all").splitlines()), "history_blobs_scanned": len(blobs), "current_files": len(files), "findings": [], "notice": "Allowlisted source only; basic token patterns plus exact reviewer-password exclusion. Not a comprehensive secret audit.", "sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (ROOT / "artifacts/submission-20261021/source-scan.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Staged {len(files)} files; preserved {report['existing_commits']} genuine commits; no detected credentials")


if __name__ == "__main__":
    main()
