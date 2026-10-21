"""Start a disposable localhost demo with an isolated copy of user research data."""

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import store

parser = argparse.ArgumentParser()
parser.add_argument("--folder", default="artifacts/demo-20261015")
parser.add_argument("--port", type=int, default=8766)
args = parser.parse_args()
folder = (ROOT / args.folder).resolve()
if not folder.is_relative_to((ROOT / "artifacts").resolve()):
    raise ValueError("Isolated demo must stay inside artifacts/")
if args.port == 8765:
    raise ValueError("Refuse to replace the main website port")
folder.mkdir(parents=True, exist_ok=True)
target = folder / "demo.sqlite3"
if not target.exists():
    with sqlite3.connect(store.database_path()) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
store.DB_PATH = target
import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="127.0.0.1", port=args.port)
