"""Real-paper developer walkthrough sandbox; no synthetic scientific measurements."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import accounts, database, projects, store

FOLDER = ROOT / "artifacts/transfer-comparison-20261020/workflow"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    target = FOLDER / "library.sqlite3"
    if not args.serve:
        if target.exists():
            raise ValueError("Refuse to replace walkthrough data")
        FOLDER.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(store.DB_PATH) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
    store.DB_PATH = target
    accounts.AUTH_PATH = FOLDER / "accounts.sqlite3"
    accounts.path = lambda identifier: (
        FOLDER / "accounts" / identifier / "library.sqlite3"
    )
    if args.serve:
        import uvicorn
        from fastapi.staticfiles import StaticFiles

        from backend.app import app

        # Optional isolated frontend build alongside this walkthrough folder.
        candidate_frontend = FOLDER.parent / "dist"
        if candidate_frontend.is_dir():
            app.router.routes[:] = [
                r for r in app.router.routes if getattr(r, "name", None) != "frontend"
            ]
            app.mount(
                "/",
                StaticFiles(directory=candidate_frontend, html=True),
                name="frontend",
            )

        uvicorn.run(app, host="127.0.0.1", port=8767)
        return
    database.initialize()
    protocol = json.loads(
        (ROOT / "evaluation/transfer_comparison_20261020/protocol.json").read_text(
            "utf-8"
        )
    )
    files = ["1607.06450v1.pdf", "2002.04745v2.pdf"]
    project = projects.create(
        projects.ProjectInput(
            title="真实论文走查：归一化条件与证据",
            document_ids=[protocol["papers"][f]["id"] for f in files],
        )
    )
    fixture = {
        "project": project,
        "papers": [protocol["papers"][f] for f in files],
        "notice": "项目由脚本预置；笔记、对照、补查回填通过浏览器操作。开发者走查，不是真人试用。",
    }
    (FOLDER / "fixture.json").write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2), "utf-8"
    )
    print("Prepared real-paper workflow", flush=True)


if __name__ == "__main__":
    main()
