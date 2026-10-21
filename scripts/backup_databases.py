"""Online SQLite backups; includes private accounts, keep the output local."""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "data" / "backups" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    sources = [ROOT / "data/scholartrace.sqlite3", ROOT / "data/accounts.sqlite3"]
    sources += sorted((ROOT / "data/accounts").glob("*/library.sqlite3"))
    files = []
    for source in sources:
        if not source.is_file():
            continue
        relative = source.relative_to(ROOT / "data")
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with (
            sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src,
            sqlite3.connect(target) as dst,
        ):
            src.backup(dst)
            status = dst.execute("PRAGMA integrity_check").fetchone()[0]
            if status != "ok":
                raise RuntimeError("Backup integrity check failed: " + str(relative))
        files.append(
            {
                "file": relative.as_posix(),
                "bytes": target.stat().st_size,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "integrity": "ok",
            }
        )
    manifest = {
        "format": "scholartrace-database-backup-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "notice": "Private local database snapshots, including account credentials. Do not publish. PDFs, models and uploaded files are excluded. Each database is internally consistent; snapshots across accounts are not atomic. Stop services before any manual restoration.",
        "files": files,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {"output": str(output), "databases": len(files), "integrity": "ok"},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
