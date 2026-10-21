"""Build an isolated review runtime; never copy private notes or account databases."""

import hashlib
import json
import secrets
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "artifacts/public-review-20261021"


def main():
    if TARGET.exists():
        raise SystemExit("Review runtime already exists; refuse to overwrite data")
    TARGET.mkdir()
    for name in ("backend", "scripts", "frontend/dist", "models/multilingual-minilm"):
        shutil.copytree(ROOT / name, TARGET / name, ignore=shutil.ignore_patterns("__pycache__"))
    sys.path.insert(0, str(TARGET))
    from backend import accounts, database, store

    assert store.ROOT == TARGET
    accounts.initialize()
    identifier = secrets.token_hex(16)
    password = secrets.token_urlsafe(18)
    salt = secrets.token_hex(16)
    hashed = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    with accounts.connect() as con:
        con.execute("INSERT INTO users VALUES(?,?,?,?)", (identifier, "reviewer", salt, hashed))
    token = store.database_override.set(accounts.path(identifier))
    database.initialize()
    papers = []
    wanted = ["1706.03762v7.pdf", "1706.03762v1.pdf", "1607.06450v1.pdf", "2002.04745v2.pdf", "N19-1423.pdf"]
    with sqlite3.connect(ROOT / "data/scholartrace.sqlite3") as con:
        for name in wanted:
            row = con.execute("SELECT path FROM documents WHERE name=?", (name,)).fetchone()
            if row is None:
                raise ValueError(f"Missing review paper: {name}")
            dest = TARGET / "data/papers" / name
            dest.parent.mkdir(exist_ok=True, parents=True)
            shutil.copy2(row[0], dest)
            doc = store.import_pdf(dest)
            papers.append({k: doc[k] for k in ("id", "name", "pages")})
    from backend import projects

    projects.create(projects.ProjectInput(title="评审体验：论文证据与版本更新", document_ids=[p["id"] for p in papers]))
    store.database_override.reset(token)
    # This credential file stays in ignored local artifacts, never the public source/site.
    (TARGET / "review-access.json").write_text(json.dumps({"name": "reviewer", "password": password, "id": identifier}, indent=2), encoding="utf-8")
    report = {"papers": papers, "private_data_copied": False, "account": "reviewer", "port": 8768}
    (ROOT / "artifacts/submission-20261021/review-instance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Isolated reviewer account created; five public-paper files imported; no private notes or accounts copied.")


if __name__ == "__main__":
    main()
