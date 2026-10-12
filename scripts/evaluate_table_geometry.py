"""Check selected source-labelled numeric cells; preserve OCR errors outside this narrow scope."""

import hashlib
import json
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import tables

first = ROOT / "artifacts/quality-round2/tables-first-run.json"
output = ROOT / "artifacts/quality-round2/table-geometry-regression.json"
if output.exists():
    raise SystemExit("Refusing to overwrite evaluation")
report = {
    "notice": "Uses the original first-run OCR tokens; native words re-read from the PDFs. Checks selected numeric cells, not all cells, OCR character accuracy, or unseen table generalization. Scientific exponents, merged headings and reference brackets still require checking.",
    "input_sha256": hashlib.sha256(first.read_bytes()).hexdigest(),
    "code_sha256": hashlib.sha256(
        (ROOT / "backend/tables.py").read_bytes()
    ).hexdigest(),
    "results": [],
}
for sample in json.loads(first.read_text("utf8")):
    content = sample["job"]["result"]
    tokens = content["tokens"]
    area = content["source"]["bbox"]
    if "_img" not in sample["file"]:
        with pymupdf.open(ROOT / "data/competition/pdf" / sample["file"]) as pdf:
            tokens = tables.native_tokens(pdf[sample["page"] - 1], pymupdf.Rect(area))
    grid = tables.grid_from_tokens(tokens, area)
    rows = grid["rows"]
    checks = {}
    if sample["page"] == 8:
        checks["five_columns"] = len(rows[0]) == 5
        for label, expected in [
            ("Transformer (base model)", ["27.3", "38.1"]),
            ("Transformer (big)", ["28.4", "41.0"]),
        ]:
            row = next(r for r in rows if r[0] == label)
            checks[label] = row[1:3] == expected
            checks[label + ":shared_cost_marked"] = any("[跨列 4-5]" in v for v in row)
        checks["empty_french_score_preserved"] = (
            next(r for r in rows if r[0].startswith("ByteNet"))[2] == ""
        )
    elif sample["region"] == 0:
        checks["thirteen_columns"] = len(rows[0]) == 13
        base = next(r for r in rows if r[0] == "base")
        big = next(r for r in rows if r[0] == "big")
        checks["base_all_fields"] = base[1:] == [
            "6",
            "512",
            "1024",
            "8",
            "64",
            "64",
            "0.1",
            "0.1",
            "100K",
            "4.92",
            "25.8",
            "65",
        ]
        checks["big_all_fields"] = big[1:] == [
            "6",
            "1024",
            "4096",
            "16",
            "",
            "",
            "0.3",
            "",
            "300K",
            "4.33",
            "26.4",
            "213",
        ]
    else:
        checks["twelve_by_three"] = len(rows) == 12 and len(rows[0]) == 3
        checks["all_f1_scores"] = [r[2] for r in rows[1:]] == [
            "88.3",
            "90.4",
            "90.4",
            "91.7",
            "91.3",
            "91.3",
            "91.3",
            "92.1",
            "92.1",
            "92.7",
            "93.3",
        ]
    report["results"].append(
        {
            "file": sample["file"],
            "page": sample["page"],
            "region": sample["region"],
            "checks": checks,
            "rows": rows,
        }
    )
report["samples_passing"] = sum(all(r["checks"].values()) for r in report["results"])
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
print([(r["file"], r["page"], r["region"], r["checks"]) for r in report["results"]])
