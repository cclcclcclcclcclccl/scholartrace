from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.store import initialize, import_pdf

parser = argparse.ArgumentParser()
parser.add_argument("--all", action="store_true")
args = parser.parse_args()
initialize()
files = sorted((ROOT / "data/competition/pdf").glob("*.pdf"))
if not args.all:
    wanted = {"1706.03762v7.pdf", "1706.03762v1.pdf", "1706.03762v1_img.pdf", "N19-1423.pdf",
              "language_understanding_paper.pdf", "2005.14165v4.pdf", "UnderstandingDeepLearning_02_09_26_C.pdf"}
    files = [f for f in files if f.name in wanted]
for path in files:
    result = import_pdf(path)
    print(json.dumps({key: result.get(key) for key in ["name", "title", "pages", "status", "version", "already_exists"]}, ensure_ascii=False), flush=True)
